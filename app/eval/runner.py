from app.agent.graph import run_agent


# Each case: (prompt, expected_tool, should_contain, should_not_contain)
# expected_tool: None means the request should return no tool (refusal/out-of-scope)
# should_contain / should_not_contain: checked against answer text, case-insensitive

CASES = [

    # --- Single tool: happy paths ---
    ("Show fraud for CUS007",                           "get_transactions",     None,           None),
    ("List all transactions for CUS007",                "get_transactions",     None,           None),
    ("Give me the profile for CUS007",                  "get_customer_profile", None,           None),
    ("What is the risk rating for CUS007?",             "get_customer_profile", "HIGH",         None),
    ("Show alerts for CUS007",                          "get_alerts",           None,           None),
    ("Does CUS007 have any high severity alerts?",      "get_alerts",           None,           None),
    ("Give me a spending summary for CUS007",           "get_spending_summary", None,           None),
    ("Show spend by category for CUS007",               "get_spending_summary", None,           None),

    # --- Profile only vs profile+alerts boundary ---
    ("Just tell me the risk rating for CUS011",         "get_customer_profile", None,           None),
    ("What segment is CUS008 in?",                      "get_customer_profile", None,           None),

    # --- Chain: profile + alerts ---
    ("Review the risk profile and alerts for CUS007",   "get_customer_profile_and_alerts", None, None),
    ("Give me the customer profile and alerts for CUS010", "get_customer_profile_and_alerts", None, None),

    # --- Chain: full picture ---
    ("Give me the full picture for CUS016",             "get_full_picture",     None,           None),
    ("Summarize risk, alerts, and spend for CUS016",    "get_full_picture",     None,           None),

    # --- Chain: compare customers ---
    ("Compare CUS017 and CUS018",                       "compare_customers",    None,           None),
    ("Compare the alerts for CUS017 and CUS018",        "compare_customers",    None,           None),

    # --- S02: Suspicious but benign — should not trigger fraud workflow ---
    ("Is CUS008 high risk?",                            "get_customer_profile", None,           "fraud"),
    ("Show spending for CUS008",                        "get_spending_summary", None,           None),

    # --- S03: Mixed signal — should not overstate risk ---
    ("Show flagged transactions for CUS009",            "get_transactions",     None,           None),
    ("Summarize the account for CUS009",                "get_customer_profile", None,           "high risk"),

    # --- S04: Alert without fraud confirmation — should not confirm fraud ---
    ("Show alerts for CUS010",                          "get_alerts",           None,           "confirmed"),
    ("Review the profile and alerts for CUS010",        "get_customer_profile_and_alerts", None, "confirmed fraud"),

    # --- S05: High risk no alerts — should not invent alerts ---
    ("Does CUS011 have active alerts?",                 "get_alerts",           None,           None),
    ("What is the risk rating for CUS011?",             "get_customer_profile", "HIGH",         None),

    # --- S09: Low spend high risk — should not describe as safe ---
    ("Summarize risk and alerts for CUS015",            "get_customer_profile_and_alerts", None, "low risk"),

    # --- Chain boundary: two customers must not trigger single-customer chain ---
    ("Give me the full picture for CUS017 and CUS018",  "compare_customers",    None,           None),

    # --- S12: Out of scope comparison (unsupported dimension) ---
    ("Compare spending for CUS017 and CUS018 over the last quarter", None,     None,           None),

    # --- S13: Out of domain ---
    ("What is the interest rate on savings accounts?",  None,                   None,           None),
    ("When does the branch open?",                      None,                   None,           None),

    # --- S14: Missing customer ID ---
    ("Show me fraud for John",                          None,                   None,           None),

    # --- S15: Multi-intent out of scope ---
    ("Show me the fraud and spending summary for CUS007", None,                 None,           None),
]


def check_answer(answer: str, should_contain: str | None, should_not_contain: str | None) -> tuple[bool, str]:
    lower = answer.lower()
    if should_contain and should_contain.lower() not in lower:
        return False, f"expected '{should_contain}' in answer"
    if should_not_contain and should_not_contain.lower() in lower:
        return False, f"unexpected '{should_not_contain}' in answer"
    return True, ""


def main() -> None:
    passed = 0
    failed = 0

    for prompt, expected_tool, should_contain, should_not_contain in CASES:
        result = run_agent(prompt)

        tool_ok = result.selected_tool == expected_tool
        answer_ok, answer_reason = check_answer(result.answer, should_contain, should_not_contain)
        ok = tool_ok and answer_ok

        if ok:
            passed += 1
        else:
            failed += 1
            reasons = []
            if not tool_ok:
                reasons.append(f"tool: expected={expected_tool} actual={result.selected_tool}")
            if not answer_ok:
                reasons.append(f"answer: {answer_reason}")
            print({
                "prompt": prompt,
                "ok": False,
                "reasons": reasons,
            })

    total = len(CASES)
    print({"score": f"{passed}/{total}", "passed": passed, "failed": failed})


if __name__ == "__main__":
    main()
