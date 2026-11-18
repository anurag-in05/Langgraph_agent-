# AI Health Supervisor Agent

## Commands

The runtime uses Python 3.11 or newer. Install the pinned dependencies, run the test suite, and start the Streamlit app from the repository root.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
streamlit run main.py
```

For the live app, copy `.env.example` to `.env` during first-time setup. `main.py` loads that configuration.

- `GROQ_API_KEY` gives the supervisor and workers access to `llama-3.3-70b-versatile`.
- `EXERCISE_API_KEY` enables the API Ninjas exercise tool.
- `DIET_API_KEY` enables the Spoonacular meal-planning tool.

The automated suite uses scripted Groq responses and mocked HTTP requests. It requires no provider keys.

## Runtime architecture

```text
START → supervisor → fitness | dietitian | wellness → supervisor → ...
        supervisor → END when it selects FINISH
```

- `main.py` builds and caches the LangGraph graph and renders the Streamlit chat. The graph uses `InMemorySaver` and a unique `thread_id` per browser session. Checkpoints survive Streamlit reruns while the process is running. Streamlit keeps its display transcript in session state.
- `agents.py` defines the graph state and nodes. The supervisor calls Groq with a structured `Router` schema and validates the selected destination. It sees the specialist's name in the reply text when deciding whether to continue. Fitness and dietitian use LangChain's `create_agent` to run a ReAct loop with one tool each. Wellness passes a system prompt and the current conversation directly to the same model.
- `tools.py` contains the provider clients and their `@tool` wrappers. Fitness requests one muscle and exercise type and formats up to three exercises. Dietitian keeps the requested diet filter, enriches the meals with available recipe details, and formats calories in kcal and macros in grams.
- `utils.py` extracts specialist text from LangGraph `updates` events. Streamlit renders each specialist's reply when the node finishes.

Only the supervisor routes to `END`. Every specialist appends its final reply as a named `AIMessage` and returns to the supervisor. The outer graph shares the conversation history across specialists, and each ReAct worker handles its tool calls inside its own loop.

`Health_Assistant_AI_Agent.ipynb` is the original exploratory notebook. It uses Ollama and defines its prototype graph inline. `main.py` is the runtime entry point.
