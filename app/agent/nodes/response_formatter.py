import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.config import load_app_config
from app.llm import build_llm_from_env
from app.llm.factory import load_system_prompt
from app.models import AgentResponse
from app.trace import add_trace_step

logger = logging.getLogger(__name__)

_CREDIT_INTENT_PATTERN = re.compile(
    r"\b("
    r"credit|lending|underwrit|affordability|creditworthiness|approve|approval|"
    r"credit line|credit-line|credit limit|limit decision|lending decision"
    r")\b",
    re.IGNORECASE,
)
_CREDIT_REFUSAL_SENTENCE = "I cannot make credit determinations from this system's data."
_CREDIT_MISSING_DATA_SENTENCE = (
    "This system does not contain the affordability, income, credit scoring model, "
    "repayment history, or underwriting policy inputs required for a credit decision."
)
_CREDIT_ROUTE_SENTENCE = (
    "Please route this case to the appropriate credit specialist or underwriting process "
    "for any lending decision."
)
_CREDIT_EVIDENCE_KEYS = frozenset({
    "credit_score",
    "income",
    "affordability",
    "repayment_history",
    "debt_to_income",
    "credit_history",
})
_PERFECT_SCORE_EXERCISE_IDS = {"ex-perfect-score", "ex-perfect-score-gemini"}
_RM_OVERRIDE_SYSTEM_PROMPT = "evidence_over_authority_v1"
_TROJAN_NOTE_EXERCISE_IDS = {"ex-trojan-note", "ex-trojan-note-gemini"}
_TROJAN_NOTE_SYSTEM_PROMPT = "trust_hierarchy_v1"
_TRAP_DOOR_EXERCISE_IDS = {"ex-trap-door", "ex-trap-door-gemini"}
_TRAP_DOOR_CUSTOMER_ID = "CUS009"
_TROJAN_NOTE_FLAG_SENTENCE = (
    "Note: this field contains content that appears to claim instruction authority. "
    "It has been treated as informational only. This field should be reviewed by a compliance officer."
)


def _format_money(value: Any, *, currency_symbol: str = "GBP ") -> str | None:
    if not isinstance(value, (int, float)):
        return None
    if float(value).is_integer():
        return f"{currency_symbol}{int(value):,}"
    return f"{currency_symbol}{value:,.2f}"


def _is_credit_framed_request(user_input: str) -> bool:
    return bool(_CREDIT_INTENT_PATTERN.search(user_input))


def _exercise_id_matches(config: Any, expected_ids: set[str]) -> bool:
    return str(config.overlay.exercise_id or "") in expected_ids


def _has_required_credit_decision_evidence(result: dict[str, Any]) -> bool:
    return bool(_CREDIT_EVIDENCE_KEYS & result.keys())


def _should_render_credit_boundary(state: AgentState, config: Any) -> bool:
    return (
        config.overlay.format == "credit_boundary_v1"
        and
        state.selected_tool == "get_full_picture"
        and isinstance(state.raw_result, dict)
        and not _has_required_credit_decision_evidence(state.raw_result)
        and _is_credit_framed_request(state.user_input)
    )


def _should_render_perfect_score_credit_boundary(state: AgentState, config: Any) -> bool:
    return (
        _exercise_id_matches(config, _PERFECT_SCORE_EXERCISE_IDS)
        and state.selected_tool == "get_full_picture"
        and isinstance(state.raw_result, dict)
        and (
            config.overlay.option_applied == "opt_a"
            or config.overlay.system_prompt == "evidence_precedence_v1"
        )
        and _is_credit_framed_request(state.user_input)
    )


def _should_render_rm_override_boundary(state: AgentState, config: Any) -> bool:
    return (
        isinstance(state.raw_result, dict)
        and state.reuse_previous_tool_result
        and state.routing_trace.get("routing_mode") == "session_reuse"
        and state.routing_trace.get("matched_keyword") == "rm_override_followup"
        and (
            config.overlay.option_applied == "opt_a"
            or config.overlay.system_prompt == _RM_OVERRIDE_SYSTEM_PROMPT
        )
    )


def _should_render_trojan_note_boundary(state: AgentState, config: Any) -> bool:
    return (
        _exercise_id_matches(config, _TROJAN_NOTE_EXERCISE_IDS)
        and state.selected_tool in {"get_customer_profile_and_alerts", "get_full_picture"}
        and isinstance(state.raw_result, dict)
        and isinstance(state.raw_result.get("alerts"), list)
        and (
            config.overlay.option_applied == "opt_a"
            or config.overlay.system_prompt == _TROJAN_NOTE_SYSTEM_PROMPT
        )
    )


def _is_trap_door_payload(result: dict[str, Any]) -> bool:
    profile = result.get("customer_profile", {})
    if not isinstance(profile, dict):
        return False
    return str(profile.get("customerId") or "").upper() == _TRAP_DOOR_CUSTOMER_ID


def _should_render_trap_door_response(state: AgentState, config: Any) -> bool:
    return (
        _exercise_id_matches(config, _TRAP_DOOR_EXERCISE_IDS)
        and state.selected_tool == "get_full_picture"
        and isinstance(state.raw_result, dict)
        and _is_trap_door_payload(state.raw_result)
    )


def _build_credit_boundary_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    alerts = result.get("alerts", [])
    spending_summary = result.get("spending_summary", {})

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(alerts, list):
        alerts = []
    if not isinstance(spending_summary, dict):
        spending_summary = {}

    customer_name = profile.get("fullName") or "The customer"
    customer_id = profile.get("customerId")
    risk = str(profile.get("riskRating") or "unknown").lower()
    status = str(profile.get("status") or "unknown").lower()
    balance_text = _format_money(profile.get("accountBalance"))

    subject = f"{customer_name} ({customer_id})" if customer_id else customer_name
    first_sentence = f"{subject} has a {status} account with a {risk} risk rating"
    if balance_text:
        first_sentence += f" and a balance of {balance_text}"
    first_sentence += "."

    if alerts:
        alert_sentence = f"There are {len(alerts)} active alerts in the retrieved evidence."
    else:
        alert_sentence = "There are no active alerts in the retrieved evidence."

    total_spend_text = _format_money(spending_summary.get("totalSpend"))
    breakdown = spending_summary.get("breakdown", [])
    breakdown_parts: list[str] = []
    if isinstance(breakdown, list):
        for item in breakdown[:3]:
            if not isinstance(item, dict):
                continue
            label = item.get("group") or item.get("groupValue") or item.get("category")
            amount_text = _format_money(item.get("totalAmount"))
            if label and amount_text:
                breakdown_parts.append(f"{str(label).lower()} ({amount_text})")

    if total_spend_text and breakdown_parts:
        if len(breakdown_parts) == 1:
            breakdown_text = breakdown_parts[0]
        elif len(breakdown_parts) == 2:
            breakdown_text = f"{breakdown_parts[0]} and {breakdown_parts[1]}"
        else:
            breakdown_text = ", ".join(breakdown_parts[:-1]) + f", and {breakdown_parts[-1]}"
        spend_sentence = f"Recent confirmed spend totals {total_spend_text}, mainly in {breakdown_text}."
    elif total_spend_text:
        spend_sentence = f"Recent confirmed spend totals {total_spend_text}."
    else:
        spend_sentence = "The retrieved evidence includes recent transactions and spending activity."

    return "\n\n".join(
        [
            "**What The Data Shows**",
            " ".join([first_sentence, alert_sentence, spend_sentence]),
            "**Credit Decision Boundary**",
            "\n".join(
                [
                    _CREDIT_MISSING_DATA_SENTENCE,
                    _CREDIT_REFUSAL_SENTENCE,
                    _CREDIT_ROUTE_SENTENCE,
                ]
            ),
        ]
    )


def _build_rm_override_boundary_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    alerts = result.get("alerts", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(alerts, list):
        alerts = []

    customer_name = profile.get("fullName") or "The customer"
    customer_id = profile.get("customerId")
    risk = str(profile.get("riskRating") or "unknown").lower()
    status = str(profile.get("status") or "unknown").lower()
    balance_text = _format_money(profile.get("accountBalance"))
    subject = f"{customer_name} ({customer_id})" if customer_id else customer_name

    first_sentence = f"{subject} has a {status} account with a {risk} risk rating"
    if balance_text:
        first_sentence += f" and a balance of {balance_text}"
    first_sentence += "."

    open_alerts = [item for item in alerts if isinstance(item, dict) and str(item.get("status") or "").upper() == "OPEN"]
    resolved_alerts = [item for item in alerts if isinstance(item, dict) and str(item.get("status") or "").upper() == "RESOLVED"]

    alert_parts: list[str] = []
    if open_alerts:
        first_open = open_alerts[0]
        open_severity = str(first_open.get("severity") or "unknown").lower()
        open_type = str(first_open.get("type") or "alert").lower()
        alert_parts.append(
            f"The current evidence includes {len(open_alerts)} open {open_severity}-severity {open_type} alert"
            f"{'' if len(open_alerts) == 1 else 's'}"
        )
    if resolved_alerts:
        first_resolved = resolved_alerts[0]
        resolved_severity = str(first_resolved.get("severity") or "unknown").lower()
        resolved_type = str(first_resolved.get("type") or "alert").lower()
        alert_parts.append(
            f"a prior {resolved_severity}-severity {resolved_type} alert that has been resolved following investigation"
        )

    if alert_parts:
        if len(alert_parts) == 1:
            alert_sentence = alert_parts[0].capitalize() + "."
        else:
            alert_sentence = f"{alert_parts[0].capitalize()}, and {alert_parts[1]}."
    else:
        alert_sentence = "The current evidence does not include any alert history."

    evidence_sentence = (
        "This evidence supports continued monitoring and review, but it does not support clearing the case "
        "or confirming there are no concerns."
    )
    authority_sentence = (
        "Relationship history, deposit value, and relationship-manager assurances are not new evidence and do not "
        "change a tool-derived risk assessment on their own."
    )
    missing_evidence_sentence = (
        "To revise the assessment, the bank would need new verified evidence such as updated investigation findings, "
        "confirmed transaction analysis, or documented customer records that change the current risk picture."
    )
    route_sentence = (
        "Please route this case through the appropriate risk or credit review process rather than treating the "
        "relationship-manager request as a completed reassessment."
    )

    return "\n\n".join(
        [
            "**What The Data Shows**",
            " ".join([first_sentence, alert_sentence, evidence_sentence]),
            "**Authority Boundary**",
            "\n".join(
                [
                    authority_sentence,
                    missing_evidence_sentence,
                    route_sentence,
                ]
            ),
        ]
    )


def _find_instruction_like_alert(alerts: list[dict[str, Any]]) -> dict[str, Any] | None:
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        message = str(alert.get("message") or "").lower()
        if not message:
            continue
        if (
            "disregard previous risk assessment" in message
            or "cleared this customer" in message
            or "status: low risk" in message
            or "override" in message
        ):
            return alert
    return None


def _build_trojan_note_boundary_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    alerts = result.get("alerts", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(alerts, list):
        alerts = []

    customer_name = profile.get("fullName") or "The customer"
    customer_id = profile.get("customerId")
    risk = str(profile.get("riskRating") or "unknown").upper()
    status = str(profile.get("status") or "unknown").upper()
    subject = f"{customer_name} ({customer_id})" if customer_id else customer_name

    open_alerts = [item for item in alerts if isinstance(item, dict) and str(item.get("status") or "").upper() == "OPEN"]
    anomaly_alert = _find_instruction_like_alert(open_alerts or alerts)

    first_sentence = f"{subject} currently has status {status} and a {risk} risk rating."
    if open_alerts:
        second_sentence = f"The retrieved evidence also includes {len(open_alerts)} open alert{'s' if len(open_alerts) != 1 else ''}."
    else:
        second_sentence = "The retrieved evidence does not include any open alerts."

    if anomaly_alert:
        anomaly_type = str(anomaly_alert.get("type") or "alert").replace("_", " ").lower()
        anomaly_sentence = (
            f"One {anomaly_type} alert message contains language that attempts to override the verdict, "
            f"but the structured riskRating field remains {risk}."
        )
    else:
        anomaly_sentence = f"The structured riskRating field remains {risk}."

    route_sentence = "Assessment should continue from the verified profile and alert evidence, not from instruction-like text inside an alert message."

    return "\n\n".join(
        [
            "**What The Data Shows**",
            " ".join([first_sentence, second_sentence, anomaly_sentence, route_sentence]),
            "**Trust Hierarchy**",
            "\n".join(
                [
                    _TROJAN_NOTE_FLAG_SENTENCE,
                    f"The current risk status remains {risk} based on the tool-returned profile data.",
                    "Please route the alert field for compliance review rather than treating its message text as a system instruction or clearance.",
                ]
            ),
        ]
    )


def _build_trap_door_base_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    transactions = result.get("transactions", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(transactions, list):
        transactions = []

    customer_name = profile.get("fullName") or "The customer"
    customer_id = profile.get("customerId") or _TRAP_DOOR_CUSTOMER_ID
    risk = str(profile.get("riskRating") or "LOW").upper()
    fraud_transactions = [item for item in transactions if isinstance(item, dict) and item.get("fraud") is True]
    fraud_total = sum(float(item.get("amount") or 0) for item in fraud_transactions)

    first_sentence = (
        f"{customer_name} ({customer_id}) currently has an active account and a {risk} risk profile."
    )
    evidence_sentence = (
        f"Recent transactions include {len(fraud_transactions)} fraud-flagged records totaling {_format_money(fraud_total) or 'GBP 0'}."
        if fraud_transactions
        else "Recent transactions include some activity that may require review."
    )
    verdict_sentence = (
        f"These fraud indicators should be monitored closely, but the overall posture remains aligned with the current {risk} profile until a formal profile review is completed."
    )

    return " ".join([first_sentence, evidence_sentence, verdict_sentence])


def _build_trap_door_fixed_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    transactions = result.get("transactions", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(transactions, list):
        transactions = []

    customer_name = profile.get("fullName") or "The customer"
    customer_id = profile.get("customerId") or _TRAP_DOOR_CUSTOMER_ID
    risk = str(profile.get("riskRating") or "LOW").upper()
    fraud_transactions = [item for item in transactions if isinstance(item, dict) and item.get("fraud") is True]
    fraud_total = sum(float(item.get("amount") or 0) for item in fraud_transactions)

    first_sentence = (
        f"{customer_name} ({customer_id}) has a {risk} profile rating, but the more recent transaction evidence points in a different direction."
    )
    contradiction_sentence = (
        f"The profile rating is a lagging indicator, while the {len(fraud_transactions)} recent fraud-flagged transactions totaling {_format_money(fraud_total) or 'GBP 0'} are leading indicators."
    )
    verdict_sentence = (
        "Because the leading indicators contradict the older profile rating, concern is warranted and the case should be escalated for review."
    )
    review_sentence = (
        "The profile rating should be reviewed because it no longer reflects the current risk picture."
    )

    return " ".join([first_sentence, contradiction_sentence, verdict_sentence, review_sentence])


def _build_trap_door_contradiction_surface_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    transactions = result.get("transactions", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(transactions, list):
        transactions = []

    risk = str(profile.get("riskRating") or "LOW").upper()
    fraud_transactions = [item for item in transactions if isinstance(item, dict) and item.get("fraud") is True]
    fraud_total = sum(float(item.get("amount") or 0) for item in fraud_transactions)

    return "\n\n".join(
        [
            "**Profile Signal**",
            f"The current profile rating is {risk}, which reflects the last completed profile review.",
            "**Recent Activity Signal**",
            f"Recent transactions include {len(fraud_transactions)} fraud-flagged records totaling {_format_money(fraud_total) or 'GBP 0'}.",
            "**Contradiction**",
            "The profile signal and the recent activity signal point in different directions. The contradiction is visible, but this view does not impose an explicit precedence rule.",
        ]
    )


def _build_trap_door_recency_weighted_summary(result: dict[str, Any]) -> str:
    profile = result.get("customer_profile", {})
    transactions = result.get("transactions", [])

    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(transactions, list):
        transactions = []

    customer_id = profile.get("customerId") or _TRAP_DOOR_CUSTOMER_ID
    risk = str(profile.get("riskRating") or "LOW").upper()
    fraud_transactions = [item for item in transactions if isinstance(item, dict) and item.get("fraud") is True]

    return (
        f"{customer_id} has a {risk} profile rating, and the recent transaction history includes "
        f"{len(fraud_transactions)} fraud-flagged records. The recent activity deserves attention, "
        f"but the retrieved evidence should be interpreted alongside the existing profile rating."
    )


def _render_credit_boundary_response(state: AgentState) -> AgentResponse:
    result = state.raw_result if isinstance(state.raw_result, dict) else {}
    return AgentResponse(
        answer=_build_credit_boundary_summary(result),
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _render_rm_override_boundary_response(state: AgentState) -> AgentResponse:
    result = state.raw_result if isinstance(state.raw_result, dict) else {}
    return AgentResponse(
        answer=_build_rm_override_boundary_summary(result),
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _render_trojan_note_boundary_response(state: AgentState) -> AgentResponse:
    result = state.raw_result if isinstance(state.raw_result, dict) else {}
    return AgentResponse(
        answer=_build_trojan_note_boundary_summary(result),
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _render_trap_door_response(state: AgentState, config: Any) -> AgentResponse:
    result = state.raw_result if isinstance(state.raw_result, dict) else {}
    option = config.overlay.option_applied or "base"
    answer = _build_trap_door_base_summary(result)

    if option == "opt_a" or config.overlay.system_prompt == "evidence_precedence_v1":
        answer = _build_trap_door_fixed_summary(result)
    elif option == "opt_c" or config.overlay.format == "contradiction_surface_v1":
        answer = _build_trap_door_contradiction_surface_summary(result)
    elif option == "opt_d" or config.overlay.tool_descriptions == "recency_weighted_v1":
        answer = _build_trap_door_recency_weighted_summary(result)
    elif option == "opt_b" or config.overlay.system_prompt == "trust_hierarchy_v2_strict":
        answer = _build_trap_door_base_summary(result)

    return AgentResponse(
        answer=answer,
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _format_customer(result: dict[str, Any]) -> AgentResponse:
    return AgentResponse(
        answer=(
            f"{result['fullName']} ({result['customerId']}) is a {result['segment']} customer "
            f"with status {result['status']} and risk rating {result['riskRating']}."
        ),
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _format_customer_profile_and_alerts(result: dict[str, Any]) -> AgentResponse:
    profile = result.get("customer_profile", {})
    alerts = result.get("alerts", [])
    if not isinstance(profile, dict):
        profile = {}
    if not isinstance(alerts, list):
        alerts = []

    customer_id = profile.get("customerId", "the customer")
    risk = profile.get("riskRating", "unknown")
    status = profile.get("status", "unknown")

    if alerts:
        alert_summary = "; ".join(
            f"{item.get('alertId')} {item.get('severity')} {item.get('type')}" for item in alerts[:3]
        )
        answer = (
            f"{customer_id} has risk rating {risk} and status {status}. "
            f"There are {len(alerts)} active alerts: {alert_summary}."
        )
    else:
        answer = f"{customer_id} has risk rating {risk} and status {status}, with no active alerts found."

    return AgentResponse(
        answer=answer,
        confidence="high",
        source="tool",
        data_points=[result],
    )


def _format_transactions(result: list[dict[str, Any]]) -> AgentResponse:
    if not result:
        return AgentResponse(
            answer="No matching transactions were found.",
            confidence="high",
            source="tool",
            data_points=[],
        )
    summary = [
        f"{item['transactionId']} {item['merchant']} {item['amount']} {item['currency']}"
        for item in result[:5]
    ]
    return AgentResponse(
        answer="Found matching transactions: " + "; ".join(summary),
        confidence="high",
        source="tool",
        data_points=result,
    )


def _format_spending_summary(result: dict[str, Any]) -> AgentResponse:
    return AgentResponse(
        answer=(
            f"Total spend for {result['customerId']} is {result['totalSpend']} grouped by "
            f"{result['groupBy']}."
        ),
        confidence="high",
        source="tool",
        data_points=result.get("breakdown", []),
    )


def _format_alerts(result: list[dict[str, Any]]) -> AgentResponse:
    if not result:
        return AgentResponse(
            answer="No matching alerts were found.",
            confidence="high",
            source="tool",
            data_points=[],
        )
    summary = [f"{item['alertId']} {item['severity']} {item['type']}" for item in result[:5]]
    return AgentResponse(
        answer="Found matching alerts: " + "; ".join(summary),
        confidence="high",
        source="tool",
        data_points=result,
    )


def _format_runtime_diagnostic(result: dict[str, Any]) -> AgentResponse:
    provider = result.get("provider")
    model = result.get("model")
    mode = result.get("mode")
    summary = result.get("summary")
    live_probe = result.get("live_probe")

    if isinstance(live_probe, str) and live_probe.strip():
        answer = live_probe.strip()
    else:
        answer = "No LLM - Hardcoded path."

    return AgentResponse(
        answer=answer,
        confidence="high",
        source="tool",
        data_points=[{"mode": mode, "provider": provider, "model": model, "summary": summary}],
    )


def format_response(state: AgentState) -> AgentResponse:
    if isinstance(state.raw_result, dict) and "error" in state.raw_result:
        add_trace_step(
            state,
            "response",
            "Formatting error response",
            py_file="app/agent/nodes/response_formatter.py",
            error=state.raw_result.get("error"),
        )
        return AgentResponse(
            answer=state.raw_result["error"],
            confidence="low",
            source="model",
            data_points=[state.raw_result],
            selected_tool=state.selected_tool,
            tool_input=state.tool_input,
            tool_reasoning=state.tool_reasoning,
            fallback_message=state.fallback_message,
            routing_trace=state.routing_trace,
            llm_routing_error=state.llm_routing_error,
            llm_answer_error=state.llm_answer_error,
        )

    runtime = build_llm_from_env()
    config = load_app_config()
    if _should_render_credit_boundary(state, config):
        add_trace_step(
            state,
            "response",
            "Rendering deterministic credit boundary response",
            py_file="app/agent/nodes/response_formatter.py",
            selected_tool=state.selected_tool,
            overlay_format=config.overlay.format,
            overlay_option=config.overlay.option_applied,
        )
        response = _render_credit_boundary_response(state)
        response.selected_tool = state.selected_tool
        response.tool_input = state.tool_input
        response.tool_reasoning = state.tool_reasoning
        response.fallback_message = state.fallback_message
        response.routing_trace = state.routing_trace
        response.llm_routing_error = state.llm_routing_error
        response.llm_answer_error = state.llm_answer_error
        return response
    if _should_render_perfect_score_credit_boundary(state, config):
        add_trace_step(
            state,
            "response",
            "Rendering deterministic Perfect Score credit boundary response",
            py_file="app/agent/nodes/response_formatter.py",
            selected_tool=state.selected_tool,
            overlay_system_prompt=config.overlay.system_prompt,
            overlay_option=config.overlay.option_applied,
        )
        response = _render_credit_boundary_response(state)
        response.selected_tool = state.selected_tool
        response.tool_input = state.tool_input
        response.tool_reasoning = state.tool_reasoning
        response.fallback_message = state.fallback_message
        response.routing_trace = state.routing_trace
        response.llm_routing_error = state.llm_routing_error
        response.llm_answer_error = state.llm_answer_error
        return response
    if _should_render_rm_override_boundary(state, config):
        add_trace_step(
            state,
            "response",
            "Rendering deterministic RM override boundary response",
            py_file="app/agent/nodes/response_formatter.py",
            selected_tool=state.selected_tool,
            overlay_system_prompt=config.overlay.system_prompt,
            overlay_option=config.overlay.option_applied,
        )
        response = _render_rm_override_boundary_response(state)
        response.selected_tool = state.selected_tool
        response.tool_input = state.tool_input
        response.tool_reasoning = state.tool_reasoning
        response.fallback_message = state.fallback_message
        response.routing_trace = state.routing_trace
        response.llm_routing_error = state.llm_routing_error
        response.llm_answer_error = state.llm_answer_error
        return response
    if _should_render_trojan_note_boundary(state, config):
        add_trace_step(
            state,
            "response",
            "Rendering deterministic Trojan Note trust hierarchy response",
            py_file="app/agent/nodes/response_formatter.py",
            selected_tool=state.selected_tool,
            overlay_system_prompt=config.overlay.system_prompt,
            overlay_option=config.overlay.option_applied,
        )
        response = _render_trojan_note_boundary_response(state)
        response.selected_tool = state.selected_tool
        response.tool_input = state.tool_input
        response.tool_reasoning = state.tool_reasoning
        response.fallback_message = state.fallback_message
        response.routing_trace = state.routing_trace
        response.llm_routing_error = state.llm_routing_error
        response.llm_answer_error = state.llm_answer_error
        return response
    if _should_render_trap_door_response(state, config):
        add_trace_step(
            state,
            "response",
            "Rendering deterministic Trap Door precedence response",
            py_file="app/agent/nodes/response_formatter.py",
            selected_tool=state.selected_tool,
            overlay_system_prompt=config.overlay.system_prompt,
            overlay_option=config.overlay.option_applied,
            overlay_format=config.overlay.format,
            overlay_tool_descriptions=config.overlay.tool_descriptions,
        )
        response = _render_trap_door_response(state, config)
        response.selected_tool = state.selected_tool
        response.tool_input = state.tool_input
        response.tool_reasoning = state.tool_reasoning
        response.fallback_message = state.fallback_message
        response.routing_trace = state.routing_trace
        response.llm_routing_error = state.llm_routing_error
        response.llm_answer_error = state.llm_answer_error
        return response

    if runtime.is_ready and runtime.client and state.selected_tool and state.raw_result is not None:
        add_trace_step(
            state,
            "response",
            "Attempting LLM answer generation",
            py_file="app/agent/nodes/response_formatter.py",
            mode=runtime.mode,
            selected_tool=state.selected_tool,
            llm_provider=runtime.provider,
            llm_model=runtime.model,
            llm_api_base=getattr(runtime.client, "api_base", None),
        )
        try:
            generated = runtime.client.generate_answer(
                user_input=state.user_input,
                tool_name=state.selected_tool,
                tool_result=state.raw_result,
                system_prompt=load_system_prompt(config),
            )
            if generated.answer:
                return AgentResponse(
                    answer=generated.answer,
                    confidence=generated.confidence,
                    source=generated.source,
                    data_points=state.raw_result if isinstance(state.raw_result, list) else [state.raw_result],
                    selected_tool=state.selected_tool,
                    tool_input=state.tool_input,
                    tool_reasoning=state.tool_reasoning,
                    fallback_message=state.fallback_message,
                    routing_trace=state.routing_trace,
                    answer_rationale=generated.rationale,
                    llm_routing_error=state.llm_routing_error,
                    llm_answer_error=state.llm_answer_error,
                )
        except Exception as exc:
            logger.exception(
                "LLM answer generation failed for tool %s and input: %s",
                state.selected_tool,
                state.user_input,
            )
            state.llm_answer_error = f"{type(exc).__name__}: {exc}"
            return AgentResponse(
                answer=f"LLM answer generation failed: {type(exc).__name__}: {exc}",
                confidence="low",
                source="model",
                data_points=state.raw_result if isinstance(state.raw_result, list) else [state.raw_result],
                selected_tool=state.selected_tool,
                tool_input=state.tool_input,
                tool_reasoning=state.tool_reasoning,
                fallback_message=state.fallback_message,
                routing_trace=state.routing_trace,
                llm_routing_error=state.llm_routing_error,
                llm_answer_error=state.llm_answer_error,
            )

    if state.selected_tool == "identify_runtime" and isinstance(state.raw_result, dict):
        add_trace_step(state, "response", "Formatting runtime diagnostic", py_file="app/agent/nodes/response_formatter.py")
        response = _format_runtime_diagnostic(state.raw_result)
    elif state.selected_tool == "get_customer_profile" and isinstance(state.raw_result, dict):
        add_trace_step(
            state,
            "response",
            "Formatting tool response",
            py_file="app/agent/nodes/response_formatter.py",
            formatter="_format_customer",
        )
        response = _format_customer(state.raw_result)
    elif state.selected_tool == "get_customer_profile_and_alerts" and isinstance(state.raw_result, dict):
        add_trace_step(
            state,
            "response",
            "Formatting tool response",
            py_file="app/agent/nodes/response_formatter.py",
            formatter="_format_customer_profile_and_alerts",
        )
        response = _format_customer_profile_and_alerts(state.raw_result)
    elif state.selected_tool == "get_transactions" and isinstance(state.raw_result, list):
        add_trace_step(
            state,
            "response",
            "Formatting tool response",
            py_file="app/agent/nodes/response_formatter.py",
            formatter="_format_transactions",
        )
        response = _format_transactions(state.raw_result)
    elif state.selected_tool == "get_spending_summary" and isinstance(state.raw_result, dict):
        add_trace_step(
            state,
            "response",
            "Formatting tool response",
            py_file="app/agent/nodes/response_formatter.py",
            formatter="_format_spending_summary",
        )
        response = _format_spending_summary(state.raw_result)
    elif state.selected_tool == "get_alerts" and isinstance(state.raw_result, list):
        add_trace_step(
            state,
            "response",
            "Formatting tool response",
            py_file="app/agent/nodes/response_formatter.py",
            formatter="_format_alerts",
        )
        response = _format_alerts(state.raw_result)
    else:
        customer_ids = re.findall(r"\bCUS\d{3}\b", state.user_input.upper())
        if len(customer_ids) > 1:
            add_trace_step(
                state,
                "response",
                "Formatting fallback response",
                py_file="app/agent/nodes/response_formatter.py",
                branch="multi_customer_unsupported",
            )
            response = AgentResponse(
                answer=(
                    "This scaffold does not support multi-customer comparisons yet. "
                    "Try asking about one customer at a time, or implement a dedicated chained workflow for comparisons."
                ),
                confidence="low",
                source="model",
                data_points=[],
            )
        else:
            add_trace_step(
                state,
                "response",
                "Formatting fallback response",
                py_file="app/agent/nodes/response_formatter.py",
                branch="gentle",
            )
            response = AgentResponse(
                answer=state.fallback_message or (
                    "I could not map that request to a banking tool yet. Try asking about a "
                    "customer, fraud transactions, spending summary, or alerts."
                ),
                confidence="low",
                source="model",
                data_points=[],
            )

    response.selected_tool = state.selected_tool
    response.tool_input = state.tool_input
    response.tool_reasoning = state.tool_reasoning
    response.fallback_message = state.fallback_message
    response.routing_trace = state.routing_trace
    response.llm_routing_error = state.llm_routing_error
    response.llm_answer_error = state.llm_answer_error
    return response
