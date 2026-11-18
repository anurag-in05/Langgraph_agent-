import json
import os
import unittest
from unittest.mock import patch

import requests

from tools import Dietitian, FitnessData


def response_with(payload, status=200):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(payload).encode()
    return response


class ProviderToolTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, {
            "EXERCISE_API_KEY": "test-exercise-key",
            "DIET_API_KEY": "test-diet-key",
        }))
        self.get = self.enterContext(patch("tools.requests.get"))

    def test_workout_sends_selected_filters_and_limits_results_to_three(self):
        self.get.return_value = response_with([
            {"name": name, "muscle": "quadriceps", "instructions": "Use slow, even movements."}
            for name in ("Step-up", "Squat", "Lunge", "Leg extension")
        ])

        with patch("tools.random.choice", side_effect=["quadriceps", "strength"]):
            workout = FitnessData().generate_workout_plan("lower_body")

        self.assertEqual(self.get.call_args.kwargs["params"], {
            "type": "strength", "muscle": "quadriceps", "difficulty": "intermediate",
        })
        self.assertEqual(self.get.call_args.kwargs["timeout"], 10)
        self.assertIn("Exercise 3: Lunge", workout)
        self.assertNotIn("Leg extension", "\n".join(workout))

    def test_workout_skips_malformed_items(self):
        self.get.return_value = response_with([
            None,
            {"name": "Incomplete exercise"},
            {"name": "Step-up", "muscle": "quadriceps", "instructions": "Use a low step."},
        ])

        workout = FitnessData().generate_workout_plan("lower_body")

        self.assertIn("Exercise 1: Step-up", workout)
        self.assertNotIn("Incomplete exercise", "\n".join(workout))

    def test_workout_timeout_and_quota_produce_a_friendly_tool_result(self):
        self.get.side_effect = [
            requests.Timeout("request timed out"),
            response_with({"error": "Monthly quota exceeded"}, status=400),
        ]
        for failure in ("timeout", "quota"):
            with self.subTest(failure=failure):
                workout = FitnessData().generate_workout_plan("unknown workout category")
                self.assertIn("couldn't fetch exercises", "\n".join(workout))

    def test_meal_request_keeps_the_day_and_sends_only_an_explicit_diet(self):
        self.get.return_value = response_with({"meals": [], "nutrients": {}})
        for diet, expected in (("vegetarian", "vegetarian"), ("vegan", "vegan"), ("None", None)):
            with self.subTest(diet=diet):
                Dietitian().generate_meal_plan(diet)
                call = self.get.call_args
                self.assertTrue(call.args[0].endswith("/mealplanner/generate"))
                self.assertEqual(call.kwargs["params"]["timeFrame"], "day")
                self.assertEqual(call.kwargs["params"].get("diet"), expected)

    def test_meal_summary_survives_partial_recipe_enrichment(self):
        self.get.side_effect = [
            response_with({
                "meals": [
                    {"id": 42, "title": "Lentil stew", "readyInMinutes": 20, "servings": 2},
                    {"id": 43, "title": "Bean salad", "readyInMinutes": 10, "servings": 2},
                ],
                "nutrients": {"calories": 0, "protein": 24, "fat": 12, "carbohydrates": 54},
            }),
            response_with({"error": "Over quota"}, status=402),
            response_with({
                "extendedIngredients": [{"original": "1 cup beans"}, {}, None],
                "instructions": "Mix in a bowl.",
            }),
        ]

        plan = "\n".join(Dietitian().generate_meal_plan("vegan"))

        self.assertIn("Lentil stew", plan)
        self.assertIn("Bean salad", plan)
        self.assertIn("1 cup beans", plan)
        self.assertIn("Mix in a bowl.", plan)
        self.assertIn("Calories: 0 kcal", plan)
        self.assertIn("Protein: 24 g", plan)
        self.assertNotIn("Instructions:\n None", plan)

    def test_invalid_meal_payloads_produce_a_friendly_tool_result(self):
        invalid_json = response_with({})
        invalid_json._content = b"not JSON"
        self.get.side_effect = [response_with([]), invalid_json, response_with({"meals": "wrong"})]

        for payload in ("wrong root type", "invalid JSON", "wrong meals type"):
            with self.subTest(payload=payload):
                plan = Dietitian().generate_meal_plan("vegetarian")
                self.assertIn("couldn't fetch a meal plan", "\n".join(plan))

    def test_meal_summary_omits_invalid_time_servings_and_nutrient_values(self):
        meal_plan = response_with({})
        meal_plan._content = b'''{
            "meals": [{"title": "Lentil stew", "readyInMinutes": {}, "servings": []}],
            "nutrients": {"protein": 1e309, "calories": "unknown"}
        }'''
        self.get.return_value = meal_plan

        plan = "\n".join(Dietitian().generate_meal_plan("vegan"))

        self.assertIn("Lentil stew", plan)
        self.assertNotIn("Ready in:", plan)
        self.assertNotIn("Servings:", plan)
        self.assertIn("Protein: N/A", plan)
        self.assertIn("Calories: N/A", plan)
