---
name: trade-plan-auditor
description: Audit a crypto trade plan before entry — check the stop, the invalidation, the position size, the risk against the cap, and the risk/reward, and return GO, FIX, or NO-GO with the exact gaps to fix.
summary: Audit a crypto trade plan before entry — stop, invalidation, risk, size, and reward, with a GO, FIX, or NO-GO verdict.
version: 1.0.0
tags:
  - crypto
  - trading
  - risk
  - position-sizing
  - pre-trade
  - audit
  - onchain
  - discipline
keywords:
  - trade plan audit
  - position sizing
  - risk reward
  - stop loss
  - invalidation
  - pre-trade check
  - crypto trading
use_cases:
  - Audit a crypto trade plan before entering it
  - Check a position size against the risk cap before sending an order
  - Find the gaps in a trade plan that must be fixed before entry
---

# Trade Plan Auditor

Audit a crypto trade plan before entry: check the stop, the
invalidation, the position size, the risk against the cap, and the
risk/reward — and return one verdict: **GO**, **FIX**, or **NO-GO**.

This skill does NOT predict prices. It does not say what to buy,
sell, or hold, and it never places an order. It checks whether the
plan itself is sound, using only the numbers the trader supplies.
An audited plan can still lose; the audit checks the plan, not the
market.

Use this skill when the user asks to check a trade plan before
entering, to size a position, to check whether a stop or an
invalidation is missing, or to review why a plan should not be
entered yet.

## The plan

The trader supplies a trade-plan JSON file in the format in
`reference/audit-rules.md`. The required fields are: symbol, side
(`long` or `short`), account_usd, entry, target, and position_usd.
The stop is optional in the file — a plan without a stop is
audited, not rejected, and fails the stop check. Optional fields:
invalidation, thesis, trade_type (`cex` or `onchain`),
honeypot_check, slippage_pct, analyst_score, and the threshold
overrides (max_risk_usd, max_risk_pct, min_risk_reward,
max_position_pct, max_slippage_pct, min_analyst_score). When an
override is absent, the defaults in `reference/audit-rules.md`
apply.

## Run the audit

```bash
python3 scripts/audit.py --input plan.json --output audit.json
```

The script is dependency-free Python 3, standard library only, no
network, no credentials. It reads only the plan file given on the
command line and writes only the report file. Read the report back
and present it to the trader in this order:

1. The verdict, in plain words.
2. The computed numbers: risk in USD and as a percentage of the
   account, the allowed risk, the reward, the risk/reward ratio,
   and the maximum position the risk cap allows.
3. Every failed check, with its detail — hard fails first, then
   the fixable gaps.
4. The next action from the report.

## The checks, in order

1. **Stop is set.** The stop must be present and on the correct
   side of the entry (below it for a long, above it for a short).
   Missing or wrong-sided: hard fail.
2. **Invalidation is written.** The plan must state the condition
   that proves it wrong, with a price or an exact condition. No
   invalidation at all: hard fail. Written but vague, with no
   level: fixable gap.
3. **Risk is within the cap.** Risk is the position size times the
   stop distance. It must be within the allowed risk — the smaller
   of the dollar cap and the percentage cap. Above the cap: hard
   fail.
4. **Risk/reward is at least the minimum.** Reward is the position
   size times the target distance, divided by the risk. Below the
   minimum: fixable gap.
5. **Position is within the size limit.** One position must not
   concentrate the account above the limit. Above it: fixable gap.
6. **Thesis is written.** The plan must state its reason. Missing:
   fixable gap.
7. **On-chain checks.** For on-chain trades only: the honeypot
   check must have passed, and the slippage must be within the
   limit. Either failing: fixable gap. Skipped for other trades.
8. **Analyst score.** When the plan carries an analyst score, it
   must clear the pass bar. Below it: fixable gap. Skipped when
   the plan carries no score.

## Verdicts

- **GO** — every applicable check passes. Enter on the plan's own
  terms.
- **FIX** — no hard fail, but at least one fixable gap is listed.
  Fix the gaps and run the audit again. Do not enter until the
  verdict is GO.
- **NO-GO** — a hard fail: no usable stop, risk above the cap, or
  no invalidation written at all. Do not enter. Rewrite the plan.

## Rules for the agent

- Never invent a stop, a target, a price, or a score the trader
  did not supply. A missing field is a failed check, not a value
  to fill in.
- Never present a GO verdict as a promise the trade will win. Say
  plainly that an audited plan can still lose.
- Never place, send, or recommend an order. The audit ends at the
  verdict.
- The daily risk cap across several trades is outside this audit:
  one audit checks one plan. Say so when the trader asks about a
  day of trades.
- When a threshold override in the plan loosens a default, say so
  in the presentation — the trader should see that the bar was
  moved.

## Honest limits

The auditor checks the plan as written; it cannot verify that the
thesis is true, that the market will respect the levels, or that
the honeypot and slippage values the trader supplied are correct.
It works from the plan's own numbers and the defaults in
`reference/audit-rules.md`, and it says so in every report.
