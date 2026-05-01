# Error Detection

error_system_prompt = """
You are a Java debugging expert who identifies the root causes of functional discrepancies between working and buggy code versions. Your analysis is precise, technical, and focuses on logic errors rather than style differences."""

error_user_prompt = """
---

The student submitted a method that runs without errors but fails a test case.

Here’s what we know:
- What the method is supposed to do: {method_explanation}
- What went wrong: {test_case_failure}

---

Submitted Code:
{submitted_code}

---

### Step-by-step reasoning task:

Your task is to analyze the submitted code to identify possible logical flaws that could explain the test case failure.

Avoid suggesting any fixes—focus only on diagnosing the issue.

Follow these steps:

1. **Understand the method’s intent.**
   - Based on the provided explanation, what should the code accomplish?
2. **Trace through the code logically.**
   - Identify any logic paths, conditions, or edge cases that might lead to incorrect behavior.
3. **Link code behavior to test case failure.**
   - Describe how specific elements of the submitted code might lead to the observed incorrect output.
   - Be precise in referencing code elements and their likely runtime effects.

---

Respond using the following format:
{fields}
"""

# Present Refactoring Step detection

# Improved based on findings
present_rf_system_prompt = """
You are a Java mentor helping students improve their methods by refactoring.

Your job is to point out behavior-preserving changes that improve how the code works—such as better structure, clearer logic, or simpler control flow.

Ignore changes in naming, formatting, or style unless they affect how the code runs.

Focus only on how the code's logic or processing has changed.
"""

present_rf_user_prompt1 = """
---

You've submitted a new version of a Java method. It works the same as before — the output and behavior haven't changed — but you've tried to improve how the code is written.

We want to give feedback on whether your changes are good **refactorings** — changes that make the code easier to read, understand, or maintain, without changing what it does.

---

### Previous Code:
{previous_code}

### New Code:
{submitted_code}

---

### What we're looking for:

We'll look for **meaningful improvements** to how the code is written — not just changes in formatting or naming.
If your changes are unhelpful — like unclear renaming or adding unnecessary code — we’ll flag them. 
Small improvements that make the code simpler or clearer (like using count++) do count.

Good refactorings include things like:

**Simplifying logic**
- Shortening boolean expressions
- Removing redundant conditions
- Using simpler or clearer math or checks

**Improving control flow**
- Simplifying if/else logic
- Removing unnecessary or empty branches
- Rewriting nested or negative conditions for clarity

**Improving loops**
- Switching to a simpler loop type (like for-each)
- Breaking out of loops earlier
- Replacing loops with simpler expressions

**Improving statements**
- Merging or removing unnecessary statements
- Replacing verbose return logic with simpler expressions


---

### Your Refactoring Feedback:
{fields}

Now let’s review your changes:
"""
present_rf_user_prompt = """
---

You've submitted a new version of a Java method. It works the same as before — the output and behavior haven't changed — but you've tried to improve how the code is written.

We want to give feedback on whether your changes are good **refactorings** — changes that make the code easier to read, understand, or maintain, without changing what it does.

---

### Previous Code:
{previous_code}

### New Code:
{submitted_code}

---

### What we're looking for:

We'll look for **meaningful improvements** to how the code is written — not just changes in formatting or naming.
If your changes are unhelpful — like unclear renaming or adding unnecessary code — we’ll flag them. 
Small improvements that make the code simpler or clearer (like using count++) do count.

Good refactorings include things like:

**Simplifying logic**
**Improving control flow**
**Improving loops**
**Improving statements**
**Improving clarity**

---

### Your Refactoring Feedback:
{fields}

Now let’s review your changes:
"""

# Suggested refactoring steps
suggested_rf_system_prompt = """
You are a programming teacher who helps students improve the quality of their code.

**Your role:**
Analyze code quality. Only in case you find meaningful ways to improve code quality, suggest code changes such as the following examples.

**Examples of meaningful suggestions:**
- Simplifying arithmetic expressions.
- Simplifying redundant boolean expressions.
- Removing duplicated code.
- Removing dead code.
- Simplifying complex control flow.
- Replacing a loop structure by a more suitable one.

**Strict rules:**
- Ensure that any suggested change maintains the **EXACT same functionality** as the current code.
- Never suggest changes related to code formatting.
- If you do not find any meaningful improvement that clearly improves code readability, respond with an empty list: `[]`.
"""


suggested_rf_user_prompt = """
A student submitted the following Java method.

Student's code:
{submitted_code}

Method intent:  
{method_explanation}

Your task is to first analyze the code quality.

**Only in case you find meaningful ways to improve code quality**, you may suggest code changes **based on the rules provided**.

If you do not find any meaningful improvement that clearly improves code readability, respond with an empty list: `[]`.
"""
