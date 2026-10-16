# Render the NFC-amended Hebrew configuration with the original frozen IRR template.
args <- commandArgs(trailingOnly = FALSE)
script <- sub('^--file=', '', grep('^--file=', args, value = TRUE)[[1]])
base <- normalizePath(file.path(dirname(script), '..'))
out <- file.path(base, 'v5/results/dev_check_1_hebrew_nfc')
stem <- 'dev_check_1_qwen3.6_35b-a3b_bloom_v5_p005v1nfc-he-full-b5-t0-s20261009'
pred <- file.path(out, paste0(stem, '_predictions.jsonl'))
raw <- file.path(out, paste0(stem, '_raw_responses.jsonl'))
if (!file.exists(pred) || !file.exists(raw)) stop('Complete Hebrew NFC outputs are required')
rmarkdown::render(
  file.path(base, 'scripts/llm_human_irr_report.Rmd'),
  params = list(
    run_label = paste('v5 Hebrew NFC amendment', stem),
    predictions_path = normalizePath(pred), raw_responses_path = normalizePath(raw),
    split_path = file.path(base, 'splits/hebrew/dev_check_1.jsonl'),
    human_reference_path = file.path(base, 'splits/hebrew/dev_check_1_human_reference.jsonl'),
    audit_csv_path = file.path(out, paste0('llm-human-audit_', stem, '.csv')),
    inspected_ids_path = file.path(base, 'splits/hebrew/inspected_rows.txt')
  ),
  output_file = file.path(out, paste0('llm-human-irr_', stem, '.html')),
  intermediates_dir = tempdir(), envir = new.env(), quiet = TRUE
)
