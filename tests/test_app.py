import json
import os
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit import cache_resource
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "main.py"


def assistant_message(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def tool_call(name, arguments, call_id="call_1"):
    response = assistant_message(None)
    response["choices"][0]["message"]["tool_calls"] = [
        {
            "id": call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments)},
        }
    ]
    return response


def route_to(destination):
    return tool_call("Router", {"next": destination})


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "GROQ_API_KEY": "test-groq-key",
            "EXERCISE_API_KEY": "test-exercise-key",
            "DIET_API_KEY": "test-diet-key",
            "LANGSMITH_TRACING": "false",
        }))
        self.complete = self.enterContext(patch("groq.resources.chat.completions.Completions.create"))
        self.http_get = self.enterContext(patch("tools.requests.get"))
        self.http_get.side_effect = AssertionError("Unexpected provider request")
        self.addCleanup(cache_resource.clear)

    def open_app(self):
        app = AppTest.from_file(str(APP_PATH)).run()
        self.assertFalse(app.exception)
        self.assertTrue(app.chat_input)
        return app

    def send(self, app, prompt):
        app.chat_input[0].set_value(prompt).run()
        self.assertFalse(app.exception)

    def test_fitness_and_dietitian_can_act_on_tool_results_in_the_same_turn(self):
        self.complete.side_effect = [
            route_to("fitness"),
            tool_call("fitness_data_tool", {"query": "lower_body"}),
            tool_call("fitness_data_tool", {"query": "upper_body"}, "call_2"),
            assistant_message("Try the step-up and wall push-up."),
            route_to("dietitian"),
            tool_call("diet_tool", {"query": "vegan"}),
            assistant_message("Try lentil stew."),
            route_to("FINISH"),
        ]
        self.http_get.side_effect = [
            Mock(ok=True, json=Mock(return_value=[
                {"name": "Step-up", "muscle": "quadriceps", "instructions": "Use a low step."},
            ])),
            Mock(ok=True, json=Mock(return_value=[
                {"name": "Wall push-up", "muscle": "chest", "instructions": "Stand by a wall."},
            ])),
            Mock(ok=True, json=Mock(return_value={
                "meals": [{"id": 42, "title": "Lentil stew", "readyInMinutes": 20, "servings": 2}],
                "nutrients": {"calories": 420, "protein": 24, "fat": 12, "carbohydrates": 54},
            })),
            Mock(ok=True, json=Mock(return_value={
                "extendedIngredients": [{"original": "1 cup lentils"}],
                "instructions": "Simmer until tender.",
            })),
        ]

        app = self.open_app()
        self.send(app, "Suggest a workout and a vegan meal plan.")

        self.assertFalse(app.error)
        visible_replies = [entry.value for entry in app.markdown if "**Agent:**" in entry.value]
        self.assertEqual(len(visible_replies), 2)
        self.assertIn("`fitness`\n\nTry the step-up and wall push-up.", visible_replies[0])
        self.assertIn("`dietitian`\n\nTry lentil stew.", visible_replies[1])

        requests = [call.kwargs for call in self.complete.call_args_list]
        self.assertIn("Step-up", requests[2]["messages"][-1]["content"])
        self.assertIn("Wall push-up", requests[3]["messages"][-1]["content"])
        self.assertIn("1 cup lentils", requests[6]["messages"][-1]["content"])
        self.assertEqual(requests[4]["messages"][-1]["content"],
                         "fitness: Try the step-up and wall push-up.")
        self.assertEqual(requests[7]["messages"][-1]["content"], "dietitian: Try lentil stew.")

    def test_follow_up_uses_its_own_thread_history(self):
        self.complete.side_effect = [
            route_to("wellness"), assistant_message("Try a quiet pause."), route_to("FINISH"),
            route_to("wellness"), assistant_message("Start with a shorter pause."), route_to("FINISH"),
            route_to("wellness"), assistant_message("Try a break after studying."), route_to("FINISH"),
        ]
        first_session = self.open_app()
        self.send(first_session, "How can I unwind before bed?")
        self.send(first_session, "Can I make it shorter?")
        second_session = self.open_app()
        self.send(second_session, "How can I take a break after studying?")

        requests = [call.kwargs["messages"] for call in self.complete.call_args_list]
        self.assertFalse(first_session.error)
        self.assertFalse(second_session.error)
        self.assertEqual(requests[1][-1]["content"], "How can I unwind before bed?")
        self.assertEqual([message["content"] for message in requests[4][1:]], [
            "How can I unwind before bed?",
            "Here's your wellness tip: Try a quiet pause.",
            "Can I make it shorter?",
        ])
        self.assertEqual([message["content"] for message in requests[7][1:]], [
            "How can I take a break after studying?",
        ])
        visible_replies = [entry.value for entry in first_session.markdown]
        self.assertTrue(any("Try a quiet pause." in reply for reply in visible_replies))
        self.assertTrue(any("Start with a shorter pause." in reply for reply in visible_replies))

    def test_recursion_limit_ends_a_turn_with_an_error(self):
        self.complete.side_effect = lambda **request: (
            route_to("wellness") if request.get("tools") else assistant_message("Take a pause.")
        )

        app = self.open_app()
        with self.assertLogs(level="ERROR"):
            self.send(app, "Give me a simple wellness suggestion.")

        self.assertEqual(len(app.error), 1)
        self.assertLessEqual(self.complete.call_count, 15)
        self.assertTrue(any("Take a pause." in entry.value for entry in app.markdown))

    def test_recursion_limit_bounds_repeated_react_tool_calls(self):
        def keep_calling_tool(**request):
            if self.complete.call_count > 20:
                raise AssertionError("The agent exceeded the test's maximum call count")
            tool_name = request["tools"][0]["function"]["name"]
            if tool_name == "Router":
                return route_to("fitness")
            return tool_call(tool_name, {"query": "lower_body"}, f"call_{self.complete.call_count}")

        self.complete.side_effect = keep_calling_tool
        self.http_get.side_effect = None
        self.http_get.return_value = Mock(ok=True, json=Mock(return_value=[
            {"name": "Step-up", "muscle": "quadriceps", "instructions": "Use a low step."},
        ]))

        app = self.open_app()
        with self.assertLogs(level="ERROR") as captured:
            self.send(app, "Suggest a workout.")

        self.assertEqual(len(app.error), 1)
        self.assertLessEqual(self.complete.call_count, 15)
        self.assertIn("GraphRecursionError", "\n".join(captured.output))

    def test_missing_groq_key_is_explained_in_the_chat(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            app = AppTest.from_file(str(APP_PATH)).run()

        self.assertFalse(app.exception)
        self.assertTrue(any("GROQ_API_KEY" in entry.value for entry in app.error))

    def test_invalid_supervisor_route_displays_an_error(self):
        self.complete.side_effect = [route_to("unknown_specialist")]

        app = self.open_app()
        with self.assertLogs(level="WARNING"):
            self.send(app, "Can you help me plan a workout?")

        self.assertEqual(len(app.error), 1)
