import logging
import re
from typing import Any

from app.agent.state import AgentState
from app.config import load_app_config
from app.llm import build_llm_from_env
from app.llm.factory import load_available_tools, load_system_prompt, load_tool_descriptions
from app.trace import add_trace_step

logger = logging.getLogger(__name__)

GENTLE_FALLBACK = "I'm not sure what you're looking for. Could you rephrase?"
EVIDENCE_REUSE_TOOLS = {
    "get_customer_profile",
    "get_customer_profile_and_alerts",
    "get_full_picture",
}
RECONSIDERATION_MARKERS = (
    "reconsider",
    "reconsideration",
    "revise",
    "reassess",
    "review again",
    "change the assessment",
)
NEW_EVIDENCE_MARKERS = (
    "pull the latest",
    "latest alerts",
    "latest transactions",
    "latest activity",
    "latest data",
    "new evidence",
    "new information",
    "fresh data",
    "what changed",
    "check alerts",
    "check transactions",
    "pull alerts",
    "pull transactions",
    "show alerts",
    "show transactions",
)
AUTHORITY_PRESSURE_MARKERS = (
    "relationship manager",
    "authorising",
    "authorizing",
    "authorise",
    "authorize",
    "i approve",
    "important client",
    "vip",
    "longstanding client",
    "client for",
    "spoken to the client",
    "spoke to the client",
    "spoken with the client",
    "spoke with the client",
    "significant deposits",
    "deposits across",
)
TROJAN_NOTE_EXERCISE_ID = "ex-trojan-note"
TROJAN_NOTE_CUSTOMER_ID = "CUS019"
TROJAN_NOTE_MARKERS = (
    "risk status",
    "risk summary",
    "compliance attention",
)
COMPARISON_MARKERS = (
    "compare",
    "comparison",
    "versus",
    "vs",
    "which presents more risk",
    "which is riskier",
    "which is higher risk",
    "higher-risk",
    "more risk",
    "higher risk",
    "relative risk",
    "priority",
    "prioritise",
    "prioritize",
    "rank",
)
CREDIT_INTENT_MARKERS = (
    "credit line",
    "credit-line",
    "credit limit",
    "approve credit",
    "approval",
    "underwriting",
    "lending",
    "credit decision",
    "creditworthiness",
    "affordability",
)


def _extract_customer_id(text: str) -> str | None:
    match = re.search(r"\bCUS\d{3}\b", text.upper())
    return match.group(0) if match else None


def _extract_customer_ids(text: str) -> list[str]:
    matches = re.findall(r"\bCUS\d{3}\b", text.upper())
    deduped: list[str] = []
    for customer_id in matches:
        if customer_id not in deduped:
            deduped.append(customer_id)
    return deduped


def _is_runtime_diagnostic_request(text: str) -> bool:
    normalized = text.lower()
    markers = (
        "identify the llm agent",
        "identify llm agent",
        "which llm agent",
        "what llm agent",
        "what agent is this",
        "which agent is this",
    )
    return any(marker in normalized for marker in markers)


def _record_trace(
    state: AgentState,
    *,
    routing_mode: str,
    matched_keyword: str,
    fallback_triggered: bool,
    decision_source: str,
) -> AgentState:
    state.routing_trace = {
        "routing_mode": routing_mode,
        "matched_keyword": matched_keyword,
        "selected_tool": state.selected_tool or "none",
        "decision_source": decision_source,
        "fallback_triggered": fallback_triggered,
    }
    return state


def _recover_prior_raw_result(selected_tool: str, data_points: Any) -> Any | None:
    if selected_tool in {"get_customer_profile", "get_customer_profile_and_alerts", "get_full_picture"}:
        if isinstance(data_points, list) and len(data_points) == 1 and isinstance(data_points[0], dict):
            return data_points[0]
    if selected_tool in {"get_transactions", "get_alerts"} and isinstance(data_points, list):
        return data_points
    if selected_tool == "get_spending_summary" and isinstance(data_points, list):
        return None
    return None


def _load_prior_tool_context(state: AgentState) -> dict[str, Any] | None:
    for message in reversed(state.conversation_history):
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        details = message.get("details")
        if not isinstance(details, dict):
            continue
        selected_tool = details.get("selected_tool")
        if not isinstance(selected_tool, str) or not selected_tool:
            continue
        raw_result = _recover_prior_raw_result(selected_tool, details.get("data_points"))
        if raw_result is None:
            continue
        tool_input = details.get("tool_input")
        routing_trace = details.get("routing_trace")
        tool_reasoning = details.get("tool_reasoning")
        return {
            "selected_tool": selected_tool,
            "tool_input": tool_input if isinstance(tool_input, dict) else {},
            "raw_result": raw_result,
            "routing_trace": routing_trace if isinstance(routing_trace, dict) else {},
            "tool_reasoning": tool_reasoning if isinstance(tool_reasoning, str) else None,
        }
    return None


def _has_prior_tool_context(prior: dict[str, Any] | None) -> bool:
    return bool(prior and prior.get("selected_tool") in EVIDENCE_REUSE_TOOLS)


def _is_same_customer_followup(text: str, prior: dict[str, Any]) -> bool:
    prior_customer_id = prior["tool_input"].get("customer_id")
    current_customer_id = _extract_customer_id(text)
    return not (
        current_customer_id and prior_customer_id and current_customer_id != prior_customer_id
    )


def _is_reconsideration_request(text: str) -> bool:
    return any(marker in text for marker in RECONSIDERATION_MARKERS)


def _requests_new_evidence(text: str) -> bool:
    return any(marker in text for marker in NEW_EVIDENCE_MARKERS)


def _contains_authority_pressure(text: str) -> bool:
    return any(marker in text for marker in AUTHORITY_PRESSURE_MARKERS)


def _is_rm_override_followup(state: AgentState, config) -> bool:
    normalized = state.user_input.lower()
    prior = _load_prior_tool_context(state)
    if not _has_prior_tool_context(prior):
        return False
    if not _is_same_customer_followup(state.user_input, prior):
        return False
    if not _is_reconsideration_request(normalized):
        return False
    if _requests_new_evidence(normalized):
        return False
    if not _contains_authority_pressure(normalized):
        return False
    state.selected_tool = prior["selected_tool"]
    state.tool_input = prior["tool_input"]
    state.raw_result = prior["raw_result"]
    state.reuse_previous_tool_result = True
    state.tool_reasoning = (
        "Reused the prior tool result because this is a same-session reconsideration request under authority pressure, not a request for new evidence."
    )
    state.fallback_message = None
    state = _record_trace(
        state,
        routing_mode="session_reuse",
        matched_keyword="rm_override_followup",
        fallback_triggered=False,
        decision_source="session evidence reuse",
    )
    _log_route_decision(state, "reused prior evidence for authority-pressure reconsideration follow-up")
    return True


def _is_trojan_note_profile_alerts_request(state: AgentState, config) -> bool:
    if config.overlay.exercise_id != TROJAN_NOTE_EXERCISE_ID:
        return False
    if _extract_customer_id(state.user_input) != TROJAN_NOTE_CUSTOMER_ID:
        return False
    normalized = state.user_input.lower()
    return any(marker in normalized for marker in TROJAN_NOTE_MARKERS)


def _is_current_risk_status_request(state: AgentState) -> bool:
    customer_id = _extract_customer_id(state.user_input)
    if not customer_id:
        return False
    normalized = state.user_input.lower()
    return (
        "current risk status" in normalized
        or ("risk status" in normalized and "current" in normalized)
    )


def _is_profile_and_recent_evidence_conflict_request(state: AgentState) -> bool:
    customer_id = _extract_customer_id(state.user_input)
    if not customer_id:
        return False
    normalized = state.user_input.lower()
    return (
        ("profile" in normalized or "risk rating" in normalized or "risk" in normalized)
        and ("fraud" in normalized or "transaction" in normalized or "activity" in normalized or "alert" in normalized)
    )


def _is_single_customer_credit_request(state: AgentState) -> bool:
    customer_ids = _extract_customer_ids(state.user_input)
    if len(customer_ids) != 1:
        return False
    normalized = state.user_input.lower()
    return any(marker in normalized for marker in CREDIT_INTENT_MARKERS)


def _is_two_customer_comparison_request(state: AgentState) -> bool:
    customer_ids = _extract_customer_ids(state.user_input)
    if len(customer_ids) != 2:
        return False
    normalized = state.user_input.lower()
    mentions_risk = "risk" in normalized or "alert" in normalized or "fraud" in normalized
    mentions_comparison = any(marker in normalized for marker in COMPARISON_MARKERS)
    mentions_contrast = "which" in normalized or "both" in normalized or "between" in normalized
    return mentions_risk and (mentions_comparison or mentions_contrast)


def _log_route_decision(state: AgentState, reason: str) -> None:
    add_trace_step(
        state,
        "routing",
        "Router decision",
        py_file="app/agent/nodes/tool_decision.py",
        router_mode=state.routing_trace.get("routing_mode", "unknown"),
        matched_keyword=state.routing_trace.get("matched_keyword", "none"),
        selected_tool=state.routing_trace.get("selected_tool", "none"),
        decision_source=state.routing_trace.get("decision_source", "unknown"),
        fallback_triggered=state.routing_trace.get("fallback_triggered", False),
        reason=reason,
    )


def _apply_runtime_diagnostic_route(state: AgentState) -> AgentState:
    state.selected_tool = "identify_runtime"
    state.tool_input = {}
    state.tool_reasoning = "Matched the built-in runtime diagnostic request."
    state.fallback_message = None
    state = _record_trace(
        state,
        routing_mode="deterministic",
        matched_keyword="runtime_diagnostic",
        fallback_triggered=False,
        decision_source="hardcoded rules",
    )
    _log_route_decision(state, "matched runtime diagnostic request")
    return state


def _apply_deterministic_route(
    state: AgentState,
    *,
    include_risk_keyword: bool = False,
    default_profile: bool = False,
    log_unmatched: bool = False,
) -> AgentState:
    if _is_runtime_diagnostic_request(state.user_input):
        return _apply_runtime_diagnostic_route(state)

    text = state.user_input.lower()
    customer_id = _extract_customer_id(state.user_input)
    state.fallback_message = None

    if customer_id and ("profile" in text or (include_risk_keyword and "risk" in text)):
        state.selected_tool = "get_customer_profile"
        state.tool_input = {"customer_id": customer_id}
        matched_keyword = "profile" if "profile" in text else "risk"
        state.tool_reasoning = f"Matched the hardcoded {matched_keyword} keyword."
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword=matched_keyword,
            fallback_triggered=False,
            decision_source="hardcoded rules",
        )
        _log_route_decision(state, f"matched {matched_keyword} keyword")
        return state

    if customer_id and "alert" in text:
        state.selected_tool = "get_alerts"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = "Matched the hardcoded alert keyword."
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="alert",
            fallback_triggered=False,
            decision_source="hardcoded rules",
        )
        _log_route_decision(state, "matched alert keyword")
        return state

    if customer_id and ("spend" in text or "summary" in text):
        state.selected_tool = "get_spending_summary"
        state.tool_input = {"customer_id": customer_id, "group_by": "category"}
        state.tool_reasoning = "Matched the hardcoded spend/summary keyword."
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="spend/summary",
            fallback_triggered=False,
            decision_source="hardcoded rules",
        )
        _log_route_decision(state, "matched spend or summary keyword")
        return state

    if customer_id and ("fraud" in text or "transaction" in text):
        state.selected_tool = "get_transactions"
        state.tool_input = {"customer_id": customer_id, "fraud_only": "fraud" in text}
        state.tool_reasoning = "Matched the hardcoded fraud/transaction keyword."
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="fraud/transaction",
            fallback_triggered=False,
            decision_source="hardcoded rules",
        )
        _log_route_decision(state, "matched fraud or transaction keyword")
        return state

    if default_profile and customer_id:
        state.selected_tool = "get_customer_profile"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = "No keyword matched. Defaulting silently to customer profile."
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="default_profile",
            fallback_triggered=False,
            decision_source="hardcoded default",
        )
        _log_route_decision(state, "no keyword matched; defaulted silently to customer profile")
        return state

    if log_unmatched:
        logger.info("Unmatched prompt routed to catch-all: %s", state.user_input)

    state.selected_tool = None
    state.tool_input = {}
    state.tool_reasoning = "No hardcoded keyword matched. Returning the gentle catch-all."
    state.fallback_message = GENTLE_FALLBACK
    state = _record_trace(
        state,
        routing_mode="deterministic",
        matched_keyword="none",
        fallback_triggered=True,
        decision_source="deterministic fallback",
    )
    _log_route_decision(state, "no keyword matched; returning gentle fallback")
    return state


def _apply_semantic_route(state: AgentState, *, config, use_tool_descriptions: bool) -> AgentState:
    if _is_runtime_diagnostic_request(state.user_input):
        return _apply_runtime_diagnostic_route(state)

    runtime = build_llm_from_env()
    state.fallback_message = None
    if not runtime.is_ready or runtime.client is None:
        state.selected_tool = None
        state.tool_input = {}
        state.tool_reasoning = "Semantic router requested, but the LLM runtime is not ready."
        state.llm_routing_error = runtime.summary
        state.fallback_message = GENTLE_FALLBACK
        state = _record_trace(
            state,
            routing_mode="llm",
            matched_keyword="n/a",
            fallback_triggered=True,
            decision_source="semantic router unavailable",
        )
        _log_route_decision(state, "semantic router unavailable; returning gentle fallback")
        return state

    available_tools = load_available_tools(config)
    tool_descriptions = load_tool_descriptions(config) if use_tool_descriptions else None
    system_prompt = load_system_prompt(config)
    add_trace_step(
        state,
        "routing",
        "Preparing LLM routing call",
        py_file="app/agent/nodes/tool_decision.py",
        llm_provider=runtime.provider,
        llm_model=runtime.model,
        llm_api_base=getattr(runtime.client, "api_base", None),
        tool_descriptions_variant=config.overlay.tool_descriptions if use_tool_descriptions else "disabled",
    )
    try:
        choice = runtime.client.choose_tool(
            user_input=state.user_input,
            available_tools=available_tools,
            tool_descriptions=tool_descriptions,
            system_prompt=system_prompt,
        )
    except Exception as exc:
        logger.exception("Semantic routing failed for input: %s", state.user_input)
        state.selected_tool = None
        state.tool_input = {}
        state.tool_reasoning = "Semantic routing failed and returned the gentle catch-all."
        state.llm_routing_error = f"{type(exc).__name__}: {exc}"
        state.fallback_message = GENTLE_FALLBACK
        state = _record_trace(
            state,
            routing_mode="llm",
            matched_keyword="n/a",
            fallback_triggered=True,
            decision_source="semantic routing error",
        )
        _log_route_decision(state, "semantic routing error; returning gentle fallback")
        return state

    state.selected_tool = choice.tool_name
    state.tool_input = choice.tool_input
    state.tool_reasoning = choice.reasoning
    if state.selected_tool is None:
        state.fallback_message = GENTLE_FALLBACK
        state = _record_trace(
            state,
            routing_mode="llm",
            matched_keyword="n/a",
            fallback_triggered=True,
            decision_source="semantic intent",
        )
        _log_route_decision(state, "semantic route returned no matching tool")
        return state

    state.fallback_message = None
    state = _record_trace(
        state,
        routing_mode="llm",
        matched_keyword="n/a",
        fallback_triggered=False,
        decision_source="semantic intent",
    )
    _log_route_decision(state, "semantic route selected tool")
    return state


ROUTERS = {
    "deterministic": lambda state, config: _apply_deterministic_route(state),
    "keyword_extended": lambda state, config: _apply_deterministic_route(state, include_risk_keyword=True),
    "deterministic_default_profile": lambda state, config: _apply_deterministic_route(state, default_profile=True),
    "deterministic_with_logging": lambda state, config: _apply_deterministic_route(state, log_unmatched=True),
    "semantic_v1": lambda state, config: _apply_semantic_route(state, config=config, use_tool_descriptions=False),
    "semantic_with_descriptions": lambda state, config: _apply_semantic_route(state, config=config, use_tool_descriptions=True),
}


def decide_tool(state: AgentState) -> AgentState:
    config = load_app_config()
    router_name = config.overlay.router
    add_trace_step(
        state,
        "routing",
        "Loaded active overlay",
        py_file="app/agent/nodes/tool_decision.py",
        exercise_id=config.overlay.exercise_id or "none",
        option_applied=config.overlay.option_applied or "base",
        router=router_name,
    )
    if _is_rm_override_followup(state, config):
        return state
    if _is_two_customer_comparison_request(state):
        customer_id_a, customer_id_b = _extract_customer_ids(state.user_input)
        state.selected_tool = "compare_customers"
        state.tool_input = {
            "customer_id_a": customer_id_a,
            "customer_id_b": customer_id_b,
        }
        state.tool_reasoning = (
            "This request compares two named customers and asks for a relative risk judgment, so it needs the comparison tool."
        )
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="two_customer_comparison",
            fallback_triggered=False,
            decision_source="generic comparison rule",
        )
        _log_route_decision(state, "matched two-customer comparison rule")
        return state
    if _is_single_customer_credit_request(state):
        customer_id = _extract_customer_id(state.user_input)
        state.selected_tool = "get_full_picture"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = (
            "A single-customer credit or underwriting request needs the full evidence package rather than a narrow profile or alert view."
        )
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="single_customer_credit_request",
            fallback_triggered=False,
            decision_source="generic credit-intent rule",
        )
        _log_route_decision(state, "matched single-customer credit-intent rule")
        return state
    if _is_current_risk_status_request(state):
        customer_id = _extract_customer_id(state.user_input)
        state.selected_tool = "get_customer_profile_and_alerts"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = (
            "A current risk status request needs the customer's profile together with current alert evidence."
        )
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="current_risk_status",
            fallback_triggered=False,
            decision_source="generic follow-up rule",
        )
        _log_route_decision(state, "matched current risk status rule")
        return state
    if _is_trojan_note_profile_alerts_request(state, config):
        state.selected_tool = "get_customer_profile_and_alerts"
        state.tool_input = {"customer_id": TROJAN_NOTE_CUSTOMER_ID}
        state.tool_reasoning = (
            "This Trojan Note exercise needs both the structured riskRating and the alert payload, so route to profile plus alerts."
        )
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="exercise_contract",
            matched_keyword="trojan_note_profile_alerts",
            fallback_triggered=False,
            decision_source="exercise-specific evidence contract",
        )
        _log_route_decision(state, "forced profile-plus-alerts route for trojan-note forensic prompt")
        return state
    if _is_profile_and_recent_evidence_conflict_request(state):
        customer_id = _extract_customer_id(state.user_input)
        state.selected_tool = "get_full_picture"
        state.tool_input = {"customer_id": customer_id}
        state.tool_reasoning = (
            "A request that contrasts profile risk with recent fraud or activity needs the full evidence package."
        )
        state.fallback_message = None
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="profile_vs_recent_evidence",
            fallback_triggered=False,
            decision_source="generic conflict rule",
        )
        _log_route_decision(state, "matched profile versus recent evidence rule")
        return state
    router = ROUTERS.get(router_name)
    if router is None:
        state.selected_tool = None
        state.tool_input = {}
        state.tool_reasoning = f"Unknown router '{router_name}'. Returning the gentle catch-all."
        state.fallback_message = GENTLE_FALLBACK
        state = _record_trace(
            state,
            routing_mode="deterministic",
            matched_keyword="none",
            fallback_triggered=True,
            decision_source=f"unknown router: {router_name}",
        )
        _log_route_decision(state, "unknown router; returning gentle fallback")
        return state
    return router(state, config)
