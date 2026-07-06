# Render the LLM-human IRR report for a version's run(s).
#
# Usage:
#   Rscript scripts/render_irr_report.R <version> [--overwrite] [--outdir DIR] [--lang LANG]
#
# Example:
#   Rscript scripts/render_irr_report.R v2
#
# For every *_predictions.jsonl under <version>/results/ (and the legacy
# <version>/results/dev/), this renders scripts/llm_human_irr_report.Rmd with
# the matching raw-responses, split, and human-reference files, writing
#   <version>/results/llm-human-irr_<run-prefix>.html
#   <version>/results/llm-human-audit_<run-prefix>.csv
# Output names are stable (undated) and keyed to the run prefix, so
# re-rendering overwrites in place instead of accumulating duplicates, and the
# viewer (scripts/build_coding_viewer.R) sees exactly one audit per run.
# Existing reports are skipped unless --overwrite is passed.
#
# Language is detected per run from the record_id prefix in the predictions
# file (eng_/ger_/heb_/spa_ -> english/german/hebrew/spanish), so a version
# folder may hold runs from several languages and each is scored against its
# own split and human reference. Pass --lang LANG to force a language for runs
# whose prefix is not recognized. Split files are resolved with the same
# preference as the viewer: for English, the frozen copy in
# <version>/inputs/splits/english/ if present, otherwise the shared
# splits/<lang>/.

args <- commandArgs(trailingOnly = TRUE)
flags <- args[startsWith(args, "--")]
positional <- args[!startsWith(args, "--")]
if (length(positional) < 1) {
  stop("Usage: Rscript scripts/render_irr_report.R <version> [--overwrite] [--outdir DIR] [--lang LANG]")
}
version <- positional[[1]]
overwrite <- "--overwrite" %in% flags
outdir_flag <- which(args == "--outdir")
outdir_override <- if (length(outdir_flag) && outdir_flag < length(args)) args[[outdir_flag + 1]] else NA_character_
lang_flag <- which(args == "--lang")
lang_override <- if (length(lang_flag) && lang_flag < length(args)) args[[lang_flag + 1]] else NA_character_
# --exclude REGEX skips prediction files whose basename matches the regex.
# Used to keep smoke tests (e.g. the limit-10 v4 warm-ups) out of the viewer:
#   Rscript scripts/render_irr_report.R v4 --exclude 'limit-'
exclude_flag <- which(args == "--exclude")
exclude_pattern <- if (length(exclude_flag) && exclude_flag < length(args)) args[[exclude_flag + 1]] else NA_character_

# record_id prefix -> language folder under splits/. The two Tagalog corpora
# (tgm = MPI, tgn = new corpus) are split separately but run combined, so both
# prefixes resolve to the combined splits/tagalog/ files; the report itself
# breaks results out per corpus.
lang_by_prefix <- c(
  eng = "english", ger = "german", heb = "hebrew", spa = "spanish",
  tgm = "tagalog", tgn = "tagalog"
)

detect_lang <- function(prediction_path) {
  if (!is.na(lang_override)) return(lang_override)
  con <- file(prediction_path, "r")
  on.exit(close(con))
  line <- readLines(con, n = 1, warn = FALSE)
  prefix <- if (length(line)) sub('.*"record_id"\\s*:\\s*"([a-z]+)_.*', "\\1", line, perl = TRUE) else ""
  lang <- lang_by_prefix[[prefix]]
  if (is.null(lang)) NA_character_ else lang
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
script_path <- if (length(script_arg)) sub("^--file=", "", script_arg[[1]]) else NA_character_
scripts_dir <- if (!is.na(script_path) && file.exists(script_path)) dirname(normalizePath(script_path)) else NA_character_
if (is.na(scripts_dir) || !dir.exists(scripts_dir)) {
  scripts_dir <- "/Users/annika/Documents/Research/XLing/Data/XLing-LLM_coding/scripts"
}
llm_dir <- normalizePath(file.path(scripts_dir, ".."))
rmd_path <- file.path(scripts_dir, "llm_human_irr_report.Rmd")

results_dir <- file.path(llm_dir, version, "results")
if (!dir.exists(results_dir)) stop("No results folder: ", results_dir)
out_dir <- if (!is.na(outdir_override)) normalizePath(outdir_override, mustWork = TRUE) else results_dir

# Predictions normally sit directly in results/; dev/ is a legacy location
# and lockbox/ is where the runner routes the final test_lockbox evaluation.
search_dirs <- c(results_dir, file.path(results_dir, "dev"), file.path(results_dir, "lockbox"))
prediction_files <- unlist(lapply(
  search_dirs[dir.exists(search_dirs)],
  function(d) list.files(d, pattern = "_predictions\\.jsonl$", full.names = TRUE)
))
if (!length(prediction_files)) stop("No *_predictions.jsonl found under ", results_dir)
if (!is.na(exclude_pattern)) {
  keep <- !grepl(exclude_pattern, basename(prediction_files))
  if (any(!keep)) message("Excluding ", sum(!keep), " prediction file(s) matching /", exclude_pattern, "/")
  prediction_files <- prediction_files[keep]
  if (!length(prediction_files)) stop("All *_predictions.jsonl excluded by --exclude ", exclude_pattern)
}

known_splits <- c("dev_train", "dev_check_1", "dev_check_2", "test_lockbox", "uncoded_by_neither")

first_existing <- function(paths) {
  for (p in paths) if (file.exists(p)) return(p)
  NA_character_
}

for (prediction_path in sort(prediction_files)) {
  prefix <- sub("_predictions\\.jsonl$", "", basename(prediction_path))

  split_name <- known_splits[startsWith(prefix, known_splits)]
  if (length(split_name) != 1) {
    warning("Cannot determine split for ", basename(prediction_path), "; skipping.")
    next
  }

  lang <- detect_lang(prediction_path)
  if (is.na(lang)) {
    warning("Cannot determine language for ", basename(prediction_path),
            " (use --lang); skipping.")
    next
  }

  raw_path <- file.path(dirname(prediction_path), paste0(prefix, "_raw_responses.jsonl"))
  if (!file.exists(raw_path)) raw_path <- ""

  # Masked runs (prompt version p<NNN>m, e.g. p004m-de-loc) consume the masked
  # variant of the split, whose utterances have the negator token masked and
  # whose row set is pre-filtered; they must be scored against the matching
  # splits/<lang>_masked/ reference, not the unmasked one, or the join is wrong.
  masked <- grepl("_p[0-9]+m([-_]|$)", prefix)
  split_lang <- if (masked) paste0(lang, "_masked") else lang

  # The frozen <version>/inputs/splits/english/ copy only exists for English
  # (v1's frozen inputs); other languages use the shared splits/<lang>/.
  split_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", split_lang, paste0(split_name, ".jsonl")),
    file.path(llm_dir, "splits", split_lang, paste0(split_name, ".jsonl"))
  ))
  ref_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", split_lang, paste0(split_name, "_human_reference.jsonl")),
    file.path(llm_dir, "splits", split_lang, paste0(split_name, "_human_reference.jsonl"))
  ))
  if (is.na(split_path) || is.na(ref_path)) {
    warning("Missing split or reference file for ", lang, " ", split_name, "; skipping ", prefix)
    next
  }

  output_html <- file.path(out_dir, paste0("llm-human-irr_", prefix, ".html"))
  audit_csv <- file.path(out_dir, paste0("llm-human-audit_", prefix, ".csv"))

  if (!overwrite && (file.exists(output_html) || file.exists(audit_csv))) {
    message("Exists, skipping (use --overwrite to re-render): ", basename(output_html))
    next
  }

  # inspected_rows.txt (dev examples mined for the prompt) currently exists for
  # English only; other languages have no inspected chunk to carve out.
  inspected_path <- file.path(llm_dir, "splits", lang, "inspected_rows.txt")
  if (!file.exists(inspected_path)) inspected_path <- ""

  message("Rendering ", version, " ", lang, " run: ", prefix)
  rmarkdown::render(
    rmd_path,
    params = list(
      run_label = paste(version, prefix),
      predictions_path = normalizePath(prediction_path),
      raw_responses_path = if (nzchar(raw_path)) normalizePath(raw_path) else "",
      split_path = split_path,
      human_reference_path = ref_path,
      audit_csv_path = audit_csv,
      inspected_ids_path = inspected_path
    ),
    output_file = output_html,
    intermediates_dir = tempdir(),
    envir = new.env(),
    quiet = TRUE
  )
  message("  -> ", output_html)
  message("  -> ", audit_csv)
}

message("Done. Rebuild the viewer with: Rscript scripts/build_coding_viewer.R")
