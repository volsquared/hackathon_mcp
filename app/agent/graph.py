from app.agent.nodes.response_formatter import format_response
from app.agent.nodes.tool_decision import decide_tool
from app.agent.nodes.tool_execution import execute_tool
from app.agent.state import AgentState
from app.models import AgentResponse


def run_agent(user_input: str) -> AgentResponse:
    state = AgentState(user_input=user_input)
    state = decide_tool(state)
    state = execute_tool(state)
    return format_response(state)
