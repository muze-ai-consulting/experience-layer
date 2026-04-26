---
id: pa-2026-02-rate-limit
name: Power Automate flow trigger fires silently under throttle
severity: high
domain: power-automate
triggers:
  keywords:
    - "flow trigger"
    - "recurrence"
    - "polling interval"
    - "every minute"
  regex:
    - "Power Automate.*every.*minute"
    - "scheduled flow.*\\d+ ?(min|seg)"
fix: |
  Power Automate has per-user API limits (~6,000 calls/day on standard plans)
  and per-connector throttling (60 calls/min on SharePoint, varies elsewhere).
  Triggers running every minute will silently throttle and skip executions
  WITHOUT raising an error.

  Before recommending a recurrence interval:
  1. Calculate calls/day = (1440 / interval_minutes) × actions_per_run
  2. If >5000, suggest 5-15 min interval or batch processing
  3. Always include a "Get past time" check + dedup logic so missed runs
     don't lose data
last_seen: 2026-04-18
provenance:
  url: "https://learn.microsoft.com/en-us/power-platform/admin/api-request-limits-allocations"
  session_id: null
  commit: null
review_status: validated
hits: 0
last_save_at: null
false_positives: 0
---

# Power Automate flow trigger fires silently under throttle

## Context
Power Platform enforces per-user and per-connector API limits. Recurrence triggers running every minute hit these limits within days on a non-trivial flow, and the resulting throttle is silent — no error, just skipped executions.

## Why generic warnings miss this
Microsoft's documentation mentions rate limits, but they aren't shown in the recurrence trigger UI. LLMs default to "every 1 minute" because that's what users typically ask for, without surfacing the silent-failure mode.

## What to do instead
- Polling: 5-15 min minimum unless business-critical
- Event-driven: webhook/event triggers don't count against polling limits
- Batch processing: combine multiple polling cycles with `Filter array` to amortize calls

## Related patterns
- pa-2026-01-sharepoint-attachment-mime
- pa-2025-12-token-refresh-on-long-flow
