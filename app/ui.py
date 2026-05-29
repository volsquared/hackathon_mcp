from pathlib import Path
import sys

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent.graph import run_agent
from app.config import load_app_config
from app.eval.runner import get_eval_suite_metadata, run_eval_suite
from app.llm.factory import build_llm_runtime
from app.logging_config import setup_logging


LOG_FILE = setup_logging()
st.set_page_config(page_title="Hackathon Agent", page_icon=":bank:", layout="wide")

config = load_app_config()
llm_runtime = build_llm_runtime(config)
eval_suite_meta = get_eval_suite_metadata(config)

st.title("Hackathon Banking Agent")
st.caption("Ask questions grounded in the local Java banking API.")

with st.sidebar:
    st.subheader("Explore")
    st.caption("Open the animated architecture view inside Streamlit.")
    if st.button("Architecture View", use_container_width=True):
        st.switch_page("pages/Architecture_Map.py")
    st.divider()
    st.subheader("Overlay")
    st.caption(
        f"router={config.overlay.router} | exercise={config.overlay.exercise_id or 'none'} | option={config.overlay.option_applied or 'base'}"
    )
    st.divider()
    st.subheader("Runtime Mode")
    st.metric("Mode", llm_runtime.mode)
    st.caption(llm_runtime.summary)
    st.caption(f"Logs: {LOG_FILE}")
    if llm_runtime.provider and llm_runtime.model:
        st.code(f"{llm_runtime.provider} / {llm_runtime.model}")
    if eval_suite_meta:
        st.divider()
        st.subheader("Evaluation")
        if eval_suite_meta.get("description"):
            st.caption(str(eval_suite_meta["description"]))
        eval_disabled = not llm_runtime.is_ready
        if st.button(
            str(eval_suite_meta.get("button_label") or "Run eval suite"),
            use_container_width=True,
            disabled=eval_disabled,
        ):
            with st.spinner("Running evaluation suite..."):
                try:
                    st.session_state["eval_suite_result"] = run_eval_suite(config)
                    st.session_state["eval_suite_error"] = None
                except Exception as exc:
                    st.session_state["eval_suite_error"] = f"{type(exc).__name__}: {exc}"
        if eval_disabled:
            st.caption("Live LLM mode is required to run evals.")

st.info(f"Running in `{llm_runtime.mode}` mode.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "eval_suite_result" not in st.session_state:
    st.session_state["eval_suite_result"] = None
if "eval_suite_error" not in st.session_state:
    st.session_state["eval_suite_error"] = None

eval_suite_error = st.session_state.get("eval_suite_error")
eval_suite_result = st.session_state.get("eval_suite_result")
if eval_suite_error:
    st.error(eval_suite_error)
if isinstance(eval_suite_result, dict):
    st.subheader(str(eval_suite_result.get("title") or "Evaluation Suite"))
    if eval_suite_result.get("description"):
        st.caption(str(eval_suite_result["description"]))
    st.metric(
        "Pass Rate",
        f"{eval_suite_result.get('percentage', 0)}%",
        help=f"{eval_suite_result.get('pass_rate', '0/0')} cases passed",
    )
    for case in eval_suite_result.get("cases", []):
        if not isinstance(case, dict):
            continue
        status = "PASS" if case.get("passed") else "FAIL"
        with st.expander(f"{status} - {case.get('title', 'Case')}", expanded=not bool(case.get("passed"))):
            principle = case.get("principle")
            if principle:
                st.caption(str(principle))
            st.write(str(case.get("summary") or ""))
            st.code(f"Selected tool: {case.get('selected_tool') or 'none'}")
            st.markdown("**Prompts**")
            for prompt_text in case.get("prompts", []):
                st.code(str(prompt_text))
            st.markdown("**Final answer**")
            st.markdown(str(case.get("final_answer") or ""))
            st.markdown(f"**Criteria** `{case.get('pass_rate', '0/0')}`")
            for criterion in case.get("criteria", []):
                if not isinstance(criterion, dict):
                    continue
                marker = "PASS" if criterion.get("passed") else "FAIL"
                st.write(f"{marker}: {criterion.get('criterion')}")
                explanation = criterion.get("explanation")
                if explanation:
                    st.caption(str(explanation))


def render_details(details: dict) -> None:
    trace = details.get("routing_trace") or {}
    tool_reasoning = details.get("tool_reasoning") or "none"
    if trace:
        st.caption("Routing Trace")
        st.code(
            "\n".join(
                [
                    f"Routing mode:    {trace.get('routing_mode', 'unknown')}",
                    f"Matched keyword: {trace.get('matched_keyword', 'none')}",
                    f"Selected tool:   {trace.get('selected_tool', 'none')}",
                    f"Decision source: {trace.get('decision_source', 'n/a')}",
                    f"Fallback:        {'triggered' if trace.get('fallback_triggered') else 'no'}",
                    f"Reasoning:       {tool_reasoning}",
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

    result = run_agent(prompt, conversation_history=st.session_state.messages)

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
