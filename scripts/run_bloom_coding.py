#!/usr/bin/env python3
"""Run Bloom negation coding with a local Ollama model.

This runner is intentionally dev-first: it refuses to run on test_lockbox unless
--allow-lockbox is passed, strips human/evaluation fields before prompting, and
validates model output before writing predictions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


# Resolve paths relative to this standalone XLing-LLM_coding folder. This keeps
# the script portable after the folder is pushed to its own Git repository and
# cloned onto Oscar.
LLM_DIR = Path(__file__).resolve().parents[1]
DEFAULT_PROMPT = LLM_DIR / "v3" / "bloom_v3_english_prompt.md"
DEFAULT_SPLIT_DIR = LLM_DIR / "splits" / "english"
# Development runs write directly into the version's results folder; the
# split name in every output filename keeps runs distinguishable. The one
# exception is the final lockbox evaluation, which is routed to a lockbox/
# subfolder automatically so its outputs stay physically separated from dev
# outputs, per LLM_validation_plan.md.
DEFAULT_RESULTS_DIR = LLM_DIR / "v3" / "results"
DEFAULT_OLLAMA_URL = "http://localhost:11434/api/chat"

# These version strings are saved in raw-response metadata and the terminal
# summary. The schema and prompt versions are also used in output filenames as
# compact run locators; the full prompt path stays in metadata. Defaults track
# the current policy/prompt version; pass --schema-version/--prompt-version
# (with matching --prompt and --results-dir) to reproduce an older run.
DEFAULT_SCHEMA_VERSION = "bloom_v3"
DEFAULT_PROMPT_VERSION = "p003"

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
    for prediction in predictions:
        if not isinstance(prediction, dict):
            raise ValidationError("Each prediction must be an object.")
        extra = set(prediction) - {"record_id", "bloom_label", "flags", "comments"}
        missing = {"record_id", "bloom_label", "flags", "comments"} - set(prediction)
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
    decoding time.
    """
    flag_value = {"type": "string", "enum": sorted(ALLOWED_FLAG_VALUES)}
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
                    "properties": {
                        "record_id": {"type": "string", "enum": expected_ids},
                        "comments": {"type": "string"},
                        "bloom_label": {
                            "type": "string",
                            "enum": sorted(ALLOWED_LABELS),
                        },
                        "flags": {
                            "type": "object",
                            "properties": {flag: flag_value for flag in FLAG_ORDER},
                            "required": FLAG_ORDER,
                            "additionalProperties": False,
                        },
                    },
                    "required": ["record_id", "comments", "bloom_label", "flags"],
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
    timeout: int,
    num_ctx: int | None = None,
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
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "format": output_schema,
        "options": {"temperature": temperature},
    }
    # Pin the context window when asked. The default (model/server-chosen, often
    # 32k) sizes a multi-GB KV cache that can force a large model to spill layers
    # onto CPU; batches here are small, so a few-thousand-token window is ample
    # and keeps the model fully on GPU.
    if num_ctx is not None:
        request_payload["options"]["num_ctx"] = num_ctx
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
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Could not reach Ollama at {url}. Is `ollama serve` running on this node?"
        ) from exc

    # Ollama chat responses place the model's text in message.content.
    content = (raw_response.get("message") or {}).get("content")
    if not content:
        raise RuntimeError(f"Ollama response did not include message.content: {raw_response}")
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
        help="Retry a batch this many times after schema validation failures.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--num-ctx",
        type=int,
        default=None,
        help="Pin Ollama's context window (tokens). Lower (e.g. 8192) shrinks "
        "the KV cache so a large model fits fully on the GPU. Default: "
        "model/server default.",
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
    predictions = []
    raw_responses = []
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
                    f"Retrying batch {batch_number} after validation failure "
                    f"({attempt}/{args.max_retries}).",
                    file=sys.stderr,
                )
            payload, raw_response = ollama_chat(
                url=args.ollama_url,
                model=args.model,
                prompt=prompt,
                records=batch_records,
                output_schema=output_schema,
                temperature=args.temperature,
                timeout=args.timeout,
                num_ctx=args.num_ctx,
                validation_feedback=validation_feedback,
            )
            last_payload = payload
            last_raw_response = raw_response
            try:
                batch_predictions = validate_response(
                    payload, expected_ids, args.schema_version
                )
                last_error = None
                break
            except ValidationError as exc:
                last_error = exc
                validation_feedback = str(exc)
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
