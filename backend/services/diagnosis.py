"""Build Java test programs and interpret their results."""

import re
from typing import Dict, List, Tuple


def build_java_execution_harness(user_code: str, test_code: str) -> str:
    """Put submitted code and tests in an executable Java class."""

    return f"""
public class Main {{
{user_code}

public static void main(String[] args) {{
{test_code}
}}
}}""".strip()


def build_java_test_runner_code(call_method: str, result_type: str, tests: List[Dict]) -> str:
    """Generate Java statements that run the exercise tests."""

    def format_input(arg):
        """Format one test input as a Java argument."""

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


def parse_test_result_line(line: str):
    """Read one test result from program output."""

    match = re.match(r"TEST_RESULT:(\d+)\|expected=(.+?)\|actual=(.+)", line)
    if not match:
        return None
    return {
        "index": int(match.group(1)),
        "expected": match.group(2).strip(),
        "actual": match.group(3).strip(),
    }


def interpret_execution_result(judge_result: Dict, exercise: Dict) -> Dict:
    """Turn Judge0 output into a diagnosis response."""

    output = judge_result.get("stdout") or judge_result.get("output") or ""
    stderr = judge_result.get("stderr") or ""
    error_output = judge_result.get("compile_output", "") or stderr

    status_id = judge_result.get("status", {}).get("id", 3)
    if status_id == 6:
        return {"status": "compile_error", "message": error_output}

    test_results_found = False
    for line in output.splitlines():
        if line.startswith("TEST_RESULT:"):
            test_results_found = True
            match = parse_test_result_line(line)
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


# Compatibility aliases for callers outside the renamed service surface.
build_java_program = build_java_execution_harness
generate_test_code = build_java_test_runner_code
parse_test_output = parse_test_result_line
interpret_diagnosis_result = interpret_execution_result