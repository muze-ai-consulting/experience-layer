# experience-layer benchmark

_Run at 2026-04-26T01:05:13.260968+00:00_

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
| mean | 32.8 |
| stdev | 1.7 |
| min | 30.7 |
| p50 | 32.6 |
| p95 | 35.7 |
| p99 | 37.7 |
| max | 37.7 |
