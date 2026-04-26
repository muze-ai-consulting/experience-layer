---
id: solana-2025-11-jito-bundle-tip
name: Jito bundle without explicit tip account fails silently
severity: high
domain: solana
triggers:
  keywords:
    - "jito"
    - "bundle"
    - "tip"
    - "MEV"
  regex:
    - "Jito.*bundle"
    - "sendBundle"
fix: |
  A Jito bundle submitted without a tip transfer to one of the Jito tip accounts
  is accepted by the RPC and silently dropped — no error, no inclusion. The
  searcher sees "submitted" and waits forever for confirmation.

  Required structure:
  1. Include a SystemProgram.transfer to one of the published Jito tip accounts
     (rotate across the 8 public ones to spread load)
  2. Tip must be in lamports, in the same bundle as the transactions you want
     landed — not a separate transaction
  3. Tip amount: minimum ~10_000 lamports for non-priority bundles; bid
     dynamically against current bundle market for priority slots
  4. Verify inclusion via Jito's bundle status endpoint, not via standard
     RPC `getTransaction` — which can return null even for landed bundles
     during the brief window before the leader's block is propagated
last_seen: 2025-11-20
provenance:
  url: "https://docs.jito.wtf/lowlatencytxnsend/"
  session_id: null
  commit: null
review_status: validated
hits: 0
last_save_at: null
false_positives: 0
---

# Jito bundle without explicit tip account fails silently

## Context
Jito's block-engine accepts bundle submissions and returns a bundle ID immediately. If no tip is included (or the tip goes to a non-tip account), the bundle is silently dropped. The searcher's tooling reports "submitted" but the transactions never land, and standard RPC queries can't distinguish "dropped" from "still pending".

## Why generic warnings miss this
Jito's docs cover this but it's easy to miss when copying example code that omits the tip for brevity. LLMs often suggest "submit the bundle to Jito" without the tip-account requirement, because the API surface accepts the call without one.

## What to do instead
- Always include a tip transfer in the bundle itself
- Rotate across the 8 public tip accounts to avoid hot-spotting
- Use Jito's bundle status endpoint (not `getTransaction`) for inclusion verification
- If running a searcher: dynamically bid based on the bundle market, don't hardcode tip amounts

## Related patterns
- solana-2025-09-priority-fee-vs-base-fee
- solana-2025-08-blockhash-expiry-on-retry
