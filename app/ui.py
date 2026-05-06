from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.graph import run_agent
from app.config import load_app_config
from app.llm.factory import build_llm_runtime
from app.logging_config import setup_logging


LOG_FILE = setup_logging()
st.set_page_config(page_title="Hackathon Agent", page_icon=":bank:", layout="wide")

config = load_app_config()
llm_runtime = build_llm_runtime(config)

st.title("Hackathon Banking Agent")
st.caption("Ask questions grounded in the local Java banking API.")

with st.sidebar:
    st.subheader("Explore")
    st.caption("Open the animated architecture view inside Streamlit.")
    if st.button("Architecture View", use_container_width=True):
        st.switch_page("pages/Architecture_Map.py")
    st.divider()
    st.subheader("Runtime Mode")
    st.metric("Mode", llm_runtime.mode)
    st.caption(llm_runtime.summary)
    st.caption(f"Logs: {LOG_FILE}")
    if llm_runtime.provider and llm_runtime.model:
        st.code(f"{llm_runtime.provider} / {llm_runtime.model}")

st.info(f"Running in `{llm_runtime.mode}` mode.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_details(details: dict) -> None:
    trace = details.get("routing_trace") or {}
    if trace:
        st.caption("Routing Trace")
        st.code(
            "\n".join(
                [
                    f"Matched keyword: {trace.get('matched_keyword', 'none')}",
                    f"Selected tool:   {trace.get('selected_tool', 'none')}",
                    f"Fallback:        {'triggered' if trace.get('fallback_triggered') else 'no'}",
                ]
            )
        )
    st.json(details)


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("details"):
            with st.expander("Details", expanded=False):
                render_details(message["details"])

prompt = st.chat_input("Example: Show fraud for CUS007")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    result = run_agent(prompt)

    details = {
        "confidence": result.confidence,
        "source": result.source,
        "data_points": result.data_points,
        "selected_tool": result.selected_tool,
        "tool_input": result.tool_input,
        "tool_reasoning": result.tool_reasoning,
        "fallback_message": result.fallback_message,
        "routing_trace": result.routing_trace,
        "answer_rationale": result.answer_rationale,
        "llm_routing_error": result.llm_routing_error,
        "llm_answer_error": result.llm_answer_error,
    }

    st.session_state.messages.append(
        {"role": "assistant", "content": result.answer, "details": details}
    )

    with st.chat_message("assistant"):
        st.markdown(result.answer)
        with st.expander("Details", expanded=False):
            render_details(details)
