"""Build prompt data and hint trees for feedback."""

from typing import Dict, List

from backend.schemas import Exercise


def build_prompt_context(request_data, exercise: Exercise) -> Dict:
    """Combine a feedback request with the exercise description."""

    return {
        "submitted_code": request_data.submitted_code,
        "previous_code": request_data.previous_code,
        "method_explanation": exercise.description,
        "language": "C#" if exercise.language == "csharp" else "Java",
    }


def generate_non_equivalence_feedback(request_data, exercise: Exercise, client_wrapper) -> Dict:
    """Explain why a refactoring changed behavior."""

    test_case_failure = request_data.test_case_failure or "A test failed."
    prompt_data = build_prompt_context(request_data, exercise)
    prompt_data["test_case_failure"] = test_case_failure
    prompt_type = "ERROR" if request_data.hint_group == "STATE-BASED" else "STEP_ERROR"
    response = client_wrapper.request_structured_response(prompt_type, prompt_data)
    return {"error_summary": response.error_summary}


def build_hint_tree(suggestions: List[Dict]) -> Dict:
    """Turn model suggestions into a hint tree."""

    def create_hint_node(text, hint_type, index, children=None, meta=None):
        """Create one hint tree node."""

        return {
            "Tree": [
                text,
                hint_type,
                children or [],
                index,
                -1,
                meta or {},
            ]
        }

    def attach_hint_chain(suggestion: Dict, index_start: int):
        """Build the hint steps for one suggestion."""

        index = index_start
        meta = {
            "title": suggestion.get("title"),
            "suggestion": suggestion.get("suggestion"),
            "reason": suggestion.get("reason"),
            "target_code": suggestion.get("target_code"),
            "refactored_code": suggestion.get("refactored_code"),
        }

        general = suggestion.get("general_hint") or "Consider refactoring this part of the code."
        general_node = create_hint_node(general, "hint", index, meta=meta)
        index += 1

        targeted = suggestion.get("targeted_hint")
        if targeted:
            targeted_node = create_hint_node(targeted, "hint", index)
            general_node["Tree"][2].append(targeted_node)
            index += 1
        else:
            targeted_node = None

        refactored_code = suggestion.get("refactored_code")
        if refactored_code:
            code_node = create_hint_node(refactored_code, "code", index)
            (targeted_node or general_node)["Tree"][2].append(code_node)
            index += 1

        return general_node, index

    tree_nodes = []
    index = 1
    for suggestion in suggestions:
        node, index = attach_hint_chain(suggestion, index)
        tree_nodes.append(node)

    for index in range(len(tree_nodes) - 1):
        tree_nodes[index]["Tree"][4] = tree_nodes[index + 1]["Tree"][3]

    return {"Tree": ["Suggested Refactorings", "hint", tree_nodes, 0, -1, {}]}


build_code_prompt_context = build_prompt_context
generate_notequiv_feedback = generate_non_equivalence_feedback