# Code Review — AI Health Supervisor Agent

_Reviewed 2026-09-24. Every bug below was reproduced using mocked HTTP responses or a fake LLM. No real Groq, API Ninjas or Spoonacular calls were made, because no `.env` was present._

**Status (2026-09-24):** Bugs 1–5 are fixed and verified with the same mocked checks, but not yet committed. The smaller issues and the Git/GitHub items below are still open.

**Summary:** The app starts and the supervisor → worker design is sound, but there are 5 confirmed bugs. The version on GitHub doesn't run for anyone who clones it.

---

## Bugs

### ✅ FIXED — 1. Diet type is ignored — `tools.py:109`
`generate_meal_plan(query)` calls `self.fetch_meal(query)`, which passes the diet as the first argument, `time_frame`.

- **Reproduced:** `diet_tool("vegetarian")` sends `timeFrame=vegetarian&diet=None` to Spoonacular.
- **Impact:** Users never get the vegetarian or vegan plan they asked for.
- **Fix:** `meal_plan = self.fetch_meal(diet=query)`

### ✅ FIXED — 2. The chat has no memory between messages — `main.py:12–23`
Streamlit reruns `main.py` from the top on every message, so `MemorySaver()` and the graph are rebuilt each time and earlier messages are lost.

- **Reproduced:** On the second message, the supervisor saw only 1 message in its history instead of 3.
- **Impact:** Follow-ups like "make it vegan too" lose all context.
- **Fix:** Build the graph inside a function marked `@st.cache_resource`. Also take `thread_id` from `st.session_state` (for example a `uuid4`) instead of the hard-coded `"2"`. Otherwise all users of a deployed app share one conversation.

### ✅ FIXED — 3. The wellness agent never sees the user's message — `agents.py:94–102`
The `PromptTemplate` has no input variables, so `chain.invoke(state)` drops the conversation.

- **Reproduced:** A message about exam anxiety never reached the LLM.
- **Impact:** The user gets a generic tip whatever they said.
- **Fix:** Send a system prompt plus `state["messages"]` to the LLM, for example with `ChatPromptTemplate` and a `MessagesPlaceholder`.

### ✅ FIXED — 4. The workout type is hard-coded — `tools.py:63`
`fetch_exercises('stretching', ...)` ignores the random `type` chosen on line 62.

- **Reproduced:** Every request sent `type=stretching`.
- **Impact:** Strength and powerlifting exercises never appear.
- **Fix:** `self.fetch_exercises(type, muscle, difficulty)`

### ✅ FIXED — 5. API failures crash the tools — `tools.py`
| Scenario | Result |
|---|---|
| API Ninjas returns `{"error": "Invalid API Key."}` (bad key or quota) | `KeyError: slice(None, 3, None)`: the dict is sliced like a list (line 65) |
| LLM passes a category that isn't in the list, e.g. `"legs"` | `TypeError`: `muscle_targets.get()` returns `None` (line 61) |
| Spoonacular quota exceeded (402) | `TypeError: 'NoneType' object is not iterable` (line 115) |
| Slow or unresponsive API | The app hangs indefinitely: no `timeout=` on any `requests.get` |

- **Impact:** `main.py` doesn't catch errors, so the user is likely to see a raw traceback. That includes a `GraphRecursionError` if the supervisor keeps routing past `recursion_limit=15`.
- **Fix:**
  - Check `response.ok` and the type of the result.
  - Fall back to `'full_body'` for unknown categories.
  - Add `timeout=10` to every request.
  - Wrap `graph.stream(...)` in `main.py` in a `try/except` that shows a friendly error.

---

## Smaller issues
- **Wrong nutrient unit** — `tools.py:131`: protein is labelled `kcal` but is in grams, and calories are never shown.
- **Supervisor prompt is thin** — `agents.py:27–39`: it only lists the workers' names and not what each handles. It's also missing a space, so it reads "…respond with FINISH.Guidelines:".
- **A check that does nothing** — `tools.py:67`: `if data not in output` compares a dict with a list of strings, so it's always true.
- **Mismatched type hint** — `mental_health_node` lacks the `-> Command[Literal["supervisor"]]` annotation the other workers have, so graph diagrams won't show its edge.
- **Leftover debug code:**
  - `print()` calls in `tools.py:64, 110` and `main.py:73`.
  - Unused imports in `agents.py`: `HumanMessage`, `StateGraph`, `START`, `MemorySaver`, `Annotated`, `streamlit`, plus the unused `memory` object.
  - `logging.info` output is never shown because logging is never configured.
- **Deprecated API** — `create_react_agent` is deprecated in LangGraph 1.0 and will be removed in 2.0. Switch to `from langchain.agents import create_agent`.
- **Unpinned dependencies** — `requirements.txt` has no versions, so a future install may break.

---

## Git / GitHub
- ✅ **No secrets leaked.** No API keys appear in the git history, and `.env` is gitignored.
- ❌ **The pushed version is broken.** The Groq migration is uncommitted, so `origin/main` still:
  - uses local Ollama (`qwen2.5:14b`), while the README says Groq;
  - never calls `load_dotenv()`, so API keys aren't loaded from `.env`;
  - is missing `streamlit` and `python-dotenv` from `requirements.txt`.
- ℹ️ There's a detached commit, `d37120b WIP: Claude Code rate-limit checkpoint`, that includes `__pycache__/*.pyc` files. It isn't on `main` and wasn't pushed, so it's harmless.

---

## Suggested fix order
1. Bugs 1–3: an interviewer would notice these in a live demo.
2. Bug 5 (error handling and timeouts), then bug 4.
3. Commit and push the Groq migration together with these fixes.
4. The smaller issues.
