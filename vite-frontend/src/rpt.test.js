import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const exercises = [
  {
    id: '0.isOvenReady',
    language: 'java',
    description: 'Check the oven temperature.',
    start_method: 'public static boolean isOvenReady(int temperature) {}',
  },
  {
    id: '1.busTicketPrice',
    language: 'java',
    description: 'Calculate the ticket price.',
    start_method: 'public static double calculateBusTicketPrice(int age) {}',
  },
];

const hintTree = {
  Tree: [
    'Suggested Refactorings',
    'hint',
    [
      {
        Tree: [
          'Inspect the conditional',
          'hint',
          [{ Tree: ['Try returning early', 'hint', [], 2, -1, {}] }],
          1,
          4,
          { refactored_code: 'return value;', reason: 'This removes a nested branch.' },
        ],
      },
      { Tree: ['Check the boundary case', 'hint', [], 4, -1, {}] },
    ],
    0,
    -1,
    {},
  ],
};

describe('exercise and hint workflows', () => {
  let initializeRefactoringTutor;

  beforeEach(async () => {
    vi.resetModules();
    document.body.innerHTML = `
      <div id="exerciseSelect"></div>
      <button id="runBtn"></button>
      <button id="gethinttree"></button>
      <button id="loadex"></button>
      <div id="exname"></div>
      <div id="exdesc"></div>
      <div id="refactoringCardContainer"></div>
      <div id="feedbackContainer"></div>
      <div id="summaryErrorBox"></div>
      <div id="locationErrorBox"></div>
      <div id="hints"></div>
      <div id="loadingSpinner"></div>
    `;

    let editorCode = '';
    vi.stubGlobal('editor', {
      getValue: vi.fn(() => editorCode),
      setValue: vi.fn((value) => {
        editorCode = value;
      }),
      session: { setMode: vi.fn() },
    });
    window.currentUser = { username: 'learner', group: 'group-a' };

    ({ initializeRefactoringTutor } = await import('./rpt.js'));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.body.innerHTML = '';
    delete window.currentUser;
    delete window.startApp;
  });

  function mockBackend({
    exerciseData = exercises,
    diagnosis = { status: 'correct' },
    diagnoses,
    diagnosisFailures = [],
    hints = { hint_tree: hintTree, suggestions: [] },
    hintFailure,
    correctFeedback = {
      present_refactorings: false,
      refactor_steps: [],
      general_feedback: 'No structural changes were found.',
    },
    notEquivalentFeedback = { error_summary: 'The change alters behavior.' },
  } = {}) {
    const requests = [];
    const diagnosisResponses = diagnoses ?? [diagnosis];
    let diagnosisIndex = 0;
    const fetchMock = vi.fn(async (url, options = {}) => {
      requests.push({ url, options });
      if (url === '/exercises') {
        return { json: async () => exerciseData.map(({ id, description, language }) => ({ id, description, language })) };
      }
      if (url.startsWith('/exercise/')) {
        const exercise = exerciseData.find(({ id }) => id === url.slice('/exercise/'.length));
        return { json: async () => exercise };
      }
      if (url === '/diagnose') {
        const currentIndex = diagnosisIndex++;
        if (diagnosisFailures[currentIndex]) throw new Error(diagnosisFailures[currentIndex]);
        const result = diagnosisResponses[Math.min(currentIndex, diagnosisResponses.length - 1)];
        return { json: async () => result };
      }
      if (url === '/hint_tree') {
        if (hintFailure) throw new Error(hintFailure);
        return { json: async () => hints };
      }
      if (url === '/correct_feedback') return { json: async () => correctFeedback };
      if (url === '/notequiv_feedback') return { json: async () => notEquivalentFeedback };
      if (url === '/log_action') return { json: async () => ({ status: 'ok' }) };
      throw new Error(`Unexpected frontend request: ${url}`);
    });

    vi.stubGlobal('fetch', fetchMock);
    return { requests, fetchMock };
  }

  it('loads the selected exercise into the editor and diagnoses it', async () => {
    const { requests } = mockBackend();

    await initializeRefactoringTutor();

    expect(document.getElementById('exname').textContent).toBe('Exercise 0.isOvenReady');
    expect(document.getElementById('exdesc').textContent).toBe(exercises[0].description);
    expect(editor.getValue()).toBe(exercises[0].start_method);
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1);

    const selector = document.getElementById('exerciseSelect');
    selector.value = exercises[1].id;
    selector.dispatchEvent(new Event('input', { bubbles: true }));

    await vi.waitFor(() => {
      expect(document.getElementById('exname').textContent).toBe('Exercise 1.busTicketPrice');
    });

    expect(editor.getValue()).toBe(exercises[1].start_method);
    expect(requests.some(({ url }) => url === `/exercise/${exercises[1].id}`)).toBe(true);
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);

    await vi.waitFor(() => {
      expect(requests.some(({ url, options }) => {
        if (url !== '/log_action') return false;
        const payload = JSON.parse(options.body);
        return payload.action === 'NewExercise' &&
          payload.exercise === exercises[1].id &&
          payload.current_code === exercises[1].start_method;
      })).toBe(true);
    });

    const newExerciseLog = requests
      .filter(({ url }) => url === '/log_action')
      .map(({ options }) => JSON.parse(options.body))
      .find(({ action }) => action === 'NewExercise');
    expect(newExerciseLog.previous_code).toBe(exercises[1].start_method);
  });

  it('switches the editor mode when a C# exercise is selected', async () => {
    const csharpExercise = {
      id: '0.isOvenRead.cs',
      language: 'csharp',
      description: 'Check the oven temperature.',
      start_method: 'public static bool isOvenReady(int temperature) {}',
    };
    const { requests } = mockBackend({ exerciseData: [...exercises, csharpExercise] });

    await initializeRefactoringTutor();
    const selector = document.getElementById('exerciseSelect');
    selector.value = csharpExercise.id;
    selector.dispatchEvent(new Event('input', { bubbles: true }));

    await vi.waitFor(() => {
      expect(editor.session.setMode).toHaveBeenLastCalledWith('ace/mode/csharp');
      expect(editor.getValue()).toBe(csharpExercise.start_method);
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
    });
  });

  it('restarts the current exercise, resets the editor and diagnosis cache, and logs the restart', async () => {
    const editedCode = 'public static boolean isOvenReady(int temperature) { return false; }';
    const { requests } = mockBackend();

    await initializeRefactoringTutor();
    editor.setValue(editedCode);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2));

    document.getElementById('loadex').click();
    await vi.waitFor(() => {
      expect(editor.getValue()).toBe(exercises[0].start_method);
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(3);
      expect(requests.some(({ url, options }) => {
        if (url !== '/log_action') return false;
        const payload = JSON.parse(options.body);
        return payload.action === 'RestartExercise' &&
          payload.current_code === exercises[0].start_method;
      })).toBe(true);
    });

    document.getElementById('runBtn').click();
    await vi.waitFor(() => {
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(4);
      expect(requests.filter(({ url }) => url === '/log_action')).toHaveLength(3);
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'No structural changes were found.',
      );
    });
  });

  it('requests fresh hints after switching exercises with identical starter code', async () => {
    const sameStarterExercises = exercises.map((exercise) => ({ ...exercise }));
    sameStarterExercises[1].start_method = sameStarterExercises[0].start_method;
    const { requests } = mockBackend({ exerciseData: sameStarterExercises });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(1));

    const selector = document.getElementById('exerciseSelect');
    selector.value = sameStarterExercises[1].id;
    selector.dispatchEvent(new Event('input', { bubbles: true }));
    await vi.waitFor(() => {
      expect(document.getElementById('exname').textContent).toBe('Exercise 1.busTicketPrice');
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
    });

    document.getElementById('gethinttree').click();
    await vi.waitFor(() => {
      expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(2);
      expect(document.querySelectorAll('.hint-block')).toHaveLength(2);
    });
  });

  it('does not request quality hints when the diagnosis is not equivalent', async () => {
    const { requests } = mockBackend({ diagnosis: { status: 'notequiv', reason: 'A test failed.' } });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'You need to fix code functionality to get hints on code quality.',
      );
    });

    expect(requests.some(({ url }) => url === '/hint_tree')).toBe(false);
  });

  it('reveals hint cards and expands a hint through code and reason', async () => {
    const { requests } = mockBackend();

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => {
      expect(document.querySelectorAll('.hint-block')).toHaveLength(2);
    });

    const [firstHint, secondHint] = document.querySelectorAll('.hint-block');
    expect(firstHint.style.display).toBe('block');
    expect(secondHint.style.display).toBe('none');

    document.getElementById('newhint').click();
    expect(secondHint.style.display).toBe('block');
    expect(document.getElementById('newhint').style.display).toBe('none');

    const targetedHint = [...firstHint.querySelectorAll('p')].find((element) =>
      element.textContent.includes('Try returning early'),
    );
    const codeBlock = firstHint.querySelector('pre');
    const expandButton = firstHint.querySelector('md-text-button');

    expect(targetedHint.style.display).toBe('none');
    expect(codeBlock.style.display).toBe('none');

    expandButton.click();
    await vi.waitFor(() => expect(targetedHint.style.display).toBe('block'));

    expandButton.click();
    await vi.waitFor(() => {
      expect(codeBlock.style.display).toBe('block');
      expect(firstHint.querySelector('md-outlined-button')?.textContent).toBe('Get Reason');
    });

    firstHint.querySelector('md-outlined-button').click();
    expect(firstHint.textContent).toContain('This removes a nested branch.');
    expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(1);
  });

  it('shows compile errors and logs the diagnosed submission', async () => {
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return true; }';
    const { requests } = mockBackend({
      diagnoses: [{ status: 'correct' }, { status: 'compile_error', message: 'Missing semicolon' }],
    });

    await initializeRefactoringTutor();
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Compile Error: Missing semicolon',
      );
      expect(requests.some(({ url }) => url === '/log_action')).toBe(true);
    });

    const loggedAction = JSON.parse(requests.find(({ url }) => url === '/log_action').options.body);
    expect(loggedAction).toMatchObject({
      username: 'learner',
      group: 'group-a',
      exercise: exercises[0].id,
      current_code: submittedCode,
      action: 'Diagnose',
      previous_code: exercises[0].start_method,
      code_status: 'compile_error',
      feedback: 'Missing semicolon',
    });
    expect(document.getElementById('loadingSpinner').style.display).toBe('none');
  });

  it('shows behavior-change feedback and logs its explanation', async () => {
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return false; }';
    const { requests } = mockBackend({
      diagnoses: [
        { status: 'correct' },
        {
          status: 'notequiv',
          call: 'isOvenReady(150)',
          expected: 'true',
          actual: 'false',
          reason: 'Expected true, got false',
        },
      ],
    });

    await initializeRefactoringTutor();
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Calling `isOvenReady(150)` should return `true`, but it got `false`.',
      );
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'The change alters behavior.',
      );
    });

    const feedbackRequest = requests.find(({ url }) => url === '/notequiv_feedback');
    expect(JSON.parse(feedbackRequest.options.body)).toMatchObject({
      exercise_id: exercises[0].id,
      submitted_code: submittedCode,
      test_case_failure: 'Expected true, got false',
      hint_group: 'group-a',
    });
    const loggedAction = JSON.parse(requests.find(({ url }) => url === '/log_action').options.body);
    expect(loggedAction).toMatchObject({
      action: 'Diagnose',
      code_status: 'notequiv',
      feedback: 'The change alters behavior.',
    });
  });

  it('renders refactoring feedback for behavior-preserving code', async () => {
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return temperature >= 150; }';
    const { requests } = mockBackend({
      diagnoses: [{ status: 'correct' }, { status: 'correct' }],
      correctFeedback: {
        present_refactorings: true,
        refactor_steps: [{ title: 'Simplify condition', description: 'Return the result directly.', reason: 'Avoid a temporary.' }],
        general_feedback: null,
      },
    });

    await initializeRefactoringTutor();
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'You performed 1 refactoring(s).',
      );
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Return the result directly.',
      );
    });

    const feedbackRequest = requests.find(({ url }) => url === '/correct_feedback');
    expect(JSON.parse(feedbackRequest.options.body)).toMatchObject({
      exercise_id: exercises[0].id,
      submitted_code: submittedCode,
      previous_code: exercises[0].start_method,
    });
    const loggedAction = JSON.parse(requests.find(({ url }) => url === '/log_action').options.body);
    expect(loggedAction).toMatchObject({
      action: 'Diagnose',
      code_status: 'correct',
      feedback: JSON.stringify([
        { title: 'Simplify condition', description: 'Return the result directly.', reason: 'Avoid a temporary.' },
      ]),
    });
  });

  it('reuses a diagnosis for unchanged code and rediagnoses edited code', async () => {
    const { requests } = mockBackend({
      diagnoses: [
        { status: 'correct' },
        { status: 'correct' },
        { status: 'correct' },
      ],
    });

    await initializeRefactoringTutor();
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return true; }';
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(1));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);

    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(2));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);

    editor.setValue(`${submittedCode}\n// edited`);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(3));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(3);
  });

  it('clears the loading spinner when diagnosis requests fail', async () => {
    const { requests } = mockBackend({
      diagnosisFailures: [null, 'Diagnosis service unavailable'],
    });

    await initializeRefactoringTutor();
    editor.setValue('changed code');
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Server error: Diagnosis service unavailable',
      );
    });

    expect(document.getElementById('loadingSpinner').style.display).toBe('none');
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
  });

  it('leaves logout beacon registration to the login module', async () => {
    mockBackend();
    const addEventListener = vi.spyOn(window, 'addEventListener');

    await initializeRefactoringTutor();

    expect(addEventListener).not.toHaveBeenCalledWith('beforeunload', expect.any(Function));
  });

  it('clears hint spinners when the hint request fails', async () => {
    mockBackend({ hintFailure: 'Hints unavailable' });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Hint error: Hints unavailable',
      );
    });

    expect(document.getElementById('loadingSpinner').style.display).toBe('none');
    expect(document.querySelector('.inline-spinner')).toBeNull();
  });

  it('shows a completion message for an empty hint tree', async () => {
    mockBackend({ hints: { hint_tree: { Tree: ['Suggested Refactorings', 'hint', [], 0, -1, {}] }, suggestions: [] } });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Your code already looks good!',
      );
    });
    expect(document.querySelector('.hint-block')).toBeNull();
  });

  it('shows hint service errors without rendering a hint tree', async () => {
    mockBackend({ hints: { error: 'Rate limit reached' } });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Hint service error: Rate limit reached',
      );
    });
    expect(document.querySelector('.hint-block')).toBeNull();
    expect(document.querySelector('.inline-spinner')).toBeNull();
  });

  it('does not interpret model-provided hint content as HTML', async () => {
    const hostileText = '<img src=x onerror="window.__xss=1">';
    const hostileHintTree = {
      Tree: [
        'Suggested Refactorings',
        'hint',
        [
          {
            Tree: [
              hostileText,
              'hint',
              [{ Tree: [hostileText, 'hint', [], 2, -1, {}] }],
              1,
              -1,
              { refactored_code: hostileText, reason: hostileText },
            ],
          },
        ],
        0,
        -1,
        {},
      ],
    };
    mockBackend({ hints: { hint_tree: hostileHintTree, suggestions: [] } });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();
    await vi.waitFor(() => expect(document.querySelector('.hint-block')).not.toBeNull());

    const hint = document.querySelector('.hint-block');
    hint.querySelector('md-text-button').click();
    hint.querySelector('md-text-button').click();
    await vi.waitFor(() => expect(hint.querySelector('md-outlined-button')).not.toBeNull());
    hint.querySelector('md-outlined-button').click();

    expect(hint.querySelectorAll('img, script, iframe, [onerror], [onload]')).toHaveLength(0);
  });

  it('does not interpret markdown feedback from the server as executable HTML', async () => {
    const hostileFeedback = '**Safe feedback**\n<img src=x onerror="window.__xss=1">';
    mockBackend({
      diagnoses: [
        { status: 'correct' },
        {
          status: 'notequiv',
          call: 'isOvenReady(150)',
          expected: 'true',
          actual: 'false',
          reason: 'Values differ',
        },
      ],
      notEquivalentFeedback: { error_summary: hostileFeedback },
    });

    await initializeRefactoringTutor();
    editor.setValue('changed code');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(document.querySelector('.feedback-markdown')).not.toBeNull());

    const markdown = document.querySelector('.feedback-markdown');
    expect(markdown.querySelectorAll('script, iframe, [onerror], [onload]')).toHaveLength(0);
    expect(markdown.querySelector('strong')?.textContent).toBe('Safe feedback');
  });

  it('does not interpret hint-service error messages as HTML', async () => {
    const hostileError = '<img src=x onerror="window.__xss=1">';
    mockBackend({ hints: { error: hostileError } });

    await initializeRefactoringTutor();
    document.getElementById('gethinttree').click();
    await vi.waitFor(() => {
      expect(document.querySelector('#feedbackContainer .failure')).not.toBeNull();
    });

    expect(
      document.getElementById('feedbackContainer').querySelectorAll('img, script, iframe, [onerror], [onload]'),
    ).toHaveLength(0);
  });
});