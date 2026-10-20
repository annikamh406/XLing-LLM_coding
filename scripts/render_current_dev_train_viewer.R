# Render audits for current-prompt dev_train runs missing from the viewer.
# Keep the frozen general renderer and scoring template unchanged.
library(jsonlite)
script <- sub('^--file=', '', grep('^--file=',commandArgs(FALSE),value=TRUE)[[1]])
base <- normalizePath(file.path(dirname(script),'..'))
results <- file.path(base,'v5/results')
paths <- c(
 list.files(file.path(results,'gemma_gpu_comparison_condo'),pattern='-r2-full-b1-t0_predictions\\.jsonl$',full.names=TRUE),
 list.files(file.path(results,'hebrew_nfc_dev'),pattern='_predictions\\.jsonl$',full.names=TRUE),
 list.files(file.path(results,'prompt_experiments'),pattern='(gemma4_31b.*full-b1-rdefault-t0|qwen3.6_35b-a3b.*full-b5-rdefault-t0)_predictions\\.jsonl$',full.names=TRUE),
 list.files(file.path(results,'dev_train_current'),pattern='_predictions\\.jsonl$',full.names=TRUE)
)
if(!length(paths)) stop('No current dev_train predictions found')
langs <- c(eng='english',ger='german',heb='hebrew',spa='spanish',tgm='tagalog',tgn='tagalog')
for(path in sort(paths)) {
 prefix <- sub('_predictions\\.jsonl$','',basename(path))
 split <- if(startsWith(prefix,'dev_train_gemma_gpu_v5')) 'dev_train_gemma_gpu_v5' else if(startsWith(prefix,'dev_train_promptpair_v5')) 'dev_train_promptpair_v5' else if(startsWith(prefix,'dev_train_prompttest_v5')) 'dev_train_prompttest_v5' else 'dev_train'
 first <- fromJSON(readLines(path,n=1,warn=FALSE))
 lang <- langs[[sub('_.*','',first$record_id)]]
 split_path <- file.path(base,'splits',lang,paste0(split,'.jsonl'))
 ref_path <- file.path(base,'splits',lang,paste0(split,'_human_reference.jsonl'))
 audit <- file.path(dirname(path),paste0('llm-human-audit_',prefix,'.csv'))
 html <- file.path(dirname(path),paste0('llm-human-irr_',prefix,'.html'))
 stopifnot(file.exists(split_path),file.exists(ref_path))
 if(file.exists(audit)&&file.exists(html)) next
 inspected <- file.path(base,'splits',lang,'inspected_rows.txt')
 message('Rendering ',prefix)
 rmarkdown::render(file.path(base,'scripts/llm_human_irr_report.Rmd'),params=list(
  run_label=paste('v5',prefix),predictions_path=path,
  raw_responses_path=sub('_predictions.jsonl$','_raw_responses.jsonl',path),
  split_path=split_path,human_reference_path=ref_path,audit_csv_path=audit,
  inspected_ids_path=if(file.exists(inspected)) inspected else ''),
  output_file=html,intermediates_dir=tempdir(),envir=new.env(),quiet=TRUE)
}
message('Current dev_train audits ready. Rebuild with Rscript scripts/build_coding_viewer.R')
