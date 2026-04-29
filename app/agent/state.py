from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    user_input: str
    selected_tool: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    raw_result: Any = None
    fatal_error: dict[str, Any] | None = None
    tool_reasoning: str | None = None
    llm_routing_error: str | None = None
    llm_answer_error: str | None = None
