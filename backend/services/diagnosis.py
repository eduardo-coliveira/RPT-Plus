"""Build test programs and interpret their results."""

import re
import json
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

from backend.schemas import Exercise, ExerciseTest


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
        inputs = ", ".join(format_input(arg) for arg in _test_value(test, "inputs"))
        expected = _test_value(test, "expected")
        call = f"{call_method}({inputs})"
        lines.append(
            f'{result_type} result{index} = {call};\n'
            f'System.out.println("TEST_RESULT:{index}|expected={expected}|actual=" + result{index});'
        )

    return "\n".join(lines)


def build_csharp_execution_harness(user_code: str, test_code: str) -> str:
    """Put submitted code and tests in an executable C# program."""

    return f"""
public class Program {{
{user_code}

public static void Main(string[] args) {{
{test_code}
}}
}}""".strip()


def build_csharp_test_runner_code(call_method: str, tests: List[Any]) -> str:
    """Generate C# statements that run the exercise tests."""

    def format_value(value):
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str):
            return json.dumps(value)
        return str(value)

    def format_input(value):
        if not isinstance(value, list):
            return format_value(value)
        if value:
            first = value[0]
            element_type = "bool" if isinstance(first, bool) else "double" if isinstance(first, float) else "string" if isinstance(first, str) else "int"
        else:
            element_type = "int"
        values = ", ".join(format_value(item) for item in value)
        return f"new {element_type}[] {{ {values} }}"

    lines = []
    for index, test in enumerate(tests):
        inputs = ", ".join(format_input(value) for value in _test_value(test, "inputs"))
        expected = str(_test_value(test, "expected")).lower()
        lines.append(
            f'var result{index} = {call_method}({inputs});\n'
            f'System.Console.WriteLine("TEST_RESULT:{index}|expected={expected}|actual=" + '
            f'System.Convert.ToString(result{index}, System.Globalization.CultureInfo.InvariantCulture).ToLowerInvariant());'
        )
    return "\n".join(lines)


def build_execution_harness(user_code: str, exercise: Exercise) -> str:
    """Build a language-specific executable harness for an exercise."""

    if exercise.language == "java":
        test_code = build_java_test_runner_code(exercise.call_method, exercise.result_type, exercise.tests)
        return build_java_execution_harness(user_code, test_code)
    if exercise.language == "csharp":
        test_code = build_csharp_test_runner_code(exercise.call_method, exercise.tests)
        return build_csharp_execution_harness(user_code, test_code)
    raise ValueError(f"Unsupported exercise language: {exercise.language}")


def _test_value(test, key: str):
    return test[key] if isinstance(test, dict) else getattr(test, key)


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


def interpret_execution_result(judge_result: Dict, exercise: Exercise) -> Dict:
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

            if not _test_values_equal(match["expected"], match["actual"]):
                test = exercise.tests[match["index"]]
                inputs = _test_value(test, "inputs")
                return {
                    "status": "notequiv",
                    "call": f'{exercise.call_method}({", ".join(map(str, inputs))})',
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


def _test_values_equal(expected: str, actual: str) -> bool:
    if expected.lower() in {"true", "false"} or actual.lower() in {"true", "false"}:
        return expected.lower() == actual.lower()
    try:
        return Decimal(expected) == Decimal(actual)
    except InvalidOperation:
        return expected == actual


# Compatibility aliases for callers outside the renamed service surface.
build_java_program = build_java_execution_harness
generate_test_code = build_java_test_runner_code
parse_test_output = parse_test_result_line
interpret_diagnosis_result = interpret_execution_result