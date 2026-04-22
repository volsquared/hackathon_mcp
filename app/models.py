from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    answer: str
    confidence: Literal["high", "medium", "low"]
    source: Literal["tool", "model"]
    data_points: list[Any] = Field(default_factory=list)
    selected_tool: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
