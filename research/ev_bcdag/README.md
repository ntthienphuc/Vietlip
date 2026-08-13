# EV-B-C-DAG batch/QC add-on

This folder preserves the exact frozen pre-verifier router and its 256-request,
49% accounting policy. It is intentionally separate from the interactive API.

Run the routing diagnostic with the server virtual environment:

```powershell
server\.venv\Scripts\python.exe research\ev_bcdag\run_batch_advisor.py `
  final-results.json --output ev-routing.json
```

The input may be the JSON produced by the three-mode benchmark runner. Only
`visual_only` rows are used. The output says which clips the frozen router
would send to AV-HuBERT, but it does not execute AV-HuBERT and never changes the
Auto-AVSR transcript.

This boundary is mandatory: the frozen one-shot result improved selective WER
at the same verifier budget but missed the precommitted coverage floor by
0.6447 percentage points. Its risk calibration also predates the deployed
epoch-13 Auto-AVSR checkpoint. A partial window does not reproduce the canonical
256-request operating condition.
