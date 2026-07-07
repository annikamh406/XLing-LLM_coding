# Certainty-vs-agreement graphs across all v4 runs.
#
# Usage:
#   Rscript scripts/build_certainty_agreement.R [version]   (default: v4)
#
# v4 predictions carry a binary `certain` (Yes/No) mirroring the human coders'
# `certain_bloom` column. This script crosses the two into a 2x2
# (LLM certain x human certain: Yes/Yes, Yes/No, No/Yes, No/No) and asks how
# label agreement moves across the cells, per the calibration checks in
# v4/CHANGES_FROM_V3.md section 7.
#
# Outputs (to <version>/results/certainty_agreement/):
#   certainty_agreement_by_run.csv        per run x certainty cell counts
#   human_human_certainty.csv             human-human baseline per language
#   certainty_2x2_llm_vs_human_by_model.png
#   certainty_2x2_llm_vs_human_by_language.png
#   certainty_2x2_llm_vs_human_masked.png
#   certainty_2x2_human_vs_human.png
#   llm_certainty_calibration_by_language.png
#   human_certainty_three_level.png
#
# Conventions (matching scripts/llm_human_irr_report.Rmd):
# * Labels are collapsed (Nonpossession -> nonexistence); agreement requires
#   both sides to have non-missing Bloom labels.
# * Inspected rows (splits/<lang>/inspected_rows.txt) are development data and
#   are excluded everywhere here.
# * Human `certain_bloom` is inconsistently filled: some coders answer Yes
#   explicitly, others leave it blank and only mark No when uncertain (German
#   coder 1 has zero explicit Yes). For the 2x2, a labeled row counts as
#   certain unless the coder explicitly answered No ("uncertain is explicit").
#   The three-level figure keeps Yes / blank / No separate so that assumption
#   can be inspected.
# * `limit-` smoke runs are skipped. Masked runs (p<NNN>m) are scored against
#   the masked references and plotted separately from unmasked runs (their row
#   sets differ; see the masked-arm evaluation note in CHANGES_FROM_V3.md).

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(purrr)
  library(stringr)
  library(ggplot2)
  library(jsonlite)
  library(readr)
})

args <- commandArgs(trailingOnly = TRUE)
version <- if (length(args) >= 1) args[[1]] else "v4"

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
script_path <- if (length(script_arg)) sub("^--file=", "", script_arg[[1]]) else NA_character_
scripts_dir <- if (!is.na(script_path) && file.exists(script_path)) dirname(normalizePath(script_path)) else NA_character_
if (is.na(scripts_dir) || !dir.exists(scripts_dir)) {
  scripts_dir <- "/Users/annika/Documents/Research/XLing/Data/XLing-LLM_coding/scripts"
}
llm_dir <- normalizePath(file.path(scripts_dir, ".."))
results_dir <- file.path(llm_dir, version, "results")
if (!dir.exists(results_dir)) stop("No results folder: ", results_dir)
out_dir <- file.path(results_dir, "certainty_agreement")
dir.create(out_dir, showWarnings = FALSE)

read_jsonl <- function(path) jsonlite::stream_in(file(path), verbose = FALSE)

label_bloom <- function(x) {
  x <- as.character(x)
  case_when(
    is.na(x) ~ NA_character_,
    x %in% c("Nonpossession", "Nonposession") ~ "nonexistence",
    x == "Nonexistence" ~ "nonexistence",
    x == "Rejection" ~ "rejection",
    x == "Denial" ~ "denial",
    x == "Uncoded" ~ "uncoded",
    x == "Excluded" ~ "excluded",
    TRUE ~ "other"
  )
}

# Normalize a raw certain answer to "Yes"/"No"/NA ("YEs" typos, blanks).
certain_raw3 <- function(x) {
  x <- str_to_lower(str_trim(as.character(x)))
  case_when(x == "yes" ~ "Yes", x == "no" ~ "No", TRUE ~ NA_character_)
}

# Binary certainty for a labeled row: only an explicit No counts as uncertain.
certain_binary <- function(raw3, has_label) {
  if_else(has_label, if_else(coalesce(raw3 == "No", FALSE), "No", "Yes"), NA_character_)
}

wilson_ci <- function(k, n, z = 1.96) {
  p <- k / n
  centre <- (p + z^2 / (2 * n)) / (1 + z^2 / n)
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / (1 + z^2 / n)
  tibble(lo = pmax(0, centre - half), hi = pmin(1, centre + half))
}

lang_by_prefix <- c(
  eng = "english", ger = "german", heb = "hebrew", spa = "spanish",
  tgm = "tagalog", tgn = "tagalog"
)

known_splits <- c("dev_train", "dev_check_1", "dev_check_2", "test_lockbox", "uncoded_by_neither")

first_existing <- function(paths) {
  for (p in paths) if (file.exists(p)) return(p)
  NA_character_
}

read_inspected <- function(lang) {
  path <- file.path(llm_dir, "splits", lang, "inspected_rows.txt")
  if (!file.exists(path)) return(character(0))
  lines <- trimws(readLines(path, warn = FALSE))
  lines[nzchar(lines) & !startsWith(lines, "#")]
}

# Human reference -> one row per record x coder with label + certainty.
load_human_long <- function(ref_path) {
  human_raw <- read_jsonl(ref_path)
  map_dfr(1:2, function(i) {
    coder <- human_raw[[paste0("coder_", i)]]
    raw3 <- certain_raw3(coder$certain_bloom)
    lab <- label_bloom(coder$bloom_label)
    tibble(
      record_id = human_raw$record_id,
      coder = paste0("human_", i),
      human_label = lab,
      human_certain3 = if_else(!is.na(lab), coalesce(raw3, "blank"), NA_character_),
      human_certain = certain_binary(raw3, !is.na(lab))
    )
  })
}

# ---------------------------------------------------------------------------
# Discover runs
# ---------------------------------------------------------------------------

prediction_files <- list.files(results_dir, pattern = "_predictions\\.jsonl$", full.names = TRUE)
prediction_files <- prediction_files[!grepl("limit-", basename(prediction_files))]
if (!length(prediction_files)) stop("No non-smoke *_predictions.jsonl under ", results_dir)

human_cache <- new.env()
runs <- list()

for (prediction_path in sort(prediction_files)) {
  prefix <- sub("_predictions\\.jsonl$", "", basename(prediction_path))
  split_name <- known_splits[startsWith(prefix, known_splits)]
  if (length(split_name) != 1) { warning("Cannot determine split for ", prefix, "; skipping."); next }

  m <- str_match(prefix, paste0("^", split_name, "_(.+)_bloom_", version, "_(p[0-9]+m?(?:-[a-z]+-[a-z]+)?)$"))
  if (is.na(m[1, 1])) { warning("Cannot parse run prefix ", prefix, "; skipping."); next }
  model <- m[1, 2]
  prompt <- m[1, 3]
  masked <- grepl("^p[0-9]+m", prompt)
  variant <- case_when(
    grepl("-engex$", prompt) ~ "engex",
    grepl("-loc$", prompt) ~ "loc",
    TRUE ~ "single"
  )

  predictions_raw <- read_jsonl(prediction_path)
  if (!"certain" %in% names(predictions_raw)) {
    warning("No `certain` field in ", prefix, " (pre-v4 schema?); skipping.")
    next
  }

  rec_prefix <- sub("_.*", "", predictions_raw$record_id[[1]])
  lang <- lang_by_prefix[[rec_prefix]]
  if (is.null(lang)) { warning("Unknown record prefix in ", prefix, "; skipping."); next }

  split_lang <- if (masked) paste0(lang, "_masked") else lang
  ref_path <- first_existing(c(
    file.path(llm_dir, version, "inputs", "splits", split_lang, paste0(split_name, "_human_reference.jsonl")),
    file.path(llm_dir, "splits", split_lang, paste0(split_name, "_human_reference.jsonl"))
  ))
  if (is.na(ref_path)) { warning("No human reference for ", split_lang, " ", split_name, "; skipping ", prefix); next }

  if (!exists(ref_path, envir = human_cache)) {
    assign(ref_path, load_human_long(ref_path), envir = human_cache)
  }
  human_long <- get(ref_path, envir = human_cache)

  llm <- predictions_raw %>%
    transmute(
      record_id,
      llm_label = label_bloom(bloom_label),
      llm_certain = certain_raw3(certain)
    )
  n_missing_certain <- sum(is.na(llm$llm_certain) & !is.na(llm$llm_label))
  if (n_missing_certain > 0) {
    message(prefix, ": ", n_missing_certain, " prediction(s) with unparseable `certain`; dropped from cells.")
  }

  inspected <- read_inspected(lang)

  pairs <- llm %>%
    inner_join(human_long, by = "record_id") %>%
    filter(!is.na(llm_label), !is.na(human_label), !(record_id %in% inspected)) %>%
    mutate(
      run = prefix, model = model, language = lang,
      variant = variant, masked = masked, split = split_name,
      agree = llm_label == human_label
    )

  runs[[prefix]] <- pairs
  message(sprintf("%-60s %s %s%s: %d LLM-human pairs", prefix, lang, variant,
                  if (masked) " masked" else "", nrow(pairs)))
}

pair_rows <- bind_rows(runs)
if (!nrow(pair_rows)) stop("No usable runs found.")

combo_levels <- c("Yes / Yes", "Yes / No", "No / Yes", "No / No")
pair_rows <- pair_rows %>%
  filter(!is.na(llm_certain)) %>%
  mutate(combo = factor(paste(llm_certain, human_certain, sep = " / "), combo_levels))

# ---------------------------------------------------------------------------
# Human-human baseline (unmasked dev_train references, one per language)
# ---------------------------------------------------------------------------

hh_rows <- map_dfr(unique(pair_rows$language[!pair_rows$masked]), function(lang) {
  ref_path <- first_existing(c(
    file.path(llm_dir, "splits", lang, "dev_train_human_reference.jsonl")
  ))
  if (is.na(ref_path)) return(tibble())
  human_long <- get(ref_path, envir = human_cache)
  inspected <- read_inspected(lang)
  human_long %>%
    filter(!(record_id %in% inspected)) %>%
    pivot_wider(names_from = coder, values_from = c(human_label, human_certain3, human_certain)) %>%
    filter(!is.na(human_label_human_1), !is.na(human_label_human_2)) %>%
    transmute(
      language = lang,
      combo = factor(paste(human_certain_human_1, human_certain_human_2, sep = " / "), combo_levels),
      agree = human_label_human_1 == human_label_human_2
    )
})

# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

summarise_cells <- function(df, ...) {
  df %>%
    group_by(...) %>%
    summarise(n = n(), n_agree = sum(agree), agreement = mean(agree), .groups = "drop") %>%
    bind_cols(wilson_ci(.$n_agree, .$n))
}

by_run <- summarise_cells(pair_rows, run, model, language, variant, masked, combo)
write_csv(by_run, file.path(out_dir, "certainty_agreement_by_run.csv"))

hh_summary <- summarise_cells(hh_rows, language, combo)
write_csv(hh_summary, file.path(out_dir, "human_human_certainty.csv"))

model_labels <- function(x) str_replace_all(x, "_", ":")

theme_cert <- theme_minimal(base_size = 12) +
  theme(
    panel.grid.minor = element_blank(),
    legend.position = "bottom",
    plot.title.position = "plot"
  )

bar_with_n <- function(df, fill_var, dodge = 0.85) {
  ggplot(df, aes(combo, agreement, fill = .data[[fill_var]])) +
    geom_col(position = position_dodge(dodge), width = 0.78) +
    geom_errorbar(aes(ymin = lo, ymax = hi), position = position_dodge(dodge),
                  width = 0.18, linewidth = 0.3, colour = "grey30") +
    geom_text(aes(label = paste0("n=", n), y = 0.015), position = position_dodge(dodge),
              angle = 90, hjust = 0, size = 2.7, colour = "white", fontface = "bold") +
    scale_y_continuous(labels = scales::percent, limits = c(0, 1), expand = expansion(mult = c(0, 0.02))) +
    labs(x = NULL, y = "Bloom label agreement") +
    theme_cert
}

# Fig 1: LLM x human certainty vs LLM-human agreement, pooled, unmasked.
fig1 <- pair_rows %>%
  filter(!masked) %>%
  summarise_cells(model, combo) %>%
  mutate(model = model_labels(model)) %>%
  bar_with_n("model") +
  scale_fill_brewer(palette = "Set2", name = NULL) +
  labs(
    title = "Agreement by certainty: LLM certain / human coder certain",
    subtitle = paste0(
      version, " unmasked runs, pooled across languages, prompt variants, and both human coders.\n",
      "Human 'certain' = did not explicitly answer No (blanks count as certain); inspected rows excluded."
    )
  )
ggsave(file.path(out_dir, "certainty_2x2_llm_vs_human_by_model.png"), fig1,
       width = 9, height = 5.5, dpi = 150)

# Fig 2: same, per language.
fig2 <- pair_rows %>%
  filter(!masked) %>%
  summarise_cells(model, language, combo) %>%
  mutate(model = model_labels(model), language = str_to_title(language)) %>%
  bar_with_n("model") +
  facet_wrap(~language) +
  scale_fill_brewer(palette = "Set2", name = NULL) +
  theme(axis.text.x = element_text(angle = 30, hjust = 1)) +
  labs(
    title = "Agreement by certainty per language: LLM certain / human coder certain",
    subtitle = paste0(version, " unmasked runs, pooled across prompt variants and both human coders.")
  )
ggsave(file.path(out_dir, "certainty_2x2_llm_vs_human_by_language.png"), fig2,
       width = 11, height = 7, dpi = 150)

# Fig 3: masked arm.
if (any(pair_rows$masked)) {
  fig3 <- pair_rows %>%
    filter(masked) %>%
    summarise_cells(model, combo) %>%
    mutate(model = model_labels(model)) %>%
    bar_with_n("model") +
    scale_fill_brewer(palette = "Set2", name = NULL) +
    labs(
      title = "Masked arm: agreement by certainty (LLM certain / human coder certain)",
      subtitle = paste0(
        version, " masked runs (negator hidden), pooled across languages and variants.\n",
        "Row set is the pre-filtered masked split; not comparable to unmasked figures' denominators."
      )
    )
  ggsave(file.path(out_dir, "certainty_2x2_llm_vs_human_masked.png"), fig3,
         width = 9, height = 5.5, dpi = 150)
}

# Fig 4: human-human baseline.
fig4 <- hh_summary %>%
  mutate(language = str_to_title(language)) %>%
  bar_with_n("language") +
  scale_fill_brewer(palette = "Set1", name = NULL) +
  labs(
    title = "Human-human baseline: agreement by certainty (coder 1 certain / coder 2 certain)",
    subtitle = "dev_train rows with both human Bloom labels; inspected rows excluded."
  )
ggsave(file.path(out_dir, "certainty_2x2_human_vs_human.png"), fig4,
       width = 9, height = 5.5, dpi = 150)

# Fig 5: LLM calibration only (falsification check 4 in CHANGES_FROM_V3.md):
# agreement when the LLM says certain Yes vs No, per model and language.
fig5 <- pair_rows %>%
  filter(!masked, !is.na(llm_certain)) %>%
  summarise_cells(model, language, llm_certain) %>%
  mutate(
    model = model_labels(model), language = str_to_title(language),
    llm_certain = factor(llm_certain, c("Yes", "No"))
  ) %>%
  ggplot(aes(model, agreement, fill = llm_certain)) +
  geom_col(position = position_dodge(0.85), width = 0.78) +
  geom_errorbar(aes(ymin = lo, ymax = hi), position = position_dodge(0.85),
                width = 0.18, linewidth = 0.3, colour = "grey30") +
  geom_text(aes(label = paste0("n=", n), y = 0.015), position = position_dodge(0.85),
            angle = 90, hjust = 0, size = 2.7, colour = "white", fontface = "bold") +
  facet_wrap(~language) +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1), expand = expansion(mult = c(0, 0.02))) +
  scale_fill_manual(values = c(Yes = "#2c7fb8", No = "#f03b20"), name = "LLM certain") +
  labs(
    x = NULL, y = "Agreement with human coders",
    title = "LLM calibration: agreement when the model says it is certain vs not",
    subtitle = paste0(version, " unmasked runs, pooled across prompt variants and both human coders.\n",
                      "Calibration check: the Yes bar should beat the No bar for every model (CHANGES_FROM_V3 #4).")
  ) +
  theme_cert +
  theme(axis.text.x = element_text(angle = 30, hjust = 1))
ggsave(file.path(out_dir, "llm_certainty_calibration_by_language.png"), fig5,
       width = 11, height = 7, dpi = 150)

# Fig 6: three-level human certainty (explicit Yes / blank / explicit No), so
# the blank-means-certain assumption behind the 2x2 is inspectable.
h3_llm <- pair_rows %>%
  filter(!masked) %>%
  mutate(human_certain3 = factor(human_certain3, c("Yes", "blank", "No"))) %>%
  summarise_cells(model, human_certain3) %>%
  mutate(series = model_labels(model))

hh_three <- map_dfr(unique(hh_rows$language), function(lang) {
  ref_path <- file.path(llm_dir, "splits", lang, "dev_train_human_reference.jsonl")
  human_long <- get(ref_path, envir = human_cache)
  inspected <- read_inspected(lang)
  wide <- human_long %>%
    filter(!(record_id %in% inspected)) %>%
    pivot_wider(names_from = coder, values_from = c(human_label, human_certain3, human_certain)) %>%
    filter(!is.na(human_label_human_1), !is.na(human_label_human_2)) %>%
    mutate(agree = human_label_human_1 == human_label_human_2)
  bind_rows(
    wide %>% transmute(human_certain3 = human_certain3_human_1, agree),
    wide %>% transmute(human_certain3 = human_certain3_human_2, agree)
  )
}) %>%
  mutate(human_certain3 = factor(human_certain3, c("Yes", "blank", "No"))) %>%
  summarise_cells(human_certain3) %>%
  mutate(series = "human vs human")

fig6 <- bind_rows(h3_llm %>% select(-model), hh_three) %>%
  ggplot(aes(human_certain3, agreement, fill = series)) +
  geom_col(position = position_dodge(0.85), width = 0.78) +
  geom_errorbar(aes(ymin = lo, ymax = hi), position = position_dodge(0.85),
                width = 0.18, linewidth = 0.3, colour = "grey30") +
  geom_text(aes(label = paste0("n=", n), y = 0.015), position = position_dodge(0.85),
            angle = 90, hjust = 0, size = 2.7, colour = "white", fontface = "bold") +
  scale_y_continuous(labels = scales::percent, limits = c(0, 1), expand = expansion(mult = c(0, 0.02))) +
  scale_fill_brewer(palette = "Set2", name = NULL) +
  labs(
    x = "Human coder's raw certain_bloom answer",
    y = "Agreement with that coder's label",
    title = "Raw human certainty (explicit Yes / blank / explicit No) vs agreement",
    subtitle = paste0("Blank cells behave like explicit Yes if coders only flag uncertainty;\n",
                      "this is the assumption behind treating blank as certain in the 2x2 figures.")
  ) +
  theme_cert
ggsave(file.path(out_dir, "human_certainty_three_level.png"), fig6,
       width = 9, height = 5.5, dpi = 150)

message("\nWrote CSVs and figures to ", out_dir)
