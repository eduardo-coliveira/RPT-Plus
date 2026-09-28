/** Render feedback, hints, messages, and loading state in the page. */

import DOMPurify from 'dompurify';
import { marked } from 'marked';

marked.setOptions({ breaks: true });

/** Render Markdown after removing unsafe content. */
export function renderSanitizedMarkdown(markdownText) {
  const html = marked.parse(markdownText);
  const container = document.createElement('div');
  container.className = 'feedback-markdown';
  container.innerHTML = DOMPurify.sanitize(html);
  return container;
}

/** Build a feedback chip that lists refactoring steps. */
export function createRefactoringFeedbackChip(steps, typeLabel, alertClass) {
  const chip = createFeedbackChip(
    alertClass,
    typeLabel,
    `You performed ${steps.length} refactoring(s).`,
  );

  renderEmbeddedCards(steps).forEach((card) => chip.appendChild(card));
  return chip;
}

/** Build a feedback chip that explains a behavior change. */
export function createNonEquivalentFeedbackChip(feedback, alertClass, typeLabel) {
  const chip = createFeedbackChip(
    alertClass,
    typeLabel,
    'Here is what might have gone wrong.',
  );

  const card = document.createElement('div');
  card.className = 'embedded-card';
  const title = document.createElement('h3');
  title.textContent = 'Explanation';
  card.appendChild(title);

  const summaryDetails = document.createElement('details');
  const summary = document.createElement('summary');
  const summaryLabel = document.createElement('strong');
  summaryLabel.textContent = 'What went wrong';
  summary.appendChild(summaryLabel);
  summaryDetails.appendChild(summary);
  summaryDetails.appendChild(renderSanitizedMarkdown(feedback.error_summary));
  card.appendChild(summaryDetails);
  chip.appendChild(card);

  return chip;
}

/** Build the shared container and heading for a feedback chip. */
function createFeedbackChip(alertClass, typeLabel, introText) {
  const chip = document.createElement('div');
  chip.className = `chip ${alertClass}`;
  chip.style.flexDirection = 'column';
  chip.style.alignItems = 'stretch';

  const header = document.createElement('div');
  const headerLabel = document.createElement('strong');
  headerLabel.textContent = typeLabel;
  header.appendChild(headerLabel);
  header.appendChild(document.createTextNode(introText));
  header.style.marginBottom = '8px';
  chip.appendChild(header);
  return chip;
}

/** Render one card for each refactoring step. */
function renderEmbeddedCards(steps) {
  return steps.map((step, index) => {
    const card = document.createElement('div');
    card.className = 'embedded-card';

    const title = document.createElement('h3');
    title.textContent = `${index + 1}. ${step.title}`;
    card.appendChild(title);

    for (const [label, value] of [
      ['Description', step.description],
      ['Reason', step.reason],
    ]) {
      if (!value) continue;
      const detail = document.createElement('details');
      const summary = document.createElement('summary');
      summary.textContent = label;
      detail.appendChild(summary);
      detail.appendChild(renderSanitizedMarkdown(value));
      card.appendChild(detail);
    }

    return card;
  });
}

/** Render the hint cards and connect their callbacks. */
export function renderCurrentHintTree(hintTree, { onEmpty, onExpandHint, onGetCode }) {
  clearMessages();
  const container = document.getElementById('hints');
  container.innerHTML = '';

  const children = hintTree.Tree[2];
  if (!children || children.length === 0) {
    onEmpty();
    return;
  }

  children.forEach((node) => {
    const card = document.createElement('div');
    card.className = 'card hint-block';
    card.style.marginBottom = '1rem';

    const treeData = node.Tree;
    const meta = treeData[5] || {};
    const generalHint = treeData[0];
    const targetedHint = treeData[2][0]?.Tree?.[0];
    const refactoredCode = meta.refactored_code;
    const reason = meta.reason;
    let step = 0;

    const hintContent = document.createElement('div');
    const generalHintText = document.createElement('p');
    generalHintText.appendChild(document.createElement('br'));
    generalHintText.textContent = generalHint;
    hintContent.appendChild(generalHintText);
    card.appendChild(hintContent);

    const targetedElement = document.createElement('p');
    targetedElement.style.display = 'none';
    targetedElement.appendChild(document.createElement('br'));
    targetedElement.appendChild(document.createTextNode(targetedHint || 'No targeted hint available.'));
    card.appendChild(targetedElement);

    const codeBlock = document.createElement('pre');
    codeBlock.style.display = 'none';
    const code = document.createElement('code');
    code.textContent = refactoredCode || '// No refactored code available.';
    codeBlock.appendChild(code);
    card.appendChild(codeBlock);

    const reasonElement = document.createElement('p');
    reasonElement.style.display = 'none';
    const reasonLabel = document.createElement('strong');
    reasonLabel.textContent = 'Reason:';
    reasonElement.appendChild(reasonLabel);
    reasonElement.appendChild(document.createElement('br'));
    reasonElement.appendChild(document.createTextNode(reason || 'No reason provided.'));
    card.appendChild(reasonElement);

    const expandButton = document.createElement('md-text-button');
    expandButton.innerHTML = `Explain more <svg slot="icon" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="M450-200v-250H200v-60h250v-250h60v250h250v60H510v250h-60Z"/></svg>`;
    expandButton.onclick = async () => {
      step++;
      if (step === 1 && targetedHint) {
        targetedElement.style.display = 'block';
        await onExpandHint(targetedHint);
        expandButton.innerText = 'Get Code';
      } else if (step === 2 && refactoredCode) {
        codeBlock.style.display = 'block';
        await onGetCode(refactoredCode);
        expandButton.remove();

        if (reason) {
          const reasonButton = document.createElement('md-outlined-button');
          reasonButton.textContent = 'Get Reason';
          reasonButton.onclick = () => {
            reasonElement.style.display = 'block';
            reasonButton.remove();
          };
          card.appendChild(reasonButton);
        }
      } else if (step === 3 && reason) {
        reasonElement.style.display = 'block';
        expandButton.remove();
      } else {
        expandButton.remove();
      }
    };
    card.appendChild(expandButton);
    container.appendChild(card);
  });

  const newHintButton = document.createElement('md-outlined-button');
  newHintButton.id = 'newhint';
  newHintButton.innerHTML = `New Hint <svg slot="icon" xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 -960 960 960" width="24"><path d="M450-200v-250H200v-60h250v-250h60v250h250v60H510v250h-60Z"/></svg>`;
  newHintButton.style.display = 'inline-block';
  newHintButton.onclick = () => {
    const next = document.querySelector('.hint-block:not(.shown)');
    if (next) {
      next.classList.add('shown');
      next.style.display = 'block';
    }
    if (!document.querySelector('.hint-block:not(.shown)')) {
      newHintButton.style.display = 'none';
    }
  };
  container.appendChild(newHintButton);

  document.querySelectorAll('.hint-block').forEach((card, index) => {
    card.style.display = index === 0 ? 'block' : 'none';
    if (index === 0) card.classList.add('shown');
  });
}

/** Clear feedback messages and error panels. */
export function clearMessages() {
  document.getElementById('feedbackContainer').innerHTML = '';
  document.getElementById('summaryErrorBox').style.display = 'none';
  document.getElementById('locationErrorBox').style.display = 'none';
}

/** Remove the rendered hints. */
export function clearHintDisplay() {
  const container = document.getElementById('hints');
  if (container) container.innerHTML = '';
}

/** Add a text message to the feedback area. */
export function appendFeedbackMessage(message, className, label) {
  const container = document.getElementById('feedbackContainer');
  const chip = document.createElement('div');
  chip.className = `chip ${className}`;
  const heading = document.createElement('strong');
  heading.textContent = label;
  chip.appendChild(heading);
  chip.appendChild(document.createTextNode(message));
  container.appendChild(chip);
}

/** Show a loading message until an operation finishes. */
export async function appendLoadingMessage(message, className, label, awaitedPromise, options = {}) {
  const { prepend = false } = options;
  const container = document.getElementById('feedbackContainer');
  const chip = document.createElement('div');
  const id = `chip-spinner-${Date.now()}`;
  chip.className = `chip ${className}`;
  chip.id = id;

  const heading = document.createElement('strong');
  heading.textContent = label;
  chip.appendChild(heading);
  chip.appendChild(document.createTextNode(message));

  const spinner = document.createElement('div');
  spinner.className = 'inline-spinner';
  spinner.innerHTML = `
    <svg width="20" height="20" viewBox="0 0 50 50">
      <circle cx="25" cy="25" r="20" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"
        stroke-dasharray="31.4 31.4" transform="rotate(-90 25 25)" />
    </svg>
  `;
  chip.appendChild(spinner);

  if (prepend) container.prepend(chip);
  else container.appendChild(chip);

  try {
    return await awaitedPromise;
  } finally {
    document.getElementById(id)?.remove();
  }
}

/** Show or hide the loading indicator. */
export function setLoadingIndicatorVisible(isVisible) {
  const spinner = document.getElementById('loadingSpinner');
  if (spinner) spinner.style.display = isVisible ? 'inline-block' : 'none';
}