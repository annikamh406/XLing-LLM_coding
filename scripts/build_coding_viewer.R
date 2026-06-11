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
#     results folder (paired by record-id overlap; for multi-record batches
#     the thinking is attached to every record with a shared-batch count)
#
# The audit CSV rows are embedded verbatim; all agreement/kappa numbers are
# computed in the browser from the same collapsed-label columns and
# denominators as the IRR reports.
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

build_run <- function(audit_path, version) {
  rows <- readr::read_csv(audit_path, col_types = readr::cols(.default = readr::col_character()))
  rows[is.na(rows)] <- ""
  audit_ids <- rows$record_id
  split_name <- chr1(rows$split[1])
  results_dir <- dirname(audit_path)

  # Pair the raw-responses file by record-id overlap, so multiple runs can
  # coexist in one results folder without relying on filename conventions.
  # Raw files normally sit next to the audit; dev/ is a legacy location and
  # lockbox/ holds the final test_lockbox evaluation outputs.
  raw_dirs <- c(results_dir, file.path(results_dir, "dev"), file.path(results_dir, "lockbox"))
  raw_files <- unlist(lapply(
    raw_dirs[dir.exists(raw_dirs)],
    function(d) list.files(d, pattern = "_raw_responses\\.jsonl$", full.names = TRUE)
  ))
  best_raw <- NULL
  best_overlap <- 0
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

  thinking_map <- list()
  thinking_shared <- list()
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
      for (id in ids) {
        thinking_map[[id]] <- think
        thinking_shared[[id]] <- length(ids)
      }
    }
  }

  # Prefer the frozen per-version inputs so each run is shown against the
  # exact split files it consumed; fall back to the shared splits.
  split_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", "english", paste0(split_name, ".jsonl")),
    file.path(llm_dir, "splits", "english", paste0(split_name, ".jsonl"))
  ))
  ref_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", "english", paste0(split_name, "_human_reference.jsonl")),
    file.path(llm_dir, "splits", "english", paste0(split_name, "_human_reference.jsonl"))
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

  rows_list <- lapply(seq_len(nrow(rows)), function(i) {
    row <- as.list(rows[i, ])
    rid <- row$record_id
    s <- split_records[[rid]]
    h <- human_records[[rid]]
    extras <- list(
      child_age_raw = chr1(s$child_age_raw),
      child_age_months = chr1(s$child_age_months),
      context_before_lines = context_list(s$context_before),
      context_after_lines = context_list(s$context_after),
      human_1_certain = chr1(h$coder_1$certain_bloom),
      human_1_other_possibility = chr1(h$coder_1$other_possibility_bloom),
      human_1_one_of_two = chr1(h$coder_1$definitely_one_of_two_bloom),
      human_2_certain = chr1(h$coder_2$certain_bloom),
      human_2_other_possibility = chr1(h$coder_2$other_possibility_bloom),
      human_2_one_of_two = chr1(h$coder_2$definitely_one_of_two_bloom),
      llm_thinking = chr1(thinking_map[[rid]]),
      llm_thinking_shared_n = chr1(thinking_shared[[rid]])
    )
    c(row, extras)
  })

  context_window <- ""
  if (length(split_records)) context_window <- chr1(split_records[[1]]$context_window_size)

  list(
    meta = list(
      version = version,
      split = split_name,
      language = chr1(rows$language[1]),
      model = model,
      schema_version = schema_version,
      prompt_version = prompt_version,
      run_date = run_date,
      context_window = context_window,
      n_rows = nrow(rows),
      audit_csv = basename(audit_path)
    ),
    rows = rows_list
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

# Order runs chronologically within each version: by version number, then run
# date, then size (a limit-N smoke run precedes the full run from the same day).
run_order <- order(
  vapply(runs, function(r) as.integer(sub("^v", "", r$meta$version)), integer(1)),
  vapply(runs, function(r) ifelse(nzchar(r$meta$run_date), r$meta$run_date, "9999-99-99"), character(1)),
  vapply(runs, function(r) r$meta$n_rows, numeric(1))
)
runs <- runs[run_order]

payload <- list(
  generated_on = format(Sys.Date()),
  runs = runs
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

    .page { max-width: 1500px; margin: 0 auto; padding: 18px 22px 40px; }

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
      grid-template-columns: 390px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }

    .list-panel, .detail-panel, .table-panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 10px;
      min-width: 0;
    }

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
    .record-list { max-height: calc(100vh - 200px); overflow: auto; border-radius: 0 0 10px 10px; }

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

    .detail-panel { padding: 14px 16px 16px; }
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

    .footnote { margin-top: 14px; color: var(--muted); font-size: 12px; max-width: 100ch; }

    .trend-panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 16px; }
    .trend-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
    .trend-controls { display: flex; gap: 6px; }
    .trend-svg-wrap { overflow-x: auto; }
    .trend-legend { display: flex; flex-wrap: wrap; gap: 14px; margin-top: 8px; font-size: 12px; color: var(--muted); align-items: center; }
    .trend-legend .swatch { display: inline-block; width: 18px; height: 0; border-top: 3px solid; vertical-align: middle; margin-right: 5px; border-radius: 2px; }
    .trend-legend .shape { font-family: var(--mono); margin-right: 4px; color: var(--ink); }

    @media (max-width: 1100px) {
      .workspace { grid-template-columns: 1fr; }
      .record-list { max-height: 380px; }
      .summary-strip { grid-template-columns: 1fr 1fr; }
    }
    @media (max-width: 720px) {
      .page { padding: 12px; }
      .coding-grid, .control-row { grid-template-columns: 1fr; }
      .run-picker select { min-width: 0; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>XLing LLM&ndash;Human Coding Viewer</h1>
        <p class="subhead" id="pageSub"></p>
      </div>
      <div class="run-picker">
        <label for="runSelect">Run</label>
        <select id="runSelect"></select>
      </div>
    </header>

    <nav class="tabs">
      <button class="tab-btn active" id="tabBtnExplorer" type="button">Run explorer</button>
      <button class="tab-btn" id="tabBtnTrends" type="button">Agreement across versions</button>
    </nav>

    <div id="tabExplorer">
      <div class="run-chips" id="runChips"></div>
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
          <div>
            <h2>Agreement across versions</h2>
            <p class="subhead">One column per scored run, ordered by version. Marker shape shows which dev split the run used; the human&ndash;human pair on the same rows is the baseline band.</p>
          </div>
          <div class="trend-controls segmented" style="grid-template-columns: 1fr 1fr;">
            <button id="trendAgreement" class="seg-btn active" type="button">Agreement %</button>
            <button id="trendKappa" class="seg-btn" type="button">Cohen&rsquo;s &kappa;</button>
          </div>
        </div>
        <div class="trend-svg-wrap" id="trendChart"></div>
        <div class="trend-legend" id="trendLegend"></div>
      </section>

      <section class="table-panel">
        <h2>Run-by-run numbers</h2>
        <p class="caption">Same conventions as the run explorer: collapsed labels, denominator = rows where both compared coders have a non-missing Bloom label.</p>
        <div id="trendTable"></div>
      </section>
    </div>

    <p class="footnote" id="footNote"></p>
  </div>

  <script id="audit-data" type="application/json">', json_data, '</script>
  <script>
    const payload = JSON.parse(document.getElementById("audit-data").textContent);
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

    function runLabel(run) {
      const m = run.meta;
      const bits = [m.version, m.split, m.model || "model unknown", "n=" + m.n_rows];
      if (m.run_date) bits.push(m.run_date);
      return bits.join(" \\u00b7 ");
    }

    // ---- per-run state (recomputed by loadRun) ----
    let rows = [];
    let meta = {};
    let coderName = {};
    let coderShort = {};
    let pairDefs = [];
    const state = { runIdx: 0, selectedId: null, sort: "line", trendMetric: "agreement" };

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

    function loadRun(idx) {
      state.runIdx = idx;
      const run = payload.runs[idx];
      rows = run.rows;
      meta = run.meta;

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
      $("sortLine").classList.add("active");
      $("sortReview").classList.remove("active");
      $("search").value = "";

      renderHeader();
      populateFilters();
      renderSummary();
      renderTriage();
      renderIrr();
      renderFootnote();
      renderList();
    }

    function renderHeader() {
      $("pageSub").textContent =
        `Bloom coding pilot: each run codes child negation tokens with the LLM as a third independent coder. ` +
        `${payload.runs.length} scored run${payload.runs.length === 1 ? "" : "s"} embedded; generated ${payload.generated_on}.`;
      $("runChips").innerHTML = [
        ["version", meta.version],
        ["model", meta.model || "unknown"],
        ["split", meta.split + " (n=" + meta.n_rows + ")"],
        ["prompt", (meta.prompt_version || "?") + " / " + (meta.schema_version || "?")],
        ["run", meta.run_date || "date unknown"],
        ["language", meta.language]
      ].map(([k, v]) => `<span class="run-chip">${esc(k)} <b>${esc(v)}</b></span>`).join("");
    }

    function renderSummary() {
      const hh = pairStatsRows(rows, pairDefs[0].a, pairDefs[0].b, false);
      const l1 = pairStatsRows(rows, pairDefs[1].a, pairDefs[1].b, false);
      const l2 = pairStatsRows(rows, pairDefs[2].a, pairDefs[2].b, false);
      const cons = consensusStats(rows);
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
      rows.forEach(r => { const k = statusFor(r).key; counts[k] = (counts[k] || 0) + 1; });
      return counts;
    }

    function renderTriage() {
      const counts = statusCounts();
      const active = $("statusFilter").value;
      const nFlagMismatch = flagMismatchRows(rows).length;
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
      const counts = statusCounts();
      $("statusFilter").innerHTML = `<option value="all">All rows (${rows.length})</option>` + statusDefs
        .filter(s => counts[s.key])
        .map(s => `<option value="${s.key}">${esc(s.text)} (${counts[s.key]})</option>`).join("");

      const labels = [...new Set(rows.map(r => clean(r.llm_label_collapsed)).filter(Boolean))].sort();
      $("llmLabelFilter").innerHTML = `<option value="all">All labels</option>` +
        labels.map(l => `<option value="${esc(l)}">${esc(l)}</option>`).join("");

      const transcripts = [...new Set(rows.map(r => clean(r.transcript_id)).filter(Boolean))].sort();
      $("transcriptFilter").innerHTML = `<option value="all">All transcripts (${transcripts.length})</option>` +
        transcripts.map(t => `<option value="${esc(t)}">${esc(t)}</option>`).join("");
      $("transcriptCell").style.display = transcripts.length < 2 ? "none" : "";

      const nRaised = rows.filter(r => flagInfo(r).length).length;
      const nMismatch = flagMismatchRows(rows).length;
      $("flagFilter").innerHTML = `<option value="all">All rows</option>
        <option value="raised">Any flag raised (${nRaised})</option>
        <option value="mismatch">Flag mismatches (${nMismatch})</option>`;
    }

    function bindControls() {
      $("runSelect").innerHTML = payload.runs
        .map((run, i) => `<option value="${i}">${esc(runLabel(run))}</option>`).join("");
      $("runSelect").addEventListener("change", () => loadRun(Number($("runSelect").value)));

      $("tabBtnExplorer").addEventListener("click", () => setTab("explorer"));
      $("tabBtnTrends").addEventListener("click", () => setTab("trends"));

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
    }

    function setTab(tab) {
      $("tabExplorer").classList.toggle("hidden", tab !== "explorer");
      $("tabTrends").classList.toggle("hidden", tab !== "trends");
      $("tabBtnExplorer").classList.toggle("active", tab === "explorer");
      $("tabBtnTrends").classList.toggle("active", tab === "trends");
      if (tab === "trends") renderTrends();
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
      let out = rows.filter(row => {
        if (status !== "all" && statusFor(row).key !== status) return false;
        if (llmLabel !== "all" && clean(row.llm_label_collapsed) !== llmLabel) return false;
        if (transcript !== "all" && clean(row.transcript_id) !== transcript) return false;
        if (flagMode === "raised" && !flagInfo(row).length) return false;
        if (flagMode === "mismatch" && !flagInfo(row).some(f => f.mismatch)) return false;
        if (q) {
          const haystack = [
            row.record_id, row.transcript_id, row.target_utterance, row.target_negator,
            row.context_before, row.context_after,
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
      $("visibleCount").textContent = visible.length === rows.length
        ? `All ${rows.length} coded tokens`
        : `${visible.length} of ${rows.length} coded tokens match`;
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
        return `<button class="record-row${sel}" type="button" data-id="${esc(row.record_id)}">
          <span class="row-head">
            <span class="row-loc">L${esc(row.line)}</span>
            <span class="row-utt">${esc(row.target_utterance)}</span>
            <span class="status ${s.cls}">${esc(s.text)}</span>
          </span>
          <span class="row-chips">${chips}${flagChips}</span>
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
      if (who !== "llm") {
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

      const beforeLines = row.context_before_lines || [];
      const afterLines = row.context_after_lines || [];
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
        convoInner = `<div class="no-context">${esc(fallbackContext(row.context_before))}

` + transcriptLine({ line: row.line, speaker: row.speaker, utterance: row.target_utterance }, "target", row.target_negator) +
          `<div class="no-context">${esc(fallbackContext(row.context_after))}</div></div>`;
      }

      const sharedN = Number(row.llm_thinking_shared_n);
      const reasoningTitle = Number.isFinite(sharedN) && sharedN > 1
        ? `Model reasoning (shared across a batch of ${sharedN} records)`
        : "Model reasoning for this token";
      const reasoning = clean(row.llm_thinking)
        ? `<details class="reasoning"><summary>${reasoningTitle}</summary><pre>${esc(row.llm_thinking)}</pre></details>`
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
          <span class="status ${s.cls}" title="${esc(s.desc)}">${esc(s.text)}</span>
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
      $("irrCaption").innerHTML = `Computed on all ${rows.length} rows of this run with the same conventions as the IRR report: collapsed labels, denominator = rows where both coders have a non-missing Bloom label. Content-only columns restrict both labels to nonexistence / rejection / denial.`;
      $("irrTable").innerHTML = `<table><thead><tr>
          <th>Pair</th><th class="numeric">n</th><th class="numeric">Agreement</th><th class="numeric">&kappa;</th>
          <th class="numeric">Content n</th><th class="numeric">Content agreement</th><th class="numeric">Content &kappa;</th>
        </tr></thead><tbody>${
        pairDefs.map(p => {
          const all = pairStatsRows(rows, p.a, p.b, false);
          const content = pairStatsRows(rows, p.a, p.b, true);
          return `<tr>
            <td>${esc(p.name)}${p.baseline ? ` <span class="muted">(baseline)</span>` : ""}</td>
            <td class="numeric">${all.n}</td><td class="numeric">${pct(all.agreement)}</td><td class="numeric">${num(all.kappa)}</td>
            <td class="numeric">${content.n}</td><td class="numeric">${pct(content.agreement)}</td><td class="numeric">${num(content.kappa)}</td>
          </tr>`;
        }).join("")
      }</tbody></table>`;
    }

    function renderCounts(visible) {
      $("countsCaption").textContent = visible.length === rows.length
        ? `Collapsed labels per coder, all ${rows.length} rows.`
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
      $("flagTableCaption").textContent = (visible.length === rows.length
        ? `All ${rows.length} rows. `
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

    function trendStats() {
      return payload.runs.map(run => ({
        meta: run.meta,
        hh: pairStatsRows(run.rows, "human_1_label_collapsed", "human_2_label_collapsed", false),
        l1: pairStatsRows(run.rows, "llm_label_collapsed", "human_1_label_collapsed", false),
        l2: pairStatsRows(run.rows, "llm_label_collapsed", "human_2_label_collapsed", false),
        cons: consensusStats(run.rows)
      }));
    }

    function shapeMarkup(shape, x, y, r, color) {
      if (shape === "square") return `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" fill="${color}" stroke="#fff" stroke-width="1.2"/>`;
      if (shape === "diamond") return `<rect x="${x - r}" y="${y - r}" width="${2 * r}" height="${2 * r}" fill="${color}" stroke="#fff" stroke-width="1.2" transform="rotate(45 ${x} ${y})"/>`;
      if (shape === "triangle") return `<polygon points="${x},${y - r * 1.2} ${x - r * 1.15},${y + r} ${x + r * 1.15},${y + r}" fill="${color}" stroke="#fff" stroke-width="1.2"/>`;
      return `<circle cx="${x}" cy="${y}" r="${r}" fill="${color}" stroke="#fff" stroke-width="1.2"/>`;
    }

    function renderTrends() {
      const stats = trendStats();
      const metric = state.trendMetric;
      const value = (s, key) => metric === "agreement" ? s[key].agreement : s[key].kappa;

      const splits = [...new Set(stats.map(s => s.meta.split))];
      const shapeFor = Object.fromEntries(splits.map((sp, i) => [sp, splitShapes[i % splitShapes.length]]));

      const ml = 64, mr = 24, mt = 18, mb = 64;
      const colW = Math.max(120, Math.min(220, 760 / stats.length));
      const width = ml + mr + colW * stats.length;
      const height = 380;
      const plotH = height - mt - mb;

      let yMin = 0, yMax = 1;
      if (metric === "kappa") {
        const vals = stats.flatMap(s => trendSeries.map(t => value(s, t.key))).filter(Number.isFinite);
        yMin = Math.min(0, Math.floor(Math.min(...vals, 0) * 10) / 10);
        yMax = 1;
      }
      const yPos = (v) => mt + plotH - ((v - yMin) / (yMax - yMin)) * plotH;
      const xPos = (i) => ml + colW * i + colW / 2;

      const parts = [];
      parts.push(`<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" font-family="inherit" role="img" aria-label="Agreement across versions">`);

      const ticks = metric === "agreement" ? [0, 0.25, 0.5, 0.75, 1] : [yMin, 0, 0.25, 0.5, 0.75, 1].filter((v, i, a) => a.indexOf(v) === i);
      for (const t of ticks) {
        const y = yPos(t);
        parts.push(`<line x1="${ml}" y1="${y}" x2="${width - mr}" y2="${y}" stroke="#e3e7e2" stroke-width="1"/>`);
        parts.push(`<text x="${ml - 8}" y="${y + 4}" text-anchor="end" font-size="11" fill="#687076">${metric === "agreement" ? (t * 100).toFixed(0) + "%" : t.toFixed(2)}</text>`);
      }

      stats.forEach((s, i) => {
        const x = xPos(i);
        if (i > 0) parts.push(`<line x1="${ml + colW * i}" y1="${mt}" x2="${ml + colW * i}" y2="${mt + plotH}" stroke="#f0f2ef" stroke-width="1"/>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 22}" text-anchor="middle" font-size="13" font-weight="700" fill="#202124">${esc(s.meta.version)}</text>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 38}" text-anchor="middle" font-size="11" fill="#687076">${esc(s.meta.split)} &middot; n=${s.meta.n_rows}</text>`);
        parts.push(`<text x="${x}" y="${mt + plotH + 52}" text-anchor="middle" font-size="10.5" fill="#9aa3a9">${esc(s.meta.model || "")}${s.meta.run_date ? " &middot; " + esc(s.meta.run_date) : ""}</text>`);
      });

      const labelCols = stats.map(() => []);
      for (const series of trendSeries) {
        const pts = stats.map((s, i) => ({ col: i, x: xPos(i), y: yPos(value(s, series.key)), v: value(s, series.key), split: s.meta.split }))
          .filter(p => Number.isFinite(p.v));
        if (pts.length > 1) {
          const d = pts.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
          parts.push(`<path d="${d}" fill="none" stroke="${series.color}" stroke-width="2.2" ${series.dash ? `stroke-dasharray="${series.dash}"` : ""} opacity="0.85"/>`);
        }
        for (const p of pts) {
          parts.push(shapeMarkup(shapeFor[p.split], p.x, p.y, 5.5, series.color));
          labelCols[p.col].push({
            y: p.y, x: p.x, color: series.color,
            text: metric === "agreement" ? (p.v * 100).toFixed(1) + "%" : p.v.toFixed(2)
          });
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
      $("trendChart").innerHTML = parts.join("");

      const shapeGlyph = { circle: "\\u25cf", square: "\\u25a0", diamond: "\\u25c6", triangle: "\\u25b2" };
      $("trendLegend").innerHTML =
        trendSeries.map(t => `<span><span class="swatch" style="border-top-color:${t.color}; ${t.dash ? "border-top-style:dashed;" : ""}"></span>${esc(t.name)}</span>`).join("") +
        `<span style="margin-left:8px; border-left:1px solid var(--border); padding-left:14px;">Split:</span>` +
        splits.map(sp => `<span><span class="shape">${shapeGlyph[shapeFor[sp]]}</span>${esc(sp)}</span>`).join("");

      $("trendTable").innerHTML = `<table><thead><tr>
          <th>Run</th><th>Split</th><th class="numeric">n</th>
          <th class="numeric">Human&ndash;human</th><th class="numeric">LLM vs consensus</th>
          <th class="numeric">LLM vs coder 1</th><th class="numeric">LLM vs coder 2</th>
        </tr></thead><tbody>${
        stats.map(s => `<tr>
          <td><b>${esc(s.meta.version)}</b> ${esc(s.meta.model || "")} ${esc(s.meta.prompt_version || "")}${s.meta.run_date ? " &middot; " + esc(s.meta.run_date) : ""}</td>
          <td>${esc(s.meta.split)}</td><td class="numeric">${s.meta.n_rows}</td>
          <td class="numeric">${pct(s.hh.agreement)} <span class="muted">(&kappa; ${num(s.hh.kappa)}, n=${s.hh.n})</span></td>
          <td class="numeric">${pct(s.cons.agreement)} <span class="muted">(n=${s.cons.n})</span></td>
          <td class="numeric">${pct(s.l1.agreement)} <span class="muted">(&kappa; ${num(s.l1.kappa)}, n=${s.l1.n})</span></td>
          <td class="numeric">${pct(s.l2.agreement)} <span class="muted">(&kappa; ${num(s.l2.kappa)}, n=${s.l2.n})</span></td>
        </tr>`).join("")
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
