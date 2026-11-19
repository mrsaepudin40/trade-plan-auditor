# Trade plan audit rules

## Plan schema

Required fields:

| Field | Meaning |
| --- | --- |
| `symbol` | The asset, e.g. `SAMPLE` |
| `side` | `long` or `short` |
| `account_usd` | Total account value in USD, positive number |
| `entry` | Planned entry price, positive number |
| `target` | Planned target price, positive number |
| `position_usd` | Planned position size in USD, positive number |

Optional fields:

| Field | Meaning |
| --- | --- |
| `stop` | Stop price. May be absent — a plan without a stop is audited and fails the stop check, not rejected as malformed. |
| `invalidation` | The condition that proves the plan wrong, in words |
| `thesis` | The reason for the trade, in words |
| `trade_type` | `cex` (default) or `onchain` |
| `honeypot_check` | `pass` when the honeypot gate passed, anything else when it did not |
| `slippage_pct` | Slippage the order will use, in percent |
| `analyst_score` | Analyst score from 0 to 100, when the plan carries one |
| `max_risk_usd` | Override for the dollar risk cap |
| `max_risk_pct` | Override for the percentage risk cap |
| `min_risk_reward` | Override for the minimum risk/reward |
| `max_position_pct` | Override for the position size limit |
| `max_slippage_pct` | Override for the slippage limit |
| `min_analyst_score` | Override for the analyst score bar |

A plan missing a required field, with a side other than `long` or
`short`, or with a non-positive number where a positive number is
required, is malformed: the script exits 1 and writes no report.

## Defaults

These defaults come from the trader's own standing rules. Every
one of them can be overridden in the plan file; they are defaults,
not promises.

- **Max risk per trade: $10 and 1% of the account.** The allowed
  risk is the smaller of the two. The trader's bot defaults to
  $2 per trade and caps a single trade at $10, with a daily cap
  of $10 — the daily cap across several trades is outside one
  audit, which checks a single plan.
- **Minimum risk/reward: 1.5.** The reward must be at least 1.5
  times the risk.
- **Max position size: 8% of the account.** From the trader's
  paper-trading setup, where positions are 8% of capital.
- **Max slippage on on-chain trades: 3%.** From the trader's bot
  setup.
- **Analyst score bar: 70 out of 100.** From the trader's paper
  setup, where a score of 70+ passes.

For reference only, not enforced by the gate: the trader's bot
uses a take-profit of +70% and a stop-loss of -25% per on-chain
micro-trade, and the paper setup uses a stop of -6% with a
trailing stop. A plan that states those levels is checked against
the rules above; the percentages themselves are not pass/fail
criteria.

## The checks

1. **Stop is set (hard).** The stop must be present and on the
   correct side of the entry: below it for a long, above it for a
   short. Missing or wrong-sided is a hard fail.
2. **Invalidation is written (hard when absent, soft when vague).**
   The plan must state what proves it wrong. Absent entirely is a
   hard fail. Present but with no price level or exact condition
   — fewer than 10 characters, no number, and no word like
   below, above, breaks, closes, holds, or loses — is a fixable
   gap.
3. **Risk is within the cap (hard).** Risk is the position size
   times the stop distance as a percentage of the entry. With no
   usable stop, the whole position counts as the risk. Above the
   allowed risk is a hard fail.
4. **Risk/reward is at least the minimum (soft).** Reward is the
   position size times the target distance as a percentage of the
   entry, divided by the risk. Below the minimum is a fixable gap.
   A target that gives no positive reward fails the check.
5. **Position is within the size limit (soft).** The position as a
   percentage of the account must not exceed the limit. Above it
   is a fixable gap.
6. **Thesis is written (soft).** Missing is a fixable gap.
7. **On-chain checks (soft; skipped for other trades).** The
   honeypot check must have passed, and the slippage must be
   within the limit. The honeypot gate is mandatory and
   fail-closed: anything other than a pass fails the check.
8. **Analyst score (soft; skipped when absent).** A carried score
   must clear the pass bar. Below it is a fixable gap.

## Computed numbers

- `stop_distance_pct` — the stop's distance from the entry, in
  percent. Null when there is no usable stop.
- `risk_usd` — the position times the stop distance. With no
  usable stop, the full position.
- `risk_pct` — the risk as a percentage of the account.
- `allowed_risk_usd` — the smaller of the dollar cap and the
  percentage cap applied to the account.
- `reward_usd` — the position times the target distance.
- `risk_reward` — reward divided by risk.
- `max_position_usd` — the largest position the allowed risk
  permits at the plan's stop distance. Null with no usable stop.
- `position_pct` — the position as a percentage of the account.

## Verdicts

- **GO** — every applicable check passes.
- **FIX** — no hard fail, at least one fixable gap. Fix the gaps
  and run the audit again; do not enter until the verdict is GO.
- **NO-GO** — at least one hard fail: no usable stop, risk above
  the cap, or no invalidation written at all. Do not enter;
  rewrite the plan.

## Honest limits

The auditor checks the plan as written. It cannot verify that the
thesis is true, that the market will respect the entry, stop, or
target levels, or that the honeypot, slippage, or analyst-score
values the trader supplied are correct. It never predicts a price,
never recommends an order, and never places one. A GO verdict is
not a promise the trade will win.
