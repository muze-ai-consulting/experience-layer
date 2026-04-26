# experience-layer benchmark

_Run at 2026-04-26T01:24:53.784402+00:00_

## Corpus

3 patterns loaded from `examples/`:
- `frontend`: 1
- `power-automate`: 1
- `solana`: 1

## Precision / Recall

| metric | value |
|---|---|
| total cases | 20 |
| true positives  (fired correctly) | **10** |
| true negatives  (silent correctly) | **10** |
| false positives (fired wrongly)   | **0** |
| false negatives (missed)          | **0** |
| precision | **1.00** |
| recall    | **1.00** |
| F1        | **1.00** |

_No misses — every case classified correctly._

## Timing

_30 iterations of the full retrieve.py subprocess pipeline. Includes Python interpreter startup — this is the latency a UserPromptSubmit hook adds to each prompt._

| stat | ms |
|---|---|
| mean | 28.3 |
| stdev | 0.7 |
| min | 27.0 |
| p50 | 28.5 |
| p95 | 28.9 |
| p99 | 29.8 |
| max | 29.8 |
