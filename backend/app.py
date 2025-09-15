from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from backend.schemas import CodeRequest, HintRequest, DiagnoseRequest
from backend.prompting import get_client_wrapper
import os
import requests
import json
import re
from typing import List, Dict, Tuple

# === FastAPI App Setup ===

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PISTON_URL = "https://emkc.org/api/v2/piston/execute"
app.state.client_wrapper = get_client_wrapper("gpt-4-turbo", local=False)

# === Load Exercises ===

with open(os.path.join("exercise_data","exercises.json")) as f:
    EXERCISES = {ex["id"]: ex for ex in json.load(f)}


# === Routes ===

@app.get("/")
def read_root():
    return {"status": "ok"}


@app.get("/exercises")
def list_exercises():
    return [{"id": ex["id"], "description": ex["description"]} for ex in EXERCISES.values()]


@app.get("/exercise/{exercise_id}")
def get_exercise(exercise_id: str):
    ex = EXERCISES.get(exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return ex


@app.post("/run_code")
async def run_code(data: CodeRequest):
    piston_data = {
        "language": "java",
        "version": "17.0.4",
        "files": [{"name": "Main.java", "content": data.code}]
    }
    try:
        response = requests.post(PISTON_URL, json=piston_data)
        response.raise_for_status()
        
        return response.json()
    except Exception as e:
        return {"error": str(e)}


@app.post("/diagnose")
async def diagnose(data: DiagnoseRequest):
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    full_code = build_java_program(data.submitted_code, generate_test_code(ex["call_method"], ex["result_type"], ex["tests"]))

    try:
        response = requests.post(PISTON_URL, json={
            "language": "java",
            "version": "15.0.2",
            "files": [{"name": "Main.java", "content": full_code}]
        }).json()

        run_info = response.get("run", {})
        output = run_info.get("output", "")
        stderr = run_info.get("stderr", "")
        exit_code = run_info.get("code", 0)
        
        

        # === Catch Compile or Runtime Errors ===

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
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        prompt_data = {
            "submitted_code": data.submitted_code,
            "previous_code": "",
            "method_explanation": ex["description"]
        }
        suggested = app.state.client_wrapper.call("SUGGESTED", prompt_data)
        tree = build_hint_tree([s.model_dump() for s in suggested.suggestions])
        return {
            "status": "correct",
            "hint_tree": tree,
            "suggestions": suggested.suggestions
            }
    except Exception as e:
        return {"error": str(e)}


@app.post("/correct_feedback")
async def get_correct_feedback(data: DiagnoseRequest):
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
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        test_case_failure = data.test_case_failure or "A test failed."
        prompt_data = {
            "submitted_code": data.submitted_code,
            "test_case_failure": test_case_failure,
            "method_explanation": ex["description"]
        }
        response = app.state.client_wrapper.call("ERROR", prompt_data)
        return {
            "error_summary": response.error_summary,
            "error_location": response.error_location
        }
    except Exception as e:
        return {"error": str(e)}

    

@app.post("/hints")
async def get_flat_hints(data: HintRequest):
    ex = EXERCISES.get(data.exercise_id)
    if not ex:
        raise HTTPException(status_code=404, detail="Exercise not found")

    try:
        prompt_data = {
            "submitted_code": data.submitted_code,
            "previous_code": "",  
            "method_explanation": ex["description"]
        }

        suggested = app.state.client_wrapper.call("SUGGESTED", prompt_data)
        return {"suggestions": suggested.suggestions}

    except Exception as e:
        return {"error": str(e)}


# === Internal Helpers ===

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

        # Step 3: concrete hint
        concrete = suggestion.get("concrete_hint")
        if concrete:
            concrete_node = make_node(concrete, "step", index)
            (targeted_node or general_node)["Tree"][2].append(concrete_node)
            index += 1
        else:
            concrete_node = None

        # Step 4: refactored code (text in meta, visual in tree)
        refactored_code = suggestion.get("refactored_code")
        if refactored_code:
            code_node = make_node(refactored_code, "code", index)
            (concrete_node or targeted_node or general_node)["Tree"][2].append(code_node)
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


