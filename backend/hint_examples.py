from refactoring_misconceptions.errors import ALL_SNIPPETS

def get_snippet_by_id(snippet_id):
    return next(s for s in ALL_SNIPPETS if s["id"] == snippet_id)

HINT_TREE_EXAMPLES = [
    {
        "error_id": "C1",
        "hint_tree": {
            "general_hint": "You merged two if statements without considering the else branch. The boolean expression does not cover all possible cases.",
            # "targeted_hint": "Can you rewrite the boolean expression using OR and NOT operators to handle cases where positivesOnly is false?",
            "targeted_hint": """First write the expression for the only case where sum += value is not executed.\n
                                Negate the whole expression.\n
                                Then apply De Morgan's law: The negation of 'A and B' is the same as 'not A or not B'.""",
            "refactored_code": "if (!positivesOnly || value > 0) {{\n    sum += value;\n}}"
        }
    },
    {
        "error_id": "C4",
        "hint_tree": {
            "general_hint": "You reversed the expression in the if statement incorrectly. The current boolean expression is always true.",
            # "targeted_hint": "Can you rewrite the boolean expression using an AND operator to properly check for weekdays?",
            "targeted_hint": """First take the original exercise expression: 'day == 6 || day == 7'.\n
                                Negate the whole expression.\n
                                Then apply De Morgan's law: The negation of 'A or B' is the same as 'not A and not B'.""",
            "refactored_code": "if (day != 6 && day != 7) {{\n    score -= 3;\n}}"
        }
    }
]