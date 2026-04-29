from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    answer: str
    confidence: Literal["high", "medium", "low"]
    source: Literal["tool", "model"]
    data_points: list[Any] = Field(default_factory=list)
    selected_tool: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    tool_reasoning: str | None = None
    answer_rationale: str | None = None
    llm_routing_error: str | None = None
    llm_answer_error: str | None = None
