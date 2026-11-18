from collections.abc import Mapping

from langchain_core.messages import AIMessage


def parse_langgraph_output(updates: Mapping[str, object]) -> list[tuple[str, str]]:
    """Extract specialist replies from one graph update for the chat UI."""
    replies = []
    for node, update in updates.items():
        if node == "supervisor" or not isinstance(update, Mapping):
            continue
        for message in update.get("messages", []):
            if isinstance(message, AIMessage):
                replies.append((node, message.text))
            elif isinstance(message, str):
                replies.append((node, message))
    return replies
