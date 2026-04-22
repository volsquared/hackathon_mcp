from requests import RequestException

from app.agent.state import AgentState
from app.tools.alerts import get_alerts
from app.tools.customer import get_customer_profile
from app.tools.spending_summary import get_spending_summary
from app.tools.transactions import get_transactions


def execute_tool(state: AgentState) -> AgentState:
    try:
        if state.selected_tool == "get_customer_profile":
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

    return state
