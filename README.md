# AI Health Supervisor Agent

A Streamlit chat app for workout suggestions, meal plans, and everyday mental wellness. A LangGraph supervisor routes each request to the relevant specialists and streams their replies to the chat.

![Supervisor and three specialist agents](Architectural_Diagram.png)

## How it works

The supervisor uses Groq to choose the next specialist or end the turn. Fitness and dietitian are ReAct workers. They can call their own tool, read the result, and decide whether to call it again or answer. Wellness uses the conversation history in a direct model call. Each worker returns control to the supervisor. An in-memory LangGraph checkpoint keeps follow-up messages in the same browser session.

## Run locally

Use Python 3.11 or newer. From the repository root, install the pinned runtime dependencies.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For first-time setup, copy `.env.example` to `.env` and fill in the keys you plan to use.

| Variable | Used for |
| --- | --- |
| `GROQ_API_KEY` | Chat and routing. The key needs access to `llama-3.3-70b-versatile`. [Groq console](https://console.groq.com/keys) · [Groq model catalog](https://console.groq.com/docs/models) |
| `EXERCISE_API_KEY` | Exercise lookups for the fitness worker. [API Ninjas](https://api-ninjas.com/profile) |
| `DIET_API_KEY` | Meal plans and recipe details for the dietitian worker. [Spoonacular console](https://spoonacular.com/food-api/console#Profile) |

Start Streamlit after setting up the keys.

```bash
streamlit run main.py
```

## Run the tests

```bash
python -m unittest discover -s tests -v
```

The tests use Streamlit's `AppTest`, scripted model responses, and mocked HTTP responses. They run without API keys and cover routing, ReAct tool calls, conversation memory, and provider errors.

[CLAUDE.md](CLAUDE.md) describes the runtime modules. [CODE_REVIEW.md](CODE_REVIEW.md) records the original review. [Health_Assistant_AI_Agent.ipynb](Health_Assistant_AI_Agent.ipynb) is the original Ollama prototype.
