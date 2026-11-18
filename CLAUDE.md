# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

AI Health Supervisor Agent — a multi-agent LangGraph app that routes user health questions to one of three specialist agents (Fitness, Dietitian, Mental Wellness) via a central Supervisor agent, served through a Streamlit chat UI. LLM inference runs via Groq's hosted API (`llama-3.3-70b-versatile`).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Configure secrets (copy the template, then fill in real keys)
cp .env.example .env

# Run the app
streamlit run main.py
```

Required environment variables (`.env`, loaded via `python-dotenv` in `tools.py`):
- `GROQ_API_KEY` — key for Groq's hosted inference API (agent reasoning/responses)
- `EXERCISE_API_KEY` — key for the api-ninjas.com Exercises API (fitness tool)
- `DIET_API_KEY` — key for the Spoonacular Food API (dietitian tool)

There is no test suite, linter, or type-checker configured in this repo.

## Architecture

Core pattern: a **LangGraph supervisor multi-agent state machine**, where a supervisor node classifies each turn and routes control to one worker node, which then hands control back to the supervisor. Loop continues until the supervisor emits `FINISH`.

```
START -> supervisor -> {fitness | dietitian | wellness} -> supervisor -> ... -> END
```

- **`main.py`** — entry point. Builds the `StateGraph`, registers the four nodes, compiles it with a `MemorySaver` checkpointer, and renders the Streamlit chat UI. Streams `graph.stream(...)` and renders each intermediate step as it arrives (so partial agent output appears live rather than waiting for `FINISH`).
- **`agents.py`** — defines:
  - `State(MessagesState)` — adds a `next: str` field to the standard LangGraph messages state.
  - `Router(TypedDict)` — structured-output schema (`next: Literal[...]`) the supervisor LLM call is constrained to, so routing is a typed decision rather than free text.
  - `supervisor_node` — calls `llm.with_structured_output(Router)` over the full message history plus a system prompt describing the three workers; returns a `Command(goto=<worker or END>)`.
  - `fitness_node` / `dietitian_node` — each wraps a `create_react_agent(llm, tools=[...])` (LangGraph prebuilt ReAct agent) scoped to a single tool, then returns `Command(goto="supervisor")` with the agent's last message tagged with its `name`.
  - `mental_health_node` — no tool; runs a plain prompt-template → LLM chain (no external API), also returns to `supervisor`.
  - Every worker node routes back to `"supervisor"` — workers never end the graph or call each other directly; only the supervisor can route to `END`.
- **`tools.py`** — external API integrations, each wrapped as a `@tool`-decorated function consumed by the ReAct agents:
  - `FitnessData` — calls the api-ninjas.com exercises API; `generate_workout_plan(query)` picks a random muscle group from `{full_body, upper_body, lower_body}` and returns a formatted 3-exercise list.
  - `Dietitian` — calls the Spoonacular `mealplanner/generate` + `recipes/{id}/information` endpoints; `generate_meal_plan(query)` (`query` = diet type, e.g. `vegetarian`/`vegan`/`None`) fetches a day's meals, enriches each with recipe/ingredient detail, and appends daily macro totals.
- **`utils.py`** — `parse_langgraph_output(stream_event)` unpacks a single `graph.stream()` step dict into `(agent_name, content)` tuples, skipping the `supervisor` key (its output is routing metadata, not user-facing content) and unwrapping `AIMessage`s.

### Notable conventions
- Workers are intentionally narrow: each agent's system prompt explicitly restricts it to its own domain (e.g. fitness agent "can only answer queries related to workout"), relying on the supervisor for all cross-domain orchestration rather than letting workers reason about routing.
- Conversation memory is per-`thread_id` via LangGraph's `MemorySaver` (in-memory only, not persisted across process restarts); `main.py` builds the graph once via `@st.cache_resource` (Streamlit reruns the script every message, so an uncached `MemorySaver` would lose history) and uses a per-browser-session `thread_id` (a `uuid4` in `st.session_state`).
- `Health_Assistant_AI_Agent.ipynb` is the original exploratory notebook this architecture was developed in — it contains the same classes/nodes/graph inline (not imported from the `.py` modules) and is kept as a prototyping/reference copy, not the runtime entry point.

