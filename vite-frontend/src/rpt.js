/** Manage exercise loading, diagnosis, hints, feedback, and action logging. */

import * as rptApi from './rptApi.js';
import * as rptView from './rptView.js';

const workflowState = {
  availableExercises: [],
  selectedExerciseId: '1.even',
  submittedCode: '',
  lastKnownFunctionalCode: '',
  previousSubmittedCode: '',
  hints: [],
  hintTree: undefined,
  hintedCodeSnapshot: '',
  isGeneratingHints: false,
  hintRequestGeneration: 0,
  diagnosisResult: '',
  lastDiagnosedCode: '',
  diagnosedCodeSnapshot: '',
};

/** Record a learner action with the current exercise context. */
async function recordUserAction(action, details = {}) {
  const user = window.currentUser || { username: 'anonymous', group: 'unknown' };
  const payload = {
    username: user.username,
    group: user.group,
    exercise: workflowState.selectedExerciseId,
    current_code: typeof editor !== 'undefined' ? editor.getValue() : '',
    action,
    previous_code: details.previous_code ?? workflowState.previousSubmittedCode,
    code_status: details.code_status ?? null,
    feedback: details.feedback ?? null,
    hint_tree: details.hint_tree ?? null,
  };

  try {
    await rptApi.recordAction(payload);
  } catch (error) {
    console.warn('Action logging failed:', error);
  }
}

/** Start the tutor workflow and register its controls. */
export async function initializeRefactoringTutor() {
  await loadExerciseCatalog();
  document.getElementById('runBtn').addEventListener('click', () => {
    void handleCodeSubmission();
  });
  document.getElementById('gethinttree').addEventListener('click', () => {
    void handleHintRequest();
  });
  document.getElementById('loadex').addEventListener('click', async () => {
      await loadExerciseById(workflowState.selectedExerciseId);
      await recordUserAction('RestartExercise');
  });
  document.getElementById('exerciseSelect').addEventListener('input', async (event) => {
    workflowState.selectedExerciseId = event.target.value;
    await loadExerciseById(workflowState.selectedExerciseId);
    await recordUserAction('NewExercise');
  });

}

window.startApp = initializeRefactoringTutor;

/** Load the exercise catalog and fill the exercise selector. */
async function loadExerciseCatalog() {
  workflowState.availableExercises = await rptApi.fetchExerciseSummaries();
  const select = document.getElementById('exerciseSelect');
  select.innerHTML = '';

  const defaultExercise = workflowState.availableExercises.find((exercise) => exercise.id === '0.isOvenReady') || workflowState.availableExercises[0];
  workflowState.selectedExerciseId = defaultExercise.id;

  workflowState.availableExercises.forEach((exercise) => {
    const option = document.createElement('md-select-option');
    option.value = exercise.id;
    option.textContent = exercise.id;
    if (exercise.id === workflowState.selectedExerciseId) option.setAttribute('selected', 'true');
    select.appendChild(option);
  });

  if (workflowState.selectedExerciseId) await loadExerciseById(workflowState.selectedExerciseId);
}

/** Load an exercise, reset its state, and diagnose its starter code. */
async function loadExerciseById(exerciseId) {
  workflowState.hintRequestGeneration += 1;
  workflowState.isGeneratingHints = false;
  rptView.clearMessages();
  resetHintState();
  rptView.clearHintDisplay();
  rptView.setLoadingIndicatorVisible(false);
  document.getElementById('newhint')?.remove();

  const exercise = await rptApi.fetchExerciseById(exerciseId);
  document.getElementById('exname').textContent = `Exercise ${exercise.id}`;
  document.getElementById('exdesc').textContent = exercise.description;

  workflowState.submittedCode = exercise.start_method;
  workflowState.lastKnownFunctionalCode = exercise.start_method;
  workflowState.previousSubmittedCode = exercise.start_method;
  workflowState.diagnosisResult = null;
  workflowState.lastDiagnosedCode = '';
  editor.setValue(exercise.start_method, -1);

  const container = document.getElementById('refactoringCardContainer');
  container.innerHTML = '';
  container.style.display = 'none';

  rptView.setLoadingIndicatorVisible(true);
  const initialDiagnosis = await requestCodeDiagnosis();
  rptView.setLoadingIndicatorVisible(false);

  if (initialDiagnosis) {
    workflowState.diagnosisResult = initialDiagnosis;
    workflowState.lastDiagnosedCode = exercise.start_method;
  }
}

/** Diagnose the current submission or show its cached diagnosis. */
async function handleCodeSubmission() {
  rptView.clearMessages();
  rptView.clearHintDisplay();
  workflowState.submittedCode = editor.getValue();

  if (!hasUnprocessedCodeChanges()) {
    const reused = await replayCachedDiagnosisResult();
    if (!reused) showFeedbackMessage("You haven't changed the code.", msgtype.WARNING);
    return;
  }

  rptView.setLoadingIndicatorVisible(true);
  const response = await requestCodeDiagnosis();
  rptView.setLoadingIndicatorVisible(false);
  console.log('Response: ', response);

  if (!response) return;

  workflowState.diagnosisResult = response;
  workflowState.diagnosedCodeSnapshot = workflowState.submittedCode.trim();
  workflowState.lastDiagnosedCode = workflowState.submittedCode;

  if (response.status === 'compile_error') {
    await recordUserAction('Diagnose', {
      previous_code: workflowState.previousSubmittedCode,
      code_status: response.status || 'unknown',
      feedback: response.message || null,
    });
    workflowState.previousSubmittedCode = workflowState.submittedCode;
    showCompileError(response.message);
    return;
  }

  if (response.status === 'notequiv') {
    await processNonEquivalentDiagnosis(response);
    workflowState.previousSubmittedCode = workflowState.submittedCode;
    return;
  }

  if (response.status === 'correct') {
    const feedback = await processCorrectDiagnosis();
    await recordUserAction('Diagnose', {
      previous_code: workflowState.previousSubmittedCode,
      code_status: response.status || 'unknown',
      feedback: JSON.stringify(feedback?.refactor_steps) || null,
    });
    workflowState.previousSubmittedCode = workflowState.submittedCode;
  }
}

/** Request and render feedback for a correct diagnosis. */
async function processCorrectDiagnosis() {
  const feedback = await showMessageWhileAwaiting(
    'Generating explanations... ',
    msgtype.CORRECT,
    rptApi.requestRefactoringFeedback({
      exercise_id: workflowState.selectedExerciseId,
      submitted_code: workflowState.submittedCode,
      previous_code: workflowState.lastKnownFunctionalCode,
    }).catch((error) => {
      showFeedbackMessage(`Server error: ${error.message}`, msgtype.FAILURE);
    }),
    { prepend: true },
  );
  workflowState.lastKnownFunctionalCode = workflowState.submittedCode;

  if (feedback?.present_refactorings === false) {
    showFeedbackMessage(feedback.general_feedback || 'No structural or logic changes were found.', msgtype.WARNING);
  } else if (feedback?.refactor_steps?.length > 0) {
    const steps = feedback.steps || feedback.refactor_steps;
    document.getElementById('feedbackContainer').appendChild(
      rptView.createRefactoringFeedbackChip(steps, typeLabels[msgtype.CORRECT], alertClasses[msgtype.CORRECT]),
    );
  } else {
    showFeedbackMessage('No additional improvements detected.', msgtype.CORRECT);
  }

  return feedback;
}

/** Ask the backend to diagnose the current code. */
async function requestCodeDiagnosis() {
  try {
    return await rptApi.requestDiagnosis({
      exercise_id: workflowState.selectedExerciseId,
      submitted_code: workflowState.submittedCode,
      previous_code: workflowState.previousSubmittedCode,
      username: window.currentUser?.username || 'anonymous',
    });
  } catch (error) {
    showFeedbackMessage(`Server error: ${error.message}`, msgtype.FAILURE);
  }
}

/** Ask the backend to explain a change in behavior. */
async function requestNonEquivalentFeedback(diagnosisData) {
  const result = await rptApi.requestNonEquivalentFeedback({
    exercise_id: workflowState.selectedExerciseId,
    submitted_code: workflowState.submittedCode,
    previous_code: workflowState.previousSubmittedCode,
    hint_group: window.currentUser?.group,
    test_case_failure: diagnosisData.reason,
  });
  console.log(result);
  return result;
}

/** Diagnose the code when needed and request hints. */
async function requestHintTree() {
  const generation = workflowState.hintRequestGeneration;
  const exerciseId = workflowState.selectedExerciseId;
  const currentEditorCode = editor.getValue();
  const submittedCodeSnapshot = workflowState.submittedCode;
  const previousCodeSnapshot = workflowState.previousSubmittedCode;
  const codeChangedSinceLastDiagnosis = currentEditorCode.trim() !== workflowState.lastDiagnosedCode.trim();
  const hasCachedDiagnosis = hasCachedDiagnosisForCurrentCode();
  let freshDiagnosis = hasCachedDiagnosis ? workflowState.diagnosisResult : null;

  if (!freshDiagnosis || codeChangedSinceLastDiagnosis) {
    rptView.setLoadingIndicatorVisible(true);
    freshDiagnosis = await requestCodeDiagnosis();
    rptView.setLoadingIndicatorVisible(false);
    if (generation !== workflowState.hintRequestGeneration) return null;
    if (!freshDiagnosis) {
      showFeedbackMessage('Failed to diagnose code. Please try again.', msgtype.WARNING);
      return null;
    }
    workflowState.diagnosisResult = freshDiagnosis;
    workflowState.lastDiagnosedCode = currentEditorCode;
  }

  if (freshDiagnosis.status !== 'correct') {
    await recordUserAction('GetHint', {
      previous_code: previousCodeSnapshot,
      code_status: freshDiagnosis?.status || 'unknown',
      feedback: freshDiagnosis?.message || freshDiagnosis?.reason || null,
      hint_tree: null,
    });
    if (generation !== workflowState.hintRequestGeneration) return null;
    showFeedbackMessage('You need to fix code functionality to get hints on code quality.', msgtype.FAILURE);
    return null;
  }

  if (workflowState.isGeneratingHints) {
    console.log('Hints already generating. Skipping...');
    return null;
  }

  workflowState.isGeneratingHints = true;
  try {
    const data = await rptApi.requestHintTree({
      exercise_id: exerciseId,
      submitted_code: submittedCodeSnapshot,
      previous_code: previousCodeSnapshot,
      hint_group: window.currentUser?.group,
      code_diagnosis: freshDiagnosis.status || null,
      username: window.currentUser?.username || 'anonymous',
    });
    if (generation !== workflowState.hintRequestGeneration) return null;

    console.log('Hint response:', data);
    if (data.error) {
      showFeedbackMessage(`Hint service error: ${data.error}`, msgtype.FAILURE);
      return null;
    }

    await recordUserAction('GetHint', {
      previous_code: previousCodeSnapshot,
      code_status: freshDiagnosis?.status || 'correct',
      hint_tree: data?.hint_tree ? JSON.stringify(data.hint_tree) : null,
      feedback: null,
    });
    if (generation !== workflowState.hintRequestGeneration) return null;

    workflowState.hints = Array.isArray(data?.suggestions) ? data.suggestions : [];
    workflowState.hintTree = data?.hint_tree || null;
    workflowState.hintedCodeSnapshot = submittedCodeSnapshot;

    if (!data.hint_tree) {
      const fallbackHint = Array.isArray(data.suggestions)
        ? data.suggestions.map((suggestion) => suggestion.suggestion || suggestion.general_hint || JSON.stringify(suggestion)).join('\n')
        : data.suggestions;
      showFeedbackMessage(fallbackHint || 'No structured hints available.', msgtype.HINT);
      return null;
    }
    return data;
  } catch (error) {
    if (generation !== workflowState.hintRequestGeneration) return null;
    showFeedbackMessage(`Hint error: ${error.message}`, msgtype.FAILURE);
    return null;
  } finally {
    if (generation === workflowState.hintRequestGeneration) workflowState.isGeneratingHints = false;
  }
}

/** Show existing hints or request new ones. */
async function handleHintRequest() {
  const generation = workflowState.hintRequestGeneration;
  rptView.clearMessages();
  const currentEditorCode = editor.getValue();

  if (workflowState.isGeneratingHints) {
    await showMessageWhileAwaiting('Generating... ', msgtype.HINT, waitForHintsToFinish());
    if (generation !== workflowState.hintRequestGeneration) return;
    renderCurrentHintTree(workflowState.hintTree);
    return;
  }

  if (workflowState.hintTree && currentEditorCode.trim() === workflowState.hintedCodeSnapshot.trim()) {
    workflowState.hintedCodeSnapshot = currentEditorCode;
    renderCurrentHintTree(workflowState.hintTree);
    return;
  }

  rptView.clearHintDisplay();
  const data = await showMessageWhileAwaiting('Generating... ', msgtype.HINT, requestHintTree());
  if (generation !== workflowState.hintRequestGeneration) return;

  if (data) {
    workflowState.hintTree = data.hint_tree;
    renderCurrentHintTree(workflowState.hintTree);
  }
}

/** Connect workflow callbacks to the hint renderer. */
function renderCurrentHintTree(hintTree) {
  rptView.renderCurrentHintTree(hintTree, {
    onEmpty: () => showFeedbackMessage('Your code already looks good!', msgtype.CORRECT),
    onExpandHint: (targetedHint) => recordUserAction('ExpandHint', {
      code_status: workflowState.diagnosisResult?.status || null,
      hint_tree: workflowState.hintTree ? JSON.stringify(workflowState.hintTree) : null,
      feedback: targetedHint,
    }),
    onGetCode: (refactoredCode) => recordUserAction('GetCode', {
      code_status: workflowState.diagnosisResult?.status || null,
      hint_tree: workflowState.hintTree ? JSON.stringify(workflowState.hintTree) : null,
      feedback: refactoredCode,
    }),
  });
}

/** Render feedback for a change in behavior. */
async function processNonEquivalentDiagnosis(data) {
  if (data.expected === 'N/A') {
    showFeedbackMessage('Something did not work!', msgtype.FAILURE);
  } else {
    showFeedbackMessage(`Calling \`${data.call}\` should return \`${data.expected}\`, but it got \`${data.actual}\`.`, msgtype.FAILURE);
  }

  let feedback = data.notEquivalentFeedback;
  if (!feedback) {
    feedback = await showMessageWhileAwaiting(
      'Analyzing error and generating explanation... ',
      msgtype.FAILURE,
      requestNonEquivalentFeedback(data),
    );
    data.notEquivalentFeedback = feedback;
  }

  await recordUserAction('Diagnose', {
    previous_code: workflowState.previousSubmittedCode,
    code_status: 'notequiv',
    feedback: feedback?.error_summary || null,
  });
  document.getElementById('feedbackContainer').appendChild(
    rptView.createNonEquivalentFeedbackChip(
      feedback,
      alertClasses[msgtype.FAILURE],
      typeLabels[msgtype.FAILURE],
    ),
  );
}

/** Add a labeled text message. */
function showFeedbackMessage(message, type) {
  rptView.appendFeedbackMessage(message, alertClasses[type], typeLabels[type]);
}

/** Show a message while an operation completes. */
function showMessageWhileAwaiting(message, type, promise, options = {}) {
  return rptView.appendLoadingMessage(
    message,
    alertClasses[type],
    typeLabels[type],
    promise,
    options,
  );
}

/** Show a compilation error in the feedback area. */
function showCompileError(message) {
  showFeedbackMessage(`Compile Error: ${message}`, msgtype.FAILURE);
}

/** Clear the hint data and its code snapshot. */
function resetHintState() {
  workflowState.hintTree = null;
  workflowState.hints = [];
  workflowState.hintedCodeSnapshot = '';
}

/** Check whether the editor still matches the last diagnosis. */
function hasCachedDiagnosisForCurrentCode() {
  return Boolean(
    workflowState.diagnosisResult &&
    typeof workflowState.diagnosisResult.status === 'string' &&
    editor.getValue().trim() === workflowState.lastDiagnosedCode.trim()
  );
}

/** Show the cached diagnosis for unchanged code. */
async function replayCachedDiagnosisResult() {
  if (!workflowState.diagnosisResult || workflowState.submittedCode.trim() !== workflowState.diagnosedCodeSnapshot.trim()) return false;
  switch (workflowState.diagnosisResult.status) {
    case 'compile_error':
      showCompileError(workflowState.diagnosisResult.message);
      return true;
    case 'notequiv':
      await processNonEquivalentDiagnosis(workflowState.diagnosisResult);
      return true;
    case 'correct':
      await processCorrectDiagnosis();
      return true;
    default:
      return false;
  }
}

/** Check whether the code differs from the last diagnosis. */
function hasUnprocessedCodeChanges() {
  return workflowState.submittedCode.trim() !== workflowState.diagnosedCodeSnapshot.trim();
}

const msgtype = {
  FAILURE: 0,
  HINT: 1,
  CORRECT: 2,
  WARNING: 3,
};

const alertClasses = ['failure', 'hint', 'correct', 'warning'];
const typeLabels = ['', '', '', 'Warning:'];