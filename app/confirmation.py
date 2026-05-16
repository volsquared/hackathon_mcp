from __future__ import annotations

import json
from datetime import datetime, timezone

from app.agent.state import AgentState
from app.config import OverlaySettings
from app.config import PROJECT_ROOT, load_app_config


def write_confirmation(function_name: str, state: AgentState) -> None:
    config = load_app_config()
    overlay = config.overlay
    if not overlay.exercise_id or not overlay.confirmation_output_file or not overlay.confirmation_trigger_function:
        return
    if overlay.confirmation_trigger_function != function_name:
        return
    if not _should_write_confirmation(state, overlay):
        return

    payload = {
        "stage_id": overlay.exercise_id,
        "function_name": function_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "selected_tool": state.selected_tool,
    }
    target = PROJECT_ROOT / overlay.confirmation_output_file
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _should_write_confirmation(state: AgentState, overlay: OverlaySettings) -> bool:
    if state.fatal_error is not None:
        return False
    if state.selected_tool is None or state.selected_tool == "identify_runtime":
        return False
    if state.fallback_message is not None:
        return False
    if state.routing_trace.get("fallback_triggered") is True:
        return False
    if state.raw_result is None:
        return False
    if overlay.confirmation_selected_tool and state.selected_tool != overlay.confirmation_selected_tool:
        return False
    matched_keyword = state.routing_trace.get("matched_keyword")
    if overlay.confirmation_matched_keyword and matched_keyword != overlay.confirmation_matched_keyword:
        return False
    return True
