from typing import List, Optional
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
# Requests

class CodeRequest(BaseModel):
    code: str
    
class Exercise(BaseModel):
    id: str
    description: str
    start_method: str
    call_method: str
    tests: List[Dict]

class DiagnoseRequest(BaseModel):
    exercise_id: str
    submitted_code: str
    previous_code: Optional[str] = ""
    test_case_failure: Optional[str] = None

class HintRequest(BaseModel):
    exercise_id: str
    submitted_code: str
    

class PromptRequest(BaseModel):
    prompt_type: str
    prompt_data: dict

# LLM responses
class SimpleError(BaseModel):
    error_summary: str = Field(
        description="Explanation of the mistake that was introduced."
    )
    error_location: str = Field(
        description="Where the error occurs in the code (e.g., a short snippet of issue)."
    )
    
class RefactoringStep(BaseModel):
    title: str = Field(
        description="A clear, student-friendly name for the kind of refactoring you used."
    )
    description: str = Field(
        description="What you changed in the structure, logic, or control flow of your method."
    )
    reason: Optional[str] = Field(
        description="Why this change improves the method—for example, it might reduce complexity, improve readability, or make future edits easier."
    )

class RefactoringSteps(BaseModel):
    present_refactorings: bool = Field(
        description="True if correct refactorings were found, otherwise False."
    )
    steps: List[RefactoringStep] = Field(
        description="List of structural or logical refactorings, if any."
    )
    general_feedback: Optional[str] = Field(
        description=(
            "If 'present_refactorings' is False, this should be a short, specific one-line reason explaining "
            "why the changes were bad or increased complexity. For example: "
            "'Reordering operands in an addition does not improve clarity.' "
            "If 'present_refactorings' is True, this may be left empty or used for general comments."
        )
    )


    
class SuggestedRefactoringWithHints(BaseModel):
    title: str = Field(
        description="A concise name for the suggested refactoring (e.g., 'Simplify conditional', 'Use foreach loop')."
    )
    suggestion: str = Field(
        # description="Explanation of the proposed structural or stylistic change to the current code."
        description="A description of the proposed refactoring."
    )
    reason: Optional[str] = Field(
        default=None,
        # description="Why this change would improve the code (e.g., better readability, cleaner structure, idiomatic usage)."
        description="An explanation of why this refactoring improves code quality (e.g., better readability, cleaner structure, idiomatic usage)."
    )
    target_code: Optional[str] = Field(
        default=None,
        description="The specific code snippet or section this suggestion applies to."
    )
    refactored_code: Optional[str] = Field(
        default=None,
        # description="The fully refactored version of the target code snippet, reflecting the proposed improvement."
        description="The refactored code only. No textual explanation."
    )

    # Hints to help guide students toward discovering the refactoring
    general_hint: Optional[str] = Field(
        default=None,
        # description="A broad, non-specific suggestion encouraging the student to review general aspects of the code style or structure (e.g., 'Look for patterns that repeat')."
        description="A high-level description of a quality issue in the code. It must NOT refer to a solution."
    )
    targeted_hint: Optional[str] = Field(
        default=None,
        # description="A more specific hint pointing out a particular line or block in the code that may be improved (e.g., 'Consider whether this loop can be written more simply')."
        description="A detailed textual explanation of the suggested refactoring. It must NOT include code."
    )
    # concrete_hint: Optional[str] = Field(
    #     default=None,
    #     # description="An example or nearly complete suggestion that demonstrates how the code might be changed (e.g., 'Try replacing this if-else chain with a dictionary lookup')."
    #     description="The refactored code only. No textual explanation."
    # )

class SuggestedRefactoringsWithHints(BaseModel):
    suggestions: List[SuggestedRefactoringWithHints] = Field(
        # description="List of suggested behavior-preserving refactorings with progressively specific hints to help students identify and understand improvements."
        description="List of suggested refactorings with three levels of hints to help students improve code quality."
    )