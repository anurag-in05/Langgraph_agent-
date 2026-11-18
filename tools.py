import logging
import os
import random
from math import isfinite
from typing import Annotated, Any

import requests
from langchain.tools import tool


EXERCISE_URL = "https://api.api-ninjas.com/v1/exercises"
SPOONACULAR_URL = "https://api.spoonacular.com"
REQUEST_TIMEOUT = 10  # seconds
MAX_EXERCISES = 3

MUSCLE_GROUPS = {
    "full_body": (
        "abdominals", "biceps", "calves", "chest", "forearms", "glutes", "hamstrings",
        "lower_back", "middle_back", "quadriceps", "traps", "triceps", "adductors",
    ),
    "upper_body": (
        "biceps", "chest", "forearms", "lats", "lower_back", "middle_back", "neck", "traps", "triceps",
    ),
    "lower_body": ("adductors", "calves", "glutes", "hamstrings", "quadriceps"),
}
EXERCISE_TYPES = ("powerlifting", "strength", "stretching", "strongman")
DAILY_NUTRIENTS = (
    ("Calories", "calories", "kcal"),
    ("Protein", "protein", "g"),
    ("Fat", "fat", "g"),
    ("Carbohydrates", "carbohydrates", "g"),
)
NO_EXERCISES = "I couldn't fetch exercises right now. Please try again later."
NO_MEAL_PLAN = "I couldn't fetch a meal plan right now. Please try again later."

logger = logging.getLogger(__name__)


def _get_json(
    provider: str,
    url: str,
    *,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> object:
    try:
        response = requests.get(url, params=params, headers=headers, timeout=REQUEST_TIMEOUT)
        if not response.ok:
            logger.warning("%s returned HTTP %s", provider, response.status_code)
            return None
        return response.json()
    except (requests.RequestException, ValueError) as error:
        logger.warning("%s request failed (%s)", provider, type(error).__name__)
        return None


def _objects(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


class FitnessData:
    def __init__(self) -> None:
        self.api_key = os.getenv("EXERCISE_API_KEY", "").strip()

    def fetch_exercises(self, exercise_type: str, muscle: str, difficulty: str) -> list[dict[str, Any]]:
        if not self.api_key:
            logger.warning("Set EXERCISE_API_KEY to enable exercise lookups")
            return []

        return _objects(_get_json(
            "API Ninjas",
            EXERCISE_URL,
            headers={"X-Api-Key": self.api_key},
            params={"type": exercise_type, "muscle": muscle, "difficulty": difficulty},
        ))

    def generate_workout_plan(self, query: str = "full_body", difficulty: str = "intermediate") -> list[str]:
        muscles = MUSCLE_GROUPS.get(_text(query).lower(), MUSCLE_GROUPS["full_body"])
        muscle = random.choice(muscles)
        exercise_type = random.choice(EXERCISE_TYPES)
        exercises = self.fetch_exercises(exercise_type, muscle, difficulty)

        plan = []
        exercise_count = 0
        for exercise in exercises:
            name = _text(exercise.get("name"))
            muscle = _text(exercise.get("muscle"))
            instructions = _text(exercise.get("instructions"))
            if not (name and muscle and instructions):
                continue

            exercise_count += 1
            plan.extend([
                f"Exercise {exercise_count}: {name}",
                f"Muscle: {muscle}",
                f"Instructions: {instructions}",
            ])
            if exercise_count == MAX_EXERCISES:
                break

        return plan or [NO_EXERCISES]


class Dietitian:
    def __init__(self) -> None:
        self.api_key = os.getenv("DIET_API_KEY", "").strip()

    def fetch_meal(self, time_frame: str = "day", diet: str | None = None) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("Set DIET_API_KEY to enable meal plans")
            return {}

        params = {"timeFrame": time_frame, "apiKey": self.api_key}
        diet = _text(diet)
        if diet and diet.lower() != "none":
            params["diet"] = diet

        result = _get_json("Spoonacular meal plan", f"{SPOONACULAR_URL}/mealplanner/generate", params=params)
        return result if isinstance(result, dict) else {}

    def get_recipe_information(self, recipe_id: int) -> dict[str, Any]:
        if not self.api_key:
            return {}

        result = _get_json(
            "Spoonacular recipe",
            f"{SPOONACULAR_URL}/recipes/{recipe_id}/information",
            params={"apiKey": self.api_key},
        )
        return result if isinstance(result, dict) else {}

    def generate_meal_plan(self, query: str | None) -> list[str]:
        meal_plan = self.fetch_meal(diet=query)
        meals = []
        meal_number = 0
        for meal in _objects(meal_plan.get("meals")):
            title = _text(meal.get("title"))
            if not title:
                continue

            meal_number += 1
            meals.append(f"🍽️ Meal {meal_number}: {title}")
            ready_in_minutes = meal.get("readyInMinutes")
            servings = meal.get("servings")
            if type(ready_in_minutes) is int and ready_in_minutes >= 0:
                meals.append(f"Ready in: {ready_in_minutes} min")
            if type(servings) is int and servings > 0:
                meals.append(f"Servings: {servings}")

            recipe_id = meal.get("id")
            recipe = self.get_recipe_information(recipe_id) if type(recipe_id) is int else {}
            ingredients = [
                text
                for ingredient in _objects(recipe.get("extendedIngredients"))
                if (text := _text(ingredient.get("original")))
            ]
            instructions = _text(recipe.get("instructions"))
            if ingredients:
                meals.append("📝 Ingredients:\n" + "\n".join(ingredients))
            if instructions:
                meals.append(f"📋 Instructions:\n{instructions}")
            if not ingredients and not instructions:
                meals.append("Recipe details are unavailable.")

        if not meals:
            return [NO_MEAL_PLAN]

        nutrients = meal_plan.get("nutrients")
        totals = nutrients if isinstance(nutrients, dict) else {}
        nutrient_lines = ["\n🔢 Daily Nutrients:"]
        for label, key, unit in DAILY_NUTRIENTS:
            amount = totals.get(key)
            if type(amount) is int or (type(amount) is float and isfinite(amount)):
                nutrient_lines.append(f"{label}: {amount} {unit}")
            else:
                nutrient_lines.append(f"{label}: N/A")
        meals.append("\n".join(nutrient_lines))
        return meals


@tool
def fitness_data_tool(
    query: Annotated[str, "Workout focus: full_body, upper_body, or lower_body."],
) -> list[str]:
    """Find exercises and instructions for the requested workout focus."""
    return FitnessData().generate_workout_plan(query)


@tool
def diet_tool(
    query: Annotated[str, 'Diet to follow, such as vegetarian or vegan. Use "None" for no restriction.'],
) -> list[str]:
    """Get a one-day meal plan with recipes and daily nutrient totals."""
    return Dietitian().generate_meal_plan(query)
