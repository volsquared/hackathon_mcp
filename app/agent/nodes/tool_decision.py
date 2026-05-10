import logging
import re

from app.agent.state import AgentState
from app.config import load_app_config
from app.llm import build_llm_from_env
from app.llm.factory import load_available_tools, load_system_prompt, load_tool_descriptions
from app.trace import add_trace_step

logger = logging.getLogger(__name__)

GENTLE_FALLBACK = "I'm not sure what you're looking for. Could you rephrase?"


def _extract_customer_id(text: str) -> str | None:
    match = re.search(r"\bCUS\d{3}\b", text.upper())
    return match.group(0) if match else None


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
