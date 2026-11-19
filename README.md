# trade-plan-auditor

[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python 3](https://img.shields.io/badge/python-3-blue)](scripts/audit.py)
[![API key: not required](https://img.shields.io/badge/API%20key-not%20required-brightgreen)](reference/audit-rules.md)

Audit a crypto trade plan before entry: check the stop, the
invalidation, the position size, the risk against the cap, and the
risk/reward — and return GO, FIX, or NO-GO with the exact gaps to
fix.

This skill does NOT predict prices. It does not say what to buy,
sell, or hold, and it never places an order. It checks whether the
plan itself is sound, using only the numbers the trader supplies.

## What it does

Feed it a trade-plan JSON file (a format in
`reference/audit-rules.md`) and it returns an audit report with
one verdict: **GO**, **FIX**, or **NO-GO**.

- **Stop first.** The stop must be present and on the correct side
  of the entry (below it for a long, above it for a short). A plan
  with no usable stop is a NO-GO — without a stop the loss is
  uncapped.
- **Invalidation in words.** The plan must state the condition
  that proves it wrong, with a price or an exact condition. No
  invalidation at all is a NO-GO; a vague one with no level is a
  fixable gap.
- **Deterministic risk math.** Risk is the position size times the
  stop distance. It must be within the allowed risk — the smaller
  of the dollar cap ($10 by default) and the percentage cap (1%
  of the account by default). The report also gives the reward,
  the risk/reward ratio, and the largest position the risk cap
  allows at the plan's stop distance.
- **Position concentration.** One position must not exceed 8% of
  the account by default.
- **On-chain checks.** For on-chain trades only: the honeypot gate
  must have passed (fail-closed — anything other than a pass
  fails), and the slippage must be within 3% by default.
- **Analyst score.** When the plan carries an analyst score, it
  must clear the 70-out-of-100 bar by default.
- **Verdicts with teeth.** GO means every applicable check passed.
  FIX means no hard fail but gaps are listed — fix them and audit
  again. NO-GO means a hard fail: no usable stop, risk above the
  cap, or no invalidation written at all.

The defaults come from a real trader's standing rules ($2 per
trade by default, $10 max per trade, 8% positions, -6% paper stop,
analyst score 70+ passing) and every one of them can be overridden
in the plan file. They are defaults, not promises.

## Run it

```bash
python3 scripts/audit.py --input plan.json --output audit.json
```

Python 3, standard library only. No network calls, no API key,
nothing to install. The auditor is pure arithmetic on the plan's
own numbers, so it works for any crypto asset the plan names.
`examples/sample-plan-go.json` is an invented plan for testing;
its audit report is in `examples/sample-audit-go.json`. Sample data
is clearly labelled and is not real market data.

## Files

- `SKILL.md` — the agent skill: the full workflow for gathering
  a trade plan, running the audit, presenting the verdict and the
  gaps, and the rules for the agent.
- `scripts/audit.py` — the complete auditor in dependency-free
  Python 3.
- `reference/audit-rules.md` — the plan schema, each check's
  definition and default threshold, the verdict rules, and the
  honest-limits note.
- `examples/` — three invented plans and their exact audit
  reports: one that passes (GO), one that fails hard (NO-GO), and
  one that needs fixes (FIX).

## Honest limits

The auditor checks the plan as written; it cannot verify that the
thesis is true, that the market will respect the levels, or that
the honeypot, slippage, or analyst-score values the trader
supplied are correct. It never predicts a price, never recommends
an order, and never places one. A GO verdict is not a promise the
trade will win.
