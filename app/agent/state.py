from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    user_input: str
    selected_tool: str | None = None
    tool_input: dict[str, Any] = field(default_factory=dict)
    raw_result: Any = None
