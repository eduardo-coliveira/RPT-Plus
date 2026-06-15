from dotenv import load_dotenv

# # Monkey patch mistralai to provide top-level Mistral import for instructor compatibility
# import mistralai
# from mistralai.client import Mistral as RealMistral
# mistralai.Mistral = RealMistral

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.schemas import CodeRequest, HintRequest, DiagnoseRequest, ActionLogRequest, LoginRequest, LogoutRequest
from backend.prompting import get_client_wrapper
# from refactoring_misconceptions.errors import ALL_SNIPPETS
# from mistralai.client import Mistral
import os
import requests
import json
import re
import time
import pymysql
from threading import RLock
from backend.database import init_db, log_action_entry, authenticate_user
from datetime import datetime
from typing import List, Dict, Tuple
from contextlib import asynccontextmanager

# Load API keys from .env file
load_dotenv()

# === FastAPI App Setup ===

RATE_LIMIT_SECONDS = 10
LOGIN_LOCK_TTL_SECONDS = 2400

_active_user_sessions: Dict[str, float] = {}
_last_request_time: Dict[str, float] = {}
_user_lock = RLock()


def _claim_user_session(username: str) -> bool:
    with app.state.user_lock:
        now = time.time()
        _prune_expired_user_sessions(now, app.state.active_user_sessions)
        # print(f"Active sessions (ID: {id(app.state.active_user_sessions)}): {app.state.active_user_sessions}")
        if username in app.state.active_user_sessions:
            print(f"User {username} already logged in")
            return False
        app.state.active_user_sessions[username] = now
        print(f"Added user {username} to sessions: {app.state.active_user_sessions}")
        return True

def _prune_expired_user_sessions(now: float, sessions: Dict[str, float]) -> None:
    expired_users = [
        username for username, locked_at in sessions.items()
        if now - locked_at >= LOGIN_LOCK_TTL_SECONDS
    ]
    for username in expired_users:
        sessions.pop(username, None)

# def _enforce_rate_limit(username: str) -> None:
#     with _user_lock:
#         now = time.time()
#         key = username or "anonymous"
#         last_call = _last_request_time.get(key)

#         if last_call is not None and (now - last_call) < RATE_LIMIT_SECONDS:
#             raise HTTPException(
#                 status_code=429,
#                 detail="Please wait 10 seconds before requesting another diagnosis or hint.",
#             )

#         _last_request_time[key] = now

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize state
    app.state.active_user_sessions = {}
    app.state.user_lock = RLock()
    # app.state.user_request_counts = {}
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# app.state.client_wrapper = get_client_wrapper("gpt-4-turbo", local=False)
# app.state.client_wrapper = get_client_wrapper("labs-devstral-small-2512")
# app.state.client_wrapper = get_client_wrapper("codestral-2508")
# DEFAULT_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
# DEFAULT_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-medium-3-5")
DEFAULT_MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-large-2512")
app.state.client_wrapper = get_client_wrapper(DEFAULT_MISTRAL_MODEL)
# app.state.client_wrapper = get_client_wrapper("codestral-latest")
# app.state.client_wrapper = get_client_wrapper("mistral-small-2506")

@app.post("/login")
async def login(data: LoginRequest):
    user = authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not _claim_user_session(user["username"]):
        raise HTTPException(status_code=409, detail="This user is already logged in elsewhere.")

    return {"username": user["username"], "group": user["group_name"]}

@app.post("/logout")
async def logout(request: LogoutRequest):
    username = request.username
    print(f"Logout request for user: {username}")
    with app.state.user_lock:
        app.state.active_user_sessions.pop(username, None)
    return {"message": f"User {username} logged out"}

JUDGE0_URL = "https://ce.judge0.com/submissions"

# === Load Exercises ===

# with open(os.path.join("exercise_data","exercises_python.json")) as f:
with open(os.path.join("exercise_data","exercises.json")) as f:
    EXERCISES = {ex["id"]: ex for ex in json.load(f)}


# === Static Files Setup ===

DIST_DIR = os.path.join(os.path.dirname(__file__), "../vite-frontend/dist")

# Mount assets folder for CSS, JS, etc.
app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")


# === Routes ===

@app.get("/")
def serve_root():
    """Serve index.html for root path"""
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


@app.get("/exercises")
def list_exercises():
    return [{"id": ex["id"], "description": ex["description"]} for ex in EXERCISES.values()]


@app.get("/exercises_python")
def list_python_exercises():
    return [{"id": ex["id"], "description": ex["description"]} for ex in EXERCISES.values()]


@app.get("/exercise/{exercise_id}")
def get_exercise(exercise_id: str):
    ex = EXERCISES.get(exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


@app.post("/run_code")
async def run_code(data: CodeRequest):
    judge0_data = {
        "language_id": 62,  # Java (OpenJDK 13.0.1)
        # "language_id": 71,  # Python 3
        "source_code": data.code,
        "stdin": "",
        "expected_output": None
    }

    try:
        # Use ?wait=true to get results immediately
        response = requests.post(f"{JUDGE0_URL}?wait=true", json=judge0_data)
        response.raise_for_status()
        result = response.json()
        
        # Convert Judge0 response to Piston-compatible format
        # Prioritize compile_output for compilation errors, then stderr for runtime errors
        error_output = result.get("compile_output", "") or result.get("stderr", "")
        
        return {
            "language": "java",
            "version": "17.0.4",
            # "language": "python",
            # "version": "3.10.0",
            "run": {
                "code": result.get("exit_code", 1),
                "signal": None,
                "output": result.get("stdout", ""),
                "stderr": error_output
            }
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/diagnose")
async def diagnose(data: DiagnoseRequest):
    # _enforce_rate_limit(username)

    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    full_code = build_java_program(data.submitted_code, generate_test_code(ex["call_method"], ex["result_type"], ex["tests"]))

    # full_code = data.submitted_code + "\n" + generate_test_code(ex["call_method"], ex["result_type"], ex["tests"])

    try:
        judge0_data = {
            "language_id": 62,  # Java (OpenJDK 13.0.1)
            # "language_id": 71,  # Python 3
            "source_code": full_code,
            "stdin": "",
            "expected_output": None
        }
        
        # Use ?wait=true to get results immediately
        response = requests.post(f"{JUDGE0_URL}?wait=true", json=judge0_data)
        response.raise_for_status()
        result = response.json()

        # print("Judge0 response:", result)  # Log the full response
       
        output = result.get("stdout") or result.get("output") or ""
        stderr = result.get("stderr") or ""
        exit_code = result.get("exit_code", 1)

        # print(f"Extracted - output: {output}, stderr: {stderr}, exit_code: {exit_code}")

        run_info = {
            "code": exit_code,
            "output": output,
            "stderr": stderr
        }       

        # run_info = {
        #     "code": result.get("exit_code", 1),
        #     "output": result.get("stdout", ""),
        #     "stderr": error_output
        # }
        
        # output = run_info["output"]
        # stderr = run_info["stderr"]
        # exit_code = run_info["code"]

        # Convert Judge0 response to Piston-compatible format for processing
        # Prioritize compile_output for compilation errors, then stderr for runtime errors
        error_output = result.get("compile_output", "") or stderr

        # Check if compilation failed
        status_id = result.get("status", {}).get("id", 3)  # 3 is Accepted, 6 is Compilation Error
        if status_id == 6:  # Compilation Error
            return {
                "status": "compile_error",
                "message": error_output
            }

        test_results_found = False
        for line in output.splitlines():
            if line.startswith("TEST_RESULT:"):
                test_results_found = True
                match = parse_test_output(line)
                if not match:
                    return {
                        "status": "notequiv",
                        "reason": stderr,
                        "expected": "N/A",
                        "actual": "N/A"
                    }

                if match["expected"] != match["actual"]:
                    test = ex["tests"][match["index"]]
                    return {
                        "status": "notequiv",
                        "call": f'{ex["call_method"]}({", ".join(map(str, test["inputs"]))})',
                        "expected": match["expected"],
                        "actual": match["actual"],
                        "reason": f"Expected {match['expected']}, got {match['actual']}"
                    }

        # No test results at all
        if not test_results_found:
            return {
                "status": "notequiv",
                "reason": stderr,
                "expected": "N/A",
                "actual": "N/A"
            }

        # === All tests passed ===
        return {
            "status": "correct"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

    

@app.post("/hint_tree")
async def get_hint_tree(data: HintRequest):
    username = data.username or "anonymous"
    # _enforce_rate_limit(username)

    # if not _check_and_increment_request_count(username):
    #     raise HTTPException(
    #         status_code=429,
    #         detail="You have exceeded the maximum number of requests (100)."
    #     )

    ex = EXERCISES.get(data.exercise_id)
    hint_group = data.hint_group
    diagnosis_status = data.code_diagnosis
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        prompt_data = {
            "submitted_code": data.submitted_code,
            "previous_code": data.previous_code,
            "method_explanation": ex["description"],
            "hint_group": hint_group,
            # "errors": ALL_SNIPPETS
        }
        # print(f'Diagnosis: {diagnosis_status}')
        # print(f'Previous:\n{data.previous_code}')
        # print(f'Current:\n{data.submitted_code}')
        # if hint_group == "STEP-BASED" and diagnosis_status == "notequiv":
        #     print("Step-based + RM feedback :)")
        #     suggested = app.state.client_wrapper.call("STEP_BASED_SUGGESTED", prompt_data)
        # else:
        suggested = app.state.client_wrapper.call("SUGGESTED", prompt_data)
        
        tree = build_hint_tree([s.model_dump() for s in suggested.suggestions])
        return {
            "status": "correct",
            "hint_tree": tree,
            "suggestions": suggested.suggestions
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/log_action")
async def log_action(data: ActionLogRequest):
    success = log_action_entry(
        username=data.username,
        exercise=data.exercise,
        current_code=data.current_code,
        action=data.action,
        previous_code=data.previous_code,
        code_status=data.code_status,
        feedback=data.feedback,
        hint_tree=data.hint_tree,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to log action")
    return {"status": "ok"}


@app.post("/correct_feedback")
async def get_correct_feedback(data: DiagnoseRequest):
    username = data.username or "anonymous"

    # if not _check_and_increment_request_count(username):
    #     raise HTTPException(
    #         status_code=429,
    #         detail="You have exceeded the maximum number of requests (100)."
    #     )
    
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        prompt_data = {
            "submitted_code": data.submitted_code,
            "previous_code": data.previous_code,  # Optionally track
            "method_explanation": ex["description"]
        }

        present = app.state.client_wrapper.call("PRESENT", prompt_data)
        return {"present_refactorings": present.present_refactorings,
                "refactor_steps": present.steps, 
                "general_feedback": present.general_feedback}

    except Exception as e:
        return {"error": str(e)}
    

@app.post("/notequiv_feedback")
async def get_notequiv_feedback(data: DiagnoseRequest):
    username = data.username or "anonymous"

    # if not _check_and_increment_request_count(username):
    #     raise HTTPException(
    #         status_code=429,
    #         detail="You have exceeded the maximum number of requests (100)."
    #     )
    
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        # if hint_group == "STATE-BASED":
        test_case_failure = data.test_case_failure or "A test failed."
        prompt_data = {
            "previous_code": data.previous_code,
            "submitted_code": data.submitted_code,
            "test_case_failure": test_case_failure,
            "method_explanation": ex["description"]
        }
        if data.hint_group == "STATE-BASED":
            # print("State-based feedback")
            response = app.state.client_wrapper.call("ERROR", prompt_data)
        else:
            # print("Step-based feedback")
            response = app.state.client_wrapper.call("STEP_ERROR", prompt_data)
        return {
            "error_summary": response.error_summary
            # "error_location": response.error_location
        }

    except Exception as e:
        return {"error": str(e)}

# === Internal Helpers ===

# def _check_and_increment_request_count(username: str) -> bool:
#     with app.state.user_lock:
#         # Initialize count for new users
#         if username not in app.state.user_request_counts:
#             app.state.user_request_counts[username] = 0

#         count = app.state.user_request_counts[username]
#         print(f"User {username} request count: {count}")  # Debug
#         return count <= 10

def build_java_program(user_code: str, test_code: str) -> str:
    return f"""
public class Main {{
{user_code}

public static void main(String[] args) {{
{test_code}
}}
}}""".strip()


def generate_test_code(call_method: str, result_type:str, tests: List[Dict]) -> str:
    def format_input(arg):
        if isinstance(arg, list):
            if len(arg) > 0:
                element_type = type(arg[0]).__name__  # gets the type name as string
            else:
                element_type = 'int'  
            return f"new {element_type}[]{{{','.join(map(str, arg))}}}"
        if isinstance(arg, bool):
            return str(arg).lower()  # Java uses lowercase: true / false
        return str(arg)

    lines = []
    for i, test in enumerate(tests):
        inputs = ", ".join(format_input(arg) for arg in test["inputs"])
        expected = test["expected"]
        call = f"{call_method}({inputs})"
        lines.append(f'{result_type} result{i} = {call};\nSystem.out.println("TEST_RESULT:{i}|expected={expected}|actual=" + result{i});')

    return "\n".join(lines)
    # def format_input(arg):
    #     if isinstance(arg, list):
    #         return str(arg)  # Python lists are directly usable
    #     if isinstance(arg, bool):
    #         return str(arg)  # Python uses True/False
    #     return str(arg)

    # lines = []
    # for i, test in enumerate(tests):
    #     inputs = ", ".join(format_input(arg) for arg in test["inputs"])
    #     expected = test["expected"]
    #     call = f"{call_method}({inputs})"
    #     lines.append(f'result{i} = {call}\nprint(f"TEST_RESULT:{i}|expected={expected}|actual={{result{i}}}")')

    # return "\n".join(lines)



def parse_test_output(line: str):
    match = re.match(r"TEST_RESULT:(\d+)\|expected=(.+?)\|actual=(.+)", line)
    if not match:
        return None
    return {
        "index": int(match.group(1)),
        "expected": match.group(2).strip(),
        "actual": match.group(3).strip()
    }
    
def build_hint_tree(suggestions: List[Dict]) -> Dict:
    def make_node(text, hint_type, index, children=None, meta=None):
        return {
            "Tree": [
                text,            # 0: DESCRIPTION
                hint_type,       # 1: HINTTYPE ("hint", "step", "code")
                children or [],  # 2: BRANCHES
                index,           # 3: PREFIXNR
                -1,              # 4: NEXTSIB
                meta or {}       # 5: METADATA
            ]
        }

    def attach_hint_chain(suggestion: Dict, index_start: int) -> Tuple[Dict, int]:
        index = index_start

        # Shared metadata
        meta = {
            "title": suggestion.get("title"),
            "suggestion": suggestion.get("suggestion"),
            "reason": suggestion.get("reason"),
            "target_code": suggestion.get("target_code"),
            "refactored_code": suggestion.get("refactored_code"),
        }

        # Step 1: general hint
        general = suggestion.get("general_hint") or "Consider refactoring this part of the code."
        general_node = make_node(general, "hint", index, meta=meta)
        index += 1

        # Step 2: targeted hint
        targeted = suggestion.get("targeted_hint")
        if targeted:
            targeted_node = make_node(targeted, "hint", index)
            general_node["Tree"][2].append(targeted_node)
            index += 1
        else:
            targeted_node = None

        # # Step 3: concrete hint
        # concrete = suggestion.get("concrete_hint")
        # if concrete:
        #     concrete_node = make_node(concrete, "step", index)
        #     (targeted_node or general_node)["Tree"][2].append(concrete_node)
        #     index += 1
        # else:
        #     concrete_node = None

        # Step 4: refactored code (text in meta, visual in tree)
        refactored_code = suggestion.get("refactored_code")
        if refactored_code:
            code_node = make_node(refactored_code, "code", index)
            # (concrete_node or targeted_node or general_node)["Tree"][2].append(code_node)
            (targeted_node or general_node)["Tree"][2].append(code_node)
            index += 1

        return general_node, index

    tree_nodes = []
    index = 1  # root = 0
    for suggestion in suggestions:
        node, index = attach_hint_chain(suggestion, index)
        tree_nodes.append(node)

    # Link top-level siblings
    for i in range(len(tree_nodes) - 1):
        tree_nodes[i]["Tree"][4] = tree_nodes[i + 1]["Tree"][3]

    return {
        "Tree": ["Suggested Refactorings", "hint", tree_nodes, 0, -1, {}]
    }


# Fallback route for SPA - serve index.html for all unmatched routes
@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    """Serve index.html for client-side routing"""
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


