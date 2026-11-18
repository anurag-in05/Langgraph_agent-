import logging
import os
from collections.abc import Iterator
from uuid import uuid4

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents import GRAPH_STEP_LIMIT, State, create_agent_nodes
from utils import parse_langgraph_output


GROQ_MODEL = "llama-3.3-70b-versatile"
WELCOME_MESSAGE = (
    "Hi, I’m your AI Health Assistant. Ask me about **workouts**, "
    "**meal plans**, or **everyday mental wellness**."
)
RESPONSE_ERROR = "I couldn’t finish that request. Please try again."

logger = logging.getLogger(__name__)


@st.cache_resource
def build_graph(api_key: str) -> CompiledStateGraph:
    """Keep the graph and its in-memory checkpoints across Streamlit reruns."""
    model = ChatGroq(model=GROQ_MODEL, api_key=api_key)
    graph = StateGraph(State)
    for name, node in create_agent_nodes(model).items():
        graph.add_node(name, node)
    graph.add_edge(START, "supervisor")
    return graph.compile(checkpointer=InMemorySaver())


def stream_specialist_replies(prompt: str, thread_id: str, api_key: str) -> Iterator[tuple[str, str]]:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": GRAPH_STEP_LIMIT}
    inputs = {"messages": [HumanMessage(content=prompt)]}
    graph = build_graph(api_key)
    for event in graph.stream(inputs, config=config, stream_mode="updates", version="v2"):
        yield from parse_langgraph_output(event["data"])


def run_app() -> None:
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    st.title("AI Health Assistant")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": WELCOME_MESSAGE}]
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = str(uuid4())

    history = st.session_state.messages
    for message in history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if not api_key:
        st.error("Add GROQ_API_KEY to your .env file to start chatting.")
        return

    prompt = st.chat_input("Your question")
    if not prompt:
        return

    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"), st.spinner("Preparing a reply…"):
        try:
            for specialist, text in stream_specialist_replies(prompt, st.session_state.thread_id, api_key):
                reply = f"**Agent:** `{specialist}`\n\n{text}"
                history.append({"role": "assistant", "content": reply})
                st.markdown(reply)
                st.markdown("---")
        except Exception as error:
            logger.error("Could not generate a reply (%s)", type(error).__name__)
            history.append({"role": "assistant", "content": RESPONSE_ERROR})
            st.error(RESPONSE_ERROR)


if __name__ == "__main__":
    run_app()
