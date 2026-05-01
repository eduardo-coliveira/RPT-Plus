// Refactored RPT Frontend

const apiUrl = "";

let exercises = [];
let currentExerciseId = "1.even";
let submittedCode = "";
let previousFunctionalCode = "";
let previousCode = "";
let currentHints = [];
let currentHintTree;
let isGeneratingHints = false;


window.addEventListener("DOMContentLoaded", async () => {
  await loadExercises();
  document.getElementById("runBtn").addEventListener("click", handleRun);
  document.getElementById("gethinttree").addEventListener("click", handleHints);
  document.getElementById("loadex").addEventListener("click", () => loadExercise(currentExerciseId));
  document.getElementById("exerciseSelect").addEventListener("input", (e) => {
    currentExerciseId = e.target.value;
    loadExercise(currentExerciseId);
  });
});

async function loadExercises() {
  const res = await fetch(`${apiUrl}/exercises`);
  exercises = await res.json();
  const select = document.getElementById("exerciseSelect");
  select.innerHTML = "";

  let defaultExercise = exercises.find(ex => ex.id === "1.even") || exercises[0];
  currentExerciseId = defaultExercise.id;

  exercises.forEach((ex) => {
    const option = document.createElement("md-select-option");
    option.value = ex.id;
    option.textContent = ex.id;
    if (ex.id === currentExerciseId) option.setAttribute("selected", "true");
    select.appendChild(option);
  });

  if (currentExerciseId) {
    await loadExercise(currentExerciseId);
  }
}


async function loadExercise(id) {
  clearMessages();
  clearHints();
  hideSpinner();
  document.getElementById("newhint")?.remove();
  const res = await fetch(`${apiUrl}/exercise/${id}`);
  const ex = await res.json();

  document.getElementById("exname").textContent = `Exercise ${ex.id}`;
  document.getElementById("exdesc").textContent = ex.description;

  submittedCode = ex.start_method;
  previousFunctionalCode = ex.start_method;
  previousCode = ex.start_method;

  currentHints = [];
  currentHintTree = null;
  editor.setValue(ex.start_method, -1);

  const container = document.getElementById("refactoringCardContainer");
  container.innerHTML = "";
  container.style.display = "none";
}


async function handleRun() {
  clearMessages();
  clearHints();
  submittedCode = editor.getValue();

  if (!isNewSubmission()) {
    showMsg("You haven't changed the code.", msgtype.WARNING);
    return;
  }

  showSpinner();
  const response = await diagnoseCode();
  hideSpinner();
  if (!response) return;

  if (response.status === "compile_error") return handleError(response.message);
  if (response.status === "notequiv") return handleNotEquivalent(response);
  if (response.status === "correct") return handleCorrect();
}

async function handleCorrect() {
  const feedbackPromise = showMsgWithSpinner(
    "Generating explanations... ",
    msgtype.CORRECT,
    generateCorrectFeedback(),
    { prepend: true }
  );
  const hintPromise = generateHints();
  
  // Start spinner for hints using your built-in function
  const hintResultPromise = showMsgWithSpinner(
    "Looking for further improvements... ",
    msgtype.HINT,
    hintPromise
  );


  // Handle feedback as soon as it's ready
  const feedback = await feedbackPromise;
  previousFunctionalCode = submittedCode;

  if (feedback?.present_refactorings === false) {
    showMsg(
      feedback.general_feedback || "No structural or logic changes were found.",
      msgtype.WARNING
    );
  } else if (feedback?.refactor_steps?.length > 0) {
    const steps = feedback.steps || feedback.refactor_steps;

    const chip = document.createElement("div");
    chip.className = `chip ${alertClasses[msgtype.CORRECT]}`;
    chip.style.flexDirection = "column";
    chip.style.alignItems = "stretch";

    const header = document.createElement("div");
    header.innerHTML = `<strong>${typeLabels[msgtype.CORRECT]}</strong>You performed ${steps.length} refactoring(s).`;
    header.style.marginBottom = "8px";
    chip.appendChild(header);

    const embeddedCards = renderEmbeddedCards(steps);
    embeddedCards.forEach(card => chip.appendChild(card));

    document.getElementById("feedbackContainer").appendChild(chip);
  } else {
    showMsg("No additional improvements detected.", msgtype.CORRECT);
  }

  // When hint generation is done, show improvement summary
  const hintResult = await hintResultPromise;

  if (hintResult) {
    currentHints = hintResult.suggestions || [];
    currentHintTree = hintResult.hint_tree;

    const numHints = currentHints.length;
    const improvementMsg = numHints > 0
      ? `There is still ${numHints} potential improvement${numHints > 1 ? "s" : ""} you can make.`
      : "No additional improvements detected after analysis.";

    showMsg(improvementMsg, numHints > 0 ? msgtype.WARNING : msgtype.CORRECT);
  }
}





async function diagnoseCode() {
  try {
    const res = await fetch(`${apiUrl}/diagnose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        exercise_id: currentExerciseId,
        submitted_code: submittedCode,
        previous_code: previousCode,
      })
    });
    previousCode = submittedCode;
    return await res.json();
  } catch (err) {
    showMsg(`Server error: ${err.message}`, msgtype.FAILURE);
  }
}

async function generateNotEquivalentFeedback(data) {
  const res = await fetch(`${apiUrl}/notequiv_feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      exercise_id: currentExerciseId,
      submitted_code: submittedCode,
      test_case_failure: data.reason
    })
  });

  const result = await res.json();
  console.log(result);
  return result;
}



async function generateCorrectFeedback() {
  try {
    const res = await fetch(`${apiUrl}/correct_feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        exercise_id: currentExerciseId,
        submitted_code: submittedCode,
        previous_code: previousFunctionalCode,
      })
    });
    // previousCode = submittedCode;
    return await res.json();
  } catch (err) {
    showMsg(`Server error: ${err.message}`, msgtype.FAILURE);
  }
}

async function generateHints() {
  if (isGeneratingHints) {
    console.log("Hints already generating. Skipping...");
    return null;
  }

  isGeneratingHints = true;
  try {
    const res = await fetch(`${apiUrl}/hint_tree`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        exercise_id: currentExerciseId,
        submitted_code: submittedCode
      })
    });

    const data = await res.json();
    console.log("Hint response:", data);

    if (!data.hint_tree) {
      // showMsg("No structured hints available.", msgtype.FAILURE);
      showMsg(data.suggestions, msgtype.HINT);
      return null;
    }

    return data;
  } catch (err) {
    showMsg(`Hint error: ${err.message}`, msgtype.FAILURE);
    return null;
  } finally {
    isGeneratingHints = false;
  }
}


async function handleHints() {
  clearMessages();
  submittedCode = editor.getValue();
  console.log("[handleHints] Invoked");
  // If already generating, show spinner message and wait for it to finish
  if (isGeneratingHints) {
    console.log("[handleHints] Hints are already generating. Waiting...");
    await showMsgWithSpinner(
      "Generating... ",
      msgtype.HINT,
      waitForHintsToFinish()
    );
    console.log("[handleHints] Finished waiting. Rendering currentHintTree.");
    renderHintTree(currentHintTree);
    return;
  }

  // If we already have a valid hint tree and code hasn't changed, render it immediately
  if (currentHintTree && submittedCode.trim() === previousFunctionalCode.trim()) {
    console.log("[handleHints] Reusing existing hint tree.");
    renderHintTree(currentHintTree);
    return;
  }

  // Otherwise, generate new hints
  console.log("[handleHints] No valid hint tree or code changed. Generating new hints...");
  const data = await showMsgWithSpinner(
    "Generating... ",
    msgtype.HINT,
    generateHints()
  );

  if (data) {
    console.log("[handleHints] Hints generated successfully:", data);
    currentHintTree = data.hint_tree;
    renderHintTree(currentHintTree);
  } else {
    console.warn("[handleHints] Hint generation failed or returned null.");
  }
}

function waitForHintsToFinish(interval = 100) {
  return new Promise((resolve) => {
    const check = () => {
      if (!isGeneratingHints) return resolve();
      setTimeout(check, interval);
    };
    check();
  });
}



function isNewSubmission() {
  return (submittedCode.trim() !== previousCode.trim()) && (submittedCode.trim() !== previousFunctionalCode.trim());
}

function handleError(message) {
  showMsg(`Compile Error: ${message}`, msgtype.FAILURE);
}

async function handleNotEquivalent(data) {
  // Message about what failed
  console.log(data)
  if (data.expected == 'N/A') {
    showMsg(
    `Something didn't work!`,
    msgtype.FAILURE
  );
  }
  else {
    showMsg(
    `Calling \`${data.call}\` should return \`${data.expected}\`, but got \`${data.actual}\`.`,
    msgtype.FAILURE
  );
  }


  // Spinner + fetch explanation
  const feedback = await showMsgWithSpinner(
    "Analyzing error and generating explanation... ",
    msgtype.FAILURE,
    generateNotEquivalentFeedback(data)
  );

  // Render explanation chip + embedded content
  const chip = document.createElement("div");
  chip.className = `chip ${alertClasses[msgtype.FAILURE]}`;
  chip.style.flexDirection = "column";
  chip.style.alignItems = "stretch";

  const header = document.createElement("div");
  header.innerHTML = `<strong>${typeLabels[msgtype.FAILURE]}</strong>: Here's what might have gone wrong.`;
  header.style.marginBottom = "8px";
  chip.appendChild(header);

  const card = document.createElement("div");
  card.className = "embedded-card";

  const title = document.createElement("h3");
  title.textContent = "Explanation";
  card.appendChild(title);

  const summaryDetails = document.createElement("details");
  const summarySummary = document.createElement("summary");
  summarySummary.innerHTML = `<strong>What went wrong</strong>`;
  summaryDetails.appendChild(summarySummary);

  const summaryContent = document.createElement("p");
  summaryContent.textContent = feedback.error_summary;
  summaryDetails.appendChild(summaryContent);
  card.appendChild(summaryDetails);

  const locationDetails = document.createElement("details");
  const locationSummary = document.createElement("summary");
  locationSummary.innerHTML = `<strong>Where in the code</strong>`;
  locationDetails.appendChild(locationSummary);

  const locationContent = document.createElement("code");
  locationContent.textContent = feedback.error_location;
  locationDetails.appendChild(locationContent);
  card.appendChild(locationDetails);

  chip.appendChild(card);

  document.getElementById("feedbackContainer").appendChild(chip);
}




function renderCards(items, type, containerId = "refactoringCardContainer") {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  container.style.display = "flex";

  const formatter = type === "RefactoringStep" ? formatRefactoringStep : formatSuggestedRefactoringWithHints;
  items.forEach((item, i) => {
    container.appendChild(createCard(formatter(item, i)));
  });
}

function createCard({ title, fields }) {
  const card = document.createElement("div");
  card.className = "card";

  if (title) {
    const heading = document.createElement("h3");
    heading.textContent = title;
    card.appendChild(heading);
  }

  fields.forEach(({ label, value, isCode }) => {
    if (!value) return;
    const detail = document.createElement("details");
    const summary = document.createElement("summary");
    summary.innerHTML = `<strong>${label}</strong>`;
    detail.appendChild(summary);

    const content = document.createElement(isCode ? "code" : "p");
    content.textContent = value;
    detail.appendChild(content);
    card.appendChild(detail);
  });

  return card;
}

function formatRefactoringStep(step, index) {
  return {
    title: `${index + 1}. ${step.title}`,
    fields: [
      { label: "Description", value: step.description },
      { label: "Reason", value: step.reason }
    ]
  };
}

function formatSuggestedRefactoringWithHints(step, index) {
  return {
    title: `${index + 1}. ${step.title}`,
    fields: [
      { label: "Suggestion", value: step.suggestion },
      { label: "Reason", value: step.reason },
      { label: "Target Code", value: step.target_code, isCode: true },
      { label: "Refactored Code", value: step.refactored_code, isCode: true },
      { label: "General Hint", value: step.general_hint },
      { label: "Targeted Hint", value: step.targeted_hint },
      { label: "Concrete Hint", value: step.concrete_hint },
    ]
  };
}

function renderHintTree(tree) {
  clearMessages();
  const container = document.getElementById("hints");
  container.innerHTML = "";

  const root = tree.Tree;
  const children = root[2]; // top-level suggestions

  if (!children || children.length === 0) {
    showMsg("Your code already looks good!", msgtype.CORRECT);
    return;
  }

  children.forEach((node, index) => {
    const card = document.createElement("div");
    card.className = "card hint-block";
    card.style.marginBottom = "1rem";

    const treeData = node.Tree;
    const meta = treeData[5] || {};

    const generalHint = treeData[0];
    const targetedHint = treeData[2][0]?.Tree?.[0];
    const concreteHint = treeData[2][0]?.Tree?.[2]?.[0]?.Tree?.[0];
    const refactoredCode = meta.refactored_code;
    const reason = meta.reason;

    let step = 0;

    // General hint (always visible)
    const hintContent = document.createElement("div");
    hintContent.innerHTML = `<p><br>${generalHint}</p>`;
    card.appendChild(hintContent);

    // Hidden elements
    const targetedEl = document.createElement("p");
    targetedEl.style.display = "none";
    targetedEl.innerHTML = `<br>${targetedHint || "No targeted hint available."}`;
    card.appendChild(targetedEl);

    const concreteEl = document.createElement("p");
    concreteEl.style.display = "none";
    concreteEl.innerHTML = `<br>${concreteHint || "No concrete hint available."}`;
    card.appendChild(concreteEl);

    const codeBlock = document.createElement("pre");
    codeBlock.style.display = "none";
    codeBlock.innerHTML = `<code>${refactoredCode || "// No refactored code available."}</code>`;
    card.appendChild(codeBlock);

    const reasonEl = document.createElement("p");
    reasonEl.style.display = "none";
    reasonEl.innerHTML = `<strong>Reason:</strong><br>${reason || "No reason provided."}`;
    card.appendChild(reasonEl);

    // Expand button
    const expandBtn = document.createElement("md-text-button");
    expandBtn.innerHTML = `Explain more <svg slot="icon" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="M450-200v-250H200v-60h250v-250h60v250h250v60H510v250h-60Z"/></svg>`;
    expandBtn.onclick = () => {
      step++;
      if (step === 1 && targetedHint) {
        targetedEl.style.display = "block";
      } else if (step === 2 && concreteHint) {
        concreteEl.style.display = "block";
        expandBtn.innerText = "Get Code";
      } else if (step === 3 && refactoredCode) {
        codeBlock.style.display = "block";
        expandBtn.remove();
      } else {
        expandBtn.remove();
      }
    };
    card.appendChild(expandBtn);

    // Reason button
    const reasonBtn = document.createElement("md-outlined-button");
    reasonBtn.textContent = "Get Reason";
    reasonBtn.onclick = () => {
      reasonEl.style.display = "block";
      reasonBtn.remove();
    };
    card.appendChild(reasonBtn);

    container.appendChild(card);
  });

  // New Hint Button (created dynamically and moved to bottom)
  const newHintBtn = document.createElement("md-outlined-button");
  newHintBtn.id = "newhint";
  newHintBtn.innerHTML = `New Hint <svg slot="icon" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="M450-200v-250H200v-60h250v-250h60v250h250v60H510v250h-60Z"/></svg>`;
  newHintBtn.style.display = "inline-block";
  newHintBtn.onclick = () => {
    const next = document.querySelector(".hint-block:not(.shown)");
    if (next) {
      next.classList.add("shown");
      next.style.display = "block";
    }
    if (!document.querySelector(".hint-block:not(.shown)")) {
      newHintBtn.style.display = "none";
    }
  };
  container.appendChild(newHintBtn);

  // Show only the first card
  const cards = document.querySelectorAll(".hint-block");
  cards.forEach((c, i) => {
    c.style.display = i === 0 ? "block" : "none";
    if (i === 0) c.classList.add("shown");
  });
}


function flattenHintTree(treeRoot) {
  const result = [];

  function walk(node) {
    const t = node.Tree;
    if (!t || t.length < 1) return;
    result.push(t[0]); // description
    if (Array.isArray(t[2])) {
      for (const child of t[2]) {
        walk(child);
      }
    }
  }

  walk(treeRoot);
  return result;
}

function renderEmbeddedCards(steps) {
  return steps.map((step, i) => {
    const card = document.createElement("div");
    card.className = "embedded-card";

    const title = document.createElement("h3");
    title.textContent = `${i + 1}. ${step.title}`;
    card.appendChild(title);

    const fields = [
      { label: "Description", value: step.description },
      { label: "Reason", value: step.reason }
    ];

    fields.forEach(({ label, value }) => {
      if (!value) return;

      const detail = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = label;
      detail.appendChild(summary);

      const content = document.createElement("p");
      content.textContent = value;
      detail.appendChild(content);
      card.appendChild(detail);
    });

    return card;
  });
}


function showMsg(msg, type) {
  const container = document.getElementById("feedbackContainer");
  const chip = document.createElement("div");
  chip.className = `chip ${alertClasses[type]}`;
  chip.innerHTML = `<strong>${typeLabels[type]}</strong>${msg}`;
  container.appendChild(chip);
}

async function showMsgWithSpinner(msg, type, awaitedPromise, options = {}) {
  const { prepend = false } = options;
  const container = document.getElementById("feedbackContainer");

  const chip = document.createElement("div");
  chip.className = `chip ${alertClasses[type]}`;
  const id = `chip-spinner-${Date.now()}`;
  chip.id = id;

  const label = document.createElement("strong");
  label.textContent = `${typeLabels[type]}`;
  chip.appendChild(label);

  const message = document.createTextNode(`${msg}`);
  chip.appendChild(message);

  const spinner = document.createElement("div");
  spinner.className = "inline-spinner";
  spinner.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"
        stroke-dasharray="31.4 31.4" transform="rotate(-90 25 25)">
        <animateTransform attributeName="transform" type="rotate"
          values="0 25 25;360 25 25" dur="1s" repeatCount="indefinite" />
      </circle>
    </svg>
  `;
  chip.appendChild(spinner);

  if (prepend) {
    container.prepend(chip);
  } else {
    container.appendChild(chip);
  }

  try {
    return await awaitedPromise;
  } finally {
    const existing = document.getElementById(id);
    if (existing) existing.remove();
  }
}




function clearMessages() {
  document.getElementById("feedbackContainer").innerHTML = "";
  document.getElementById("summaryErrorBox").style.display = "none";
  document.getElementById("locationErrorBox").style.display = "none";
}

function clearHints() {
  const hintsContainer = document.getElementById("hints");
  if (hintsContainer) hintsContainer.innerHTML = "";
}

function showSpinner() {
  const spinner = document.getElementById("loadingSpinner");
  if (spinner) spinner.style.display = "inline-block";
}

function hideSpinner() {
  const spinner = document.getElementById("loadingSpinner");
  if (spinner) spinner.style.display = "none";
}

const msgtype = {
  FAILURE: 0,
  HINT: 1,
  CORRECT: 2,
  WARNING: 3,
};

const alertClasses = ["failure", "hint", "correct", "warning"];
const typeLabels = ["", "", "", "Warning:"];
