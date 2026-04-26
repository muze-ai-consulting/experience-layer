---
id: react-2026-03-useeffect-infinite-loop
name: useEffect with object/array dependency causes infinite re-render
severity: med
domain: frontend
triggers:
  keywords:
    - "useEffect"
    - "infinite loop"
    - "infinite re-render"
    - "useEffect dependency"
  regex:
    - "useEffect\\([^)]+\\[\\s*\\{"
    - "useEffect.*\\[\\s*\\["
fix: |
  Object and array literals in a useEffect dependency array are reference-new
  on every render, which triggers the effect every render — looking like an
  infinite loop because the effect updates state that re-renders the component.

  Fix options (in order of preference):
  1. Move the object/array OUTSIDE the component if it's truly constant
  2. Wrap with `useMemo` / `useCallback` so the reference is stable
  3. Depend on the primitive fields instead of the object: `[obj.id, obj.name]`
  4. If you genuinely need to react to the object change, use a deep-equal
     check via a third-party hook (e.g., use-deep-compare-effect)

  Never use an empty dependency array `[]` to "fix" this — it just means the
  effect doesn't re-run when it should, hiding the bug.
last_seen: 2026-03-10
provenance:
  url: "https://react.dev/learn/removing-effect-dependencies"
  session_id: null
  commit: null
review_status: validated
hits: 0
last_save_at: null
false_positives: 0
---

# useEffect with object/array dependency causes infinite re-render

## Context
A React component renders, runs `useEffect`, the effect updates state, the component re-renders, the effect runs again — silently, on every paint. The browser tab spikes to 100% CPU. The user sees nothing wrong in the rendered output and assumes the network is slow.

## Why generic warnings miss this
The lint rule `react-hooks/exhaustive-deps` flags missing dependencies but does NOT flag inline object/array literals in the dependency array. The code looks correct. The infinite loop only manifests at runtime, often only on slower machines where the symptom is more obvious.

## What to do instead
- Hoist the object out of the component if it's a constant
- Use `useMemo`/`useCallback` for derived values that need to be in deps
- Prefer primitive dependencies over object dependencies whenever possible
- If the deep-equal case is unavoidable, document why and use a vetted hook

## Related patterns
- react-2025-11-stale-closure-in-useeffect
- react-2025-09-setstate-in-render
