# V6.7: Remove five redundant worked examples

V6.7 starts from V6.4 and removes worked examples J, K, T, U, and X.
The contrast section still teaches prohibition versus rule reporting,
difficulty versus resistance, and placement vetoes. The basic category
examples (including B and C), the other worked examples, and their original
IDs stay unchanged. The policy and classification rules stay unchanged.
Rebuild the prompts with `python3 v6/6.7/make_prompts.py`.

On Oscar, from the repository root:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v67_diagnostic.sh
bash scripts/submit_v67_diagnostic.sh
```

Five jobs run the same 200 records with the same context, seed assignments,
model, and inference settings. Results and resumable checkpoints go to
`v6/results/dev_train_diagnostic_6_7/`.

After downloading results, run `python3 scripts/summarize_v67_diagnostic.py`.
The report compares against V6.4 on the same records, separately for targeted
errors and the two control groups.
