import logging

from requests import RequestException

from app.agent.state import AgentState
from app.llm import build_llm_from_env
from app.tools.alerts import get_alerts
from app.tools.customer import get_customer_profile
from app.tools.spending_summary import get_spending_summary
from app.tools.transactions import get_transactions

logger = logging.getLogger(__name__)


def execute_tool(state: AgentState) -> AgentState:
    try:
        if state.selected_tool == "identify_runtime":
            runtime = build_llm_from_env()
            if runtime.is_ready and runtime.client:
                state.raw_result = {
                    "mode": runtime.mode,
                    "provider": runtime.provider,
                    "model": runtime.model,
                    "summary": runtime.summary,
                    "is_ready": runtime.is_ready,
                    "live_probe": runtime.client.run_diagnostic_probe(),
                }
            else:
                state.raw_result = {
                    "mode": runtime.mode,
                    "provider": runtime.provider,
                    "model": runtime.model,
                    "summary": runtime.summary,
                    "is_ready": runtime.is_ready,
                    "live_probe": None,
                }
        elif state.selected_tool == "get_customer_profile":
            state.raw_result = get_customer_profile(state.tool_input["customer_id"])
        elif state.selected_tool == "get_customer_profile_and_alerts":
            customer_id = state.tool_input["customer_id"]
            state.raw_result = {
                "customer_profile": get_customer_profile(customer_id),
                "alerts": get_alerts(customer_id=customer_id),
            }
        elif state.selected_tool == "get_full_picture":
            customer_id = state.tool_input["customer_id"]
            state.raw_result = {
                "customer_profile": get_customer_profile(customer_id),
                "alerts": get_alerts(customer_id=customer_id),
                "transactions": get_transactions(customer_id=customer_id),
                "spending_summary": get_spending_summary(customer_id=customer_id, group_by="category"),
            }
        elif state.selected_tool == "compare_customers":
            customer_id_a = state.tool_input["customer_id_a"]
            customer_id_b = state.tool_input["customer_id_b"]
            state.raw_result = {
                "customer_a": {
                    "customer_profile": get_customer_profile(customer_id_a),
                    "alerts": get_alerts(customer_id=customer_id_a),
                    "transactions": get_transactions(customer_id=customer_id_a),
                },
                "customer_b": {
                    "customer_profile": get_customer_profile(customer_id_b),
                    "alerts": get_alerts(customer_id=customer_id_b),
                    "transactions": get_transactions(customer_id=customer_id_b),
                },
            }
        elif state.selected_tool == "get_transactions":
            state.raw_result = get_transactions(
                customer_id=state.tool_input.get("customer_id"),
                fraud_only=state.tool_input.get("fraud_only", False),
            )
        elif state.selected_tool == "get_spending_summary":
            state.raw_result = get_spending_summary(
                customer_id=state.tool_input["customer_id"],
                group_by=state.tool_input["group_by"],
            )
        elif state.selected_tool == "get_alerts":
            state.raw_result = get_alerts(
                customer_id=state.tool_input.get("customer_id"),
                severity=state.tool_input.get("severity"),
            )
        else:
            state.raw_result = None
    except KeyError:
        state.raw_result = {"error": "Required tool input is missing."}
    except RequestException as exc:
        state.raw_result = {
            "error": "Failed to reach the Java API.",
            "details": str(exc),
        }
    except Exception as exc:
        logger.exception("Execution failed for tool %s", state.selected_tool)
        state.raw_result = {
            "error": f"{type(exc).__name__}: {exc}",
            "phase": "tool_execution",
        }

    return state
