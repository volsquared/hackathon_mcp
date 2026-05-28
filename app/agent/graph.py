import logging

from app.agent.nodes.response_formatter import format_response
from app.agent.nodes.tool_decision import decide_tool
from app.agent.nodes.tool_execution import execute_tool
from app.agent.state import AgentState
from app.confirmation import write_confirmation
from app.models import AgentResponse
from app.trace import add_trace_step, render_trace_report

logger = logging.getLogger(__name__)


def run_agent(user_input: str, conversation_history: list[dict] | None = None) -> AgentResponse:
    state = AgentState(user_input=user_input, conversation_history=conversation_history or [])
    add_trace_step(state, "request", "Received user request", py_file="app/agent/graph.py", user_input=user_input)
    state = decide_tool(state)
    if state.fatal_error is not None:
        state.raw_result = state.fatal_error
        add_trace_step(state, "result", "Fatal error before formatting", py_file="app/agent/graph.py", payload=state.fatal_error)
        response = format_response(state)
        logger.info("\n%s", render_trace_report(state, confidence=response.confidence, source=response.source))
        return response
    state = execute_tool(state)
    response = format_response(state)
    write_confirmation("run_agent", state)
    logger.info("\n%s", render_trace_report(state, confidence=response.confidence, source=response.source))
    return response
