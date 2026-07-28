#!/usr/bin/env python3
"""Run Bloom negation coding with a local Ollama model.

This runner is intentionally dev-first: it refuses to run on test_lockbox unless
--allow-lockbox is passed, strips human/evaluation fields before prompting, and
validates model output before writing predictions.
"""

from __future__ import annotations

import argparse
import http.client
import json
import random
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# Resolve paths relative to this standalone XLing-LLM_coding folder. This keeps
# the script portable after the folder is pushed to its own Git repository and
# cloned onto Oscar.
LLM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = LLM_DIR / "v5" / "bloom_v5_english_prompt.md"
DEFAULT_SPLIT_DIR = LLM_DIR / "splits" / "english"
# Development runs write directly into the version's results folder; the
# split name in every output filename keeps runs distinguishable. The one
# exception is the final lockbox evaluation, which is routed to a lockbox/
# subfolder automatically so its outputs stay physically separated from dev
# outputs, per LLM_validation_plan.md.
DEFAULT_RESULTS_DIR = LLM_DIR / "v5" / "results"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"

# These version strings are saved in raw-response metadata and the terminal
# summary. The schema and prompt versions are also used in output filenames as
# compact run locators; the full prompt path stays in metadata. Defaults track
# the current policy/prompt version; pass --schema-version/--prompt-version
# (with matching --prompt and --results-dir) to reproduce an older run.
DEFAULT_SCHEMA_VERSION = "bloom_v5"
DEFAULT_PROMPT_VERSION = "p005"

# Local copies of the schema constraints. Keeping these in code makes validation
# cheap and avoids depending on external JSON-schema packages on Oscar.
ALLOWED_LABELS = {
    "Nonexistence",
    "Rejection",
    "Denial",
    "Nonpossession",
    "Uncoded",
    "Excluded",
}
# Flag order matches bloom_vN_output.schema.json; constrained decoding emits
# properties in this order, so it should not be alphabetized.
FLAG_ORDER = [
    "foreign_language_negation",
    "singing",
    "mimicry",
    "tag_question",
    "repetition",
    "not_a_negation",
]
REQUIRED_FLAGS = set(FLAG_ORDER)
ALLOWED_FLAG_VALUES = {"Yes", "No"}


def schema_has_certain(schema_version: str) -> bool:
    """bloom_v4 added the per-prediction `certain` key (Yes/No confidence,
    mirroring the human coders' certain_bloom column). Reproductions of
    v1-v3 runs must keep validating against the original contract, so the
    key is gated on the schema version rather than always required."""
    return schema_version not in {"bloom_v1", "bloom_v2", "bloom_v3"}

# Only these fields are sent to the LLM. The split JSONL records also include
# human coder labels and split metadata; those must never be included in the
# prompt because they would leak evaluation information to the model.
PROMPT_RECORD_FIELDS = [
    "record_id",
    "language",
    "transcript_id",
    "half",
    "line",
    "speaker",
    "child_id",
    "target_negator",
    "target_utterance",
    "negator_index_in_utterance",
    "negators_in_utterance",
    "context_window_size",
    "context_before",
    "context_after",
]


class ValidationError(Exception):
    """Raised when model output violates the local Bloom output contract."""


class RetryableBatchError(Exception):
    """A transient batch failure that should trigger a reseeded retry rather
    than aborting the whole run. Covers HTTP timeouts (GPU contention or a
    runaway generation) and empty model output (gemma's thinking/output flip,
    where the unconstrained thinking channel loops and content comes back
    empty). Distinct from ValidationError, which gets a corrective hint fed back
    to the model; a RetryableBatchError just resamples with a new seed."""


def read_jsonl(path: Path) -> list[dict]:
    """Read newline-delimited JSON records from a split or results file."""
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_jsonl(path: Path, records: list[dict]) -> None:
    """Write records as newline-delimited JSON, creating the parent directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def clean_model_name(model: str) -> str:
    """Convert an Ollama model name into a safe filename component."""
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", model).strip("_") or "model"


def prompt_record(record: dict) -> dict:
    """Return only the fields that the LLM is allowed to see.

    Fields absent from the split record are omitted (rather than sent as null)
    so that runs against older split files, such as the frozen v1 inputs in
    v1/inputs/, produce byte-identical prompt payloads to the original runs.
    """
    return {field: record[field] for field in PROMPT_RECORD_FIELDS if field in record}


def chunks(items: list[dict], size: int):
    """Yield successive fixed-size batches while preserving record order."""
    for start in range(0, len(items), size):
        yield start, items[start : start + size]


def extract_json_object(text: str) -> dict:
    """Parse a JSON object from an LLM response.

    Ollama is asked to return JSON, but local models can still occasionally wrap
    output in Markdown fences or add a short preamble. This parser first tries
    strict JSON, then falls back to the first {...} span.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def validate_response(
    payload: dict, expected_ids: list[str], schema_version: str
) -> list[dict]:
    """Validate one model response against the Bloom output contract.

    This is deliberately strict. If a model omits a record, invents an ID,
    changes enum spelling, or adds extra keys, the run should fail before any
    final prediction file is written.
    """
    if not isinstance(payload, dict):
        raise ValidationError("Top-level output is not a JSON object.")
    if payload.get("schema_version") != schema_version:
        raise ValidationError(f"schema_version must be {schema_version!r}.")
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        raise ValidationError("predictions must be a list.")

    expected = set(expected_ids)
    seen = set()
    cleaned = []

    # Validate every prediction object independently before checking for any
    # batch-level missing IDs.
    required_keys = {"record_id", "bloom_label", "flags", "comments"}
    if schema_has_certain(schema_version):
        required_keys = required_keys | {"certain"}
    for prediction in predictions:
        if not isinstance(prediction, dict):
            raise ValidationError("Each prediction must be an object.")
        extra = set(prediction) - required_keys
        missing = required_keys - set(prediction)
        if extra:
            raise ValidationError(f"Unexpected prediction keys: {sorted(extra)}")
        if missing:
            raise ValidationError(f"Missing prediction keys: {sorted(missing)}")

        record_id = prediction["record_id"]
        if record_id not in expected:
            raise ValidationError(f"Unexpected record_id: {record_id}")
        if record_id in seen:
            raise ValidationError(f"Duplicate record_id: {record_id}")
        seen.add(record_id)

        label = prediction["bloom_label"]
        if label not in ALLOWED_LABELS:
            raise ValidationError(f"{record_id}: invalid bloom_label {label!r}")

        if schema_has_certain(schema_version):
            certain = prediction["certain"]
            if certain not in ALLOWED_FLAG_VALUES:
                raise ValidationError(f"{record_id}: invalid certain {certain!r}")

        flags = prediction["flags"]
        if not isinstance(flags, dict):
            raise ValidationError(f"{record_id}: flags must be an object.")
        if set(flags) != REQUIRED_FLAGS:
            raise ValidationError(
                f"{record_id}: flags must be exactly {sorted(REQUIRED_FLAGS)}"
            )
        bad_flags = {
            key: value for key, value in flags.items() if value not in ALLOWED_FLAG_VALUES
        }
        if bad_flags:
            raise ValidationError(f"{record_id}: invalid flag values {bad_flags}")

        comments = prediction["comments"]
        if not isinstance(comments, str):
            raise ValidationError(f"{record_id}: comments must be a string.")
        if len(comments) > 300:
            raise ValidationError(f"{record_id}: comments exceed 300 characters.")

        cleaned.append(prediction)

    missing_ids = expected - seen
    if missing_ids:
        raise ValidationError(f"Missing predictions for: {sorted(missing_ids)}")
    if len(predictions) != len(expected_ids):
        raise ValidationError("Prediction count does not match input count.")
    return cleaned


def build_output_schema(expected_ids: list[str], schema_version: str) -> dict:
    """Build a per-batch JSON schema for Ollama structured outputs.

    Sent as the request's `format` field (Ollama >= 0.5), this makes the server
    constrain decoding with a grammar derived from the schema: the model cannot
    emit extra keys, misspelled enum values, or record IDs outside this batch.
    validate_response still runs afterwards because a grammar cannot enforce
    that every expected record_id appears exactly once, nor the comment-length
    cap (maxLength is omitted here rather than trusting grammar support for it).

    Property order matters: constrained decoding emits properties in the order
    listed below, so it must match bloom_vN_output.schema.json — in particular
    comments before bloom_label, so the stated reason precedes the label at
    decoding time (and, since bloom_v4, certain after bloom_label, so the
    label precedes the confidence judgment).
    """
    flag_value = {"type": "string", "enum": sorted(ALLOWED_FLAG_VALUES)}
    item_properties: dict = {
        "record_id": {"type": "string", "enum": expected_ids},
        "comments": {"type": "string"},
        "bloom_label": {
            "type": "string",
            "enum": sorted(ALLOWED_LABELS),
        },
    }
    if schema_has_certain(schema_version):
        item_properties["certain"] = {
            "type": "string",
            "enum": sorted(ALLOWED_FLAG_VALUES),
        }
    item_properties["flags"] = {
        "type": "object",
        "properties": {flag: flag_value for flag in FLAG_ORDER},
        "required": FLAG_ORDER,
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "schema_version": {"type": "string", "enum": [schema_version]},
            "predictions": {
                "type": "array",
                "minItems": len(expected_ids),
                "maxItems": len(expected_ids),
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": list(item_properties),
                    "additionalProperties": False,
                },
            },
        },
        "required": ["schema_version", "predictions"],
        "additionalProperties": False,
    }


def ollama_chat(
    *,
    url: str,
    model: str,
    prompt: str,
    records: list[dict],
    output_schema: dict,
    temperature: float,
    top_p: float | None,
    top_k: int | None,
    min_p: float | None,
    timeout: int,
    num_ctx: int | None = None,
    num_predict: int | None = None,
    seed: int | None = None,
    validation_feedback: str | None = None,
) -> tuple[dict, dict]:
    """Send one batch to Ollama's local /api/chat endpoint."""
    # The prompt file is sent as the system message. The current batch is sent
    # as the user message so the model sees exactly the records it should code.
    user_content = (
        "Code the following batch. Return only the JSON output object.\n\n"
        + json.dumps(records, ensure_ascii=False, indent=2)
    )
    if validation_feedback:
        user_content += (
            "\n\nYour previous response failed local validation. "
            "Return the full corrected JSON object for the same batch. "
            f"Validation error: {validation_feedback}"
        )
    # Passing a JSON schema as `format` makes Ollama grammar-constrain decoding
    # to the schema (structured outputs). validate_response below stays as a
    # backstop for the properties a grammar cannot express.
    options = {"temperature": temperature}
    if top_p is not None:
        options["top_p"] = top_p
    if top_k is not None:
        options["top_k"] = top_k
    if min_p is not None:
        options["min_p"] = min_p
    # Pin the context window when asked. The default (model/server-chosen, often
    # 32k) sizes a multi-GB KV cache that can force a large model to spill layers
    # onto CPU; batches here are small, so a few-thousand-token window is ample
    # and keeps the model fully on GPU.
    if num_ctx is not None:
        options["num_ctx"] = num_ctx
    # Cap total generation. The JSON `format` grammar constrains `content`, but
    # the model's "thinking" channel is unconstrained and can run away into an
    # infinite loop, producing empty content and eventually hitting the HTTP
    # timeout. A cap makes that fail fast (empty content -> retryable) instead.
    if num_predict is not None and num_predict > 0:
        options["num_predict"] = num_predict
    # A seed only bites at temperature > 0; the retry loop pairs a bumped
    # temperature with a per-attempt seed so a deterministic degenerate response
    # cannot repeat identically on every retry.
    if seed is not None:
        options["seed"] = seed
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "format": output_schema,
        "options": options,
    }
    # Use Python's standard-library HTTP client so the script runs on Oscar
    # without installing requests/openai/etc.
    data = json.dumps(request_payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        # A read timeout is transient (GPU contention or a runaway generation),
        # not a misconfiguration. Make it retryable so one slow batch does not
        # abort the whole run.
        raise RetryableBatchError(
            f"Ollama request timed out after {timeout}s "
            f"(GPU contention or a runaway generation)."
        ) from exc
    except (http.client.HTTPException, ConnectionError) as exc:
        # Server closed/reset the connection mid-request (e.g. RemoteDisconnected,
        # IncompleteRead, ConnectionResetError). On Oscar this is typically Ollama
        # crashing or being OOM-killed under concurrent load. These escape urllib's
        # URLError wrapping because they're raised during getresponse(), so catch
        # them explicitly and treat as retryable.
        raise RetryableBatchError(
            f"Ollama dropped the connection mid-request ({type(exc).__name__}: {exc}). "
            f"Server may have crashed under load."
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {url}. Is `ollama serve` running on this node?"
        ) from exc

    # Ollama chat responses place the model's text in message.content. Empty
    # content means the model spent its budget in the unconstrained "thinking"
    # channel (the gemma thinking/output flip) without emitting the schema-
    # constrained answer. Treat as retryable so a reseeded resample can recover.
    content = (raw_response.get("message") or {}).get("content")
    if not content:
        raise RetryableBatchError(
            f"Ollama returned empty message.content (thinking-channel runaway?): {raw_response}"
        )
    return extract_json_object(content), raw_response


def parse_args() -> argparse.Namespace:
    """Define the command-line interface for local/Oscar runs."""
    parser = argparse.ArgumentParser(
        description="Run Bloom coding on an English split with Ollama."
    )
    parser.add_argument("--split", default="dev_train", help="Split name to code.")
    parser.add_argument("--model", default="llama3.2", help="Ollama model name.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional max records to code, e.g. --limit 20 for a smoke test.",
    )
    parser.add_argument("--batch-size", type=int, default=5, help="Records per LLM call.")
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Retry a batch this many times after a schema validation failure "
        "OR a transient failure (timeout / empty thinking-channel response). "
        "Retries resample with a bumped temperature and a per-attempt seed.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional reproducible base seed. Batch N uses seed + N - 1 on "
        "its first attempt; retries derive deterministic fresh seeds.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=None,
        help="Optional nucleus-sampling threshold forwarded to Ollama.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Optional top-k sampling cutoff forwarded to Ollama.",
    )
    parser.add_argument(
        "--min-p",
        type=float,
        default=None,
        help="Optional min-p sampling cutoff forwarded to Ollama.",
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high"),
        default=None,
        help="Optional Harmony reasoning-effort header. This is a native "
        "gpt-oss control; omit it for the historical/default behavior.",
    )
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="Pin Ollama's context window (tokens). Lower (e.g. 8192) shrinks "
        "the KV cache so a large model fits fully on the GPU. Default: "
        "model/server default.",
    )
    parser.add_argument(
        "--num-predict",
        type=int,
        default=8000,
        help="Cap total tokens generated per batch. Bounds gemma's thinking "
        "channel so a runaway loop fails fast (empty content -> retried) instead "
        "of running until --timeout. Set 0 or negative for no cap (Ollama "
        "default). Default 8000 leaves ample room for genuine reasoning + JSON.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=1200,
        help="HTTP timeout seconds per batch. Default 1200: a large model "
        "thinking over a multi-record batch (plus a cold first-load) can exceed "
        "the old 300s. Lower it for small/fast models if you want fail-fast.",
    )
    parser.add_argument(
        "--schema-version",
        default=DEFAULT_SCHEMA_VERSION,
        help="Expected schema_version in model output, e.g. bloom_v2.",
    )
    parser.add_argument(
        "--prompt-version",
        default=DEFAULT_PROMPT_VERSION,
        help="Prompt version tag recorded in filenames and metadata, e.g. p002.",
    )
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--split-dir", type=Path, default=DEFAULT_SPLIT_DIR)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Output directory (default: the current version's results folder, "
        "or its lockbox/ subfolder for test_lockbox runs).",
    )
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument(
        "--allow-lockbox",
        action="store_true",
        help="Required to run on test_lockbox after pipeline freeze.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing prediction/raw response files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Lockbox discipline: the held-out test split requires an explicit override
    # so it cannot be run accidentally during prompt iteration.
    if args.split == "test_lockbox" and not args.allow_lockbox:
        print(
            "Refusing to run on test_lockbox without --allow-lockbox.",
            file=sys.stderr,
        )
        return 2
    if args.limit is not None and args.limit <= 0:
        print("--limit must be positive.", file=sys.stderr)
        return 2
    if args.batch_size <= 0:
        print("--batch-size must be positive.", file=sys.stderr)
        return 2
    if args.max_retries < 0:
        print("--max-retries must be zero or positive.", file=sys.stderr)
        return 2
    if args.seed is not None and args.seed < 0:
        print("--seed must be zero or positive.", file=sys.stderr)
        return 2
    if args.top_p is not None and not 0 < args.top_p <= 1:
        print("--top-p must be in (0, 1].", file=sys.stderr)
        return 2
    if args.top_k is not None and args.top_k <= 0:
        print("--top-k must be positive.", file=sys.stderr)
        return 2
    if args.min_p is not None and not 0 <= args.min_p <= 1:
        print("--min-p must be in [0, 1].", file=sys.stderr)
        return 2

    # Locate the requested split and prompt. By default these are resolved
    # relative to the standalone XLing-LLM_coding folder.
    split_path = args.split_dir / f"{args.split}.jsonl"
    if not split_path.exists():
        print(f"Split file not found: {split_path}", file=sys.stderr)
        return 2
    if not args.prompt.exists():
        print(f"Prompt file not found: {args.prompt}", file=sys.stderr)
        return 2

    # Load the split and optionally truncate for smoke tests, e.g. --limit 20.
    records = read_jsonl(split_path)
    if args.limit is not None:
        records = records[: args.limit]
    if not records:
        print("No records to code.", file=sys.stderr)
        return 2

    # Build traceable but compact output filenames. Full provenance is stored
    # below in raw-response metadata and printed in the terminal summary.
    model_slug = clean_model_name(args.model)
    limit_suffix = f"_limit-{args.limit}" if args.limit is not None else ""
    output_prefix = f"{args.split}_{model_slug}_{args.schema_version}_{args.prompt_version}{limit_suffix}"
    results_dir = args.results_dir
    if results_dir is None:
        results_dir = (
            DEFAULT_RESULTS_DIR / "lockbox"
            if args.split == "test_lockbox"
            else DEFAULT_RESULTS_DIR
        )
    prediction_path = results_dir / f"{output_prefix}_predictions.jsonl"
    raw_path = results_dir / f"{output_prefix}_raw_responses.jsonl"

    # Avoid clobbering previous runs unless the user explicitly requests it.
    if not args.overwrite and (prediction_path.exists() or raw_path.exists()):
        print(
            f"Output already exists. Use --overwrite to replace:\n"
            f"  {prediction_path}\n  {raw_path}",
            file=sys.stderr,
        )
        return 2

    prompt = args.prompt.read_text(encoding="utf-8")
    if args.reasoning_effort is not None:
        prompt = f"Reasoning: {args.reasoning_effort}\n\n{prompt}"
    decoding_options = {
        "temperature": args.temperature,
        "seed": args.seed,
        "top_p": args.top_p,
        "top_k": args.top_k,
        "min_p": args.min_p,
        "num_ctx": args.num_ctx,
        "num_predict": args.num_predict,
    }
    predictions = []
    raw_responses = []
    retry_rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    started_at = time.time()

    # Process records in deterministic order. Each batch is independently
    # validated, then appended to the run-level outputs.
    for batch_index, batch in chunks(records, args.batch_size):
        batch_number = batch_index // args.batch_size + 1
        batch_records = [prompt_record(record) for record in batch]
        expected_ids = [record["record_id"] for record in batch_records]
        output_schema = build_output_schema(expected_ids, args.schema_version)
        print(
            f"Coding batch {batch_number}: {expected_ids[0]}..{expected_ids[-1]}",
            file=sys.stderr,
        )
        validation_feedback = None
        last_payload = None
        last_raw_response = None
        last_error = None

        # Local models may produce syntactically valid JSON that still violates
        # our schema. Retry the same batch with the validation error included so
        # the model gets a chance to repair missing/extra keys or bad enum text.
        for attempt in range(args.max_retries + 1):
            if attempt:
                print(
                    f"Retrying batch {batch_number} after "
                    f"{type(last_error).__name__} ({attempt}/{args.max_retries}).",
                    file=sys.stderr,
                )
            # At temperature 0 the model is deterministic, so a degenerate
            # response (a timeout-inducing or empty thinking-channel runaway)
            # would repeat identically on every retry. On retries, nudge the
            # temperature up and vary the seed so the resample can escape.
            #
            # By default retry seeds come from system randomness so a fresh
            # resubmission can escape a repeatedly degenerate batch. An
            # explicit --seed deliberately makes the experiment reproducible,
            # including its retry sequence.
            attempt_temperature = (
                args.temperature
                if attempt == 0
                else max(args.temperature, 0.4 + 0.3 * (attempt - 1))
            )
            if attempt == 0:
                attempt_seed = (
                    None if args.seed is None else args.seed + batch_number - 1
                )
            else:
                attempt_seed = retry_rng.randrange(2**31)
            try:
                payload, raw_response = ollama_chat(
                    url=args.ollama_url,
                    model=args.model,
                    prompt=prompt,
                    records=batch_records,
                    output_schema=output_schema,
                    temperature=attempt_temperature,
                    top_p=args.top_p,
                    top_k=args.top_k,
                    min_p=args.min_p,
                    timeout=args.timeout,
                    num_ctx=args.num_ctx,
                    num_predict=args.num_predict,
                    seed=attempt_seed,
                    validation_feedback=validation_feedback,
                )
                last_payload = payload
                last_raw_response = raw_response
                batch_predictions = validate_response(
                    payload, expected_ids, args.schema_version
                )
                last_error = None
                break
            except ValidationError as exc:
                # Schema-valid JSON, wrong shape: feed the error back so the
                # next attempt can repair the specific key/enum problem.
                last_error = exc
                validation_feedback = str(exc)
            except RetryableBatchError as exc:
                # Timeout or empty/degenerate response: resample with a fresh
                # seed rather than feeding a (non-existent) validation hint.
                last_error = exc
                validation_feedback = None
        else:
            batch_predictions = []

        if last_error is not None:
            failure_path = results_dir / f"{output_prefix}_failed_batch-{batch_number}.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            failure_path.write_text(
                json.dumps(
                    {
                        "batch_number": batch_number,
                        "record_ids": expected_ids,
                        "model": args.model,
                        "schema_version": args.schema_version,
                        "prompt_version": args.prompt_version,
                        "prompt_path": str(args.prompt),
                        "reasoning_effort": args.reasoning_effort or "default",
                        "decoding_options": decoding_options,
                        "validation_error": str(last_error),
                        "parsed_payload": last_payload,
                        "raw_response": last_raw_response,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            raise last_error

        predictions.extend(batch_predictions)
        raw_responses.append(
            {
                "batch_number": batch_number,
                "record_ids": expected_ids,
                "model": args.model,
                "schema_version": args.schema_version,
                "prompt_version": args.prompt_version,
                "prompt_path": str(args.prompt),
                "reasoning_effort": args.reasoning_effort or "default",
                "decoding_options": decoding_options,
                "raw_response": raw_response,
            }
        )

    # Write only after every batch succeeds. This prevents partial prediction
    # files from looking like complete validated outputs.
    write_jsonl(prediction_path, predictions)
    write_jsonl(raw_path, raw_responses)
    elapsed = time.time() - started_at
    print(
        json.dumps(
            {
                "split": args.split,
                "model": args.model,
                "schema_version": args.schema_version,
                "prompt_version": args.prompt_version,
                "prompt_path": str(args.prompt),
                "reasoning_effort": args.reasoning_effort or "default",
                "decoding_options": decoding_options,
                "n_records": len(records),
                "batch_size": args.batch_size,
                "prediction_path": str(prediction_path),
                "raw_response_path": str(raw_path),
                "elapsed_seconds": round(elapsed, 2),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
