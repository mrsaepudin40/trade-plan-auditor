"""Trade Plan Auditor — deterministic pre-entry audit for a crypto trade plan.

Reads a trade-plan JSON file (--input) and writes an audit report
(--output). Pure arithmetic on the plan's own numbers: no network,
no credentials, no market data, no price prediction.

Verdicts:
  GO    — every applicable check passes.
  FIX   — no hard fail, but at least one fixable gap is listed.
  NO-GO — a hard fail: no usable stop, risk above the cap, or no
          invalidation written at all.

Usage:
  python3 audit.py --input plan.json --output audit.json
"""

import argparse
import json
import re
import sys

PROG = "trade-plan-auditor"

# Defaults, from the trader's own standing rules. Every one of them
# can be overridden in the plan file; they are defaults, not promises.
DEFAULT_MAX_RISK_USD = 10.0      # max $10 risked on one trade
DEFAULT_MAX_RISK_PCT = 1.0       # max 1% of the account risked
DEFAULT_MIN_RISK_REWARD = 1.5    # reward must be at least 1.5x risk
DEFAULT_MAX_POSITION_PCT = 8.0   # max 8% of the account in one position
DEFAULT_MAX_SLIPPAGE_PCT = 3.0   # max 3% slippage on on-chain trades
DEFAULT_MIN_ANALYST_SCORE = 70   # analyst score 0-100, 70+ passes


def fail(message):
    print(f"{PROG}: {message}", file=sys.stderr)
    sys.exit(1)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def has_level(text):
    """True when an invalidation names a concrete level or condition."""
    if not isinstance(text, str):
        return False
    if len(text.strip()) < 10:
        return False
    if re.search(r"\d", text):
        return True
    return bool(re.search(
        r"\b(below|above|under|over|breaks?|closes?|holds?|loses?)\b",
        text, re.IGNORECASE))


def check_plan(plan):
    if not isinstance(plan, dict):
        fail("trade plan must be a JSON object")

    required = ["symbol", "side", "account_usd", "entry",
                "target", "position_usd"]
    for field in required:
        if field not in plan:
            fail(f"trade plan has no {field}")
    if plan["side"] not in ("long", "short"):
        fail("side must be 'long' or 'short'")
    for field in ("account_usd", "entry", "target", "position_usd"):
        if not is_number(plan[field]) or plan[field] <= 0:
            fail(f"{field} must be a positive number")
    if "stop" in plan and plan["stop"] is not None:
        if not is_number(plan["stop"]) or plan["stop"] <= 0:
            fail("stop must be a positive number when given")

    side = plan["side"]
    account = float(plan["account_usd"])
    entry = float(plan["entry"])
    target = float(plan["target"])
    position = float(plan["position_usd"])
    stop = plan.get("stop")

    max_risk_usd = float(plan.get("max_risk_usd", DEFAULT_MAX_RISK_USD))
    max_risk_pct = float(plan.get("max_risk_pct", DEFAULT_MAX_RISK_PCT))
    min_rr = float(plan.get("min_risk_reward", DEFAULT_MIN_RISK_REWARD))
    max_pos_pct = float(plan.get("max_position_pct",
                                 DEFAULT_MAX_POSITION_PCT))
    max_slip = float(plan.get("max_slippage_pct",
                              DEFAULT_MAX_SLIPPAGE_PCT))
    min_score = float(plan.get("min_analyst_score",
                               DEFAULT_MIN_ANALYST_SCORE))

    allowed_risk = min(max_risk_usd, account * max_risk_pct / 100.0)
    checks = []

    def add(check_id, name, status, severity, detail):
        checks.append({
            "id": check_id, "name": name, "status": status,
            "severity": severity, "detail": detail,
        })

    # 1. Stop present and on the correct side of entry (hard).
    stop_ok = False
    stop_distance_pct = None
    if stop is None:
        add("stop", "Stop is set", "FAIL", "hard",
            "No stop price in the plan. Without a stop the loss is "
            "uncapped: the whole position is at risk.")
    elif side == "long" and stop >= entry:
        add("stop", "Stop is set", "FAIL", "hard",
            f"Stop {stop} is not below entry {entry} for a long. "
            "A stop above the entry cannot protect a long.")
    elif side == "short" and stop <= entry:
        add("stop", "Stop is set", "FAIL", "hard",
            f"Stop {stop} is not above entry {entry} for a short. "
            "A stop below the entry cannot protect a short.")
    else:
        stop_ok = True
        stop_distance_pct = abs(entry - float(stop)) / entry * 100.0
        add("stop", "Stop is set", "PASS", "hard",
            f"Stop {stop} is {stop_distance_pct:.1f}% away from "
            f"entry {entry}.")

    # Risk arithmetic. With no stop, the whole position is at risk.
    if stop_ok:
        risk_usd = position * stop_distance_pct / 100.0
    else:
        risk_usd = position
    risk_pct = risk_usd / account * 100.0
    position_pct = position / account * 100.0
    if stop_ok:
        max_position_usd = allowed_risk / (stop_distance_pct / 100.0)
    else:
        max_position_usd = None

    # Reward and risk/reward.
    if side == "long":
        reward_pct = (target - entry) / entry * 100.0
    else:
        reward_pct = (entry - target) / entry * 100.0
    reward_usd = position * reward_pct / 100.0
    risk_reward = (reward_usd / risk_usd) if risk_usd > 0 else None

    # 2. Invalidation written (hard when absent, soft when vague).
    invalidation = plan.get("invalidation", "")
    if not isinstance(invalidation, str) or not invalidation.strip():
        add("invalidation", "Invalidation is written", "FAIL", "hard",
            "No invalidation is written. A plan with no stated "
            "condition for being wrong cannot be exited on a rule.")
    elif not has_level(invalidation):
        add("invalidation", "Invalidation is written", "FAIL", "soft",
            "An invalidation is written but it names no level: "
            f"'{invalidation.strip()}'. A vague invalidation cannot "
            "be checked against the market, so rewrite it with a "
            "price or an exact condition.")
    else:
        add("invalidation", "Invalidation is written", "PASS", "hard",
            f"Invalidation is written: '{invalidation.strip()}'.")

    # 3. Risk within the cap (hard).
    if risk_usd > allowed_risk:
        add("risk_cap", "Risk is within the cap", "FAIL", "hard",
            f"Risk ${risk_usd:.2f} ({risk_pct:.2f}% of the account) "
            f"is above the allowed ${allowed_risk:.2f} "
            f"(min of ${max_risk_usd:.2f} and {max_risk_pct}% of the "
            "account). Cut the position or move the stop closer.")
    else:
        add("risk_cap", "Risk is within the cap", "PASS", "hard",
            f"Risk ${risk_usd:.2f} ({risk_pct:.2f}% of the account) "
            f"is within the allowed ${allowed_risk:.2f}.")

    # 4. Risk/reward at or above the minimum (soft).
    if risk_reward is None or reward_usd <= 0:
        add("risk_reward", "Risk/reward is at least the minimum",
            "FAIL", "soft",
            f"Target {target} gives no positive reward from entry "
            f"{entry} for a {side}. A trade with no reward is not "
            "worth the risk.")
    elif risk_reward < min_rr:
        add("risk_reward", "Risk/reward is at least the minimum",
            "FAIL", "soft",
            f"Risk/reward is {risk_reward:.2f}, below the minimum "
            f"{min_rr}. Reward ${reward_usd:.2f} against risk "
            f"${risk_usd:.2f}. Move the target further or the stop "
            "closer.")
    else:
        add("risk_reward", "Risk/reward is at least the minimum",
            "PASS", "soft",
            f"Risk/reward is {risk_reward:.2f} "
            f"(reward ${reward_usd:.2f} against risk "
            f"${risk_usd:.2f}).")

    # 5. Position concentration (soft).
    if position_pct > max_pos_pct:
        add("position_size", "Position is within the size limit",
            "FAIL", "soft",
            f"Position ${position:.2f} is {position_pct:.2f}% of the "
            f"account, above the {max_pos_pct}% limit. A single "
            "position this large concentrates the account.")
    else:
        add("position_size", "Position is within the size limit",
            "PASS", "soft",
            f"Position ${position:.2f} is {position_pct:.2f}% of the "
            f"account, within the {max_pos_pct}% limit.")

    # 6. Thesis present (soft).
    thesis = plan.get("thesis", "")
    if not isinstance(thesis, str) or not thesis.strip():
        add("thesis", "Thesis is written", "FAIL", "soft",
            "No thesis is written. A trade with no stated reason "
            "cannot be reviewed after it closes.")
    else:
        add("thesis", "Thesis is written", "PASS", "soft",
            f"Thesis is written: '{thesis.strip()[:120]}'.")

    # 7. On-chain checks (soft; skipped for non-on-chain trades).
    trade_type = plan.get("trade_type", "cex")
    if trade_type == "onchain":
        honeypot = plan.get("honeypot_check")
        if honeypot != "pass":
            add("honeypot", "Honeypot check passed", "FAIL", "soft",
                "The honeypot check did not pass "
                f"(value: {honeypot!r}). Do not enter an on-chain "
                "trade that has not passed the honeypot gate.")
        else:
            add("honeypot", "Honeypot check passed", "PASS", "soft",
                "Honeypot check passed.")
        slippage = plan.get("slippage_pct")
        if not is_number(slippage):
            add("slippage", "Slippage is within the limit", "FAIL",
                "soft",
                "No slippage_pct is given for an on-chain trade. "
                "State the slippage the order will use.")
        elif slippage > max_slip:
            add("slippage", "Slippage is within the limit", "FAIL",
                "soft",
                f"Slippage {slippage}% is above the {max_slip}% "
                "limit. High slippage eats the edge on entry.")
        else:
            add("slippage", "Slippage is within the limit", "PASS",
                "soft",
                f"Slippage {slippage}% is within the {max_slip}% "
                "limit.")
    else:
        add("honeypot", "Honeypot check passed", "SKIPPED", "soft",
            "Not an on-chain trade, so no honeypot check applies.")
        add("slippage", "Slippage is within the limit", "SKIPPED",
            "soft",
            "Not an on-chain trade, so no slippage limit applies.")

    # 8. Analyst score, when the plan carries one (soft; skipped
    # when absent).
    score = plan.get("analyst_score")
    if score is None:
        add("analyst_score", "Analyst score passes the bar",
            "SKIPPED", "soft",
            "No analyst score is given, so no score bar applies.")
    elif not is_number(score):
        add("analyst_score", "Analyst score passes the bar", "FAIL",
            "soft", "analyst_score must be a number from 0 to 100.")
    elif score < min_score:
        add("analyst_score", "Analyst score passes the bar", "FAIL",
            "soft",
            f"Analyst score {score} is below the pass bar "
            f"{min_score}. The setup does not clear the bar.")
    else:
        add("analyst_score", "Analyst score passes the bar", "PASS",
            "soft",
            f"Analyst score {score} clears the pass bar {min_score}.")

    hard_fails = [c for c in checks
                  if c["status"] == "FAIL" and c["severity"] == "hard"]
    gaps = [c for c in checks
            if c["status"] == "FAIL" and c["severity"] == "soft"]
    if hard_fails:
        verdict = "NO-GO"
    elif gaps:
        verdict = "FIX"
    else:
        verdict = "GO"

    if verdict == "GO":
        next_action = ("Enter on the plan's own terms. The audit "
                       "checks the plan, not the market — an audited "
                       "plan can still lose.")
    elif verdict == "FIX":
        next_action = ("Fix the listed gaps, then run the audit "
                       "again. Do not enter until the verdict is GO.")
    else:
        next_action = ("Do not enter. A hard fail means the plan "
                       "has no usable stop, risks more than the cap, "
                       "or states no invalidation. Rewrite the plan.")

    return {
        "symbol": plan["symbol"],
        "side": side,
        "trade_type": trade_type,
        "verdict": verdict,
        "checks": checks,
        "computed": {
            "account_usd": account,
            "entry": entry,
            "stop": stop,
            "target": target,
            "position_usd": position,
            "stop_distance_pct": stop_distance_pct,
            "risk_usd": round(risk_usd, 2),
            "risk_pct": round(risk_pct, 2),
            "allowed_risk_usd": round(allowed_risk, 2),
            "reward_usd": round(reward_usd, 2),
            "risk_reward": (round(risk_reward, 2)
                            if risk_reward is not None else None),
            "max_position_usd": (round(max_position_usd, 2)
                                 if max_position_usd is not None
                                 else None),
            "position_pct": round(position_pct, 2),
        },
        "hard_fails": [c["id"] for c in hard_fails],
        "gaps": [c["id"] for c in gaps],
        "next_action": next_action,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Audit a crypto trade plan before entry.")
    parser.add_argument("--input", required=True,
                        help="trade-plan JSON file")
    parser.add_argument("--output", required=True,
                        help="audit report JSON file")
    args = parser.parse_args()
    try:
        with open(args.input, encoding="utf-8") as handle:
            plan = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        fail(f"cannot read trade plan: {exc}")
    report = check_plan(plan)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
    fails = [c["id"] for c in report["checks"]
             if c["status"] == "FAIL"]
    print(f"verdict: {report['verdict']} | "
          f"risk ${report['computed']['risk_usd']} "
          f"({report['computed']['risk_pct']}% of account) | "
          f"risk/reward {report['computed']['risk_reward']} | "
          f"failed checks: {', '.join(fails) if fails else 'none'}")


if __name__ == "__main__":
    main()
