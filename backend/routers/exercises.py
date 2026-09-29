"""Routes and helpers for the exercise catalog."""

import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from fastapi import APIRouter, HTTPException, Request
from backend.schemas import Exercise

router = APIRouter()
EXERCISE_PATHS = {
    "java": Path(__file__).resolve().parents[2] / "exercise_data" / "exercises_java.json",
    "csharp": Path(__file__).resolve().parents[2] / "exercise_data" / "exercises_csharp.json",
}


def load_exercise_catalog(language: Optional[str] = None) -> Dict[str, Exercise]:
    """Load and validate exercises from each supported language catalog."""

    if language is not None and language not in EXERCISE_PATHS:
        raise ValueError(f"Unsupported exercise language: {language}")

    languages = [language] if language else EXERCISE_PATHS
    catalog = {}
    for exercise_language in languages:
        with EXERCISE_PATHS[exercise_language].open(encoding="utf-8") as exercise_file:
            for exercise_data in json.load(exercise_file):
                exercise = Exercise.model_validate({**exercise_data, "language": exercise_language})
                if exercise.id in catalog:
                    raise ValueError(f"Duplicate exercise ID across catalogs: {exercise.id}")
                catalog[exercise.id] = exercise
    return catalog


def find_exercise(exercise_id: str, exercise_catalog: Dict[str, Exercise]) -> Exercise:
    """Return an exercise or raise a not-found error."""

    exercise = exercise_catalog.get(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


def list_exercise_summaries(exercises: Iterable[Exercise]):
    """Create the exercise records used by the selector."""

    return [
        {"id": exercise.id, "description": exercise.description, "language": exercise.language}
        for exercise in exercises
    ]


@router.get("/exercises")
def list_exercises(request: Request, language: Optional[str] = None):
    """Return summaries for the available exercises."""

    if language is not None and language not in EXERCISE_PATHS:
        raise HTTPException(status_code=400, detail="Unsupported exercise language")
    exercises = request.app.state.exercises.values()
    if language is not None:
        exercises = (exercise for exercise in exercises if exercise.language == language)
    return list_exercise_summaries(exercises)


@router.get("/exercises_python")
def list_python_exercises(request: Request):
    """Return exercise summaries for the Python route alias."""

    return list_exercise_summaries(request.app.state.exercises.values())


@router.get("/exercise/{exercise_id}")
def get_exercise(exercise_id: str, request: Request):
    """Return the complete exercise identified by its path parameter."""

    return find_exercise(exercise_id, request.app.state.exercises).model_dump()


# Compatibility aliases for the excluded run_notequiv_feedback.py script.
load_exercises = load_exercise_catalog
get_exercise_or_404 = find_exercise