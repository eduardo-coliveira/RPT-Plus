/** Helpers for calling the refactoring tutor API. */

const apiBaseUrl = "";

/** Fetch and decode a JSON response. */
async function getJsonResponse(path) {
  const response = await fetch(`${apiBaseUrl}${path}`);
  return response.json();
}

/** Send a JSON payload and decode the response. */
async function postJsonResponse(path, payload) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

/** Load the exercise summaries for the selector. */
export function fetchExerciseSummaries() {
  return getJsonResponse("/exercises");
}

/** Load one exercise. */
export function fetchExerciseById(exerciseId) {
  return getJsonResponse(`/exercise/${exerciseId}`);
}

/** Ask the backend to diagnose submitted code. */
export function requestDiagnosis(payload) {
  return postJsonResponse("/diagnose", payload);
}

/** Ask the backend to explain a change in behavior. */
export function requestNonEquivalentFeedback(payload) {
  return postJsonResponse("/notequiv_feedback", payload);
}

/** Ask the backend for refactoring feedback. */
export function requestRefactoringFeedback(payload) {
  return postJsonResponse("/correct_feedback", payload);
}

/** Ask the backend for hints about the current submission. */
export function requestHintTree(payload) {
  return postJsonResponse("/hint_tree", payload);
}

/** Save one learner action in the backend log. */
export function recordAction(payload) {
  return postJsonResponse("/log_action", payload);
}