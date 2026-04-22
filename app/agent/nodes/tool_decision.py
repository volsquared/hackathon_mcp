import re

from app.agent.state import AgentState
from app.llm import build_llm_from_env
from app.llm.factory import load_available_tools, load_system_prompt, load_tool_descriptions


def _extract_customer_id(text: str) -> str | None:
    match = re.search(r"\bCUS\d{3}\b", text.upper())
    return match.group(0) if match else None


def _extract_customer_ids(text: str) -> list[str]:
    return re.findall(r"\bCUS\d{3}\b", text.upper())


def _deterministic_decide_tool(state: AgentState) -> AgentState:
    text = state.user_input.lower()
    customer_id = _extract_customer_id(state.user_input)
    customer_ids = _extract_customer_ids(state.user_input)

    if len(customer_ids) > 1:
        comparison_markers = ("compare", "comparison", "versus", "vs")
        unsupported_comparison_markers = ("last quarter", "last month", "over time", "trend", "quarter")
        if any(marker in text for marker in unsupported_comparison_markers):
            state.selected_tool = None
            state.tool_input = {}
            return state
        if any(marker in text for marker in comparison_markers) or "full picture" in text:
            state.selected_tool = "compare_customers"
            state.tool_input = {
                "customer_id_a": customer_ids[0],
                "customer_id_b": customer_ids[1],
            }
            return state
        state.selected_tool = None
        state.tool_input = {}
        return state

    if not customer_id and any(keyword in text for keyword in ("fraud", "transaction", "alert", "spend", "summary", "profile", "risk")):
        state.selected_tool = None
        state.tool_input = {}
        return state

    if customer_id and "full picture" in text:
        state.selected_tool = "get_full_picture"
        state.tool_input = {"customer_id": customer_id}
        return state

    if customer_id and "alert" in text and ("risk" in text or "profile" in text):
        state.selected_tool = "get_customer_profile_and_alerts"
        state.tool_input = {"customer_id": customer_id}
        return state

    if "alert" in text:
        state.selected_tool = "get_alerts"
        state.tool_input = {"customer_id": customer_id}
        return state

    if "spend" in text or "summary" in text:
        state.selected_tool = "get_spending_summary"
        state.tool_input = {"customer_id": customer_id, "group_by": "category"}
        return state

    if "fraud" in text or "transaction" in text:
        state.selected_tool = "get_transactions"
        state.tool_input = {"customer_id": customer_id, "fraud_only": "fraud" in text}
        return state

    if customer_id:
        state.selected_tool = "get_customer_profile"
        state.tool_input = {"customer_id": customer_id}
        return state

    state.selected_tool = None
    state.tool_input = {}
    return state


def decide_tool(state: AgentState) -> AgentState:
    runtime = build_llm_from_env()
    available_tools = load_available_tools()

    if runtime.is_ready and runtime.client and available_tools:
        try:
            result = runtime.client.choose_tool(
                user_input=state.user_input,
                available_tools=available_tools,
                tool_descriptions=load_tool_descriptions(),
                system_prompt=load_system_prompt(),
            )
            if result.tool_name:
                state.selected_tool = result.tool_name
                state.tool_input = result.tool_input
                return state
        except Exception:
            pass

    return _deterministic_decide_tool(state)
