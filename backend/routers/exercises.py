"""Routes and helpers for the exercise catalog."""

import json
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
EXERCISES_PATH = Path(__file__).resolve().parents[2] / "exercise_data" / "exercises.json"


def load_exercise_catalog():
    """Load the exercises into a mapping by ID."""

    with EXERCISES_PATH.open(encoding="utf-8") as exercise_file:
        return {exercise["id"]: exercise for exercise in json.load(exercise_file)}


def find_exercise_or_404(exercise_id: str, exercise_catalog: Dict):
    """Return an exercise or raise a not-found error."""

    exercise = exercise_catalog.get(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


def list_exercise_summaries(exercise_catalog: Dict):
    """Create the exercise records used by the selector."""

    return [
        {"id": exercise["id"], "description": exercise["description"]}
        for exercise in exercise_catalog.values()
    ]


@router.get("/exercises")
def list_exercises(request: Request):
    """Return summaries for the available exercises."""

    return list_exercise_summaries(request.app.state.exercises)


@router.get("/exercises_python")
def list_python_exercises(request: Request):
    """Return exercise summaries for the Python route alias."""

    return list_exercise_summaries(request.app.state.exercises)


@router.get("/exercise/{exercise_id}")
def get_exercise(exercise_id: str, request: Request):
    """Return the complete exercise identified by its path parameter."""

    return find_exercise_or_404(exercise_id, request.app.state.exercises)


# Compatibility aliases for the excluded run_notequiv_feedback.py script.
load_exercises = load_exercise_catalog
get_exercise_or_404 = find_exercise_or_404