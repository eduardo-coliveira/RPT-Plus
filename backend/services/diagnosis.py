import re
from typing import Dict, List, Tuple


def build_java_program(user_code: str, test_code: str) -> str:
    return f"""
public class Main {{
{user_code}

public static void main(String[] args) {{
{test_code}
}}
}}""".strip()


def generate_test_code(call_method: str, result_type: str, tests: List[Dict]) -> str:
    def format_input(arg):
        if isinstance(arg, list):
            if len(arg) > 0:
                element_type = type(arg[0]).__name__
            else:
                element_type = "int"
            return f"new {element_type}[]{{{','.join(map(str, arg))}}}"
        if isinstance(arg, bool):
            return str(arg).lower()
        return str(arg)

    lines = []
    for index, test in enumerate(tests):
        inputs = ", ".join(format_input(arg) for arg in test["inputs"])
        expected = test["expected"]
        call = f"{call_method}({inputs})"
        lines.append(
            f'{result_type} result{index} = {call};\n'
            f'System.out.println("TEST_RESULT:{index}|expected={expected}|actual=" + result{index});'
        )

    return "\n".join(lines)


def parse_test_output(line: str):
    match = re.match(r"TEST_RESULT:(\d+)\|expected=(.+?)\|actual=(.+)", line)
    if not match:
        return None
    return {
        "index": int(match.group(1)),
        "expected": match.group(2).strip(),
        "actual": match.group(3).strip(),
    }


def interpret_diagnosis_result(result: Dict, exercise: Dict) -> Dict:
    output = result.get("stdout") or result.get("output") or ""
    stderr = result.get("stderr") or ""
    error_output = result.get("compile_output", "") or stderr

    status_id = result.get("status", {}).get("id", 3)
    if status_id == 6:
        return {"status": "compile_error", "message": error_output}

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
                    "actual": "N/A",
                }

            if match["expected"] != match["actual"]:
                test = exercise["tests"][match["index"]]
                return {
                    "status": "notequiv",
                    "call": f'{exercise["call_method"]}({", ".join(map(str, test["inputs"]))})',
                    "expected": match["expected"],
                    "actual": match["actual"],
                    "reason": f"Expected {match['expected']}, got {match['actual']}",
                }

    if not test_results_found:
        return {
            "status": "notequiv",
            "reason": stderr,
            "expected": "N/A",
            "actual": "N/A",
        }

    return {"status": "correct"}