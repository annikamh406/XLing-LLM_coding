# V6.6.1: CHAT guide at the end

The unchanged V6.6 CHAT guide moves to the end of each of the five system
prompts, immediately before the user message containing the transcript.
The policy mirrors that move. Other wording and examples are unchanged.
Rebuild with `python3 v6/6.6.1/make_prompts.py`.

On Oscar, from the repository root:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v661_diagnostic.sh
bash scripts/submit_v661_diagnostic.sh
```

Five jobs run the same 200 records, preserving input order, context, seeds,
model and inference settings. Results and resumable checkpoints go to
`v6/results/dev_train_diagnostic_6_6_1/`.

After downloading results, run `python3 scripts/summarize_v661_diagnostic.py`.
The report compares directly against V6.6 to test placement. Inspect the
Spanish car explanation separately from label agreement: the key question
is whether the model reads `tere [: quiere]` as a replacement form.
