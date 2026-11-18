from collections.abc import Callable
from typing import Literal, get_args

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, MessagesState
from langgraph.types import Command
from typing_extensions import TypedDict

from tools import diet_tool, fitness_data_tool


GRAPH_STEP_LIMIT = 15

SUPERVISOR_PROMPT = """You route requests to three specialists:

- fitness handles workouts and exercises.
- dietitian handles nutrition and meal plans.
- wellness handles everyday stress and mental wellness.

Read the latest user request and the conversation so far. Route to one
specialist that can answer a part of the request that still needs a reply.
Specialist replies are prefixed with the specialist's name. If several
specialists are needed, call them one at a time. Return FINISH when the
request is complete or none of the specialists can help."""

FITNESS_PROMPT = """You are a fitness coach. Answer only questions about workouts
and exercises. Use your exercise tool when it helps you give a concrete plan."""

DIETITIAN_PROMPT = """You are a dietitian. Answer only questions about nutrition
and meal plans. Use your meal-planning tool when it helps, and respect
the dietary preferences the user has shared."""

WELLNESS_PROMPT = """You are a supportive mental wellness guide. Offer a
simple, kind practice for everyday stress or mental wellness that fits what
the user shared. Avoid repeating suggestions you already gave."""


class State(MessagesState):
    next: str


Route = Literal["fitness", "dietitian", "wellness", "FINISH"]


class Router(TypedDict):
    """The specialist to call next, or FINISH to end the turn."""

    next: Route


def _specialist_reply(name: str, text: str) -> Command[Literal["supervisor"]]:
    return Command(
        update={"messages": [AIMessage(content=text, name=name)]},
        goto="supervisor",
    )


def create_agent_nodes(model: BaseChatModel) -> dict[str, Callable[[State], Command]]:
    """Build the supervisor and its three specialists around one chat model."""
    # The worker graphs have their own default step limit.
    fitness_agent = create_agent(
        model, tools=[fitness_data_tool], system_prompt=FITNESS_PROMPT,
    ).with_config(recursion_limit=GRAPH_STEP_LIMIT)
    dietitian_agent = create_agent(
        model, tools=[diet_tool], system_prompt=DIETITIAN_PROMPT,
    ).with_config(recursion_limit=GRAPH_STEP_LIMIT)
    route_request = model.with_structured_output(Router, method="function_calling")

    def supervisor_node(state: State) -> Command[Literal["fitness", "dietitian", "wellness", "__end__"]]:
        messages = [SystemMessage(content=SUPERVISOR_PROMPT)]
        for message in state["messages"]:
            if isinstance(message, AIMessage) and message.name:
                # Groq's message conversion omits the name on assistant messages.
                message = AIMessage(content=f"{message.name}: {message.text}")
            messages.append(message)

        decision = route_request.invoke(messages)
        destination = decision.get("next") if isinstance(decision, dict) else None
        if destination not in get_args(Route):
            raise ValueError("The supervisor did not return a valid route.")

        next_node = END if destination == "FINISH" else destination
        return Command(goto=next_node, update={"next": next_node})

    def fitness_node(state: State) -> Command[Literal["supervisor"]]:
        result = fitness_agent.invoke({"messages": state["messages"]})
        return _specialist_reply("fitness", result["messages"][-1].text)

    def dietitian_node(state: State) -> Command[Literal["supervisor"]]:
        result = dietitian_agent.invoke({"messages": state["messages"]})
        return _specialist_reply("dietitian", result["messages"][-1].text)

    def wellness_node(state: State) -> Command[Literal["supervisor"]]:
        response = model.invoke([SystemMessage(content=WELLNESS_PROMPT), *state["messages"]])
        return _specialist_reply("wellness", f"Here's your wellness tip: {response.text}")

    return {
        "supervisor": supervisor_node,
        "fitness": fitness_node,
        "dietitian": dietitian_node,
        "wellness": wellness_node,
    }
