# Build the multi-version LLM-human coding viewer HTML.
#
# Discovers every scored run across the version folders (v1/, v2/, ...) by
# globbing vN/results/*llm-human-audit*.csv, embeds all of them in one
# self-contained HTML, and writes it to <repo>/coding_viewer.html (gitignored).
#
# Per run it joins display-side extras onto the audit rows:
#   - structured context lines + child age from the split JSONL
#     (preferring the frozen copy in vN/inputs/splits/english/ when present)
#   - coder certainty fields from the human-reference JSONL
#   - model chain-of-thought from the *_raw_responses.jsonl in the same
#     results folder (paired by record-id overlap; multi-record batch thinking
#     is stored once per run and rows carry a small reference to it)
#
# Audit values are embedded verbatim except that duplicated flattened context
# strings are replaced by references to the shared structured context store.
# All agreement/kappa numbers are computed in the browser from the same
# collapsed-label columns and denominators as the IRR reports. Rows on the inspected list
# (splits/english/inspected_rows.txt) are badged, and both the run explorer
# and the trends tab can restrict their stats to the clean (headline) subset,
# mirroring the IRR report's clean-vs-inspected stratification.
#
# Supersedes v1/results/build_visualization_tool.R (kept frozen as the v1
# single-run artifact builder).

library(jsonlite)
library(readr)

chr1 <- function(x) {
  if (is.null(x) || length(x) == 0) return("")
  x <- x[[1]]
  if (is.null(x) || is.na(x)) return("")
  as.character(x)
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
script_path <- if (length(script_arg)) sub("^--file=", "", script_arg[[1]]) else NA_character_
scripts_dir <- if (!is.na(script_path) && file.exists(script_path)) dirname(normalizePath(script_path)) else NA_character_
if (is.na(scripts_dir) || !dir.exists(scripts_dir)) {
  scripts_dir <- "/Users/annika/Documents/Research/XLing/Data/XLing-LLM_coding/scripts"
}
llm_dir <- normalizePath(file.path(scripts_dir, ".."))
output_path <- file.path(llm_dir, "coding_viewer.html")

read_jsonl <- function(path) lapply(readLines(path, warn = FALSE), jsonlite::fromJSON, simplifyVector = TRUE)

context_list <- function(df) {
  if (is.null(df) || !is.data.frame(df) || nrow(df) == 0) return(list())
  lapply(seq_len(nrow(df)), function(i) list(
    line = chr1(df$line[i]),
    speaker = chr1(df$speaker[i]),
    utterance = chr1(df$utterance[i])
  ))
}

first_existing <- function(paths) {
  for (p in paths) if (file.exists(p)) return(p)
  NA_character_
}

# Canonical inspected-rows list (development rows: content was read, mined for
# prompt examples, or adjudicated; excluded from headline metrics). Audits
# rendered since 2026-06-11 carry an `inspected` column written at scoring
# time, which is kept verbatim; the frozen v1 audit predates the column, so
# membership is derived from this list instead.
inspected_path <- file.path(llm_dir, "splits", "english", "inspected_rows.txt")
inspected_ids <- character(0)
if (file.exists(inspected_path)) {
  insp_lines <- trimws(readLines(inspected_path, warn = FALSE))
  inspected_ids <- insp_lines[nzchar(insp_lines) & !startsWith(insp_lines, "#")]
}

# record_id prefix -> language folder under splits/. Each run is shown against
# its own language's split and human reference. Both Tagalog corpora (tgm =
# MPI, tgn = new corpus) map to the combined splits/tagalog/ files.
lang_by_prefix <- c(
  eng = "english", ger = "german", heb = "hebrew", spa = "spanish",
  tgm = "tagalog", tgn = "tagalog"
)
lang_from_id <- function(record_id) {
  prefix <- sub("^([a-z]+)_.*", "\\1", record_id)
  lang <- lang_by_prefix[[prefix]]
  if (is.null(lang)) "english" else lang
}

# Stable display order for prompt-example conditions. This mirrors the viewer
# labels: native/no suffix first, then English examples, then localized
# examples. Keeping this explicit avoids accidental reordering by run date or
# filename when new masked/unmasked runs are added.
example_order <- function(prompt_version) {
  pv <- chr1(prompt_version)
  if (grepl("-engex$", pv)) return(1L)
  if (grepl("-loc$", pv)) return(2L)
  0L
}

# Transcript context is identical across models and prompt versions that use
# the same split. Keep one global copy and place only a zero-based reference on
# each audit row; otherwise the same 40-line window is embedded dozens of times
# as the run matrix grows.
context_index <- new.env(parent = emptyenv(), hash = TRUE)
context_store <- list()
context_id_for <- function(key, value) {
  if (exists(key, envir = context_index, inherits = FALSE)) {
    return(get(key, envir = context_index, inherits = FALSE))
  }
  id <- length(context_store)
  context_store[[id + 1]] <<- value
  assign(key, id, envir = context_index)
  id
}

build_run <- function(audit_path, version) {
  rows <- readr::read_csv(audit_path, col_types = readr::cols(.default = readr::col_character()))
  rows[is.na(rows)] <- ""
  if (!"inspected" %in% names(rows)) {
    rows$inspected <- ifelse(rows$record_id %in% inspected_ids, "TRUE", "FALSE")
  }
  audit_ids <- rows$record_id
  split_name <- chr1(rows$split[1])
  lang <- lang_from_id(chr1(rows$record_id[1]))
  results_dir <- dirname(audit_path)

  # Pair the raw-responses file to this audit. Raw files normally sit next to
  # the audit; dev/ is a legacy location and lockbox/ holds the final
  # test_lockbox evaluation outputs.
  raw_dirs <- c(results_dir, file.path(results_dir, "dev"), file.path(results_dir, "lockbox"))
  raw_files <- unlist(lapply(
    raw_dirs[dir.exists(raw_dirs)],
    function(d) list.files(d, pattern = "_raw_responses\\.jsonl$", full.names = TRUE)
  ))
  best_raw <- NULL
  best_overlap <- 0
  # Prefer the raw file whose name matches this audit's run prefix
  # (llm-human-audit_<prefix>.csv -> <prefix>_raw_responses.jsonl). Record-id
  # overlap alone is ambiguous when two runs share one record set (e.g. two
  # prompts on the same split), so this keeps them correctly separated.
  run_prefix <- sub("\\.csv$", "", sub("^.*llm-human-audit_", "", basename(audit_path)))
  named_raw <- raw_files[basename(raw_files) == paste0(run_prefix, "_raw_responses.jsonl")]
  if (length(named_raw)) {
    best_raw <- tryCatch(read_jsonl(named_raw[[1]]), error = function(e) NULL)
    if (!is.null(best_raw)) best_overlap <- 1
  }
  # Fall back to record-id overlap for legacy names that don't follow the
  # <prefix>_raw_responses.jsonl convention (e.g. the dated v1 files).
  if (is.null(best_raw)) {
    for (rf in raw_files) {
      batches <- tryCatch(read_jsonl(rf), error = function(e) NULL)
      if (is.null(batches)) next
      raw_ids <- unlist(lapply(batches, function(b) b$record_ids))
      overlap <- length(intersect(raw_ids, audit_ids)) / max(1, length(audit_ids))
      if (overlap > best_overlap) {
        best_overlap <- overlap
        best_raw <- batches
      }
    }
  }

  thinking_map <- list()
  thinking_batches <- list()
  model <- ""
  schema_version <- ""
  prompt_version <- ""
  run_date <- ""
  if (!is.null(best_raw) && best_overlap >= 0.5) {
    first <- best_raw[[1]]
    model <- chr1(first$model)
    schema_version <- chr1(first$schema_version)
    prompt_version <- chr1(first$prompt_version)
    run_date <- substr(chr1(first$raw_response$created_at), 1, 10)
    for (b in best_raw) {
      ids <- b$record_ids
      think <- chr1(b$raw_response$message$thinking)
      if (!nzchar(think)) next
      # Raw responses are normally batches of five records. Store the shared
      # reasoning once and let every row point to its zero-based array index;
      # embedding the same long string on all five rows made the self-contained
      # viewer exceed browser string limits as the run matrix grew.
      thinking_id <- length(thinking_batches)
      thinking_batches[[thinking_id + 1]] <- list(
        text = think,
        shared_n = length(ids)
      )
      for (id in ids) {
        thinking_map[[id]] <- thinking_id
      }
    }
  }

  # Prompt versions p<NNN>m* are the masked-negator arm. Keep this as explicit
  # run metadata rather than making the browser/UI infer meaning from the
  # otherwise easy-to-miss "m" in p004m. The filename fallback also covers a
  # usable audit whose raw-response companion is absent.
  masked <- grepl("^p[0-9]+m([-_]|$)", prompt_version) ||
    grepl("_p[0-9]+m([-_]|$)", run_prefix)
  split_lang <- if (masked) paste0(lang, "_masked") else lang

  # Prefer the frozen per-version inputs so each run is shown against the
  # exact split files it consumed; fall back to the shared splits.
  split_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", split_lang, paste0(split_name, ".jsonl")),
    file.path(llm_dir, "splits", split_lang, paste0(split_name, ".jsonl"))
  ))
  ref_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", split_lang, paste0(split_name, "_human_reference.jsonl")),
    file.path(llm_dir, "splits", split_lang, paste0(split_name, "_human_reference.jsonl"))
  ))

  split_records <- list()
  if (!is.na(split_path)) {
    split_records <- read_jsonl(split_path)
    names(split_records) <- vapply(split_records, function(r) chr1(r$record_id), character(1))
  }
  human_records <- list()
  if (!is.na(ref_path)) {
    human_records <- read_jsonl(ref_path)
    names(human_records) <- vapply(human_records, function(r) chr1(r$record_id), character(1))
  }

  # The LLM's binary `certain` (Yes/No, v4+) lives in the predictions file, not
  # every audit CSV (older audits predate the column). Read it straight from
  # the predictions companion so the certainty panel works regardless of when
  # an audit was last rendered; pre-v4 runs simply have no `certain` key and
  # contribute nothing to the panel.
  pred_files <- unlist(lapply(
    raw_dirs[dir.exists(raw_dirs)],
    function(d) list.files(d, pattern = "_predictions\\.jsonl$", full.names = TRUE)
  ))
  named_pred <- pred_files[basename(pred_files) == paste0(run_prefix, "_predictions.jsonl")]
  llm_certain_map <- list()
  if (length(named_pred)) {
    preds <- tryCatch(read_jsonl(named_pred[[1]]), error = function(e) NULL)
    for (p in preds) {
      rid <- chr1(p$record_id)
      if (nzchar(rid)) llm_certain_map[[rid]] <- chr1(p$certain)
    }
  }

  rows_list <- lapply(seq_len(nrow(rows)), function(i) {
    row <- as.list(rows[i, ])
    rid <- row$record_id
    # Drop any audit-derived llm_certain so the predictions-sourced value is the
    # single source of truth (re-rendered v4 audits carry the column; older
    # ones do not) and no duplicate JSON key is emitted.
    row$llm_certain <- NULL
    s <- split_records[[rid]]
    h <- human_records[[rid]]
    before_lines <- context_list(s$context_before)
    after_lines <- context_list(s$context_after)
    # The audit CSV carries flattened context strings, while the split supplies
    # the same content as structured lines for rendering. Keep the flattened
    # fallback only when structured context is unavailable.
    fallback_before <- chr1(row$context_before)
    fallback_after <- chr1(row$context_after)
    row$context_before <- NULL
    row$context_after <- NULL
    context_source <- if (!is.na(split_path)) split_path else audit_path
    context_id <- context_id_for(
      paste(context_source, rid, sep = "\037"),
      list(
        before = before_lines,
        after = after_lines,
        fallback_before = if (!length(before_lines)) fallback_before else "",
        fallback_after = if (!length(after_lines)) fallback_after else ""
      )
    )
    extras <- list(
      llm_certain = chr1(llm_certain_map[[rid]]),
      child_age_raw = chr1(s$child_age_raw),
      child_age_months = chr1(s$child_age_months),
      context_id = context_id,
      human_1_certain = chr1(h$coder_1$certain_bloom),
      human_1_other_possibility = chr1(h$coder_1$other_possibility_bloom),
      human_1_one_of_two = chr1(h$coder_1$definitely_one_of_two_bloom),
      human_2_certain = chr1(h$coder_2$certain_bloom),
      human_2_other_possibility = chr1(h$coder_2$other_possibility_bloom),
      human_2_one_of_two = chr1(h$coder_2$definitely_one_of_two_bloom),
      llm_thinking_id = chr1(thinking_map[[rid]])
    )
    c(row, extras)
  })

  context_window <- ""
  if (length(split_records)) context_window <- chr1(split_records[[1]]$context_window_size)

  list(
    meta = list(
      version = version,
      split = split_name,
      # Prefer the audit's language column; fall back to the record_id-derived
      # folder name (Title-cased) so every run has a non-empty language label.
      language = {
        L <- chr1(rows$language[1])
        if (nzchar(L)) L else paste0(toupper(substring(lang, 1, 1)), substring(lang, 2))
      },
      model = model,
      schema_version = schema_version,
      prompt_version = prompt_version,
      run_date = run_date,
      context_window = context_window,
      masking = if (masked) "masked" else "unmasked",
      n_rows = nrow(rows),
      audit_csv = basename(audit_path)
    ),
    rows = rows_list,
    thinking = thinking_batches
  )
}

version_dirs <- list.files(llm_dir, pattern = "^v[0-9]+$", full.names = TRUE)
version_dirs <- version_dirs[file.info(version_dirs)$isdir]
runs <- list()
for (vdir in version_dirs[order(as.integer(sub("^v", "", basename(version_dirs))))]) {
  audits <- list.files(file.path(vdir, "results"), pattern = "llm-human-audit.*\\.csv$", full.names = TRUE)
  for (audit in sort(audits)) {
    message("Adding run: ", audit)
    runs[[length(runs) + 1]] <- build_run(audit, basename(vdir))
  }
}
if (!length(runs)) stop("No audit CSVs found under v*/results/.")

# Order runs by language first, then by model, so the dropdown and the
# across-runs chart group by language and keep each model's runs contiguous
# (gemma's version history, then qwen's, etc.). Within a language+model:
# chronologically by version number, then negator condition (visible/unmasked
# first, masked second), then prompt-example condition, run date, and size.
# That keeps the comparison chart's x-axis visually paired while placing
# masked runs to the right within each language+model+version cluster.
run_order <- order(
  vapply(runs, function(r) tolower(r$meta$language), character(1)),
  vapply(runs, function(r) tolower(r$meta$model), character(1)),
  vapply(runs, function(r) as.integer(sub("^v", "", r$meta$version)), integer(1)),
  vapply(runs, function(r) identical(r$meta$masking, "masked"), logical(1)),
  vapply(runs, function(r) example_order(r$meta$prompt_version), integer(1)),
  vapply(runs, function(r) ifelse(nzchar(r$meta$run_date), r$meta$run_date, "9999-99-99"), character(1)),
  vapply(runs, function(r) r$meta$n_rows, numeric(1))
)
runs <- runs[run_order]

# Prompt experiments are a deliberately class-enriched English diagnostic, so
# they belong in their own viewer tab rather than in the population-oriented
# scored-run comparisons above. Refresh the compact summary when source
# predictions are newer, then embed it with the split manifest. The viewer
# remains usable when no prompt experiments have been copied to this machine.
prompt_results_dir <- file.path(llm_dir, "v5", "results", "prompt_experiments")
prompt_summary_path <- file.path(prompt_results_dir, "summary.csv")
prompt_manifest_path <- file.path(
  llm_dir, "splits", "english", "dev_train_prompttest_v5_manifest.json"
)
prompt_summarizer <- file.path(llm_dir, "scripts", "summarize_v5_prompt_experiments.py")
prompt_prediction_files <- if (dir.exists(prompt_results_dir)) {
  list.files(prompt_results_dir, pattern = "_predictions\\.jsonl$", full.names = TRUE)
} else {
  character(0)
}
if (
  length(prompt_prediction_files) &&
  file.exists(prompt_manifest_path) &&
  file.exists(prompt_summarizer)
) {
  needs_refresh <- !file.exists(prompt_summary_path) ||
    max(file.info(prompt_prediction_files)$mtime, na.rm = TRUE) >
      file.info(prompt_summary_path)$mtime
  if (needs_refresh) {
    summary_output <- system2(
      "python3", prompt_summarizer, stdout = TRUE, stderr = TRUE
    )
    status <- attr(summary_output, "status")
    if (!is.null(status) && status != 0) {
      warning("Prompt-experiment summary refresh failed:\n", paste(summary_output, collapse = "\n"))
    }
  }
}

prompt_experiment_rows <- list()
if (file.exists(prompt_summary_path)) {
  prompt_df <- readr::read_csv(
    prompt_summary_path,
    col_types = readr::cols(.default = readr::col_character())
  )
  prompt_df[is.na(prompt_df)] <- ""
  prompt_experiment_rows <- lapply(seq_len(nrow(prompt_df)), function(i) {
    as.list(prompt_df[i, ])
  })
}
prompt_manifest <- if (file.exists(prompt_manifest_path)) {
  jsonlite::fromJSON(prompt_manifest_path, simplifyVector = FALSE)
} else {
  list()
}

payload <- list(
  generated_on = format(Sys.Date()),
  runs = runs,
  contexts = context_store,
  prompt_experiments = list(
    available = length(prompt_experiment_rows) > 0,
    rows = prompt_experiment_rows,
    manifest = prompt_manifest
  )
)
json_data <- jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null")
json_data <- gsub("</", "<\\/", json_data, fixed = TRUE)

html <- paste0(
'<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>XLing LLM-Human Coding Viewer</title>
  <style>
    :root {
      --bg: #f7f7f4;
      --panel: #ffffff;
      --ink: #202124;
      --muted: #687076;
      --border: #d9ded8;
      --soft: #eef2ee;
      --accent: #1f6f68;
      --accent-weak: #e3f0ed;
      --warn: #a45c19;
      --warn-weak: #fff0dd;
      --bad: #a33a35;
      --bad-weak: #f8e4e2;
      --good: #2f6b3f;
      --good-weak: #e5f1e4;
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
      --sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: var(--sans);
      color: var(--ink);
      background: var(--bg);
      font-size: 14px;
      line-height: 1.45;
    }

    .page { max-width: 1680px; margin: 0 auto; padding: 18px 22px 40px; }

    h1, h2, h3 { margin: 0; }
    h1 { font-size: 21px; line-height: 1.2; }
    h2 { font-size: 15px; }
    h3 { font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; }
    p { margin: 0; }
    .muted { color: var(--muted); }
    .subhead { color: var(--muted); margin-top: 5px; font-size: 13px; max-width: 75ch; }
    .hidden { display: none !important; }

    .page-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .run-picker { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .run-picker label { font-size: 12px; font-weight: 650; color: var(--muted); margin: 0; }
    .run-picker select { min-height: 34px; min-width: 320px; }
    .masking-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 34px;
      padding: 6px 12px;
      border: 2px solid;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 850;
      letter-spacing: 0.055em;
      line-height: 1.1;
      text-transform: uppercase;
      white-space: nowrap;
      box-shadow: 0 1px 3px rgba(32, 33, 36, 0.14);
    }
    .masking-badge.masked { color: #fff; background: #6d3f8f; border-color: #4f276d; }
    .masking-badge.unmasked { color: #fff; background: #14736b; border-color: #0b5751; }
    .masking-badge.compact {
      min-height: 0;
      padding: 2px 7px;
      border-width: 1px;
      border-radius: 999px;
      font-size: 9.5px;
      box-shadow: none;
    }

    .tabs { display: flex; gap: 6px; margin: 6px 0 14px; border-bottom: 1px solid var(--border); }
    .tab-btn {
      border: 1px solid var(--border);
      border-bottom: none;
      border-radius: 8px 8px 0 0;
      background: var(--soft);
      color: var(--muted);
      padding: 8px 16px;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }
    .tab-btn.active { background: var(--panel); color: var(--ink); border-color: var(--border); position: relative; top: 1px; }

    .run-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
    .run-chip {
      font-size: 12px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 3px 10px;
      color: var(--muted);
      white-space: nowrap;
    }
    .run-chip b { color: var(--ink); font-weight: 650; }

    .summary-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 10px;
    }
    .summary-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 12px 14px;
      position: relative;
    }
    .summary-card.baseline { border-color: #b9cdc9; background: #f4f9f7; }
    .summary-card .big { font-size: 24px; font-weight: 750; line-height: 1.1; }
    .summary-card .name { font-size: 12.5px; font-weight: 650; margin-top: 3px; }
    .summary-card .sub { color: var(--muted); font-size: 12px; margin-top: 1px; }
    .baseline-tag {
      position: absolute; top: 10px; right: 12px;
      font-size: 10.5px; font-weight: 700; letter-spacing: 0.05em;
      color: var(--accent); text-transform: uppercase;
    }

    .scope-bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
    .scope-bar .seg-btn:disabled { opacity: 0.45; cursor: default; }
    .scope-note { color: var(--muted); font-size: 11.5px; max-width: 60ch; }
    .insp-chip {
      font-size: 10.5px; padding: 1px 7px; border-radius: 999px; font-weight: 700;
      background: #f1e9f6; color: #6d4a8f; border: 1px solid #d9c8e8; white-space: nowrap;
    }

    .triage-strip { display: flex; flex-wrap: wrap; gap: 7px; align-items: center; margin-bottom: 14px; }
    .triage-label { font-size: 12px; color: var(--muted); margin-right: 2px; }
    .triage-chip {
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--panel);
      padding: 4px 11px;
      font: inherit;
      font-size: 12.5px;
      cursor: pointer;
      color: var(--ink);
      display: inline-flex;
      gap: 6px;
      align-items: center;
    }
    .triage-chip strong { font-size: 13px; }
    .triage-chip.good strong { color: var(--good); }
    .triage-chip.warn strong { color: var(--warn); }
    .triage-chip.bad strong { color: var(--bad); }
    .triage-chip.missing strong { color: var(--muted); }
    .triage-chip.active { border-color: var(--accent); background: var(--accent-weak); font-weight: 650; }
    .triage-chip:hover { border-color: var(--accent); }

    .workspace {
      display: grid;
      grid-template-columns: 380px minmax(0, 1fr);
      gap: 14px;
      align-items: stretch;
      /* Height is set in JS (sizeWorkspace) to fill the viewport below the
         header, so the two panels stay balanced and each scrolls internally
         instead of the record list growing into a tall wall. */
      min-height: 480px;
    }

    .list-panel, .detail-panel, .table-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      min-width: 0;
    }
    .list-panel { display: flex; flex-direction: column; min-height: 0; }
    .list-panel .list-controls, .list-panel .list-meta { flex: none; }

    .list-controls { padding: 12px; border-bottom: 1px solid var(--border); display: grid; gap: 8px; }
    .control-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    label { display: block; font-size: 11.5px; font-weight: 650; color: var(--muted); margin-bottom: 3px; }
    input, select {
      width: 100%;
      min-height: 33px;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 5px 8px;
      background: white;
      color: var(--ink);
      font: inherit;
      font-size: 13px;
    }
    .segmented { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
    button { font: inherit; cursor: pointer; }
    .seg-btn {
      border: 1px solid var(--border);
      border-radius: 6px;
      background: var(--panel);
      color: var(--ink);
      padding: 6px 8px;
      font-size: 12.5px;
    }
    .seg-btn.active { border-color: var(--accent); background: var(--accent-weak); font-weight: 650; }
    .reset-btn {
      border: 0; background: none; color: var(--accent);
      font-size: 12.5px; padding: 2px 0; text-align: left; width: fit-content;
      text-decoration: underline;
    }

    .list-meta { padding: 8px 12px; border-bottom: 1px solid var(--border); color: var(--muted); font-size: 12px; }
    .record-list { flex: 1 1 auto; min-height: 0; overflow: auto; border-radius: 0 0 10px 10px; }

    .record-row {
      width: 100%;
      text-align: left;
      border: 0;
      border-bottom: 1px solid var(--border);
      padding: 9px 12px;
      background: white;
      display: block;
    }
    .record-row:hover { background: #fafbf8; }
    .record-row.selected { background: var(--accent-weak); box-shadow: inset 3px 0 0 var(--accent); }
    .row-head { display: flex; gap: 8px; align-items: baseline; }
    .row-loc { font-family: var(--mono); font-size: 11px; color: var(--muted); white-space: nowrap; }
    .row-utt { font-weight: 650; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .row-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 5px; align-items: center; }
    .row-chips .who { font-size: 10.5px; color: var(--muted); margin-left: 2px; }

    .status {
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11.5px;
      font-weight: 700;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .status.good { background: var(--good-weak); color: var(--good); border-color: #bcd8bd; }
    .status.warn { background: var(--warn-weak); color: var(--warn); border-color: #eccb9f; }
    .status.bad { background: var(--bad-weak); color: var(--bad); border-color: #e2bab6; }
    .status.missing { background: var(--soft); color: var(--muted); border-color: var(--border); }

    .lab {
      display: inline-flex;
      align-items: center;
      padding: 2px 9px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 12px;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .lab.mini { font-size: 10.5px; padding: 1px 7px; }
    .lab-nonexistence { background: #e5edf7; color: #2d5f8b; border-color: #c8d7ea; }
    .lab-rejection { background: #fff0dd; color: #a45c19; border-color: #eccb9f; }
    .lab-denial { background: #ece5f7; color: #5b3f96; border-color: #d4c6ec; }
    .lab-uncoded { background: #eef0f2; color: #5b6770; border-color: #d5dade; }
    .lab-excluded { background: #f3e9e3; color: #7a4f33; border-color: #e0cbb9; }
    .lab-other { background: #fbe7f1; color: #9c3970; border-color: #eec4da; }
    .lab-missing { background: #fff; color: #9aa3a9; border: 1px dashed #c4cbd0; font-weight: 600; }

    .detail-panel { padding: 14px 16px 16px; overflow-y: auto; }
    .detail-nav { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    .nav-btn {
      border: 1px solid var(--border); border-radius: 6px; background: var(--panel);
      padding: 4px 11px; font-size: 13px;
    }
    .nav-btn:hover { border-color: var(--accent); }
    .nav-btn:disabled { opacity: 0.4; cursor: default; }
    .nav-pos { color: var(--muted); font-size: 12px; }
    .kbd-hint { margin-left: auto; color: var(--muted); font-size: 11.5px; }
    .kbd-hint kbd {
      font-family: var(--mono); font-size: 10.5px; background: var(--soft);
      border: 1px solid var(--border); border-radius: 4px; padding: 0 4px;
    }

    .detail-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }
    .detail-meta { color: var(--muted); font-size: 12.5px; margin-top: 3px; }
    .detail-meta b { color: var(--ink); font-weight: 650; }

    .convo-box { margin-top: 12px; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    .convo-head {
      display: flex; justify-content: space-between; gap: 10px; align-items: baseline;
      padding: 8px 12px; background: #f0f3f0; border-bottom: 1px solid var(--border);
    }
    .convo-head .note { color: var(--muted); font-size: 11.5px; }
    .convo { max-height: 380px; overflow: auto; position: relative; padding: 6px 0; }
    .tline {
      display: grid;
      grid-template-columns: 46px 46px minmax(0, 1fr);
      gap: 8px;
      padding: 2.5px 12px;
      font-size: 13px;
    }
    .tline .lno { font-family: var(--mono); font-size: 10.5px; color: #9aa3a9; text-align: right; padding-top: 2px; }
    .tline .spk { font-weight: 750; font-size: 11.5px; padding-top: 1.5px; color: var(--muted); }
    .tline.spk-CHI .spk { color: var(--accent); }
    .tline.spk-MOT .spk, .tline.spk-FAT .spk { color: #2d5f8b; }
    .tline .utt { overflow-wrap: anywhere; color: #33383b; }
    .tline.target {
      background: var(--accent-weak);
      box-shadow: inset 3px 0 0 var(--accent);
      padding-top: 6px; padding-bottom: 6px;
      margin: 3px 0;
    }
    .tline.target .utt { font-weight: 700; font-size: 14px; color: var(--ink); }
    mark { background: #ffe28a; padding: 0 2px; border-radius: 3px; font-weight: 800; }
    .no-context { padding: 14px; color: var(--muted); font-size: 12.5px; font-family: var(--mono); white-space: pre-wrap; overflow-wrap: anywhere; }

    .coding-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .coder-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 11px 12px;
      background: #fff;
      min-width: 0;
    }
    .coder-card.match { border-color: #bcd8bd; background: #fbfdfb; }
    .coder-name { color: var(--muted); font-size: 11.5px; font-weight: 750; text-transform: uppercase; letter-spacing: 0.03em; }
    .coder-card .lab { margin-top: 7px; font-size: 13px; padding: 3px 10px; }
    .collapse-note { display: block; color: var(--muted); font-size: 11.5px; margin-top: 4px; }
    .certainty { margin-top: 7px; font-size: 12px; color: var(--muted); }
    .certainty b { color: var(--ink); font-weight: 650; }
    .comment { margin-top: 8px; color: #3a3d40; font-size: 12.5px; overflow-wrap: anywhere; }
    .not-coded { margin-top: 8px; color: #9aa3a9; font-size: 12.5px; }

    .flagmini {
      font-size: 10.5px; padding: 1px 7px; border-radius: 999px; font-weight: 700;
      border: 1px solid transparent; white-space: nowrap;
    }
    .flagmini.ok { background: var(--good-weak); color: var(--good); border-color: #bcd8bd; }
    .flagmini.bad { background: var(--bad-weak); color: var(--bad); border-color: #e2bab6; }
    .flagmini.solo { background: var(--warn-weak); color: var(--warn); border-color: #eccb9f; }

    .flag-compare { margin-top: 12px; border: 1px solid var(--border); border-radius: 8px; background: #fff; overflow: hidden; }
    .fc-row {
      display: grid;
      grid-template-columns: minmax(150px, 1fr) repeat(3, minmax(72px, auto)) minmax(0, 1.2fr);
      gap: 8px;
      padding: 7px 12px;
      border-bottom: 1px solid var(--border);
      align-items: center;
      font-size: 12.5px;
    }
    .fc-row:last-child { border-bottom: 0; }
    .fc-row.head { background: #f0f3f0; color: var(--muted); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em; }
    .fc-row.bad { background: var(--bad-weak); }
    .fc-row.ok { background: #fbfdfb; }
    .fc-name { font-weight: 650; }
    .fc-val { font-weight: 750; font-size: 12px; padding: 1px 8px; border-radius: 999px; justify-self: start; }
    .fc-val.yes { background: var(--warn-weak); color: var(--warn); border: 1px solid #eccb9f; }
    .fc-val.no { background: var(--soft); color: var(--muted); }
    .fc-val.na { color: #9aa3a9; font-weight: 600; }
    .fc-note { color: var(--muted); font-size: 11.5px; }
    .flag-compare-none { margin-top: 12px; padding: 9px 12px; color: #9aa3a9; font-size: 12px; border: 1px dashed var(--border); border-radius: 8px; }

    .verdict {
      margin-top: 12px;
      padding: 9px 12px;
      border-radius: 8px;
      background: var(--soft);
      border: 1px solid var(--border);
      font-size: 13px;
    }
    .verdict.good { background: var(--good-weak); border-color: #bcd8bd; }
    .verdict.warn { background: var(--warn-weak); border-color: #eccb9f; }
    .verdict.bad { background: var(--bad-weak); border-color: #e2bab6; }

    details.reasoning { margin-top: 12px; border: 1px solid var(--border); border-radius: 8px; background: #fff; }
    details.reasoning summary {
      cursor: pointer; padding: 9px 12px; font-weight: 650; font-size: 13px;
      color: var(--accent); list-style-position: inside;
    }
    details.reasoning[open] summary { border-bottom: 1px solid var(--border); }
    details.reasoning pre {
      margin: 0; padding: 11px 12px; max-height: 320px; overflow: auto;
      font-family: var(--mono); font-size: 11.5px; line-height: 1.5;
      white-space: pre-wrap; overflow-wrap: anywhere; color: #33383b;
    }

    .table-panel { margin-top: 16px; padding: 14px 16px; }
    .table-panel .caption { color: var(--muted); font-size: 12px; margin-top: 4px; margin-bottom: 10px; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid var(--border); padding: 7px 10px; text-align: left; font-size: 13px; }
    th { background: #f0f3f0; color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.03em; }
    tr:last-child td { border-bottom: 0; }
    td.numeric, th.numeric { text-align: right; font-variant-numeric: tabular-nums; }

    .denial-subhead { margin-top: 18px; margin-bottom: 4px; }
    .denial-detect { display: flex; flex-wrap: wrap; gap: 18px; align-items: flex-start; }
    .detect-block { flex: 1 1 320px; min-width: 280px; }
    .detect-block .block-title { font-size: 12.5px; font-weight: 650; margin-bottom: 6px; }
    .detect-block .block-title .muted { font-weight: 400; }
    .detect-grid { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 0.9fr); gap: 12px; align-items: start; }
    .confusion th, .confusion td { padding: 5px 8px; font-size: 12.5px; }
    .confusion td.tp { background: var(--good-weak); }
    .confusion td.tn { background: var(--good-weak); }
    .confusion td.fp, .confusion td.fn { background: var(--bad-weak); }
    .metric-table td { padding: 4px 8px; font-size: 12.5px; }
    .detect-empty { color: var(--muted); font-size: 12.5px; }

    .footnote { margin-top: 14px; color: var(--muted); font-size: 12px; max-width: 100ch; }

    .trend-panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
    .trend-head { margin-bottom: 14px; }
    .trend-toolbar {
      display: grid;
      grid-template-columns: repeat(3, minmax(150px, 1fr)) minmax(190px, 1.2fr);
      gap: 10px;
      padding: 12px;
      margin-bottom: 10px;
      border: 1px solid var(--border);
      border-radius: 9px;
      background: #fafbf9;
    }
    .trend-toolbar select { min-height: 34px; }
    .trend-language-filter, .trend-version-filter, .trend-model-filter {
      grid-column: 1 / -1;
      min-width: 0;
    }
    .trend-language-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    .trend-language-options { display: flex; gap: 6px; flex-wrap: wrap; }
    .trend-version-options, .trend-model-options { display: flex; gap: 6px; flex-wrap: wrap; }
    .trend-filter-label {
      display: flex;
      align-items: baseline;
      gap: 7px;
    }
    .trend-filter-label .trend-selection-count {
      color: var(--muted);
      font-size: 11px;
      font-weight: 500;
    }
    .language-action {
      border: 0;
      background: transparent;
      color: var(--accent);
      font: inherit;
      font-size: 11.5px;
      font-weight: 650;
      padding: 2px 0;
      cursor: pointer;
    }
    .language-action + .language-action { padding-left: 8px; border-left: 1px solid var(--border); }
    .trend-toolbar-actions {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 8px;
      grid-column: 1 / -1;
      padding-top: 2px;
    }
    .trend-count { color: var(--muted); font-size: 12px; }
    .trend-reset {
      border: 0;
      background: transparent;
      color: var(--accent);
      font: inherit;
      font-size: 12px;
      font-weight: 650;
      cursor: pointer;
      padding: 4px 0;
    }
    .trend-display {
      display: flex;
      align-items: flex-end;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .trend-display-group { display: grid; gap: 3px; }
    .trend-controls { display: flex; gap: 6px; }
    .series-toggles { display: flex; gap: 6px; flex-wrap: wrap; }
    .series-toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-height: 33px;
      padding: 5px 9px;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: white;
      color: var(--muted);
      font-size: 12px;
      cursor: pointer;
    }
    .series-toggle:has(input:checked) {
      border-color: var(--accent);
      background: var(--accent-weak);
      color: var(--ink);
      font-weight: 650;
    }
    .series-toggle input { width: auto; min-height: 0; margin: 0; accent-color: var(--accent); }
    .series-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
    .trend-empty { padding: 54px 16px; text-align: center; color: var(--muted); }
    .trend-chart-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(min(100%, 560px), 1fr));
      gap: 12px;
      align-items: start;
    }
    .trend-facet {
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 9px;
      background: #fff;
      padding: 10px 10px 4px;
    }
    .trend-facet-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
      padding: 0 4px 4px;
    }
    .trend-facet-head h3 { color: var(--ink); font-size: 13px; text-transform: none; letter-spacing: 0; }
    .trend-facet-head span { color: var(--muted); font-size: 11.5px; }
    .trend-svg-wrap { overflow-x: auto; }
    .trend-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 8px; font-size: 12px; color: var(--muted); align-items: center; }
    .trend-legend .swatch { display: inline-block; width: 18px; height: 0; border-top: 3px solid; vertical-align: middle; margin-right: 5px; border-radius: 2px; }
    .trend-legend .shape { font-family: var(--mono); margin-right: 4px; color: var(--ink); }

    .experiment-note {
      margin-bottom: 12px;
      padding: 12px 14px;
      border: 1px solid #b9cdc9;
      border-radius: 9px;
      background: #f4f9f7;
      color: #294a45;
      font-size: 13px;
    }
    .experiment-note b { color: #173f39; }
    .experiment-note ul { margin: 7px 0 0; padding-left: 20px; }
    .experiment-note li + li { margin-top: 4px; }
    .experiment-cards {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }
    .experiment-card {
      padding: 12px 14px;
      border: 1px solid var(--border);
      border-radius: 9px;
      background: #fff;
      min-width: 0;
    }
    .experiment-card .eyebrow {
      color: var(--muted);
      font-size: 10.5px;
      font-weight: 750;
      letter-spacing: .045em;
      text-transform: uppercase;
    }
    .experiment-card .score {
      margin-top: 4px;
      font-size: 24px;
      font-weight: 780;
      line-height: 1.05;
    }
    .experiment-card .condition { margin-top: 4px; font-size: 12px; color: var(--muted); }
    .experiment-card .condition b { color: var(--ink); }
    .experiment-chart { display: grid; gap: 7px; margin-top: 12px; }
    .experiment-row {
      display: grid;
      grid-template-columns: minmax(255px, 1.3fr) minmax(240px, 2fr) 86px 92px;
      gap: 10px;
      align-items: center;
      min-height: 36px;
      padding: 5px 8px;
      border-radius: 6px;
    }
    .experiment-row:hover { background: #f8faf7; }
    .experiment-condition { min-width: 0; }
    .experiment-condition b { display: block; font-size: 12.5px; }
    .experiment-condition span { color: var(--muted); font-size: 11px; }
    .experiment-track {
      height: 18px;
      border-radius: 4px;
      background:
        linear-gradient(to right, transparent 0 49.8%, #d9ded8 49.8% 50.2%, transparent 50.2%),
        #edf0ec;
      overflow: hidden;
      position: relative;
    }
    .experiment-bar {
      height: 100%;
      min-width: 2px;
      border-radius: 4px;
      background: var(--accent);
    }
    .experiment-value { text-align: right; font-size: 13px; font-weight: 750; font-variant-numeric: tabular-nums; }
    .experiment-delta { text-align: right; font-size: 11.5px; font-variant-numeric: tabular-nums; }
    .experiment-delta.up { color: var(--good); }
    .experiment-delta.down { color: var(--bad); }
    .experiment-delta.base { color: var(--muted); }
    .experiment-method {
      margin-top: 10px;
      color: var(--muted);
      font-size: 11.5px;
    }
    .experiment-table-wrap { overflow-x: auto; }
    .experiment-table-wrap .best-row { background: #f4f9f7; }
    .sig-chip {
      display: inline-block;
      margin-left: 4px;
      padding: 0 5px;
      border-radius: 999px;
      background: var(--good-weak);
      color: var(--good);
      font-size: 10px;
      font-weight: 750;
    }

    @media (max-width: 1100px) {
      .workspace { grid-template-columns: 1fr; height: auto !important; }
      .list-panel, .detail-panel { display: block; overflow: visible; }
      .record-list { max-height: 420px; }
      .summary-strip { grid-template-columns: 1fr 1fr; }
      .experiment-cards { grid-template-columns: 1fr 1fr; }
      .experiment-row { grid-template-columns: minmax(220px, 1fr) minmax(180px, 1.5fr) 72px 82px; }
      .trend-toolbar { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 720px) {
      .page { padding: 12px; }
      .coding-grid, .control-row { grid-template-columns: 1fr; }
      .run-picker select { min-width: 0; }
      .experiment-cards { grid-template-columns: 1fr; }
      .experiment-row { grid-template-columns: 1fr 70px; }
      .experiment-track { grid-column: 1 / -1; grid-row: 2; }
      .experiment-delta { grid-column: 2; grid-row: 1; }
      .trend-toolbar { grid-template-columns: 1fr; }
      .trend-language-filter { grid-column: span 1; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>XLing LLM&ndash;Human Coding Viewer</h1>
        <p class="subhead" id="pageSub">Loading embedded run data&hellip;</p>
      </div>
      <div class="run-picker" id="runPicker">
        <span class="masking-badge" id="maskingBadge"></span>
        <label for="runSelect">Run</label>
        <select id="runSelect"><option>Loading&hellip;</option></select>
      </div>
    </header>

    <nav class="tabs">
      <button class="tab-btn active" id="tabBtnExplorer" type="button">Run explorer</button>
      <button class="tab-btn" id="tabBtnTrends" type="button">Compare runs</button>
      <button class="tab-btn" id="tabBtnCertainty" type="button">Certainty</button>
      <button class="tab-btn" id="tabBtnExperiments" type="button">Prompt experiments</button>
    </nav>

    <div id="tabExplorer">
      <div class="run-chips" id="runChips"></div>
      <section class="scope-bar" id="scopeBar"></section>
      <section class="summary-strip" id="summaryStrip"></section>
      <section class="triage-strip" id="triageStrip"></section>

      <div class="workspace">
        <section class="list-panel">
          <div class="list-controls">
            <div>
              <label for="search">Search</label>
              <input id="search" type="search" placeholder="utterance, context, comment, label&hellip;">
            </div>
            <div class="control-row">
              <div>
                <label for="statusFilter">Agreement status</label>
                <select id="statusFilter"></select>
              </div>
              <div>
                <label for="llmLabelFilter">LLM label</label>
                <select id="llmLabelFilter"></select>
              </div>
            </div>
            <div class="control-row">
              <div id="transcriptCell">
                <label for="transcriptFilter">Transcript</label>
                <select id="transcriptFilter"></select>
              </div>
              <div>
                <label for="flagFilter">Flags</label>
                <select id="flagFilter"></select>
              </div>
            </div>
            <div>
              <label>Sort</label>
              <div class="segmented">
                <button id="sortLine" class="seg-btn active" type="button">Transcript order</button>
                <button id="sortReview" class="seg-btn" type="button">Needs review first</button>
              </div>
            </div>
            <button id="resetFilters" class="reset-btn" type="button">Reset all filters</button>
          </div>
          <div class="list-meta" id="visibleCount"></div>
          <div class="record-list" id="recordList"></div>
        </section>

        <section class="detail-panel" id="detailPanel"></section>
      </div>

      <section class="table-panel">
        <h2>Pairwise reliability</h2>
        <p class="caption" id="irrCaption"></p>
        <div id="irrTable"></div>
      </section>

      <section class="table-panel">
        <h2>Denial vs. not-denial</h2>
        <p class="caption" id="denialCaption"></p>
        <div id="denialTable"></div>
        <h3 class="denial-subhead">LLM denial detection vs. human consensus</h3>
        <p class="caption" id="denialDetectCaption"></p>
        <div id="denialDetection"></div>
      </section>

      <section class="table-panel">
        <h2>Label distribution</h2>
        <p class="caption" id="countsCaption"></p>
        <div id="labelCounts"></div>
      </section>

      <section class="table-panel">
        <h2>Flag usage</h2>
        <p class="caption" id="flagTableCaption"></p>
        <div id="flagTable"></div>
      </section>
    </div>

    <div id="tabTrends" class="hidden">
      <section class="trend-panel">
        <div class="trend-head">
          <h2>Compare runs</h2>
          <p class="subhead">Language, version/example arm, and model selections are cross-cutting. Every run matching their intersection appears in both the chart and exact run-by-run table.</p>
        </div>
        <div class="trend-toolbar">
          <div class="trend-language-filter">
            <label>Languages</label>
            <div class="trend-language-row">
              <div class="trend-language-options" id="trendLanguages"></div>
              <button class="language-action" id="trendLanguagesAll" type="button">Select all</button>
              <button class="language-action" id="trendLanguagesCurrent" type="button">Current only</button>
            </div>
          </div>
          <div class="trend-version-filter">
            <label class="trend-filter-label">Version + examples <span class="trend-selection-count" id="trendVersionsCount"></span></label>
            <div class="trend-language-row">
              <div class="trend-version-options" id="trendVersions"></div>
              <button class="language-action" id="trendVersionsAll" type="button">Select all</button>
              <button class="language-action" id="trendVersionsNone" type="button">Clear</button>
            </div>
          </div>
          <div class="trend-model-filter">
            <label class="trend-filter-label">Models <span class="trend-selection-count" id="trendModelsCount"></span></label>
            <div class="trend-language-row">
              <div class="trend-model-options" id="trendModels"></div>
              <button class="language-action" id="trendModelsAll" type="button">Select all</button>
              <button class="language-action" id="trendModelsNone" type="button">Clear</button>
            </div>
          </div>
          <div>
            <label for="trendBasis">Comparison</label>
            <select id="trendBasis">
              <option value="full">Full Bloom labels</option>
              <option value="denialAll">Denial vs. not-denial (all)</option>
              <option value="denialNeg">Denial vs. not-denial (negation only)</option>
            </select>
          </div>
          <div class="trend-toolbar-actions">
            <span class="trend-count" id="trendCount"></span>
            <button class="trend-reset" id="trendReset" type="button">Reset comparison</button>
          </div>
        </div>
        <div class="trend-display">
          <div class="trend-display-group">
            <label>Measure</label>
            <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
              <button id="trendAgreement" class="seg-btn active" type="button">Agreement %</button>
              <button id="trendKappa" class="seg-btn" type="button">Cohen&rsquo;s &kappa;</button>
            </div>
          </div>
          <div class="trend-display-group">
            <label>Rows</label>
            <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
              <button id="trendScopeAll" class="seg-btn active" type="button">All rows</button>
              <button id="trendScopeClean" class="seg-btn" type="button">Clean only</button>
            </div>
          </div>
          <div class="trend-display-group">
            <label>Lines</label>
            <div class="series-toggles">
              <label class="series-toggle"><input id="seriesCons" type="checkbox" checked><span class="series-dot" style="background:#1f6f68"></span>LLM vs consensus</label>
              <label class="series-toggle"><input id="seriesHh" type="checkbox" checked><span class="series-dot" style="background:#5b6770"></span>Human baseline</label>
              <label class="series-toggle"><input id="seriesL1" type="checkbox"><span class="series-dot" style="background:#2d5f8b"></span>LLM vs coder 1</label>
              <label class="series-toggle"><input id="seriesL2" type="checkbox"><span class="series-dot" style="background:#a45c19"></span>LLM vs coder 2</label>
              <label class="series-toggle"><input id="trendShowValues" type="checkbox">Show values</label>
            </div>
          </div>
        </div>
        <div class="trend-chart-grid" id="trendChart"></div>
        <div class="trend-legend" id="trendLegend"></div>
      </section>

      <section class="table-panel">
        <h2>Run-by-run numbers</h2>
        <p class="caption" id="trendTableCaption"></p>
        <div id="trendTable"></div>
      </section>
    </div>

    <div id="tabExperiments" class="hidden">
      <section class="trend-panel">
        <div class="trend-head">
          <h2>V5 prompt experiments</h2>
          <p class="subhead">A paired, class-enriched English diagnostic for choosing prompts and inference settings. These runs are kept separate from the main comparison because their class mix is intentionally not population-representative.</p>
        </div>
        <div class="experiment-note" id="experimentFindings"></div>
        <div class="experiment-cards" id="experimentCards"></div>
        <div class="trend-toolbar">
          <div>
            <label for="experimentModel">Model</label>
            <select id="experimentModel"></select>
          </div>
          <div>
            <label for="experimentMetric">Measure</label>
            <select id="experimentMetric">
              <option value="collapsed_accuracy_pct">Overall collapsed accuracy</option>
              <option value="rejection_accuracy_pct">Rejection accuracy</option>
              <option value="denial_accuracy_pct">Denial accuracy</option>
              <option value="nonexistence_accuracy_pct">Nonexistence accuracy</option>
              <option value="excluded_accuracy_pct">Excluded accuracy</option>
            </select>
          </div>
          <div class="trend-toolbar-actions">
            <span class="trend-count" id="experimentCount"></span>
          </div>
        </div>
        <div class="experiment-chart" id="experimentChart"></div>
        <p class="experiment-method" id="experimentMethod"></p>
      </section>

      <section class="table-panel">
        <h2>All experimental conditions</h2>
        <p class="caption" id="experimentTableCaption"></p>
        <div class="experiment-table-wrap" id="experimentTable"></div>
      </section>
    </div>

    <div id="tabCertainty" class="hidden">
      <section class="trend-panel">
        <div class="trend-head">
          <h2>Certainty vs. agreement</h2>
          <p class="subhead">Since v4 the model answers a yes/no <b>certain</b>, mirroring the human coders&rsquo; <code>certain_bloom</code> column. Each negation contributes once when both humans supplied the same Bloom label. LLM&ndash;consensus agreement is separated by the LLM&rsquo;s certainty and the two human coders&rsquo; ordered certainty responses.</p>
        </div>
        <div class="trend-toolbar">
          <div>
            <label for="certModel">Model</label>
            <select id="certModel"></select>
          </div>
          <div>
            <label for="certExamples">Prompt examples</label>
            <select id="certExamples">
              <option value="all">All example conditions</option>
              <option value="matched">Match target language</option>
              <option value="english">English examples</option>
            </select>
          </div>
          <div class="trend-toolbar-actions">
            <span class="trend-count" id="certCount"></span>
          </div>
        </div>
        <div class="trend-display">
          <div class="trend-display-group">
            <label>Negator</label>
            <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
              <button id="certMaskVisible" class="seg-btn active" type="button">Visible</button>
              <button id="certMaskMasked" class="seg-btn" type="button">Masked</button>
            </div>
          </div>
          <div class="trend-display-group">
            <label>View</label>
            <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
              <button id="certView2x2" class="seg-btn active" type="button">LLM &times; humans 2&times;4</button>
              <button id="certViewCalib" class="seg-btn" type="button">LLM calibration</button>
            </div>
          </div>
          <div class="trend-display-group">
            <label>Rows</label>
            <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
              <button id="certScopeAll" class="seg-btn active" type="button">All rows</button>
              <button id="certScopeClean" class="seg-btn" type="button">Clean only</button>
            </div>
          </div>
        </div>
        <div class="trend-chart-grid" id="certChart"></div>
        <div class="trend-legend" id="certLegend"></div>
      </section>

      <section class="table-panel">
        <h2>Certainty cell numbers</h2>
        <p class="caption" id="certTableCaption"></p>
        <div id="certTable"></div>
      </section>
    </div>

    <p class="footnote" id="footNote"></p>
  </div>

  <script id="audit-data" type="application/json">', json_data, '</script>
  <script>
    let payload;
    try {
      payload = JSON.parse(document.getElementById("audit-data").textContent);
    } catch (error) {
      document.getElementById("pageSub").textContent =
        "The embedded run data could not be loaded. Rebuild the viewer with scripts/build_coding_viewer.R.";
      document.getElementById("runSelect").innerHTML = "<option>Load failed</option>";
      throw error;
    }
    const contexts = payload.contexts || [];
    const promptExperiments = payload.prompt_experiments || { available: false, rows: [], manifest: {} };
    const labelLevels = ["nonexistence", "rejection", "denial", "uncoded", "excluded", "other"];
    const contentLevels = ["nonexistence", "rejection", "denial"];
    const flagNames = ["foreign_language_negation", "singing", "mimicry", "tag_question", "repetition", "not_a_negation"];

    const $ = (id) => document.getElementById(id);
    const clean = (v) => v == null ? "" : String(v);
    const isTrue = (v) => clean(v).toLowerCase() === "true";
    const pct = (x) => Number.isFinite(x) ? (x * 100).toFixed(1) + "%" : "&ndash;";
    const num = (x) => Number.isFinite(x) ? x.toFixed(2) : "&ndash;";

    function esc(value) {
      return clean(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll(String.fromCharCode(34), "&quot;")
        .replaceAll(String.fromCharCode(39), "&#039;");
    }

    // Whether the prompt examples match the run target language, derived from
    // the prompt_version suffix convention so it generalizes across languages:
    //   <base> + "-<lang>-loc"   -> examples localized to the target language
    //   <base> + "-<lang>-engex" -> examples kept in English (cross-language)
    //   <base> with no such suffix (e.g. p003) -> native English prompt
    // "matched" = examples are in the target language (native English or -loc).
    function exampleCondition(meta) {
      const pv = meta.prompt_version || "";
      if (/-engex$/.test(pv)) return { key: "english", matched: false, short: "Eng ex.", label: "English examples" };
      if (/-loc$/.test(pv))   return { key: "localized", matched: true, short: "Localized", label: "Localized examples" };
      return { key: "native", matched: true, short: "Native", label: "Native (English) examples" };
    }

    // For cross-language comparison, the native English prompt and a
    // non-English "-engex" prompt belong to the same English-example arm.
    // Localized prompts remain a separate arm.
    function versionExampleGroup(meta) {
      return exampleCondition(meta).key === "localized"
        ? { key: "localized", label: "Localized examples" }
        : { key: "english", label: "English examples" };
    }
    const versionExampleKey = (meta) => `${meta.version || "?"}::${versionExampleGroup(meta).key}`;

    function maskingCondition(meta) {
      const masked = meta.masking === "masked" || /^p[0-9]+m(?:-|$)/.test(meta.prompt_version || "");
      return masked
        ? { key: "masked", short: "MASKED", label: "Masked negator", color: "#6d3f8f", weak: "#f1e9f6" }
        : { key: "unmasked", short: "VISIBLE", label: "Negator visible (unmasked)", color: "#14736b", weak: "#e3f0ed" };
    }

    function maskingBadge(meta, compact = false) {
      const condition = maskingCondition(meta);
      return `<span class="masking-badge ${condition.key}${compact ? " compact" : ""}">${esc(compact ? condition.short : condition.label)}</span>`;
    }

    function runLabel(run) {
      const m = run.meta;
      const cond = exampleCondition(m);
      const bits = ["[" + maskingCondition(m).short + "]", m.language || "?", m.version];
      if (m.model) bits.push(m.model);
      bits.push(m.split, cond.label);
      if (m.prompt_version) bits.push(m.prompt_version);
      bits.push("n=" + m.n_rows);
      if (m.run_date) bits.push(m.run_date);
      return bits.join(" \\u00b7 ");
    }

    // Make the master/detail workspace fill the viewport below the header so
    // the two panels stay balanced and scroll internally, rather than letting
    // the record list grow into a tall wall. Sized in JS because the header
    // height varies with the run chips / scope note / summary cards.
    function sizeWorkspace() {
      const ws = document.querySelector(".workspace");
      if (!ws || document.getElementById("tabExplorer").classList.contains("hidden")) return;
      if (window.innerWidth <= 1100) { ws.style.height = ""; return; }
      const top = ws.getBoundingClientRect().top + window.scrollY;
      ws.style.height = Math.max(480, Math.round(window.innerHeight - top - 16)) + "px";
    }

    // ---- per-run state (recomputed by loadRun) ----
    let rows = [];
    let meta = {};
    let thinking = [];
    let coderName = {};
    let coderShort = {};
    let pairDefs = [];
    const state = {
      runIdx: 0, selectedId: null, sort: "line", scope: "all",
      trendMetric: "agreement", trendScope: "all", trendBasis: "full",
      trendLanguages: null, trendVersionExamples: null, trendModels: null,
      trendSeries: { hh: true, cons: true, l1: false, l2: false },
      trendShowValues: false,
      certModel: "all", certExamples: "all", certScope: "all", certView: "2x2", certMasking: "unmasked",
      experimentModel: "all", experimentMetric: "collapsed_accuracy_pct"
    };

    // Inspected rows are development data (read, mined for prompt examples,
    // or adjudicated) and are excluded from headline metrics; see
    // splits/english/inspected_rows.txt. The clean subset is everything else.
    const isInspected = (r) => isTrue(r.inspected);
    const inspectedDesc = "Development row: its content was read, mined for prompt examples, or adjudicated, so it is excluded from headline metrics and reported as a rule-compliance check.";
    function scopedRows() {
      if (state.scope === "clean") return rows.filter(r => !isInspected(r));
      if (state.scope === "inspected") return rows.filter(isInspected);
      return rows;
    }
    function scopeDesc() {
      const base = scopedRows();
      if (state.scope === "clean") return `the ${base.length} clean (headline) rows`;
      if (state.scope === "inspected") return `the ${base.length} inspected (compliance-check) rows`;
      return `all ${base.length} rows`;
    }

    const statusDefs = [
      { key: "llm-diff",   text: "LLM differs",        desc: "Humans agree on a label, the LLM coded something else", cls: "bad",     rank: 0 },
      { key: "none-agree", text: "Nobody agrees",      desc: "Humans split and the LLM matches neither",              cls: "bad",     rank: 1 },
      { key: "split",      text: "Humans split",       desc: "Humans disagree; the LLM sides with one of them",       cls: "warn",    rank: 2 },
      { key: "solo-diff",  text: "1 coder, differs",   desc: "Only one human label; the LLM coded something else",    cls: "warn",    rank: 3 },
      { key: "solo-match", text: "1 coder, match",     desc: "Only one human label; the LLM matches it",              cls: "good",    rank: 4 },
      { key: "all-agree",  text: "All agree",          desc: "Both humans and the LLM coded the same label",          cls: "good",    rank: 5 },
      { key: "nohuman",    text: "No human label",     desc: "Neither human recorded a Bloom label",                  cls: "missing", rank: 6 }
    ];
    const statusMap = Object.fromEntries(statusDefs.map(s => [s.key, s]));

    function statusFor(row) {
      const h1 = clean(row.human_1_label_collapsed);
      const h2 = clean(row.human_2_label_collapsed);
      const llm = clean(row.llm_label_collapsed);
      const hs = [h1, h2].filter(Boolean);
      let key;
      if (!hs.length) key = "nohuman";
      else if (hs.length === 1) key = llm === hs[0] ? "solo-match" : "solo-diff";
      else if (h1 === h2) key = llm === h1 ? "all-agree" : "llm-diff";
      else key = (llm === h1 || llm === h2) ? "split" : "none-agree";
      return statusMap[key];
    }

    function labChip(rawLabel, collapsed, mini) {
      const cls = collapsed ? "lab-" + collapsed : "lab-missing";
      const text = rawLabel || collapsed || "missing";
      return `<span class="lab ${mini ? "mini" : ""} ${cls}">${esc(text)}</span>`;
    }

    function coderCoded(row, who) {
      if (who === "llm") return true;
      return !!(clean(row[who + "_bloom"]) || clean(row[who + "_comments"]));
    }

    // For each flag that at least one coder raised, collect the value from
    // every coder (null = that human never coded the row, so their stored No
    // is missing data rather than a judgment). mismatch = some coder said Yes
    // and another said No; solo = only one coder coded, nothing to compare.
    function flagInfo(row) {
      return flagNames.map(f => {
        const vals = {};
        ["llm", "human_1", "human_2"].forEach(w => {
          vals[w] = coderCoded(row, w) ? (isTrue(row[w + "_" + f]) ? "Yes" : "No") : null;
        });
        const known = Object.values(vals).filter(v => v !== null);
        return {
          flag: f,
          vals,
          anyYes: known.includes("Yes"),
          mismatch: known.includes("Yes") && known.includes("No"),
          solo: known.length < 2
        };
      }).filter(x => x.anyYes);
    }

    function flagMismatchRows(rowSet) {
      return rowSet.filter(r => flagInfo(r).some(f => f.mismatch));
    }

    function flagTooltip(info) {
      return ["llm", "human_1", "human_2"]
        .map(w => `${coderShort[w]}: ${info.vals[w] === null ? "not coded" : info.vals[w]}`)
        .join(" / ");
    }

    // Agreement and kappa: identical logic and denominators to the IRR reports.
    function kappa(pairs, levels) {
      const n = pairs.length;
      if (!n) return NaN;
      const rowSums = {}, colSums = {};
      let diag = 0;
      for (const [a, b] of pairs) {
        rowSums[a] = (rowSums[a] || 0) + 1;
        colSums[b] = (colSums[b] || 0) + 1;
        if (a === b) diag++;
      }
      const po = diag / n;
      const pe = levels.reduce((s, l) => s + (rowSums[l] || 0) * (colSums[l] || 0), 0) / (n * n);
      return pe === 1 ? NaN : (po - pe) / (1 - pe);
    }

    function pairStatsRows(rowSet, aKey, bKey, contentOnly) {
      let pairs = rowSet
        .map(r => [clean(r[aKey]), clean(r[bKey])])
        .filter(([a, b]) => a && b);
      if (contentOnly) pairs = pairs.filter(([a, b]) => contentLevels.includes(a) && contentLevels.includes(b));
      return {
        n: pairs.length,
        agreement: pairs.length ? pairs.filter(([a, b]) => a === b).length / pairs.length : NaN,
        kappa: kappa(pairs, contentOnly ? contentLevels : labelLevels)
      };
    }

    function consensusStats(rowSet) {
      const agreed = rowSet.filter(r => {
        const a = clean(r.human_1_label_collapsed);
        return a && a === clean(r.human_2_label_collapsed);
      });
      const pairs = agreed
        .map(r => [clean(r.llm_label_collapsed), clean(r.human_1_label_collapsed)])
        .filter(([a, b]) => a && b);
      return {
        n: pairs.length,
        agreement: pairs.length ? pairs.filter(([a, b]) => a === b).length / pairs.length : NaN,
        kappa: kappa(pairs, labelLevels)
      };
    }

    // ---- Denial vs. not-denial (binary) ----
    // Collapse every label to a two-way distinction: denial vs. everything
    // else (nonexistence, rejection, uncoded, excluded). The "negation codes
    // only" scope additionally drops uncoded/excluded rows so the contrast is
    // among true negation meanings (denial vs. nonexistence/rejection), the
    // same restriction the content-only IRR columns use.
    const denialLevels = ["denial", "not-denial"];
    const isContentLabel = (v) => contentLevels.includes(clean(v));
    const denialBin = (v) => { const c = clean(v); return c ? (c === "denial" ? "denial" : "not-denial") : ""; };

    function binPairStats(rowSet, aKey, bKey, negOnly) {
      let pairs = rowSet
        .filter(r => !negOnly || (isContentLabel(r[aKey]) && isContentLabel(r[bKey])))
        .map(r => [denialBin(r[aKey]), denialBin(r[bKey])])
        .filter(([a, b]) => a && b);
      return {
        n: pairs.length,
        agreement: pairs.length ? pairs.filter(([a, b]) => a === b).length / pairs.length : NaN,
        kappa: kappa(pairs, denialLevels),
        base: pairs.length ? pairs.filter(([, b]) => b === "denial").length / pairs.length : NaN
      };
    }

    // Binary analogue of consensusStats: among rows where the two humans agree
    // on the denial-vs-not distinction, how often the LLM binary label matches.
    // negOnly drops rows whose human or LLM label is not a negation code.
    function binConsensusStats(rowSet, negOnly) {
      const agreed = rowSet.filter(r => {
        if (negOnly && !(isContentLabel(r.human_1_label_collapsed) &&
                         isContentLabel(r.human_2_label_collapsed) &&
                         isContentLabel(r.llm_label_collapsed))) return false;
        const a = denialBin(r.human_1_label_collapsed);
        return a && a === denialBin(r.human_2_label_collapsed);
      });
      const pairs = agreed
        .map(r => [denialBin(r.llm_label_collapsed), denialBin(r.human_1_label_collapsed)])
        .filter(([a, b]) => a && b);
      return {
        n: pairs.length,
        agreement: pairs.length ? pairs.filter(([a, b]) => a === b).length / pairs.length : NaN,
        kappa: kappa(pairs, denialLevels)
      };
    }

    // Treat the human binary consensus (both humans agree on denial vs. not)
    // as ground truth and score the LLM as a detector of denial (positive
    // class). Rows without consensus, or where the LLM has no label, are
    // dropped; negOnly also drops any row whose human or LLM label is not a
    // negation code.
    function denialDetection(rowSet, negOnly) {
      let tp = 0, fp = 0, fn = 0, tn = 0;
      rowSet.forEach(r => {
        if (negOnly && !(isContentLabel(r.human_1_label_collapsed) &&
                         isContentLabel(r.human_2_label_collapsed) &&
                         isContentLabel(r.llm_label_collapsed))) return;
        const h1 = denialBin(r.human_1_label_collapsed);
        const h2 = denialBin(r.human_2_label_collapsed);
        const llm = denialBin(r.llm_label_collapsed);
        if (!h1 || !h2 || !llm || h1 !== h2) return;
        const truthDenial = h1 === "denial";
        const predDenial = llm === "denial";
        if (truthDenial && predDenial) tp++;
        else if (!truthDenial && predDenial) fp++;
        else if (truthDenial && !predDenial) fn++;
        else tn++;
      });
      const n = tp + fp + fn + tn;
      const safe = (num, den) => den ? num / den : NaN;
      const sens = safe(tp, tp + fn);
      const spec = safe(tn, tn + fp);
      const prec = safe(tp, tp + fp);
      const f1 = Number.isFinite(prec) && Number.isFinite(sens) && (prec + sens) > 0
        ? 2 * prec * sens / (prec + sens) : NaN;
      return { n, tp, fp, fn, tn, acc: safe(tp + tn, n), sens, spec, prec, f1, nDenial: tp + fn };
    }

    function loadRun(idx) {
      state.runIdx = idx;
      const run = payload.runs[idx];
      rows = run.rows;
      meta = run.meta;
      thinking = run.thinking || [];

      coderName = { llm: "LLM" };
      coderShort = { llm: "LLM" };
      ["human_1", "human_2"].forEach((who, i) => {
        const sheets = [...new Set(rows.map(r => clean(r[who + "_sheet"])).filter(Boolean))];
        coderName[who] = sheets.length === 1 ? "Coder " + sheets[0] : "Human coder " + (i + 1);
        coderShort[who] = sheets.length === 1 ? sheets[0] : "H" + (i + 1);
      });
      pairDefs = [
        { name: `${coderName.human_1} vs ${coderName.human_2}`, a: "human_1_label_collapsed", b: "human_2_label_collapsed", baseline: true },
        { name: `LLM vs ${coderName.human_1}`, a: "llm_label_collapsed", b: "human_1_label_collapsed", baseline: false },
        { name: `LLM vs ${coderName.human_2}`, a: "llm_label_collapsed", b: "human_2_label_collapsed", baseline: false }
      ];

      state.selectedId = rows[0] && rows[0].record_id;
      state.sort = "line";
      if (!scopedRows().length) state.scope = "all";
      $("sortLine").classList.add("active");
      $("sortReview").classList.remove("active");
      $("search").value = "";

      renderHeader();
      renderScopeBar();
      populateFilters();
      renderSummary();
      renderTriage();
      renderIrr();
      renderDenial();
      renderFootnote();
      renderList();
      sizeWorkspace();
    }

    function renderScopeBar() {
      const nIns = rows.filter(isInspected).length;
      const nClean = rows.length - nIns;
      const defs = [
        { key: "all", text: `All rows (${rows.length})`, n: rows.length },
        { key: "clean", text: `Clean &mdash; headline (${nClean})`, n: nClean },
        { key: "inspected", text: `Inspected &mdash; compliance (${nIns})`, n: nIns }
      ];
      const note = nIns === rows.length
        ? "Every row of this run is on the inspected list: it provides rule-compliance evidence only, no headline (generalization) evidence."
        : nIns === 0
          ? "No row of this run is on the inspected list."
          : "Inspected rows are development data (read, mined for prompt examples, or adjudicated) and are excluded from headline metrics.";
      $("scopeBar").innerHTML = `<span class="triage-label">Stats subset:</span>` +
        defs.map(d => `<button class="seg-btn ${state.scope === d.key ? "active" : ""}" type="button"
            data-scope="${d.key}" ${d.n ? "" : "disabled"}>${d.text}</button>`).join("") +
        `<span class="scope-note">${note}</span>`;
      document.querySelectorAll("#scopeBar .seg-btn").forEach(btn => {
        btn.addEventListener("click", () => setScope(btn.dataset.scope));
      });
    }

    function setScope(scope) {
      state.scope = scope;
      renderScopeBar();
      populateFilters();
      renderSummary();
      renderTriage();
      renderIrr();
      renderDenial();
      renderList();
      sizeWorkspace();
    }

    function renderHeader() {
      $("pageSub").textContent =
        `Bloom coding pilot: each run codes child negation tokens with the LLM as a third independent coder. ` +
        `${payload.runs.length} scored run${payload.runs.length === 1 ? "" : "s"} embedded; generated ${payload.generated_on}.`;
      const masking = maskingCondition(meta);
      $("maskingBadge").className = `masking-badge ${masking.key}`;
      $("maskingBadge").textContent = masking.label;
      $("runChips").innerHTML = [
        ["negator", masking.label],
        ["version", meta.version],
        ["model", meta.model || "unknown"],
        ["split", meta.split + " (n=" + meta.n_rows + ")"],
        ["prompt", (meta.prompt_version || "?") + " / " + (meta.schema_version || "?")],
        ["run", meta.run_date || "date unknown"],
        ["language", meta.language],
        ["examples", exampleCondition(meta).label]
      ].map(([k, v]) => `<span class="run-chip">${esc(k)} <b>${esc(v)}</b></span>`).join("");
    }

    function renderSummary() {
      const base = scopedRows();
      const hh = pairStatsRows(base, pairDefs[0].a, pairDefs[0].b, false);
      const l1 = pairStatsRows(base, pairDefs[1].a, pairDefs[1].b, false);
      const l2 = pairStatsRows(base, pairDefs[2].a, pairDefs[2].b, false);
      const cons = consensusStats(base);
      const cards = [
        { name: pairDefs[0].name, stat: hh, sub: `&kappa; ${num(hh.kappa)} &middot; n=${hh.n}`, baseline: true },
        { name: pairDefs[1].name, stat: l1, sub: `&kappa; ${num(l1.kappa)} &middot; n=${l1.n}`, baseline: false },
        { name: pairDefs[2].name, stat: l2, sub: `&kappa; ${num(l2.kappa)} &middot; n=${l2.n}`, baseline: false },
        { name: "LLM vs human consensus", stat: cons, sub: `on the ${cons.n} rows where humans agree`, baseline: false }
      ];
      $("summaryStrip").innerHTML = cards.map(c => `
        <div class="summary-card ${c.baseline ? "baseline" : ""}">
          ${c.baseline ? `<span class="baseline-tag">baseline</span>` : ""}
          <div class="big">${pct(c.stat.agreement)}</div>
          <div class="name">${esc(c.name)}</div>
          <div class="sub">${c.sub}</div>
        </div>`).join("");
    }

    function statusCounts() {
      const counts = {};
      scopedRows().forEach(r => { const k = statusFor(r).key; counts[k] = (counts[k] || 0) + 1; });
      return counts;
    }

    function renderTriage() {
      const counts = statusCounts();
      const active = $("statusFilter").value;
      const nFlagMismatch = flagMismatchRows(scopedRows()).length;
      const flagActive = $("flagFilter").value === "mismatch";
      $("triageStrip").innerHTML = `<span class="triage-label">Jump to:</span>` + statusDefs
        .filter(s => counts[s.key])
        .map(s => `<button class="triage-chip ${s.cls} ${active === s.key ? "active" : ""}" type="button"
            data-status="${s.key}" title="${esc(s.desc)}"><strong>${counts[s.key]}</strong> ${esc(s.text)}</button>`)
        .join("") +
        (nFlagMismatch ? `<button class="triage-chip bad ${flagActive ? "active" : ""}" type="button" id="flagTriageChip"
            title="Rows where one coder raised a flag and another said No"><strong>${nFlagMismatch}</strong> &#9873; Flag mismatches</button>` : "");
      document.querySelectorAll(".triage-chip[data-status]").forEach(btn => {
        btn.addEventListener("click", () => {
          $("statusFilter").value = $("statusFilter").value === btn.dataset.status ? "all" : btn.dataset.status;
          renderList();
          renderTriage();
        });
      });
      const flagChip = $("flagTriageChip");
      if (flagChip) flagChip.addEventListener("click", () => {
        $("flagFilter").value = $("flagFilter").value === "mismatch" ? "all" : "mismatch";
        renderList();
        renderTriage();
      });
    }

    function populateFilters() {
      // Counts reflect the active stats subset; current selections are kept
      // when they still exist after a scope change.
      const keep = Object.fromEntries(
        ["statusFilter", "llmLabelFilter", "transcriptFilter", "flagFilter"].map(id => [id, $(id).value])
      );
      const base = scopedRows();
      const counts = statusCounts();
      $("statusFilter").innerHTML = `<option value="all">All rows (${base.length})</option>` + statusDefs
        .filter(s => counts[s.key])
        .map(s => `<option value="${s.key}">${esc(s.text)} (${counts[s.key]})</option>`).join("");

      const labels = [...new Set(base.map(r => clean(r.llm_label_collapsed)).filter(Boolean))].sort();
      $("llmLabelFilter").innerHTML = `<option value="all">All labels</option>` +
        labels.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join("");

      const transcripts = [...new Set(base.map(r => clean(r.transcript_id)).filter(Boolean))].sort();
      $("transcriptFilter").innerHTML = `<option value="all">All transcripts (${transcripts.length})</option>` +
        transcripts.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
      $("transcriptCell").style.display = transcripts.length < 2 ? "none" : "";

      const nRaised = base.filter(r => flagInfo(r).length).length;
      const nMismatch = flagMismatchRows(base).length;
      $("flagFilter").innerHTML = `<option value="all">All rows</option>
        <option value="raised">Any flag raised (${nRaised})</option>
        <option value="mismatch">Flag mismatches (${nMismatch})</option>`;

      Object.entries(keep).forEach(([id, val]) => {
        if (val && [...$(id).options].some(o => o.value === val)) $(id).value = val;
      });
    }

    function bindControls() {
      const runGroups = {};
      payload.runs.forEach((run, i) => {
        const lang = run.meta.language || "Unknown";
        (runGroups[lang] = runGroups[lang] || []).push(
          `<option value="${i}">${esc(runLabel(run))}</option>`);
      });
      $("runSelect").innerHTML = Object.entries(runGroups)
        .map(([lang, opts]) => `<optgroup label="${esc(lang)}">${opts.join("")}</optgroup>`).join("");
      $("runSelect").addEventListener("change", () => loadRun(Number($("runSelect").value)));

      $("tabBtnExplorer").addEventListener("click", () => setTab("explorer"));
      $("tabBtnTrends").addEventListener("click", () => setTab("trends"));
      $("tabBtnExperiments").addEventListener("click", () => setTab("experiments"));

      $("sortLine").addEventListener("click", () => setSort("line"));
      $("sortReview").addEventListener("click", () => setSort("review"));
      ["search", "statusFilter", "llmLabelFilter", "transcriptFilter", "flagFilter"].forEach(id => {
        $(id).addEventListener("input", () => { renderList(); renderTriage(); });
        $(id).addEventListener("change", () => { renderList(); renderTriage(); });
      });
      $("resetFilters").addEventListener("click", () => {
        $("search").value = "";
        $("statusFilter").value = "all";
        $("llmLabelFilter").value = "all";
        $("transcriptFilter").value = "all";
        $("flagFilter").value = "all";
        setSort("line");
        renderTriage();
      });

      $("trendAgreement").addEventListener("click", () => setTrendMetric("agreement"));
      $("trendKappa").addEventListener("click", () => setTrendMetric("kappa"));
      $("trendScopeAll").addEventListener("click", () => setTrendScope("all"));
      $("trendScopeClean").addEventListener("click", () => setTrendScope("clean"));
      $("trendLanguagesAll").addEventListener("click", () => {
        state.trendLanguages = [...new Set(payload.runs.map(r => r.meta.language || "Unknown"))];
        populateTrendControls();
        renderTrends();
      });
      $("trendLanguagesCurrent").addEventListener("click", () => {
        state.trendLanguages = [meta.language || "Unknown"];
        populateTrendControls();
        renderTrends();
      });
      $("trendModelsAll").addEventListener("click", () => {
        state.trendModels = [...new Set(payload.runs.map(r => r.meta.model || "Unknown"))];
        populateTrendControls();
        renderTrends();
      });
      $("trendModelsNone").addEventListener("click", () => {
        state.trendModels = [];
        populateTrendControls();
        renderTrends();
      });
      $("trendVersionsAll").addEventListener("click", () => {
        state.trendVersionExamples = [...new Set(payload.runs.map(r => versionExampleKey(r.meta)))];
        populateTrendControls();
        renderTrends();
      });
      $("trendVersionsNone").addEventListener("click", () => {
        state.trendVersionExamples = [];
        populateTrendControls();
        renderTrends();
      });
      $("trendBasis").addEventListener("change", () => setTrendBasis($("trendBasis").value));
      [["seriesHh", "hh"], ["seriesCons", "cons"], ["seriesL1", "l1"], ["seriesL2", "l2"]].forEach(([id, key]) => {
        $(id).addEventListener("change", () => {
          state.trendSeries[key] = $(id).checked;
          renderTrends();
        });
      });
      $("trendShowValues").addEventListener("change", () => {
        state.trendShowValues = $("trendShowValues").checked;
        renderTrends();
      });
      $("trendReset").addEventListener("click", resetTrendControls);

      $("tabBtnCertainty").addEventListener("click", () => setTab("certainty"));
      $("certModel").addEventListener("change", () => { state.certModel = $("certModel").value; renderCertainty(); });
      $("certExamples").addEventListener("change", () => { state.certExamples = $("certExamples").value; renderCertainty(); });
      $("certView2x2").addEventListener("click", () => setCertView("2x2"));
      $("certViewCalib").addEventListener("click", () => setCertView("calib"));
      $("certScopeAll").addEventListener("click", () => setCertScope("all"));
      $("certScopeClean").addEventListener("click", () => setCertScope("clean"));
      $("certMaskVisible").addEventListener("click", () => setCertMasking("unmasked"));
      $("certMaskMasked").addEventListener("click", () => setCertMasking("masked"));

      $("experimentModel").addEventListener("change", () => {
        state.experimentModel = $("experimentModel").value;
        renderExperiments();
      });
      $("experimentMetric").addEventListener("change", () => {
        state.experimentMetric = $("experimentMetric").value;
        renderExperiments();
      });

      window.addEventListener("resize", sizeWorkspace);
      window.addEventListener("resize", () => { if (!$("tabTrends").classList.contains("hidden")) renderTrends(); });
      window.addEventListener("resize", () => { if (!$("tabCertainty").classList.contains("hidden")) renderCertainty(); });
    }

    function setTab(tab) {
      $("tabExplorer").classList.toggle("hidden", tab !== "explorer");
      $("tabTrends").classList.toggle("hidden", tab !== "trends");
      $("tabCertainty").classList.toggle("hidden", tab !== "certainty");
      $("tabExperiments").classList.toggle("hidden", tab !== "experiments");
      $("runPicker").classList.toggle("hidden", tab !== "explorer");
      $("tabBtnExplorer").classList.toggle("active", tab === "explorer");
      $("tabBtnTrends").classList.toggle("active", tab === "trends");
      $("tabBtnCertainty").classList.toggle("active", tab === "certainty");
      $("tabBtnExperiments").classList.toggle("active", tab === "experiments");
      if (tab === "trends") {
        if (state.trendLanguages === null) state.trendLanguages = [meta.language || "Unknown"];
        populateTrendControls();
        renderTrends();
      }
      else if (tab === "certainty") {
        populateCertControls();
        renderCertainty();
      }
      else if (tab === "experiments") {
        populateExperimentControls();
        renderExperiments();
      }
      else sizeWorkspace();
    }

    function setTrendMetric(metric) {
      state.trendMetric = metric;
      $("trendAgreement").classList.toggle("active", metric === "agreement");
      $("trendKappa").classList.toggle("active", metric === "kappa");
      renderTrends();
    }

    function setSort(sort) {
      state.sort = sort;
      $("sortLine").classList.toggle("active", sort === "line");
      $("sortReview").classList.toggle("active", sort === "review");
      renderList();
    }

    function filteredRows() {
      const q = clean($("search").value).toLowerCase();
      const status = $("statusFilter").value;
      const llmLabel = $("llmLabelFilter").value;
      const transcript = $("transcriptFilter").value;
      const flagMode = $("flagFilter").value;
      let out = scopedRows().filter(row => {
        if (status !== "all" && statusFor(row).key !== status) return false;
        if (llmLabel !== "all" && clean(row.llm_label_collapsed) !== llmLabel) return false;
        if (transcript !== "all" && clean(row.transcript_id) !== transcript) return false;
        if (flagMode === "raised" && !flagInfo(row).length) return false;
        if (flagMode === "mismatch" && !flagInfo(row).some(f => f.mismatch)) return false;
        if (q) {
          const rowContext = contexts[Number(row.context_id)] || {};
          const contextText = [
            ...(rowContext.before || []),
            ...(rowContext.after || [])
          ].map(line => [line.line, line.speaker, line.utterance].map(clean).join(" ")).join(" ");
          const haystack = [
            row.record_id, row.transcript_id, row.target_utterance, row.target_negator,
            rowContext.fallback_before, rowContext.fallback_after, contextText,
            row.llm_bloom, row.human_1_bloom, row.human_2_bloom,
            row.llm_comments, row.human_1_comments, row.human_2_comments
          ].map(clean).join(" ").toLowerCase();
          if (!haystack.includes(q)) return false;
        }
        return true;
      });
      const byLine = (a, b) => clean(a.transcript_id).localeCompare(clean(b.transcript_id)) || Number(a.line) - Number(b.line);
      out.sort(state.sort === "review" ? (a, b) => statusFor(a).rank - statusFor(b).rank || byLine(a, b) : byLine);
      return out;
    }

    function renderList() {
      const visible = filteredRows();
      if (!visible.some(r => r.record_id === state.selectedId)) {
        state.selectedId = visible[0] ? visible[0].record_id : null;
      }
      const base = scopedRows();
      const scopeWord = state.scope === "all" ? "" : state.scope === "clean" ? " clean" : " inspected";
      $("visibleCount").textContent = visible.length === base.length
        ? `All ${base.length}${scopeWord} coded tokens`
        : `${visible.length} of ${base.length}${scopeWord} coded tokens match`;
      $("recordList").innerHTML = visible.map(row => {
        const s = statusFor(row);
        const sel = row.record_id === state.selectedId ? " selected" : "";
        const chips = ["llm", "human_1", "human_2"].map(who =>
          `<span class="who">${esc(coderShort[who])}</span>` +
          labChip(null, clean(row[who + "_label_collapsed"]), true)
        ).join("");
        const flagChips = flagInfo(row).map(f =>
          `<span class="flagmini ${f.mismatch ? "bad" : (f.solo ? "solo" : "ok")}" title="${esc(flagTooltip(f))}">&#9873; ${esc(f.flag.replaceAll("_", " "))}</span>`
        ).join("");
        const inspChip = isInspected(row)
          ? `<span class="insp-chip" title="${esc(inspectedDesc)}">inspected</span>` : "";
        return `<button class="record-row${sel}" type="button" data-id="${esc(row.record_id)}">
          <span class="row-head">
            <span class="row-loc">L${esc(row.line)}</span>
            <span class="row-utt">${esc(row.target_utterance)}</span>
            <span class="status ${s.cls}">${esc(s.text)}</span>
          </span>
          <span class="row-chips">${chips}${flagChips}${inspChip}</span>
        </button>`;
      }).join("") || `<p class="muted" style="padding:12px">No rows match the current filters.</p>`;
      document.querySelectorAll(".record-row").forEach(btn => {
        btn.addEventListener("click", () => selectRecord(btn.dataset.id));
      });
      renderDetail(visible);
      renderCounts(visible);
      renderFlagTable(visible);
    }

    function selectRecord(id) {
      state.selectedId = id;
      renderList();
      const el = document.querySelector(`.record-row[data-id="${CSS.escape(id)}"]`);
      if (el) el.scrollIntoView({ block: "nearest" });
    }

    function moveSelection(delta) {
      const visible = filteredRows();
      if (!visible.length) return;
      const idx = visible.findIndex(r => r.record_id === state.selectedId);
      const next = Math.min(visible.length - 1, Math.max(0, (idx < 0 ? 0 : idx) + delta));
      selectRecord(visible[next].record_id);
    }

    function speakerCode(s) { return clean(s).replace(/[*:]/g, ""); }

    function markNegator(utterance, negator) {
      const escaped = esc(utterance);
      const neg = esc(negator);
      if (!neg) return escaped;
      const pattern = neg.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");
      return escaped.replace(new RegExp(pattern, "gi"), m => `<mark>${m}</mark>`);
    }

    function transcriptLine(l, cls, negator) {
      const spk = speakerCode(l.speaker);
      const utt = cls === "target" ? markNegator(l.utterance, negator) : esc(l.utterance);
      return `<div class="tline ${cls} spk-${esc(spk)}">
        <span class="lno">${esc(l.line)}</span><span class="spk">${esc(spk)}</span><span class="utt">${utt}</span>
      </div>`;
    }

    function coderCard(row, who, llmCollapsed) {
      const raw = clean(row[who + "_bloom"]);
      const collapsed = clean(row[who + "_label_collapsed"]);
      const comments = clean(row[who + "_comments"]);
      const title = who === "llm" ? `LLM ${meta.model ? "&middot; " + esc(meta.model) : ""}` : esc(coderName[who]);

      if (!raw && !comments) {
        return `<div class="coder-card"><div class="coder-name">${title}</div>
          <p class="not-coded">No Bloom label recorded for this row.</p></div>`;
      }

      const collapseNote = raw && collapsed && raw.toLowerCase() !== collapsed
        ? `<span class="collapse-note">counted as ${esc(collapsed)} for agreement</span>` : "";

      const certBits = [];
      if (who === "llm") {
        const cert = clean(row.llm_certain);
        if (cert) certBits.push(`Certain: <b>${esc(cert)}</b>`);
      } else {
        const cert = clean(row[who + "_certain"]);
        const alt = clean(row[who + "_other_possibility"]);
        const oneOfTwo = clean(row[who + "_one_of_two"]);
        if (cert) certBits.push(`Certain: <b>${esc(cert)}</b>`);
        if (alt) certBits.push(`Also considered: <b>${esc(alt)}</b>`);
        if (oneOfTwo) certBits.push(`Definitely one of the two: <b>${esc(oneOfTwo)}</b>`);
      }
      const certainty = certBits.length ? `<div class="certainty">${certBits.join(" &middot; ")}</div>` : "";
      const comment = comments ? `<div class="comment">&ldquo;${esc(comments)}&rdquo;</div>` : "";
      const isMatch = who !== "llm" && collapsed && collapsed === llmCollapsed;

      return `<div class="coder-card ${isMatch ? "match" : ""}">
        <div class="coder-name">${title}</div>
        <div>${labChip(raw, collapsed, false)}${collapseNote}</div>
        ${certainty}${comment}
      </div>`;
    }

    function verdictSentence(row) {
      const s = statusFor(row);
      const h1 = clean(row.human_1_label_collapsed);
      const h2 = clean(row.human_2_label_collapsed);
      const llm = clean(row.llm_label_collapsed);
      const n1 = coderName.human_1, n2 = coderName.human_2;
      let text;
      if (s.key === "all-agree") text = `${n1} and ${n2} both coded <b>${esc(h1)}</b>; the LLM agrees.`;
      else if (s.key === "llm-diff") text = `${n1} and ${n2} both coded <b>${esc(h1)}</b>, but the LLM coded <b>${esc(llm)}</b>.`;
      else if (s.key === "split") {
        const side = llm === h1 ? n1 : n2;
        text = `${n1} coded <b>${esc(h1)}</b> and ${n2} coded <b>${esc(h2)}</b>; the LLM (<b>${esc(llm)}</b>) sides with ${side}.`;
      }
      else if (s.key === "none-agree") text = `${n1} coded <b>${esc(h1)}</b> and ${n2} coded <b>${esc(h2)}</b>; the LLM coded <b>${esc(llm)}</b>, matching neither.`;
      else if (s.key === "solo-match" || s.key === "solo-diff") {
        const who = h1 ? n1 : n2;
        const hl = h1 || h2;
        text = s.key === "solo-match"
          ? `Only ${who} recorded a Bloom label (<b>${esc(hl)}</b>); the LLM matches it.`
          : `Only ${who} recorded a Bloom label (<b>${esc(hl)}</b>); the LLM coded <b>${esc(llm)}</b> instead.`;
      }
      else text = `Neither human recorded a Bloom label for this row; the LLM coded <b>${esc(llm)}</b>.`;
      return `<div class="verdict ${s.cls}">${text}</div>`;
    }

    function fallbackContext(text) {
      return clean(text).split(" | ").join(String.fromCharCode(10));
    }

    function fcVal(v) {
      if (v === null) return `<span class="fc-val na">&ndash;</span>`;
      return `<span class="fc-val ${v === "Yes" ? "yes" : "no"}">${v}</span>`;
    }

    // Show every flag at least one coder raised, with all three values side
    // by side. All-No flags are omitted on purpose: they carry no signal.
    function flagComparison(row) {
      const info = flagInfo(row);
      if (!info.length) {
        return `<div class="flag-compare-none">No flags raised by any coder on this row.</div>`;
      }
      const head = `<div class="fc-row head"><span>Flag</span><span>LLM</span><span>${esc(coderShort.human_1)}</span><span>${esc(coderShort.human_2)}</span><span></span></div>`;
      const body = info.map(f => {
        const cls = f.mismatch ? "bad" : (f.solo ? "" : "ok");
        const note = f.mismatch ? "coders disagree" : (f.solo ? "only one coder coded this row" : "all coders agree");
        return `<div class="fc-row ${cls}">
          <span class="fc-name">${esc(f.flag.replaceAll("_", " "))}</span>
          ${fcVal(f.vals.llm)}${fcVal(f.vals.human_1)}${fcVal(f.vals.human_2)}
          <span class="fc-note">${note}</span>
        </div>`;
      }).join("");
      return `<div class="flag-compare">${head}${body}</div>`;
    }

    function renderDetail(visible) {
      const row = rows.find(r => r.record_id === state.selectedId);
      if (!row) {
        $("detailPanel").innerHTML = `<p class="muted">No row selected.</p>`;
        return;
      }
      const s = statusFor(row);
      const idx = visible.findIndex(r => r.record_id === row.record_id);
      const llmCollapsed = clean(row.llm_label_collapsed);

      const months = Number(row.child_age_months);
      const age = clean(row.child_age_raw)
        ? `child age <b>${esc(clean(row.child_age_raw).replace(/[.]$/, ""))}</b>` +
          (Number.isFinite(months) ? ` (${(Math.round(months * 10) / 10)} mo)` : "")
        : "";
      const tokenPos = clean(row.negator_index_in_utterance) && Number(row.negators_in_utterance) > 1
        ? `token <b>${esc(row.negator_index_in_utterance)} of ${esc(row.negators_in_utterance)}</b> in utterance`
        : "";
      const metaBits = [
        `<b>${esc(row.transcript_id)}</b> line <b>${esc(row.line)}</b>`,
        `speaker <b>${esc(speakerCode(row.speaker))}</b>`,
        age,
        `negator <b>${esc(row.target_negator)}</b>`,
        tokenPos
      ].filter(Boolean).join(" &middot; ");

      const rowContext = contexts[Number(row.context_id)] || {};
      const beforeLines = rowContext.before || [];
      const afterLines = rowContext.after || [];
      let convoInner;
      if (beforeLines.length || afterLines.length) {
        const before = beforeLines.map(l => transcriptLine(l, "", null)).join("");
        const after = afterLines.map(l => transcriptLine(l, "", null)).join("");
        const target = transcriptLine(
          { line: row.line, speaker: row.speaker, utterance: row.target_utterance },
          "target", row.target_negator
        );
        convoInner = before + target + after;
      } else {
        convoInner = `<div class="no-context">${esc(fallbackContext(rowContext.fallback_before))}

` + transcriptLine({ line: row.line, speaker: row.speaker, utterance: row.target_utterance }, "target", row.target_negator) +
          `<div class="no-context">${esc(fallbackContext(rowContext.fallback_after))}</div></div>`;
      }

      const thinkingId = clean(row.llm_thinking_id);
      const thinkingEntry = thinkingId === "" ? null : thinking[Number(thinkingId)];
      const thinkingText = clean(thinkingEntry && thinkingEntry.text);
      const sharedN = Number(thinkingEntry && thinkingEntry.shared_n);
      const reasoningTitle = Number.isFinite(sharedN) && sharedN > 1
        ? `Model reasoning (shared across a batch of ${sharedN} records)`
        : "Model reasoning for this token";
      const reasoning = thinkingText
        ? `<details class="reasoning"><summary>${reasoningTitle}</summary><pre>${esc(thinkingText)}</pre></details>`
        : "";

      $("detailPanel").innerHTML = `
        <div class="detail-nav">
          <button class="nav-btn" id="prevBtn" type="button" ${idx <= 0 ? "disabled" : ""}>&larr; Prev</button>
          <button class="nav-btn" id="nextBtn" type="button" ${idx >= visible.length - 1 ? "disabled" : ""}>Next &rarr;</button>
          <span class="nav-pos">${idx + 1} of ${visible.length} in current view</span>
          <span class="kbd-hint"><kbd>&uarr;</kbd><kbd>&darr;</kbd> or <kbd>j</kbd><kbd>k</kbd> to move</span>
        </div>
        <div class="detail-head">
          <div>
            <h2>${esc(row.record_id)}</h2>
            <p class="detail-meta">${metaBits}</p>
          </div>
          <span style="display:flex; gap:6px; align-items:center; flex-wrap:wrap; justify-content:flex-end;">
            ${isInspected(row) ? `<span class="insp-chip" title="${esc(inspectedDesc)}">inspected &mdash; excluded from headline</span>` : ""}
            <span class="status ${s.cls}" title="${esc(s.desc)}">${esc(s.text)}</span>
          </span>
        </div>
        <div class="convo-box">
          <div class="convo-head">
            <h3>Conversation</h3>
            <span class="note">${meta.context_window ? `The same &plusmn;${esc(meta.context_window)} lines of context the model was given. ` : ""}Target line highlighted.</span>
          </div>
          <div class="convo" id="convo">${convoInner}</div>
        </div>
        <div class="coding-grid">
          ${coderCard(row, "llm", llmCollapsed)}
          ${coderCard(row, "human_1", llmCollapsed)}
          ${coderCard(row, "human_2", llmCollapsed)}
        </div>
        ${flagComparison(row)}
        ${verdictSentence(row)}
        ${reasoning}`;

      $("prevBtn").addEventListener("click", () => moveSelection(-1));
      $("nextBtn").addEventListener("click", () => moveSelection(1));

      const convo = $("convo");
      const tgt = convo.querySelector(".tline.target");
      if (tgt) convo.scrollTop = Math.max(0, tgt.offsetTop - convo.clientHeight / 2 + tgt.clientHeight / 2);
    }

    function renderIrr() {
      const base = scopedRows();
      $("irrCaption").innerHTML = `Computed on ${scopeDesc()} of this run with the same conventions as the IRR report: collapsed labels, denominator = rows where both coders have a non-missing Bloom label. Content-only columns restrict both labels to nonexistence / rejection / denial.`;
      $("irrTable").innerHTML = `<table><thead><tr>
          <th>Pair</th><th class="numeric">n</th><th class="numeric">Agreement</th><th class="numeric">&kappa;</th>
          <th class="numeric">Content n</th><th class="numeric">Content agreement</th><th class="numeric">Content &kappa;</th>
        </tr></thead><tbody>${
        pairDefs.map(p => {
          const all = pairStatsRows(base, p.a, p.b, false);
          const content = pairStatsRows(base, p.a, p.b, true);
          return `<tr>
            <td>${esc(p.name)}${p.baseline ? ` <span class="muted">(baseline)</span>` : ""}</td>
            <td class="numeric">${all.n}</td><td class="numeric">${pct(all.agreement)}</td><td class="numeric">${num(all.kappa)}</td>
            <td class="numeric">${content.n}</td><td class="numeric">${pct(content.agreement)}</td><td class="numeric">${num(content.kappa)}</td>
          </tr>`;
        }).join("")
      }</tbody></table>`;
    }

    function renderDenial() {
      const base = scopedRows();
      $("denialCaption").innerHTML =
        `Every label collapsed to a two-way <b>denial</b> vs. <b>not-denial</b> distinction, computed on ${scopeDesc()}. ` +
        `<b>All coded</b> treats nonexistence, rejection, uncoded and excluded all as not-denial; ` +
        `<b>negation codes only</b> drops uncoded/excluded rows so the contrast is denial vs. nonexistence/rejection. ` +
        `Denominator = rows where both compared coders have a non-missing (and, for negation-codes-only, content) label.`;
      $("denialTable").innerHTML = `<table><thead><tr>
          <th>Pair</th>
          <th class="numeric">n</th><th class="numeric">Agreement</th><th class="numeric">&kappa;</th><th class="numeric">Denial rate</th>
          <th class="numeric">Neg n</th><th class="numeric">Neg agreement</th><th class="numeric">Neg &kappa;</th><th class="numeric">Neg denial rate</th>
        </tr></thead><tbody>${
        pairDefs.map(p => {
          const all = binPairStats(base, p.a, p.b, false);
          const neg = binPairStats(base, p.a, p.b, true);
          return `<tr>
            <td>${esc(p.name)}${p.baseline ? ` <span class="muted">(baseline)</span>` : ""}</td>
            <td class="numeric">${all.n}</td><td class="numeric">${pct(all.agreement)}</td><td class="numeric">${num(all.kappa)}</td><td class="numeric">${pct(all.base)}</td>
            <td class="numeric">${neg.n}</td><td class="numeric">${pct(neg.agreement)}</td><td class="numeric">${num(neg.kappa)}</td><td class="numeric">${pct(neg.base)}</td>
          </tr>`;
        }).join("")
      }</tbody></table>`;

      $("denialDetectCaption").innerHTML =
        `On rows where both humans agree on denial vs. not-denial (their consensus is the ground truth) and the LLM also coded the row. ` +
        `Positive class = denial; scored on ${scopeDesc()}.`;
      const blocks = [
        { title: "All coded rows", neg: false },
        { title: "Negation codes only", neg: true }
      ].map(b => {
        const d = denialDetection(base, b.neg);
        if (!d.n) {
          return `<div class="detect-block">
            <div class="block-title">${b.title}</div>
            <p class="detect-empty">No rows with a human binary consensus and an LLM label in this scope.</p>
          </div>`;
        }
        const metrics = [
          ["Accuracy", pct(d.acc)],
          ["Sensitivity (recall)", pct(d.sens)],
          ["Specificity", pct(d.spec)],
          ["Precision", pct(d.prec)],
          ["F1", num(d.f1)]
        ];
        return `<div class="detect-block">
          <div class="block-title">${b.title} <span class="muted">&middot; n=${d.n} (${d.nDenial} denial)</span></div>
          <div class="detect-grid">
            <table class="confusion"><thead><tr>
                <th></th><th class="numeric">Consensus denial</th><th class="numeric">Consensus not</th>
              </tr></thead><tbody>
              <tr><td>LLM denial</td><td class="numeric tp">${d.tp}</td><td class="numeric fp">${d.fp}</td></tr>
              <tr><td>LLM not</td><td class="numeric fn">${d.fn}</td><td class="numeric tn">${d.tn}</td></tr>
            </tbody></table>
            <table class="metric-table"><tbody>${
              metrics.map(([k, v]) => `<tr><td>${k}</td><td class="numeric"><b>${v}</b></td></tr>`).join("")
            }</tbody></table>
          </div>
        </div>`;
      }).join("");
      $("denialDetection").innerHTML = `<div class="denial-detect">${blocks}</div>`;
    }

    function renderCounts(visible) {
      $("countsCaption").textContent = visible.length === scopedRows().length
        ? `Collapsed labels per coder, ${scopeDesc()}.`
        : `Collapsed labels per coder, restricted to the ${visible.length} rows matching the current filters.`;
      const coders = [["LLM", "llm_label_collapsed"], [coderName.human_1, "human_1_label_collapsed"], [coderName.human_2, "human_2_label_collapsed"]];
      $("labelCounts").innerHTML = `<table><thead><tr><th>Coder</th>${
        labelLevels.map(l => `<th class="numeric">${esc(l)}</th>`).join("")
      }<th class="numeric">missing</th></tr></thead><tbody>${
        coders.map(([name, key]) => {
          const cells = labelLevels.map(l => visible.filter(r => clean(r[key]) === l).length);
          const missing = visible.filter(r => !clean(r[key])).length;
          return `<tr><td>${esc(name)}</td>${cells.map(c => `<td class="numeric">${c || `<span class="muted">&middot;</span>`}</td>`).join("")}<td class="numeric">${missing || `<span class="muted">&middot;</span>`}</td></tr>`;
        }).join("")
      }</tbody></table>`;
    }

    function renderFlagTable(visible) {
      $("flagTableCaption").textContent = (visible.length === scopedRows().length
        ? `Computed on ${scopeDesc()}. `
        : `Restricted to the ${visible.length} rows matching the current filters. `) +
        `Yes counts per coder; mismatch = rows where one coder raised the flag and another said No (rows a human never coded are excluded from their counts).`;
      $("flagTable").innerHTML = `<table><thead><tr>
          <th>Flag</th><th class="numeric">LLM yes</th>
          <th class="numeric">${esc(coderShort.human_1)} yes</th>
          <th class="numeric">${esc(coderShort.human_2)} yes</th>
          <th class="numeric">Rows with mismatch</th>
        </tr></thead><tbody>${
        flagNames.map(f => {
          const yes = (who) => visible.filter(r => coderCoded(r, who) && isTrue(r[who + "_" + f])).length;
          const mismatch = visible.filter(r => flagInfo(r).some(x => x.flag === f && x.mismatch)).length;
          const dot = `<span class="muted">&middot;</span>`;
          return `<tr><td>${esc(f.replaceAll("_", " "))}</td>
            <td class="numeric">${yes("llm") || dot}</td>
            <td class="numeric">${yes("human_1") || dot}</td>
            <td class="numeric">${yes("human_2") || dot}</td>
            <td class="numeric">${mismatch ? `<b>${mismatch}</b>` : dot}</td></tr>`;
        }).join("")
      }</tbody></table>`;
    }

    function renderFootnote() {
      $("footNote").innerHTML =
        `Conventions: <b>Nonpossession</b> is collapsed into <b>nonexistence</b> before comparison; ` +
        `<b>Uncoded</b> and <b>Excluded</b> stay explicit labels; blank human rows are missing data, not judgments; ` +
        `flags count as raised only when the coder wrote an explicit Yes. ` +
        `<b>Inspected</b> rows (per <span style="font-family:var(--mono)">splits/english/inspected_rows.txt</span>) are development data whose content informed prompt or policy edits; ` +
        `headline metrics use the clean subset and the inspected subset is a rule-compliance check only. ` +
        `These match the human&ndash;human IRR report. Small runs are smoke tests; treat their &kappa; values as descriptive. ` +
        `Current run data comes verbatim from <span style="font-family:var(--mono)">${esc(meta.version)}/results/${esc(meta.audit_csv)}</span>.`;
    }

    // ---- Trends tab ----

    const trendSeries = [
      { key: "hh", name: "Human vs human (baseline)", color: "#5b6770", dash: "6 4" },
      { key: "cons", name: "LLM vs human consensus", color: "#1f6f68", dash: "" },
      { key: "l1", name: "LLM vs human coder 1", color: "#2d5f8b", dash: "" },
      { key: "l2", name: "LLM vs human coder 2", color: "#a45c19", dash: "" }
    ];
    const splitShapes = ["circle", "square", "diamond", "triangle"];

    const trendBasisDefs = {
      full: { label: "full Bloom labels", short: "Full label" },
      denialAll: { label: "denial vs. not-denial (all coded rows)", short: "Denial (all)" },
      denialNeg: { label: "denial vs. not-denial (negation codes only)", short: "Denial (neg only)" }
    };

    function populateTrendControls() {
      const languages = [...new Set(payload.runs.map(r => r.meta.language || "Unknown"))].sort();
      const models = [...new Set(payload.runs.map(r => r.meta.model || "Unknown"))].sort();
      const conditionOrder = { english: 0, localized: 1 };
      const versionOptions = [...new Map(payload.runs.map(run => {
        const condition = versionExampleGroup(run.meta);
        const key = versionExampleKey(run.meta);
        return [key, {
          key,
          version: run.meta.version || "?",
          condition,
          label: `${run.meta.version || "?"} · ${condition.label}`
        }];
      })).values()].sort((a, b) =>
        Number(a.version.replace(/^v/, "")) - Number(b.version.replace(/^v/, "")) ||
        conditionOrder[a.condition.key] - conditionOrder[b.condition.key]
      );
      const versionKeys = versionOptions.map(option => option.key);
      const validLanguages = new Set(languages);
      const validModels = new Set(models);
      const validVersionKeys = new Set(versionKeys);
      state.trendLanguages = (state.trendLanguages || []).filter(lang => validLanguages.has(lang));
      state.trendVersionExamples = (state.trendVersionExamples === null ? versionKeys : state.trendVersionExamples)
        .filter(key => validVersionKeys.has(key));
      state.trendModels = (state.trendModels === null ? models : state.trendModels)
        .filter(model => validModels.has(model));
      $("trendLanguages").innerHTML = languages.map(lang =>
        `<label class="series-toggle"><input type="checkbox" data-trend-language="${esc(lang)}"
          ${state.trendLanguages.includes(lang) ? "checked" : ""}>${esc(lang)}</label>`
      ).join("");
      document.querySelectorAll("[data-trend-language]").forEach(input => {
        input.addEventListener("change", () => {
          const lang = input.dataset.trendLanguage;
          state.trendLanguages = input.checked
            ? [...new Set([...state.trendLanguages, lang])]
            : state.trendLanguages.filter(value => value !== lang);
          renderTrends();
        });
      });
      $("trendVersions").innerHTML = versionOptions.map(option =>
        `<label class="series-toggle"><input type="checkbox" data-trend-version="${esc(option.key)}"
          ${state.trendVersionExamples.includes(option.key) ? "checked" : ""}>${esc(option.label)}</label>`
      ).join("");
      document.querySelectorAll("[data-trend-version]").forEach(input => {
        input.addEventListener("change", () => {
          const key = input.dataset.trendVersion;
          state.trendVersionExamples = input.checked
            ? [...new Set([...state.trendVersionExamples, key])]
            : state.trendVersionExamples.filter(value => value !== key);
          $("trendVersionsCount").textContent =
            `${state.trendVersionExamples.length} of ${versionOptions.length} selected`;
          renderTrends();
        });
      });
      $("trendModels").innerHTML = models.map(model =>
        `<label class="series-toggle"><input type="checkbox" data-trend-model="${esc(model)}"
          ${state.trendModels.includes(model) ? "checked" : ""}>${esc(model)}</label>`
      ).join("");
      document.querySelectorAll("[data-trend-model]").forEach(input => {
        input.addEventListener("change", () => {
          const model = input.dataset.trendModel;
          state.trendModels = input.checked
            ? [...new Set([...state.trendModels, model])]
            : state.trendModels.filter(value => value !== model);
          $("trendModelsCount").textContent = `${state.trendModels.length} of ${models.length} selected`;
          renderTrends();
        });
      });
      $("trendVersionsCount").textContent =
        `${state.trendVersionExamples.length} of ${versionOptions.length} selected`;
      $("trendModelsCount").textContent = `${state.trendModels.length} of ${models.length} selected`;
      $("trendBasis").value = state.trendBasis;
      $("seriesHh").checked = state.trendSeries.hh;
      $("seriesCons").checked = state.trendSeries.cons;
      $("seriesL1").checked = state.trendSeries.l1;
      $("seriesL2").checked = state.trendSeries.l2;
      $("trendShowValues").checked = state.trendShowValues;
    }

    function resetTrendControls() {
      state.trendLanguages = [meta.language || "Unknown"];
      state.trendVersionExamples = [...new Set(payload.runs.map(r => versionExampleKey(r.meta)))];
      state.trendModels = [...new Set(payload.runs.map(r => r.meta.model || "Unknown"))];
      state.trendBasis = "full";
      state.trendMetric = "agreement";
      state.trendScope = "all";
      state.trendSeries = { hh: true, cons: true, l1: false, l2: false };
      state.trendShowValues = false;
      populateTrendControls();
      $("trendAgreement").classList.add("active");
      $("trendKappa").classList.remove("active");
      $("trendScopeAll").classList.add("active");
      $("trendScopeClean").classList.remove("active");
      renderTrends();
    }

    function trendRuns() {
      return payload.runs.filter(run => {
        return state.trendLanguages.includes(run.meta.language || "Unknown") &&
          state.trendVersionExamples.includes(versionExampleKey(run.meta)) &&
          state.trendModels.includes(run.meta.model || "Unknown");
      });
    }

    function trendStats() {
      const basis = state.trendBasis;
      const H1 = "human_1_label_collapsed", H2 = "human_2_label_collapsed", L = "llm_label_collapsed";
      return trendRuns().map(run => {
        const base = state.trendScope === "clean"
          ? run.rows.filter(r => !isInspected(r))
          : run.rows;
        let hh, l1, l2, cons;
        if (basis === "full") {
          hh = pairStatsRows(base, H1, H2, false);
          l1 = pairStatsRows(base, L, H1, false);
          l2 = pairStatsRows(base, L, H2, false);
          cons = consensusStats(base);
        } else {
          const negOnly = basis === "denialNeg";
          hh = binPairStats(base, H1, H2, negOnly);
          l1 = binPairStats(base, L, H1, negOnly);
          l2 = binPairStats(base, L, H2, negOnly);
          cons = binConsensusStats(base, negOnly);
        }
        return { meta: run.meta, nScope: base.length, hh, l1, l2, cons };
      });
    }

    function setTrendScope(scope) {
      state.trendScope = scope;
      $("trendScopeAll").classList.toggle("active", scope === "all");
      $("trendScopeClean").classList.toggle("active", scope === "clean");
      renderTrends();
    }

    function setTrendBasis(basis) {
      state.trendBasis = basis;
      $("trendBasis").value = basis;
      renderTrends();
    }

    // filled = examples match the target language; hollow (white fill, colored
    // outline) = English examples on a non-English target.
    function shapeMarkup(shape, x, y, r, color, filled = true) {
      const fill = filled ? color : "#fff";
      const stroke = filled ? "#fff" : color;
      const sw = filled ? 1.2 : 2;
      if (shape === "square") return `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
      if (shape === "diamond") return `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" transform="rotate(45 ${x} ${y})"/>`;
      if (shape === "triangle") return `<polygon points="${x},${y - r * 1.2} ${x - r * 1.15},${y + r} ${x + r * 1.15},${y + r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
      return `<circle cx="${x}" cy="${y}" r="${r}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
    }

    function renderTrendSvg(stats, visibleSeries, metric, containerW, shapeFor) {
      const value = (s, key) => metric === "agreement" ? s[key].agreement : s[key].kappa;
      const ml = 64, mr = 24, mt = 40, mb = 92;
      // Width is dynamic: spread columns across the available container width,
      // but clamp per-column width to [115, 240]px. The 115px floor keeps
      // columns legible (narrow viewports / many languages scroll horizontally);
      // the 240px cap stops a handful of columns from stretching absurdly wide.
      // As more languages (Hebrew, German, Tagalog, ...) add columns, colW
      // shrinks toward the floor and the chart packs / scrolls instead.
      const colW = Math.max(115, Math.min(240, (containerW - ml - mr) / stats.length));
      const width = ml + mr + colW * stats.length;
      const height = 430;
      const plotH = height - mt - mb;

      let yMin = 0, yMax = 1;
      if (metric === "kappa") {
        const vals = stats.flatMap(s => visibleSeries.map(t => value(s, t.key))).filter(Number.isFinite);
        yMin = Math.min(0, Math.floor(Math.min(...vals, 0) * 10) / 10);
        yMax = 1;
      }
      const yPos = (v) => mt + plotH - ((v - yMin) / (yMax - yMin)) * plotH;
      const xPos = (i) => ml + colW * i + colW / 2;

      const parts = [];
      parts.push(`<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" font-family="inherit" role="img" aria-label="${esc(stats[0].meta.language || "Unknown")} run comparison chart">`);

      const ticks = metric === "agreement" ? [0, 0.25, 0.5, 0.75, 1] : [yMin, 0, 0.25, 0.5, 0.75, 1].filter((v, i, a) => a.indexOf(v) === i);
      for (const t of ticks) {
        const y = yPos(t);
        parts.push(`<line x1="${ml}" y1="${y}" x2="${width - mr}" y2="${y}" stroke="#e3e7e2" stroke-width="1"/>`);
        parts.push(`<text x="${ml - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="#687076">${metric === "agreement" ? (t * 100).toFixed(0) + "%" : t.toFixed(2)}</text>`);
      }

      stats.forEach((s, i) => {
        const x = xPos(i);
        const masking = maskingCondition(s.meta);
        if (i > 0) {
          parts.push(`<line x1="${ml + colW * i}" y1="${mt}" x2="${ml + colW * i}" y2="${mt + plotH}" stroke="#f0f2ef" stroke-width="1"/>`);
        }
        parts.push(`<rect x="${ml + colW * i}" y="0" width="${colW}" height="${height}" fill="transparent"><title>${esc(runLabel({ meta: s.meta }))}</title></rect>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 18}" text-anchor="middle" font-size="13" font-weight="700" fill="#202124">${esc(s.meta.version)}</text>`);
        parts.push(`<rect x="${x - 34}" y="${mt + plotH + 25}" width="68" height="17" rx="8.5" fill="${masking.weak}" stroke="${masking.color}"/>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 37}" text-anchor="middle" font-size="9.5" font-weight="800" letter-spacing=".5" fill="${masking.color}">${esc(masking.short)}</text>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 57}" text-anchor="middle" font-size="10.5" fill="#687076">${esc(s.meta.split)} &middot; n=${s.nScope}${state.trendScope === "clean" ? " clean" : ""}</text>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 74}" text-anchor="middle" font-size="10" font-weight="600" fill="${exampleCondition(s.meta).matched ? "#1f6f68" : "#a45c19"}">${esc(exampleCondition(s.meta).short)}</text>`);
        if (!s.nScope) parts.push(`<text x="${x}" y="${mt + plotH / 2}" text-anchor="middle" font-size="11" fill="#9aa3a9" transform="rotate(-90 ${x} ${mt + plotH / 2})">all rows inspected &mdash; no headline evidence</text>`);
      });

      // Model bands replace a repeated model label beneath every run.
      let m0 = 0;
      for (let i = 1; i <= stats.length; i++) {
        const groupChanged = i === stats.length ||
          stats[i].meta.language !== stats[m0].meta.language ||
          (stats[i].meta.model || "") !== (stats[m0].meta.model || "");
        if (groupChanged) {
          const xMid = (xPos(m0) + xPos(i - 1)) / 2;
          parts.push(`<text x="${xMid}" y="20" text-anchor="middle" font-size="10.5" font-weight="650" fill="#3a4f4b">${esc(stats[m0].meta.model || "model?")}</text>`);
          if (i < stats.length && stats[i].meta.language === stats[m0].meta.language) {
            const xb = ml + colW * i;
            parts.push(`<line x1="${xb}" y1="8" x2="${xb}" y2="${mt + plotH}" stroke="#cdd4ce" stroke-width="1.2" stroke-dasharray="3 3"/>`);
          }
          m0 = i;
        }
      }

      const labelCols = stats.map(() => []);
      for (const series of visibleSeries) {
        const pts = stats.map((s, i) => ({ col: i, x: xPos(i), y: yPos(value(s, series.key)), v: value(s, series.key), split: s.meta.split, lang: s.meta.language, model: s.meta.model || "", matched: exampleCondition(s.meta).matched }))
          .filter(p => Number.isFinite(p.v));
        // Connect points only within one language AND model; start a new path
        // segment whenever either changes, so lines never bridge across
        // languages or imply a version trend spanning two different models.
        let seg = [];
        const flushSeg = () => {
          if (seg.length > 1) {
            const d = seg.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
            parts.push(`<path d="${d}" fill="none" stroke="${series.color}" stroke-width="2.2" ${series.dash ? `stroke-dasharray="${series.dash}"` : ""} opacity="0.85"/>`);
          }
          seg = [];
        };
        for (const p of pts) {
          const prev = seg[seg.length - 1];
          if (seg.length && (p.lang !== prev.lang || p.model !== prev.model)) flushSeg();
          seg.push(p);
        }
        flushSeg();
        for (const p of pts) {
          parts.push(shapeMarkup(shapeFor[p.split], p.x, p.y, 5.5, series.color, p.matched));
          if (state.trendShowValues) {
            labelCols[p.col].push({
              y: p.y, x: p.x, color: series.color,
              text: metric === "agreement" ? (p.v * 100).toFixed(1) + "%" : p.v.toFixed(2)
            });
          }
        }
      }
      // De-collide point labels within each column: sort by marker height and
      // push labels down until they are at least 13px apart.
      for (const col of labelCols) {
        col.sort((a, b) => a.y - b.y);
        let prev = -Infinity;
        for (const lab of col) {
          const ly = Math.max(prev + 13, lab.y - 7);
          prev = ly;
          parts.push(`<text x="${lab.x + 9}" y="${ly}" font-size="10.5" fill="${lab.color}">${lab.text}</text>`);
        }
      }

      parts.push("</svg>");
      return parts.join("");
    }

    function renderTrends() {
      const stats = trendStats();
      const metric = state.trendMetric;
      const visibleSeries = trendSeries.filter(series => state.trendSeries[series.key]);
      $("trendCount").textContent =
        `Showing ${stats.length} of ${payload.runs.length} run${stats.length === 1 ? "" : "s"} across ${state.trendLanguages.length} selected language${state.trendLanguages.length === 1 ? "" : "s"}.`;

      if (!stats.length) {
        $("trendChart").innerHTML = `<div class="trend-empty"><b>No runs match these filters.</b><br>Select a language, widen another filter, or reset the comparison.</div>`;
        $("trendLegend").innerHTML = "";
        $("trendTableCaption").textContent = "No runs match the current comparison filters.";
        $("trendTable").innerHTML = "";
        return;
      }

      const splits = [...new Set(stats.map(s => s.meta.split))];
      const shapeFor = Object.fromEntries(splits.map((sp, i) => [sp, splitShapes[i % splitShapes.length]]));
      const byLanguage = new Map();
      stats.forEach(stat => {
        const lang = stat.meta.language || "Unknown";
        if (!byLanguage.has(lang)) byLanguage.set(lang, []);
        byLanguage.get(lang).push(stat);
      });
      const gridW = $("trendChart").clientWidth || 1100;
      const columns = Math.max(1, Math.floor((gridW + 12) / 572));
      const visibleColumns = Math.min(columns, byLanguage.size);
      const facetW = Math.max(520, (gridW - 12 * (visibleColumns - 1)) / visibleColumns - 22);
      $("trendChart").innerHTML = visibleSeries.length
        ? [...byLanguage.entries()].map(([lang, langStats]) => `
            <section class="trend-facet">
              <div class="trend-facet-head"><h3>${esc(lang)}</h3><span>${langStats.length} run${langStats.length === 1 ? "" : "s"}</span></div>
              <div class="trend-svg-wrap">${renderTrendSvg(langStats, visibleSeries, metric, facetW, shapeFor)}</div>
            </section>`).join("")
        : `<div class="trend-empty"><b>No lines selected.</b><br>Choose at least one line to draw the charts.</div>`;

      const shapeGlyph = { circle: "\\u25cf", square: "\\u25a0", diamond: "\\u25c6", triangle: "\\u25b2" };
      $("trendLegend").innerHTML =
        visibleSeries.map(t => `<span><span class="swatch" style="border-top-color:${t.color}; ${t.dash ? "border-top-style:dashed;" : ""}"></span>${esc(t.name)}</span>`).join("") +
        `<span style="margin-left:8px; border-left:1px solid var(--border); padding-left:14px;">Split:</span>` +
        splits.map(sp => `<span><span class="shape">${shapeGlyph[shapeFor[sp]]}</span>${esc(sp)}</span>`).join("") +
        `<span style="margin-left:8px; border-left:1px solid var(--border); padding-left:14px;">Examples:</span>` +
        `<span><span class="shape">\\u25cf</span>match target language</span>` +
        `<span><span class="shape">\\u25cb</span>English examples</span>` +
        `<span style="margin-left:8px; border-left:1px solid var(--border); padding-left:14px; color:var(--muted);">Each language has its own plot; lines connect runs within one model. Hover a column for full run details.</span>`;

      $("trendTableCaption").innerHTML =
        `Comparison: <b>${esc(trendBasisDefs[state.trendBasis].label)}</b>. ` +
        (state.trendScope === "clean"
          ? `Clean rows only (inspected development rows excluded) &mdash; the headline view. `
          : `All rows, including inspected development rows; switch to &ldquo;Clean only&rdquo; for headline numbers. `) +
        `Same conventions as the run explorer: collapsed labels, denominator = rows where both compared coders have a non-missing Bloom label.`;
      $("trendTable").innerHTML = `<table><thead><tr>
          <th>Language</th><th>Model</th><th>Negator</th><th>Run</th><th>Split</th><th class="numeric">n</th>
          <th class="numeric">Human&ndash;human</th><th class="numeric">LLM vs consensus</th>
          <th class="numeric">LLM vs coder 1</th><th class="numeric">LLM vs coder 2</th>
        </tr></thead><tbody>${
        stats.map(s => `<tr>
          <td><b>${esc(s.meta.language || "?")}</b></td>
          <td>${esc(s.meta.model || "")}</td>
          <td>${maskingBadge(s.meta, true)}</td>
          <td><b>${esc(s.meta.version)}</b> ${esc(s.meta.prompt_version || "")}${s.meta.run_date ? " &middot; " + esc(s.meta.run_date) : ""}</td>
          <td>${esc(s.meta.split)}</td><td class="numeric">${s.nScope}${s.nScope === s.meta.n_rows ? "" : ` <span class="muted">of ${s.meta.n_rows}</span>`}</td>
          <td class="numeric">${pct(s.hh.agreement)} <span class="muted">(&kappa; ${num(s.hh.kappa)}, n=${s.hh.n})</span></td>
          <td class="numeric">${pct(s.cons.agreement)} <span class="muted">(n=${s.cons.n})</span></td>
          <td class="numeric">${pct(s.l1.agreement)} <span class="muted">(&kappa; ${num(s.l1.kappa)}, n=${s.l1.n})</span></td>
          <td class="numeric">${pct(s.l2.agreement)} <span class="muted">(&kappa; ${num(s.l2.kappa)}, n=${s.l2.n})</span></td>
        </tr>`).join("")
      }</tbody></table>`;
    }

    // ---- V5 prompt-experiment tab ----

    const experimentMetricDefs = {
      collapsed_accuracy_pct: { label: "Overall collapsed accuracy", n: "n" },
      rejection_accuracy_pct: { label: "Rejection accuracy", n: "rejection_n" },
      denial_accuracy_pct: { label: "Denial accuracy", n: "denial_n" },
      nonexistence_accuracy_pct: { label: "Nonexistence accuracy", n: "nonexistence_n" },
      excluded_accuracy_pct: { label: "Excluded accuracy", n: "excluded_n" }
    };
    const expNumber = (value) => {
      const n = Number(value);
      return Number.isFinite(n) ? n : NaN;
    };
    const expPct = (value) => Number.isFinite(expNumber(value)) ? expNumber(value).toFixed(1) + "%" : "&ndash;";
    const experimentRows = () => promptExperiments.rows || [];
    const experimentPrompt = (row) => clean(row.prompt_version).includes("-condensed-") ? "Condensed prompt" : "Full prompt";
    const experimentBatch = (row) => {
      const match = clean(row.prompt_version).match(/-b([0-9]+)-/);
      return match ? Number(match[1]) : Number(clean(row.batch_sizes).split(",").pop()) || 0;
    };
    const experimentDecoding = (row) => clean(row.prompt_version).includes("-qsample")
      ? "sampled decoding"
      : "temperature 0";
    const experimentCondition = (row) => {
      const reasoning = clean(row.reasoning_effort) === "high" ? "high reasoning" : "default reasoning";
      return `${experimentPrompt(row)} · batch ${experimentBatch(row)} · ${reasoning} · ${experimentDecoding(row)}`;
    };
    const bestExperiment = (model, rows = experimentRows()) => {
      const candidates = rows.filter(row => clean(row.model) === model);
      return [...candidates].sort((a, b) =>
        expNumber(b.collapsed_accuracy_pct) - expNumber(a.collapsed_accuracy_pct)
      )[0];
    };
    const findExperiment = (model, fragment) => experimentRows().find(row =>
      clean(row.model) === model && clean(row.prompt_version).includes(fragment)
    );
    const expDelta = (row) => {
      const value = expNumber(row.delta_vs_model_baseline_pp);
      if (!Number.isFinite(value)) return "";
      const sign = value > 0 ? "+" : "";
      return `${sign}${value.toFixed(1)} pp`;
    };
    const expP = (row) => {
      const value = expNumber(row.exact_sign_p_vs_model_baseline);
      if (!Number.isFinite(value)) return "";
      return value < 0.001 ? "p<.001" : `p=${value.toFixed(3).replace(/^0/, "")}`;
    };

    function populateExperimentControls() {
      const models = [...new Set(experimentRows().map(row => clean(row.model)).filter(Boolean))].sort();
      $("experimentModel").innerHTML = `<option value="all">All models (${models.length})</option>` +
        models.map(model => `<option value="${esc(model)}">${esc(model)}</option>`).join("");
      if (!models.includes(state.experimentModel)) state.experimentModel = "all";
      $("experimentModel").value = state.experimentModel;
      $("experimentMetric").value = state.experimentMetric;
    }

    function renderExperiments() {
      const allRows = experimentRows();
      if (!promptExperiments.available || !allRows.length) {
        $("experimentFindings").innerHTML = `<b>No prompt-experiment summary is embedded.</b> Rebuild the deterministic prompt-test split, run the completed conditions, then rebuild this viewer.`;
        $("experimentCards").innerHTML = "";
        $("experimentChart").innerHTML = "";
        $("experimentMethod").textContent = "";
        $("experimentTableCaption").textContent = "";
        $("experimentTable").innerHTML = "";
        return;
      }

      const gemma = bestExperiment("gemma4:31b");
      const qwen = bestExperiment("qwen3.6:35b-a3b");
      const gpt = bestExperiment("gpt-oss:120b");
      const gemmaB1 = findExperiment("gemma4:31b", "full-b1-rdefault-t0");
      const gemmaBase = findExperiment("gemma4:31b", "full-b5-rdefault-t0");
      const qwenBase = findExperiment("qwen3.6:35b-a3b", "full-b5-rdefault-t0");
      const gptHigh = findExperiment("gpt-oss:120b", "full-b5-rhigh-t0");
      const qwenSampled = allRows.filter(row =>
        clean(row.model) === "qwen3.6:35b-a3b" && clean(row.prompt_version).includes("-qsample")
      );
      const qwenSamplingDiffs = qwenSampled.map(sampled => {
        const deterministicVersion = clean(sampled.prompt_version).replace("-qsample", "-t0");
        const deterministic = allRows.find(row =>
          clean(row.model) === clean(sampled.model) &&
          clean(row.prompt_version) === deterministicVersion
        );
        return deterministic
          ? expNumber(sampled.collapsed_accuracy_pct) - expNumber(deterministic.collapsed_accuracy_pct)
          : NaN;
      }).filter(Number.isFinite);
      const qwenSampleMin = qwenSamplingDiffs.length ? Math.min(...qwenSamplingDiffs) : NaN;
      const qwenSampleMax = qwenSamplingDiffs.length ? Math.max(...qwenSamplingDiffs) : NaN;

      $("experimentFindings").innerHTML = `<b>Decision readout:</b>
        <ul>
          <li><b>Advance two settings to dev_check_1:</b> Qwen full prompt / batch 5 / temperature 0 as the pragmatic default, and Gemma full prompt / batch 1 as the accuracy-seeking challenger. Retaining the full common prompt avoids a model-specific prompt without giving up a supported gain.</li>
          <li>Gemma full/batch-1 reaches <b>${expPct(gemmaB1 && gemmaB1.collapsed_accuracy_pct)}</b>, ${esc(expDelta(gemmaB1 || {}))} vs its batch-5 baseline (${esc(expP(gemmaB1 || {}))}), but takes ${expNumber(gemmaB1 && gemmaB1.seconds_per_record).toFixed(1)} vs ${expNumber(gemmaBase && gemmaBase.seconds_per_record).toFixed(1)} seconds per record.</li>
          <li>GPT-OSS needs high reasoning: full/batch-5/high reaches <b>${expPct(gptHigh && gptHigh.collapsed_accuracy_pct)}</b>, ${esc(expDelta(gptHigh || {}))} vs its baseline (${esc(expP(gptHigh || {}))}). Qwen sampling is not supported: all ${qwenSamplingDiffs.length} sampled arms are worse by ${Math.abs(qwenSampleMax).toFixed(1)}&ndash;${Math.abs(qwenSampleMin).toFixed(1)} points.</li>
        </ul>`;

      const manifest = promptExperiments.manifest || {};
      const card = (eyebrow, row) => row ? `<article class="experiment-card">
          <div class="eyebrow">${esc(eyebrow)}</div>
          <div class="score">${expPct(row.collapsed_accuracy_pct)}</div>
          <div class="condition"><b>${esc(row.model)}</b><br>${esc(experimentCondition(row))}</div>
        </article>` : "";
      $("experimentCards").innerHTML =
        `<article class="experiment-card">
          <div class="eyebrow">Diagnostic sample</div>
          <div class="score">${esc(manifest.n_records || allRows[0].n || "?")}</div>
          <div class="condition"><b>paired English rows</b><br>class-enriched; not population-weighted</div>
        </article>` +
        card("Best Gemma", gemma) + card("Best Qwen", qwen) + card("Best GPT-OSS", gpt);

      const metric = experimentMetricDefs[state.experimentMetric];
      const filtered = allRows.filter(row =>
        state.experimentModel === "all" || clean(row.model) === state.experimentModel
      ).sort((a, b) => {
        const modelCompare = clean(a.model).localeCompare(clean(b.model));
        return state.experimentModel === "all" && modelCompare
          ? modelCompare
          : expNumber(b[state.experimentMetric]) - expNumber(a[state.experimentMetric]);
      });
      $("experimentCount").textContent =
        `${filtered.length} of ${allRows.length} completed condition${filtered.length === 1 ? "" : "s"}.`;

      const colors = {
        "gemma4:31b": "#1f6f68",
        "qwen3.6:35b-a3b": "#2d5f8b",
        "gpt-oss:120b": "#a45c19"
      };
      $("experimentChart").innerHTML = filtered.map(row => {
        const value = expNumber(row[state.experimentMetric]);
        const baseline = isTrue(row.is_model_baseline);
        const delta = expNumber(row.delta_vs_model_baseline_pp);
        const deltaClass = baseline ? "base" : delta > 0 ? "up" : delta < 0 ? "down" : "base";
        const right = state.experimentMetric === "collapsed_accuracy_pct"
          ? (baseline ? "baseline" : expDelta(row))
          : `n=${esc(row[metric.n] || "")}`;
        return `<div class="experiment-row">
          <div class="experiment-condition"><b>${esc(row.model)}</b><span>${esc(experimentCondition(row))}</span></div>
          <div class="experiment-track"><div class="experiment-bar" style="width:${Math.max(0, Math.min(100, value))}%; background:${colors[row.model] || "#1f6f68"}"></div></div>
          <div class="experiment-value">${expPct(value)}</div>
          <div class="experiment-delta ${deltaClass}">${esc(right)}</div>
        </div>`;
      }).join("");
      $("experimentMethod").innerHTML =
        `<b>${esc(metric.label)}.</b> The center guide marks 50%. Overall deltas use each model full-prompt / batch-5 / default-reasoning / temperature-0 baseline.`;

      const bestPrefixes = new Set(
        [...new Set(allRows.map(row => clean(row.model)))].map(model => clean(bestExperiment(model).run_prefix))
      );
      const tableRows = [...filtered].sort((a, b) =>
        expNumber(b.collapsed_accuracy_pct) - expNumber(a.collapsed_accuracy_pct)
      );
      $("experimentTableCaption").innerHTML =
        `Every condition uses the same ${esc(manifest.n_records || allRows[0].n || "?")} rows. Rejection n=${esc(allRows[0].rejection_n)}, denial n=${esc(allRows[0].denial_n)}, nonexistence n=${esc(allRows[0].nonexistence_n)}, excluded n=${esc(allRows[0].excluded_n)}. Paired exact sign tests are two-sided, relative to the within-model baseline, and uncorrected for multiple comparisons. Runtime comparisons are most meaningful within model.`;
      $("experimentTable").innerHTML = `<table><thead><tr>
          <th>Model</th><th>Condition</th>
          <th class="numeric">Overall</th><th class="numeric">Rejection</th><th class="numeric">Denial</th>
          <th class="numeric">Nonexist.</th><th class="numeric">Excluded</th>
          <th class="numeric">Certain Yes / acc.</th><th class="numeric">sec/row</th>
          <th class="numeric">vs baseline</th>
        </tr></thead><tbody>${tableRows.map(row => {
          const p = expP(row);
          const significant = Number.isFinite(expNumber(row.exact_sign_p_vs_model_baseline)) &&
            expNumber(row.exact_sign_p_vs_model_baseline) < 0.05;
          return `<tr class="${bestPrefixes.has(clean(row.run_prefix)) ? "best-row" : ""}">
            <td><b>${esc(row.model)}</b></td>
            <td>${esc(experimentCondition(row))}</td>
            <td class="numeric"><b>${expPct(row.collapsed_accuracy_pct)}</b></td>
            <td class="numeric">${expPct(row.rejection_accuracy_pct)}</td>
            <td class="numeric">${expPct(row.denial_accuracy_pct)}</td>
            <td class="numeric">${expPct(row.nonexistence_accuracy_pct)}</td>
            <td class="numeric">${expPct(row.excluded_accuracy_pct)}</td>
            <td class="numeric">${expPct(row.certain_yes_pct)} / ${expPct(row.certain_yes_accuracy_pct)}</td>
            <td class="numeric">${Number.isFinite(expNumber(row.seconds_per_record)) ? expNumber(row.seconds_per_record).toFixed(1) : "&ndash;"}</td>
            <td class="numeric">${isTrue(row.is_model_baseline) ? "baseline" : `${esc(expDelta(row))}<br><span class="muted">${esc(p)}</span>${significant ? `<span class="sig-chip">p&lt;.05</span>` : ""}`}</td>
          </tr>`;
        }).join("")}</tbody></table>`;
    }

    // ---- Certainty tab ----

    const certHumanProfiles = [
      "Both Yes",
      "Coder 1 Yes, Coder 2 No",
      "Coder 1 No, Coder 2 Yes",
      "Both No"
    ];
    const certComboLevels = ["Yes", "No"].flatMap(llm =>
      certHumanProfiles.map(humans => `${llm} / ${humans}`)
    );
    const modelPalette = ["#1f6f68", "#a45c19", "#2d5f8b", "#7b5ea7", "#b0413e", "#3b7a57"];
    // Stable per-model colors and a stable language order (first appearance in
    // the run list, which the R builder already sorts by language).
    const certModelList = [...new Set(payload.runs.map(r => r.meta.model || "Unknown"))].sort();
    const modelColor = Object.fromEntries(certModelList.map((m, i) => [m, modelPalette[i % modelPalette.length]]));
    const certLangOrder = [...new Set(payload.runs.map(r => r.meta.language || "Unknown"))];

    // Binary certainty. The LLM emits an explicit Yes/No. Humans fill
    // certain_bloom inconsistently (some only mark No when unsure, leaving the
    // cell blank when confident), so a labeled human row counts as certain
    // unless it explicitly says No.
    const certLLM = (v) => { const c = clean(v).toLowerCase(); return c === "yes" ? "Yes" : c === "no" ? "No" : ""; };
    const certHuman = (v) => clean(v).toLowerCase() === "no" ? "No" : "Yes";
    const runHasCertain = (run) => run.rows.some(r => certLLM(r.llm_certain));

    function certRuns() {
      return payload.runs.filter(run =>
        runHasCertain(run) &&
        // Masked and unmasked are separate arms scored against different row
        // sets (the masked split is pre-filtered), so they must never be pooled.
        (run.meta.masking || "unmasked") === state.certMasking &&
        (state.certModel === "all" || (run.meta.model || "Unknown") === state.certModel) &&
        (state.certExamples === "all" ||
          (state.certExamples === "matched" && exampleCondition(run.meta).matched) ||
          (state.certExamples === "english" && !exampleCondition(run.meta).matched)));
    }

    // One observation per negation. Agreement is defined against the shared
    // human Bloom label, so rows without two human labels or with split human
    // labels are excluded rather than double-counted or assigned an arbitrary
    // reference coder.
    function certRows(rowSet) {
      const out = [];
      for (const r of rowSet) {
        const lc = certLLM(r.llm_certain);
        const ll = clean(r.llm_label_collapsed);
        const h1 = clean(r.human_1_label_collapsed);
        const h2 = clean(r.human_2_label_collapsed);
        if (!lc || !ll || !h1 || !h2 || h1 !== h2) continue;
        const c1 = certHuman(r.human_1_certain);
        const c2 = certHuman(r.human_2_certain);
        const humanProfile =
          c1 === "Yes" && c2 === "Yes" ? "Both Yes" :
          c1 === "Yes" && c2 === "No" ? "Coder 1 Yes, Coder 2 No" :
          c1 === "No" && c2 === "Yes" ? "Coder 1 No, Coder 2 Yes" :
          "Both No";
        out.push({ llmC: lc, humanProfile, agree: ll === h1 });
      }
      return out;
    }

    function certCells(observations) {
      const m = Object.fromEntries(certComboLevels.map(c => [c, { n: 0, a: 0 }]));
      for (const o of observations) {
        const k = o.llmC + " / " + o.humanProfile;
        m[k].n++;
        if (o.agree) m[k].a++;
      }
      return certComboLevels.map(c => ({ label: c, n: m[c].n, agreement: m[c].n ? m[c].a / m[c].n : NaN }));
    }

    function certCalib(observations) {
      const m = { Yes: { n: 0, a: 0 }, No: { n: 0, a: 0 } };
      for (const o of observations) { m[o.llmC].n++; if (o.agree) m[o.llmC].a++; }
      return ["Yes", "No"].map(k => ({ label: k, n: m[k].n, agreement: m[k].n ? m[k].a / m[k].n : NaN }));
    }

    // language -> Map(model -> pooled rows) across the filtered runs, honoring
    // the clean-rows scope. Runs of the same model+language (e.g. localized and
    // English-example prompt arms) are pooled, matching the static figures.
    function certLangData() {
      const byLang = new Map();
      for (const run of certRuns()) {
        const lang = run.meta.language || "Unknown";
        const model = run.meta.model || "Unknown";
        const base = state.certScope === "clean" ? run.rows.filter(r => !isInspected(r)) : run.rows;
        if (!byLang.has(lang)) byLang.set(lang, new Map());
        const mm = byLang.get(lang);
        mm.set(model, (mm.get(model) || []).concat(base));
      }
      return byLang;
    }

    function setCertView(view) {
      state.certView = view;
      $("certView2x2").classList.toggle("active", view === "2x2");
      $("certViewCalib").classList.toggle("active", view === "calib");
      renderCertainty();
    }

    function setCertScope(scope) {
      state.certScope = scope;
      $("certScopeAll").classList.toggle("active", scope === "all");
      $("certScopeClean").classList.toggle("active", scope === "clean");
      renderCertainty();
    }

    function setCertMasking(masking) {
      state.certMasking = masking;
      $("certMaskVisible").classList.toggle("active", masking === "unmasked");
      $("certMaskMasked").classList.toggle("active", masking === "masked");
      renderCertainty();
    }

    function populateCertControls() {
      const models = [...new Set(payload.runs.filter(runHasCertain).map(r => r.meta.model || "Unknown"))].sort();
      $("certModel").innerHTML = `<option value="all">All models (${models.length})</option>` +
        models.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join("");
      if (![...$("certModel").options].some(o => o.value === state.certModel)) state.certModel = "all";
      $("certModel").value = state.certModel;
      $("certExamples").value = state.certExamples;
    }

    // Grouped bar chart: one group per certainty cell (or per LLM-certain value
    // in calibration view), one bar per model within a group.
    function renderCertSvg(groups, models, containerW, axisCaption) {
      const ml = 44, mr = 12, mt = 16, mb = 86;
      const width = Math.max(containerW, groups.length * 118 + ml + mr, 300);
      const height = 316;
      const plotH = height - mt - mb;
      const plotW = width - ml - mr;
      const yPos = (v) => mt + plotH - v * plotH;
      const groupW = plotW / groups.length;
      const humanAxisLabel = (profile) => ({
        "Both Yes": "C1 Yes · C2 Yes",
        "Coder 1 Yes, Coder 2 No": "C1 Yes · C2 No",
        "Coder 1 No, Coder 2 Yes": "C1 No · C2 Yes",
        "Both No": "C1 No · C2 No"
      })[profile] || profile;
      const parts = [];
      parts.push(`<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" font-family="inherit" role="img" aria-label="certainty agreement chart">`);
      for (const t of [0, 0.25, 0.5, 0.75, 1]) {
        const y = yPos(t);
        parts.push(`<line x1="${ml}" y1="${y}" x2="${width - mr}" y2="${y}" stroke="#e3e7e2" stroke-width="1"/>`);
        parts.push(`<text x="${ml - 6}" y="${y + 4}" text-anchor="end" font-size="10.5" fill="#687076">${(t * 100).toFixed(0)}%</text>`);
      }
      groups.forEach((g, gi) => {
        const gx = ml + groupW * gi;
        const bars = g.bars;
        const usable = groupW * 0.72;
        const barW = bars.length ? Math.min(46, usable / bars.length) : 0;
        const startX = gx + (groupW - barW * bars.length) / 2;
        bars.forEach((b, bi) => {
          const x = startX + barW * bi;
          const h = Number.isFinite(b.agreement) ? b.agreement * plotH : 0;
          const y = mt + plotH - h;
          const col = modelColor[b.model] || "#888";
          parts.push(`<rect x="${x + 2}" y="${y}" width="${Math.max(1, barW - 4)}" height="${h}" fill="${col}" rx="1.5"><title>${esc(b.model)} &mdash; ${esc(g.label)}: ${pct(b.agreement)} (n=${b.n})</title></rect>`);
          parts.push(`<text x="${x + barW / 2}" y="${y - 3}" text-anchor="middle" font-size="9.5" fill="#202124">${Number.isFinite(b.agreement) ? (b.agreement * 100).toFixed(0) : "&ndash;"}</text>`);
          if (h > 30) parts.push(`<text x="${x + barW / 2}" y="${mt + plotH - 4}" text-anchor="middle" font-size="8.5" fill="#fff" font-weight="700" transform="rotate(-90 ${x + barW / 2} ${mt + plotH - 4})">n=${b.n}</text>`);
        });
        const labelParts = g.label.split(" / ");
        const labelX = gx + groupW / 2;
        const labelY = mt + plotH + 16;
        if (labelParts.length === 2) {
          parts.push(`<text x="${labelX}" y="${labelY}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#202124"><tspan x="${labelX}">LLM ${esc(labelParts[0])}</tspan><tspan x="${labelX}" dy="14">${esc(humanAxisLabel(labelParts[1]))}</tspan></text>`);
        } else {
          parts.push(`<text x="${labelX}" y="${labelY}" text-anchor="middle" font-size="11" font-weight="700" fill="#202124">${esc(g.label)}</text>`);
        }
      });
      parts.push(`<text x="${ml + plotW / 2}" y="${height - 6}" text-anchor="middle" font-size="10.5" fill="#687076">${esc(axisCaption)}</text>`);
      parts.push("</svg>");
      return parts.join("");
    }

    function renderCertainty() {
      const byLang = certLangData();
      const view = state.certView;
      const groupLabels = view === "2x2" ? certComboLevels : ["Yes", "No"];
      const axisCaption = view === "2x2" ? "LLM certain / ordered human-coder certainty profile" : "LLM says it is certain";
      const nRuns = certRuns().length;
      const armLabel = state.certMasking === "masked" ? "masked" : "visible-negator";
      const nCertainRuns = payload.runs.filter(runHasCertain).length;
      const nArmRuns = payload.runs.filter(r => runHasCertain(r) && (r.meta.masking || "unmasked") === state.certMasking).length;
      $("certCount").textContent = nCertainRuns === 0
        ? "No runs carry a certain field yet (v4+ only)."
        : `Pooling ${nRuns} of ${nArmRuns} ${armLabel} run${nArmRuns === 1 ? "" : "s"} (of ${nCertainRuns} with certainty).`;

      if (!byLang.size) {
        const msg = nCertainRuns === 0
          ? `<b>No certainty data.</b><br>The <code>certain</code> field is emitted by v4 and later runs only; re-render this viewer once such runs are scored.`
          : `<b>No runs match these filters.</b><br>Try the other negator arm (Visible/Masked) or widen the model or prompt-examples filter.`;
        $("certChart").innerHTML = `<div class="trend-empty">${msg}</div>`;
        $("certLegend").innerHTML = "";
        $("certTableCaption").textContent = "";
        $("certTable").innerHTML = "";
        return;
      }

      const langs = certLangOrder.filter(l => byLang.has(l));
      const gridW = $("certChart").clientWidth || 1100;
      const columns = Math.max(1, Math.floor((gridW + 12) / 452));
      const visibleColumns = Math.min(columns, langs.length);
      const facetW = Math.max(380, (gridW - 12 * (visibleColumns - 1)) / visibleColumns - 22);

      // cells per language per model, reused by chart and table.
      const cellData = new Map();
      const modelsSeen = new Set();
      for (const lang of langs) {
        const mm = byLang.get(lang);
        const models = certModelList.filter(m => mm.has(m));
        models.forEach(m => modelsSeen.add(m));
        const perModel = {};
        models.forEach(m => {
          const observations = certRows(mm.get(m));
          perModel[m] = { cells: certCells(observations), calib: certCalib(observations) };
        });
        cellData.set(lang, { models, perModel });
      }

      $("certChart").innerHTML = langs.map(lang => {
        const { models, perModel } = cellData.get(lang);
        const source = (m, gi) => view === "2x2" ? perModel[m].cells[gi] : perModel[m].calib[gi];
        const groups = groupLabels.map((gl, gi) => ({
          label: gl,
          bars: models.map(m => ({ model: m, n: source(m, gi).n, agreement: source(m, gi).agreement }))
            .filter(b => b.n > 0)
        }));
        return `<section class="trend-facet">
            <div class="trend-facet-head"><h3>${esc(lang)}</h3><span>${models.length} model${models.length === 1 ? "" : "s"}</span></div>
            <div class="trend-svg-wrap">${renderCertSvg(groups, models, facetW, axisCaption)}</div>
          </section>`;
      }).join("");

      const legendModels = certModelList.filter(m => modelsSeen.has(m));
      $("certLegend").innerHTML =
        legendModels.map(m => `<span><span class="series-dot" style="background:${modelColor[m]}"></span>${esc(m)}</span>`).join("") +
        `<span style="margin-left:8px; border-left:1px solid var(--border); padding-left:14px; color:var(--muted);">Bar height = LLM&ndash;human-consensus Bloom-label agreement; number above = %, n inside. Each negation contributes once. Human &ldquo;certain&rdquo; = did not explicitly answer No.</span>`;

      $("certTableCaption").innerHTML = view === "2x2"
        ? `LLM&ndash;human-consensus agreement in each ordered certainty cell. ${state.certScope === "clean" ? "Clean rows only. " : "All rows. "}Each negation appears once; rows require two matching human Bloom labels.`
        : `Calibration against the shared human Bloom label when the LLM says certain = Yes vs No. Each negation appears once and requires two matching human Bloom labels. Yes should beat No for every model, else the field is not informative. ${state.certScope === "clean" ? "Clean rows only." : "All rows."}`;

      const cell = (o) => `${pct(o.agreement)} <span class="muted">(n=${o.n})</span>`;
      $("certTable").innerHTML = `<table><thead><tr>
          <th>Language</th><th>Model</th>${groupLabels.map(g => `<th class="numeric">${esc(g)}</th>`).join("")}
        </tr></thead><tbody>${
        langs.flatMap(lang => {
          const { models, perModel } = cellData.get(lang);
          return models.map((m, i) => `<tr>
            <td>${i === 0 ? `<b>${esc(lang)}</b>` : ""}</td><td>${esc(m)}</td>${
            groupLabels.map((gl, gi) => `<td class="numeric">${cell(view === "2x2" ? perModel[m].cells[gi] : perModel[m].calib[gi])}</td>`).join("")
          }</tr>`);
        }).join("")
      }</tbody></table>`;
    }

    document.addEventListener("keydown", (e) => {
      if ($("tabExplorer").classList.contains("hidden")) return;
      const tag = document.activeElement && document.activeElement.tagName;
      if (["INPUT", "SELECT", "TEXTAREA"].includes(tag)) return;
      if (e.key === "ArrowDown" || e.key === "j") { e.preventDefault(); moveSelection(1); }
      if (e.key === "ArrowUp" || e.key === "k") { e.preventDefault(); moveSelection(-1); }
    });

    bindControls();
    loadRun(0);
  </script>
</body>
</html>')

writeLines(html, output_path, useBytes = TRUE)
cat(output_path, "\n")
