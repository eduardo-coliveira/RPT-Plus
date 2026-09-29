from backend.services.feedback import build_hint_tree
from backend.services.diagnosis import (
    build_csharp_execution_harness,
    build_csharp_test_runner_code,
    build_java_execution_harness,
    build_java_test_runner_code,
    parse_test_result_line,
)


def test_build_java_program_wraps_submission_and_tests():
    result = build_java_execution_harness("public static int answer() { return 42; }", "System.out.println(answer());")

    assert result == (
        "public class Main {\n"
        "public static int answer() { return 42; }\n\n"
        "public static void main(String[] args) {\n"
        "System.out.println(answer());\n"
        "}\n}"
    )


def test_generate_test_code_formats_booleans_and_arrays():
    result = build_java_test_runner_code(
        "count",
        "int",
        [
            {"inputs": [True, [1, 2]], "expected": 3},
            {"inputs": [[]], "expected": 0},
        ],
    )

    assert result == (
        'int result0 = count(true, new int[]{1,2});\n'
        'System.out.println("TEST_RESULT:0|expected=3|actual=" + result0);\n'
        'int result1 = count(new int[]{});\n'
        'System.out.println("TEST_RESULT:1|expected=0|actual=" + result1);'
    )


def test_build_csharp_test_runner_formats_arrays_and_result_output():
    result = build_csharp_test_runner_code(
        "isReady",
        [{"inputs": [150], "expected": "true"}, {"inputs": [[1, 2]], "expected": 3}],
    )

    assert 'isReady(150)' in result
    assert 'isReady(new int[] { 1, 2 })' in result
    assert 'expected=true|actual=" +' in result
    assert "InvariantCulture" in result


def test_build_csharp_execution_harness_wraps_submission():
    result = build_csharp_execution_harness("public static int answer() { return 42; }", "var result = answer();")

    assert "public class Program" in result
    assert "public static void Main(string[] args)" in result
    assert "public static int answer()" in result


def test_parse_test_output_extracts_fields_and_rejects_invalid_lines():
    assert parse_test_result_line("TEST_RESULT:2|expected=7|actual= 8 ") == {
        "index": 2,
        "expected": "7",
        "actual": "8",
    }
    assert parse_test_result_line("not a test result") is None


def test_build_hint_tree_links_hints_code_and_sibling_suggestions():
    tree = build_hint_tree(
        [
            {
                "title": "Simplify",
                "suggestion": "Use a direct return",
                "reason": "Fewer branches",
                "target_code": "if (x) ...",
                "refactored_code": "return x;",
                "general_hint": "Look at the branches",
                "targeted_hint": "Can you return earlier?",
            },
            {"general_hint": "Review the loop"},
        ]
    )

    root_children = tree["Tree"][2]
    first_hint = root_children[0]["Tree"]
    targeted_hint = first_hint[2][0]["Tree"]
    code_hint = targeted_hint[2][0]["Tree"]
    second_hint = root_children[1]["Tree"]

    assert tree["Tree"][0] == "Suggested Refactorings"
    assert first_hint[:2] == ["Look at the branches", "hint"]
    assert first_hint[3:5] == [1, 4]
    assert first_hint[5]["title"] == "Simplify"
    assert targeted_hint[:2] == ["Can you return earlier?", "hint"]
    assert code_hint[:2] == ["return x;", "code"]
    assert second_hint[:2] == ["Review the loop", "hint"]
    assert second_hint[3] == 4