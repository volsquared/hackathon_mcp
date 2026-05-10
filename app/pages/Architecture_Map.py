from pathlib import Path
import sys

import streamlit as st
import streamlit.components.v1 as components


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import load_app_config
from app.llm.factory import build_llm_runtime

FLOW_HTML = PROJECT_ROOT / "docs" / "flow.html"


st.set_page_config(page_title="Architecture View", page_icon=":map:", layout="wide")

config = load_app_config()
llm_runtime = build_llm_runtime(config)

st.title("Architecture View")
st.caption("Interactive flow map for the Python hackathon starter.")
st.info(f"Running in `{llm_runtime.mode}` mode.")

with st.sidebar:
    st.subheader("Navigation")
    st.caption("Jump back to the chat UI or open the standalone file.")
    if st.button("Back To Chat", use_container_width=True):
        st.switch_page("ui.py")
    st.divider()
    st.subheader("Overlay")
    st.caption(
        f"router={config.overlay.router} | exercise={config.overlay.exercise_id or 'none'} | option={config.overlay.option_applied or 'base'}"
    )
    st.divider()
    st.subheader("Runtime Mode")
    st.metric("Mode", llm_runtime.mode)
    st.caption(llm_runtime.summary)
    if llm_runtime.provider and llm_runtime.model:
        st.code(f"{llm_runtime.provider} / {llm_runtime.model}")
    st.divider()
    st.markdown(f"`{FLOW_HTML}`")

html = FLOW_HTML.read_text(encoding="utf-8")
components.html(html, height=1550, scrolling=True)
