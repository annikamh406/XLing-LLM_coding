# Tagalog ECC recovery

Job 8351246 on `gpu3001` stopped during diagnostic record 11,
`tgm_000717`, after ten validated records. The server log reports
`CUDA error: uncorrectable ECC error encountered`; llama-server aborted and
Ollama returned HTTP 500. There was no saved model response for that request.

The separate amendment `v6/dev_train_diagnostic_6_1_1_ecc_recovery.json`
allowlists only this failure by hashes of the original failure and job/server
logs, and the original ten-record checkpoint prefix. The prompt, original
freeze, record order, seeds, model, runtime and decoding settings are unchanged.

From the repository root on Oscar, after pulling:

```bash
git pull --ff-only
DRY_RUN=1 bash scripts/submit_v611_tagalog_ecc_resume.sh
bash scripts/submit_v611_tagalog_ecc_resume.sh
```

This submits one regular-condo L40S job for Tagalog, excluding `gpu3001`.
The runner also rejects the failed physical GPU UUID. It resumes the same
checkpoint and processes the remaining 23 records using their original seeds.
Use this launcher rather than the original five-language launcher.

At actual resume, under the same condition lock, the original failure file is
moved intact to
`v6/results/dev_train_diagnostic_6_1_1/ecc_recovery/original_failure_job-8351246.json`.
The job/server logs remain in their original locations. A separate attempt
ledger and amendment hash on new batches document the hardware exception.
Local preflight and dry runs do not move files or change the checkpoint.

Only the original hardware-failed request gets this continuation allowance.
Every remaining request has one attempt and unchanged settings. A new
transport, model or validation failure, or an interrupted request without a
validated checkpoint, stops for review. The exception cannot clear another
failure or silently repeat an unresolved request. Completed checkpoints can
be resumed without repeating inference; a response checkpointed just before
interruption is reconciled with the attempt ledger.

Download the whole result directory including `ecc_recovery/` and re-run the
existing scorer:

```bash
python3 scripts/summarize_v611_diagnostic.py
```

It will include Tagalog only after all 33 validated predictions and matching
final files exist and no new active failure is present. The archived hardware
failure remains available for audit.
