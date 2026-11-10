# V6.6: CHAT-reading guide added to V6.4

This candidate adds only the approved short `reading_chat.md` guide to V6.4.
It covers speaker tiers, replacement forms, incomplete words, overlap,
repetition/revision, uncertainty and contextual annotations. The guide appears
before target-occurrence alignment in all five full English-example prompts
and in the policy. Sources: the project's `Materials/CHAT Transcription Cheat
Sheet.docx` and the official CHAT manual:
<https://talkbank.org/0info/manuals/CHAT.html>.

The V6.4 Denial-last wording, milk correction example, other examples, label
order and schema are unchanged. V6.5's preference-example pair is not included.
Prompt IDs are `p0066*`; schema remains `bloom_v6`. Rebuild from the repository
root with `python3 v6/6.6/make_prompts.py`.

## Submit on Oscar

From the repository root:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v66_diagnostic.sh
bash scripts/submit_v66_diagnostic.sh
```

Five Gemma4:31b jobs use the exact same 200 frozen training records: English 44,
German 42, Hebrew 42, Spanish 39 and Tagalog 33. IDs, order, context, references,
40/80/80 diagnostic groups and original per-record seeds remain unchanged.
The guide uses the familiar Spanish replacement form to illustrate notation;
it does not adjudicate the car case or prescribe its Bloom label.

Inference settings remain batch 1, temperature 0, context 32,768 and generation
cap 8,000, with unchanged model/runtime checks. Each job requests one L40S,
four CPUs, 48 GB RAM and 12 hours by default. Faulty node/GPU exclusions remain;
`LANGUAGES`, `WALLTIME` and `CONDO_ACCOUNT` affect scheduling only.

Freeze: `v6/dev_train_diagnostic_6_6_freeze.json`. Results and validated,
resumable checkpoints: `v6/results/dev_train_diagnostic_6_6/`. Earlier versions
and results are preserved, with no earlier checkpoints imported. Genuine
recorded failures stop for review. No local inference has been launched.

## Score

After downloading results:

```bash
python3 scripts/summarize_v66_diagnostic.py
```

Open `v6/results/dev_train_diagnostic_6_6/report/report.html`. The report
compares V6.6 with V5, V6.2 and V6.4 by language and diagnostic group, including
directional confusions, uncertainty and row-level explanations. The direct
V6.4 comparison isolates adding the guide. Portable V6.4 predictions were
validated against complete checkpoints and runtime provenance; comparator and
source hashes are frozen. Old result directories are not required on Oscar.

Only complete language conditions enter metrics. This selected training
diagnostic measures development fit/control regressions, not population
accuracy or held-out generalization. Review interpretation of replacement
forms, speaker attribution under overlap and invented meanings for corpus
codes alongside label agreement.
