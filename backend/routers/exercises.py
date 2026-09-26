import json
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()
EXERCISES_PATH = Path(__file__).resolve().parents[2] / "exercise_data" / "exercises.json"


def load_exercises():
    with EXERCISES_PATH.open(encoding="utf-8") as exercise_file:
        return {exercise["id"]: exercise for exercise in json.load(exercise_file)}


def get_exercise_or_404(exercise_id: str, exercises: Dict):
    exercise = exercises.get(exercise_id)
    if not exercise:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return exercise


def list_exercise_summaries(exercises: Dict):
    return [
        {"id": exercise["id"], "description": exercise["description"]}
        for exercise in exercises.values()
    ]


@router.get("/exercises")
def list_exercises(request: Request):
    return list_exercise_summaries(request.app.state.exercises)


@router.get("/exercises_python")
def list_python_exercises(request: Request):
    return list_exercise_summaries(request.app.state.exercises)


@router.get("/exercise/{exercise_id}")
def get_exercise(exercise_id: str, request: Request):
    return get_exercise_or_404(exercise_id, request.app.state.exercises)