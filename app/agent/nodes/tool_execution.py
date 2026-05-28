import logging

from requests import RequestException

from app.agent.state import AgentState
from app.llm import build_llm_from_env
from app.tools.alerts import get_alerts, get_alerts_request_url
from app.tools.customer import get_customer_profile, get_customer_profile_request_url
from app.tools.spending_summary import get_spending_summary, get_spending_summary_request_url
from app.tools.transactions import get_transactions, get_transactions_request_url
from app.trace import add_trace_step

logger = logging.getLogger(__name__)


def execute_tool(state: AgentState) -> AgentState:
    try:
        if state.reuse_previous_tool_result and state.raw_result is not None:
            add_trace_step(
                state,
                "execution",
                "Reusing prior tool result from session context",
                py_file="app/agent/nodes/tool_execution.py",
                selected_tool=state.selected_tool,
            )
            return state
        if state.selected_tool == "identify_runtime":
            add_trace_step(state, "execution", "Preparing runtime diagnostic", py_file="app/agent/nodes/tool_execution.py")
            runtime = build_llm_from_env()
            if runtime.is_ready and runtime.client:
                add_trace_step(state, "execution", "Running live LLM probe", py_file="app/agent/nodes/tool_execution.py", mode=runtime.mode, provider=runtime.provider, model=runtime.model)
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
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_customer_profile", customer_id=state.tool_input["customer_id"], http_url=get_customer_profile_request_url(state.tool_input["customer_id"]))
            state.raw_result = get_customer_profile(state.tool_input["customer_id"])
        elif state.selected_tool == "get_customer_profile_and_alerts":
            customer_id = state.tool_input["customer_id"]
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_customer_profile_and_alerts", customer_id=customer_id, profile_url=get_customer_profile_request_url(customer_id), alerts_url=get_alerts_request_url(customer_id=customer_id))
            state.raw_result = {
                "customer_profile": get_customer_profile(customer_id),
                "alerts": get_alerts(customer_id=customer_id),
            }
        elif state.selected_tool == "get_full_picture":
            customer_id = state.tool_input["customer_id"]
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_full_picture", customer_id=customer_id, profile_url=get_customer_profile_request_url(customer_id), alerts_url=get_alerts_request_url(customer_id=customer_id), transactions_url=get_transactions_request_url(customer_id=customer_id), spending_summary_url=get_spending_summary_request_url(customer_id=customer_id, group_by="category"))
            state.raw_result = {
                "customer_profile": get_customer_profile(customer_id),
                "alerts": get_alerts(customer_id=customer_id),
                "transactions": get_transactions(customer_id=customer_id),
                "spending_summary": get_spending_summary(customer_id=customer_id, group_by="category"),
            }
        elif state.selected_tool == "compare_customers":
            customer_id_a = state.tool_input["customer_id_a"]
            customer_id_b = state.tool_input["customer_id_b"]
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="compare_customers", customer_id_a=customer_id_a, customer_id_b=customer_id_b, customer_a_profile_url=get_customer_profile_request_url(customer_id_a), customer_a_alerts_url=get_alerts_request_url(customer_id=customer_id_a), customer_a_transactions_url=get_transactions_request_url(customer_id=customer_id_a), customer_b_profile_url=get_customer_profile_request_url(customer_id_b), customer_b_alerts_url=get_alerts_request_url(customer_id=customer_id_b), customer_b_transactions_url=get_transactions_request_url(customer_id=customer_id_b))
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
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_transactions", customer_id=state.tool_input.get("customer_id"), fraud_only=state.tool_input.get("fraud_only", False), http_url=get_transactions_request_url(customer_id=state.tool_input.get("customer_id"), fraud_only=state.tool_input.get("fraud_only", False)))
            state.raw_result = get_transactions(
                customer_id=state.tool_input.get("customer_id"),
                fraud_only=state.tool_input.get("fraud_only", False),
            )
        elif state.selected_tool == "get_spending_summary":
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_spending_summary", customer_id=state.tool_input["customer_id"], group_by=state.tool_input["group_by"], http_url=get_spending_summary_request_url(customer_id=state.tool_input["customer_id"], group_by=state.tool_input["group_by"]))
            state.raw_result = get_spending_summary(
                customer_id=state.tool_input["customer_id"],
                group_by=state.tool_input["group_by"],
            )
        elif state.selected_tool == "get_alerts":
            add_trace_step(state, "execution", "Calling Java banking API", py_file="app/agent/nodes/tool_execution.py", tool="get_alerts", customer_id=state.tool_input.get("customer_id"), severity=state.tool_input.get("severity"), http_url=get_alerts_request_url(customer_id=state.tool_input.get("customer_id"), severity=state.tool_input.get("severity")))
            state.raw_result = get_alerts(
                customer_id=state.tool_input.get("customer_id"),
                severity=state.tool_input.get("severity"),
            )
        else:
            add_trace_step(state, "execution", "No tool executed", py_file="app/agent/nodes/tool_execution.py", reason="router returned no tool")
            state.raw_result = None
    except KeyError:
        add_trace_step(state, "execution", "Execution failed", py_file="app/agent/nodes/tool_execution.py", error="Required tool input is missing", selected_tool=state.selected_tool)
        state.raw_result = {"error": "Required tool input is missing."}
    except RequestException as exc:
        add_trace_step(state, "execution", "Execution failed", py_file="app/agent/nodes/tool_execution.py", error="Failed to reach the Java API", details=str(exc))
        state.raw_result = {
            "error": "Failed to reach the Java API.",
            "details": str(exc),
        }
    except Exception as exc:
        logger.exception("Execution failed for tool %s", state.selected_tool)
        add_trace_step(state, "execution", "Execution failed", py_file="app/agent/nodes/tool_execution.py", error=f"{type(exc).__name__}: {exc}", phase="tool_execution")
        state.raw_result = {
            "error": f"{type(exc).__name__}: {exc}",
            "phase": "tool_execution",
        }

    return state
