from __future__ import annotations

from typing import Any

from app.agent.state import AgentState


def add_trace_step(state: AgentState, phase: str, title: str, **details: Any) -> None:
    state.trace_steps.append(
        {
            "phase": phase,
            "title": title,
            "details": {key: value for key, value in details.items() if value is not None},
        }
    )


def render_trace_report(state: AgentState, *, confidence: str | None = None, source: str | None = None) -> str:
    divider = "=============================================="
    lines = [
        divider,
        "TRACE REPORT",
        f"request: {state.user_input}",
        "",
    ]

    current_phase: str | None = None
    for step in state.trace_steps:
        phase = str(step.get("phase") or "").upper()
        title = str(step.get("title") or "")
        details = step.get("details") or {}
        if phase != current_phase:
            if current_phase is not None:
                lines.append("")
            lines.append(f"[{phase}]")
            current_phase = phase
        lines.append(f"  -> {title}")
        py_file = details.pop("py_file", None)
        if py_file is not None:
            lines.append(f"     py_file: {py_file}")
        for key, value in details.items():
            lines.append(f"     {key}: {value}")

    lines.extend(
        [
            "",
            "[RESULT]",
            f"  selected_tool: {state.selected_tool or 'none'}",
            f"  confidence: {confidence or 'n/a'}",
            f"  source: {source or 'n/a'}",
        ]
    )
    if state.tool_reasoning:
        lines.append(f"  reasoning: {state.tool_reasoning}")
    if state.fallback_message:
        lines.append(f"  fallback_message: {state.fallback_message}")
    if state.llm_routing_error:
        lines.append(f"  llm_routing_error: {state.llm_routing_error}")
    if state.llm_answer_error:
        lines.append(f"  llm_answer_error: {state.llm_answer_error}")
    lines.append(divider)

    return "\n".join(lines)
