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

  /** Start the tutor and forget the startup requests, so tests only see what they trigger. */
  async function startTutor(requests) {
    await initializeRefactoringTutor();
    requests.length = 0;
  }

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
    notEquivalentFeedback = { summary: 'The change alters behavior.' },
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

  it('loads the selected exercise into the editor without diagnosing it, and logs the first exercise', async () => {
    const { requests } = mockBackend();

    await initializeRefactoringTutor();

    expect(document.getElementById('exname').textContent).toBe('Exercise 0.isOvenReady');
    expect(document.getElementById('exdesc').textContent).toBe(exercises[0].description);
    expect(editor.getValue()).toBe(exercises[0].start_method);
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(0);
    const firstExerciseLog = requests
      .filter(({ url }) => url === '/log_action')
      .map(({ options }) => JSON.parse(options.body));
    expect(firstExerciseLog).toHaveLength(1);
    expect(firstExerciseLog[0]).toMatchObject({
      action: 'NewExercise',
      exercise: exercises[0].id,
      current_code: exercises[0].start_method,
    });

    const selector = document.getElementById('exerciseSelect');
    selector.value = exercises[1].id;
    selector.dispatchEvent(new Event('input', { bubbles: true }));

    await vi.waitFor(() => {
      expect(document.getElementById('exname').textContent).toBe('Exercise 1.busTicketPrice');
    });

    expect(editor.getValue()).toBe(exercises[1].start_method);
    expect(requests.some(({ url }) => url === `/exercise/${exercises[1].id}`)).toBe(true);
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(0);

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
      .find(({ action, exercise }) => action === 'NewExercise' && exercise === exercises[1].id);
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
    });
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(0);
  });

  it('restarts the current exercise, resets the editor and diagnosis cache, and logs the restart', async () => {
    const editedCode = 'public static boolean isOvenReady(int temperature) { return false; }';
    const { requests } = mockBackend();

    await startTutor(requests);
    editor.setValue(editedCode);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1));

    document.getElementById('loadex').click();
    await vi.waitFor(() => {
      expect(editor.getValue()).toBe(exercises[0].start_method);
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1);
      expect(requests.some(({ url, options }) => {
        if (url !== '/log_action') return false;
        const payload = JSON.parse(options.body);
        return payload.action === 'RestartExercise' &&
          payload.current_code === exercises[0].start_method;
      })).toBe(true);
    });

    document.getElementById('runBtn').click();
    await vi.waitFor(() => {
      expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
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
    });
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(0);

    document.getElementById('gethinttree').click();
    await vi.waitFor(() => {
      expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(2);
      expect(document.querySelectorAll('.hint-block')).toHaveLength(2);
    });
  });

  it('requests hints for the untouched starter code without diagnosing it', async () => {
    const { requests } = mockBackend();

    await startTutor(requests);
    document.getElementById('gethinttree').click();

    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(1));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(0);
  });

  it('shows a timeout message, and diagnoses the same code again on retry', async () => {
    const { requests } = mockBackend({
      diagnoses: [{ status: 'timeout', message: 'Judge0 timed out' }, { status: 'correct' }],
    });

    await startTutor(requests);
    editor.setValue('changed code');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Timeout error when compiling code. Try again.',
      );
    });
    expect(requests.some(({ url }) => url === '/log_action')).toBe(false);
    expect(document.getElementById('loadingSpinner').style.display).toBe('none');

    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2));
    expect(document.getElementById('feedbackContainer').textContent).not.toContain("You haven't changed the code.");
  });

  it('shows a timeout message for hint requests and does not cache the failed diagnosis', async () => {
    const { requests } = mockBackend({
      diagnoses: [{ status: 'timeout', message: 'Judge0 timed out' }, { status: 'correct' }],
    });

    await startTutor(requests);
    editor.setValue('changed code');
    document.getElementById('gethinttree').click();
    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Timeout error when compiling code. Try again.',
      );
    });
    expect(requests.some(({ url }) => url === '/hint_tree')).toBe(false);

    document.getElementById('gethinttree').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/hint_tree')).toHaveLength(1));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
  });

  it('does not request quality hints when the diagnosis is not equivalent', async () => {
    const { requests } = mockBackend({ diagnosis: { status: 'notequiv', reason: 'A test failed.' } });

    await startTutor(requests);
    editor.setValue('changed code');
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

    await startTutor(requests);
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
      diagnoses: [{ status: 'compile_error', message: 'Missing semicolon' }],
    });

    await startTutor(requests);
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
        {
          status: 'notequiv',
          call: 'isOvenReady(150)',
          expected: 'true',
          actual: 'false',
          reason: 'Expected true, got false',
        },
      ],
    });

    await startTutor(requests);
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      // expect(document.getElementById('feedbackContainer').textContent).toContain(
      //   'Calling `isOvenReady(150)` should return `true`, but it got `false`.',
      // );
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
      feedback: JSON.stringify({ summary: 'The change alters behavior.' }),
    });
  });

  it('logs the previous and last correct code across consecutive submissions', async () => {
    const notEquivalent = { status: 'notequiv', reason: 'Expected true, got false' };
    const code1 = 'code1';
    const code2 = 'code2';
    const { requests } = mockBackend({
      diagnoses: [notEquivalent, { status: 'correct' }],
    });
    const loggedActions = () =>
      requests.filter(({ url }) => url === '/log_action').map(({ options }) => JSON.parse(options.body));

    await startTutor(requests);
    editor.setValue(code1);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(loggedActions()).toHaveLength(1));

    editor.setValue(code2);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(loggedActions()).toHaveLength(2));

    expect(loggedActions()[0]).toMatchObject({
      code_status: 'notequiv',
      current_code: code1,
      previous_code: exercises[0].start_method,
      last_correct_code: exercises[0].start_method,
    });
    expect(loggedActions()[1]).toMatchObject({
      code_status: 'correct',
      current_code: code2,
      previous_code: code1,
      last_correct_code: exercises[0].start_method,
    });

    document.getElementById('gethinttree').click();
    await vi.waitFor(() => expect(loggedActions()).toHaveLength(3));
    expect(loggedActions()[2]).toMatchObject({
      action: 'GetHint',
      current_code: code2,
      previous_code: code1,
      last_correct_code: code2,
    });
  });

  it('sends the last correct code, not the last attempt, to the LLM feedback and omits it elsewhere', async () => {
    const notEquivalent = () => ({ status: 'notequiv', reason: 'Expected true, got false' });
    const { requests } = mockBackend({ diagnoses: [notEquivalent(), notEquivalent()] });
    const bodies = (url) => requests.filter((request) => request.url === url).map(({ options }) => JSON.parse(options.body));

    await startTutor(requests);
    editor.setValue('notequiv1');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(bodies('/notequiv_feedback')).toHaveLength(1));
    editor.setValue('notequiv2');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(bodies('/notequiv_feedback')).toHaveLength(2));

    expect(bodies('/notequiv_feedback').map(({ previous_code }) => previous_code)).toEqual([
      exercises[0].start_method,
      exercises[0].start_method,
    ]);
    bodies('/diagnose').forEach((body) => expect(body).not.toHaveProperty('previous_code'));
  });

  it('does not send previous code with hint requests', async () => {
    const { requests } = mockBackend();

    await startTutor(requests);
    document.getElementById('gethinttree').click();
    await vi.waitFor(() => expect(document.querySelectorAll('.hint-block')).toHaveLength(2));

    const hintBody = JSON.parse(requests.find(({ url }) => url === '/hint_tree').options.body);
    expect(hintBody).not.toHaveProperty('previous_code');
  });

  describe('hint requests on edited code', () => {
    const bodies = (requests, url) =>
      requests.filter((request) => request.url === url).map(({ options }) => JSON.parse(options.body));
    const logs = (requests) => bodies(requests, '/log_action');

    it('diagnoses the editor code and withholds hints when edited code is not equivalent', async () => {
      const { requests } = mockBackend({
        diagnoses: [{ status: 'correct' }, { status: 'notequiv', reason: 'Wrong result' }],
      });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(1));

      editor.setValue('code2');
      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(document.getElementById('feedbackContainer').textContent).toContain('You need to fix code functionality'));

      expect(bodies(requests, '/diagnose').at(-1).submitted_code).toBe('code2');
      expect(requests.some(({ url }) => url === '/hint_tree')).toBe(false);
      document.getElementById('gethinttree').click();
      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(logs(requests)).toHaveLength(1);
    });

    it('gives hints for edited code that is now equivalent and sends that code for hints', async () => {
      const { requests } = mockBackend({
        diagnoses: [{ status: 'notequiv', reason: 'Wrong result' }, { status: 'correct' }],
      });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(1));

      editor.setValue('code2');
      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(document.querySelectorAll('.hint-block')).toHaveLength(2));

      expect(bodies(requests, '/hint_tree')[0].submitted_code).toBe('code2');
    });

    it('does not request a second hint tree for unchanged code, and keeps submission state separate', async () => {
      const { requests } = mockBackend({
        diagnoses: [{ status: 'correct' }, { status: 'correct' }],
      });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(1));

      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(document.querySelectorAll('.hint-block').length).toBeGreaterThan(0));
      expect(bodies(requests, '/hint_tree')).toHaveLength(1);
      expect(bodies(requests, '/diagnose')).toHaveLength(1);

      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(2));
      expect(bodies(requests, '/diagnose')).toHaveLength(2);
      expect(bodies(requests, '/diagnose').at(-1).submitted_code).toBe('code1');
      expect(document.getElementById('feedbackContainer').textContent).not.toContain("You haven't changed the code.");
    });

    it('logs follow-up hint actions with the context of the hint request that built the tree', async () => {
      const { requests } = mockBackend({ diagnoses: [{ status: 'correct' }] });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(document.querySelectorAll('.hint-block')).toHaveLength(2));
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(1));

      editor.setValue('edited after the hint');
      document.querySelector('.hint-block md-text-button').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(2));

      const [getHint, expandHint] = logs(requests);
      expect(expandHint).toMatchObject({
        action: 'ExpandHint',
        current_code: getHint.current_code,
        previous_code: getHint.previous_code,
        last_correct_code: getHint.last_correct_code,
        code_status: 'correct',
      });
    });

    it('logs the previous code of a hint as the latest submission when the code was edited after it', async () => {
      const { requests } = mockBackend({ diagnoses: [{ status: 'correct' }, { status: 'correct' }] });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(1));

      editor.setValue('code2');
      document.getElementById('gethinttree').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(2));
      expect(logs(requests)[1]).toMatchObject({ action: 'GetHint', current_code: 'code2', previous_code: 'code1' });
    });

    it('logs the fix suggestion only once for a replayed diagnosis', async () => {
      const { requests } = mockBackend({
        diagnoses: [{ status: 'notequiv', reason: 'Wrong result' }],
        notEquivalentFeedback: { error_summary: 'Broken', fix_suggestion: 'Fix it', incorrect_code: 'x', previous_code: 'y' },
      });
      const seeFix = () => document.querySelector('#feedbackContainer md-text-button');

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(seeFix()).not.toBeNull());
      seeFix().click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(2));

      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(seeFix()).not.toBeNull());
      seeFix().click();
      await new Promise((resolve) => setTimeout(resolve, 20));
      expect(logs(requests).filter(({ action }) => action === 'SeeFixSuggestion')).toHaveLength(1);
    });

    it('logs the fix suggestion with the context of the diagnosis that produced it', async () => {
      const { requests } = mockBackend({
        diagnoses: [{ status: 'notequiv', reason: 'Wrong result' }],
        notEquivalentFeedback: { error_summary: 'Broken', fix_suggestion: 'Fix it', incorrect_code: 'x', previous_code: 'y' },
      });

      await startTutor(requests);
      editor.setValue('code1');
      document.getElementById('runBtn').click();
      await vi.waitFor(() => expect(document.querySelector('#feedbackContainer md-text-button')).not.toBeNull());

      editor.setValue('edited after the diagnosis');
      document.querySelector('#feedbackContainer md-text-button').click();
      await vi.waitFor(() => expect(logs(requests)).toHaveLength(2));

      const [diagnose, seeFix] = logs(requests);
      expect(seeFix).toMatchObject({
        action: 'SeeFixSuggestion',
        current_code: diagnose.current_code,
        previous_code: diagnose.previous_code,
        last_correct_code: diagnose.last_correct_code,
      });
    });
  });

  it('diagnoses and logs identical code again after a restart', async () => {
    const notEquivalent = () => ({ status: 'notequiv', reason: 'Wrong result' });
    const { requests } = mockBackend({
      diagnoses: [notEquivalent(), notEquivalent()],
    });
    const diagnoseLogs = () =>
      requests.filter(({ url }) => url === '/log_action').filter(({ options }) => JSON.parse(options.body).action === 'Diagnose');

    await startTutor(requests);
    editor.setValue('code1');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(diagnoseLogs()).toHaveLength(1));

    document.getElementById('loadex').click();
    await vi.waitFor(() => expect(editor.getValue()).toBe(exercises[0].start_method));
    editor.setValue('code1');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(diagnoseLogs()).toHaveLength(2));
  });

  it('does not log a repeated diagnosis of unchanged non-equivalent code', async () => {
    const { requests } = mockBackend({
      diagnoses: [{ status: 'notequiv', reason: 'Expected true, got false' }],
    });
    const diagnoseLogs = () =>
      requests.filter(({ url }) => url === '/log_action').filter(({ options }) => JSON.parse(options.body).action === 'Diagnose');

    await startTutor(requests);
    editor.setValue('changed code');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(diagnoseLogs()).toHaveLength(1));

    document.getElementById('runBtn').click();
    await vi.waitFor(() =>
      expect(requests.filter(({ url }) => url === '/notequiv_feedback')).toHaveLength(1),
    );
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(diagnoseLogs()).toHaveLength(1);
  });

  it('renders structured step feedback without showing its classification', async () => {
    const structuredFeedback = {
      classification: 'Refactoring misconception',
      summary: 'The refactoring removed the else behavior.',
      explanation: 'The refactoring removed the else behavior.',
      previous_code: 'if (condition) {} else {}',
      incorrect_code: 'if (condition) {}',
      failed_test: 'The false condition now skips the required behavior.',
      fix_suggestion: 'Preserve both branches when simplifying the condition.',
    };
    const { requests } = mockBackend({
      diagnoses: [
        {
          status: 'notequiv',
          call: 'isOvenReady(150)',
          expected: 'true',
          actual: 'false',
          reason: 'Expected true, got false',
        },
      ],
      notEquivalentFeedback: structuredFeedback,
    });

    await startTutor(requests);
    editor.setValue('changed code');
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      const feedback = document.getElementById('feedbackContainer');
      expect(feedback.textContent).toContain(structuredFeedback.summary);
      expect(feedback.textContent).toContain(structuredFeedback.failed_test);
      expect(feedback.textContent).not.toContain(structuredFeedback.fix_suggestion);
      expect(feedback.querySelector('md-text-button').textContent).toContain('See fix suggestion');
      expect(feedback.textContent).not.toContain(structuredFeedback.classification);
      expect(feedback.querySelectorAll('pre code')).toHaveLength(2);
      expect(feedback.querySelectorAll('pre code')[0].textContent).toBe(structuredFeedback.previous_code);
      expect(feedback.querySelectorAll('pre code')[1].textContent).toBe(structuredFeedback.incorrect_code);
    });

    document.querySelector('#feedbackContainer md-text-button').click();
    expect(document.getElementById('feedbackContainer').textContent).toContain(
      structuredFeedback.fix_suggestion,
    );
    expect(document.querySelector('#feedbackContainer md-text-button')).toBeNull();
    expect(requests.some(({ url }) => url === '/notequiv_feedback')).toBe(true);
    await vi.waitFor(() => {
      const loggedActions = requests
        .filter(({ url }) => url === '/log_action')
        .map(({ options }) => JSON.parse(options.body));
      expect(loggedActions.at(-1)).toMatchObject({
        action: 'SeeFixSuggestion',
        code_status: 'notequiv',
        feedback: structuredFeedback.fix_suggestion,
        current_code: 'changed code',
        previous_code: exercises[0].start_method,
        last_correct_code: exercises[0].start_method,
      });
    });
  });

  it('renders refactoring feedback for behavior-preserving code', async () => {
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return temperature >= 150; }';
    const { requests } = mockBackend({
      diagnoses: [{ status: 'correct' }],
      correctFeedback: {
        present_refactorings: true,
        refactor_steps: [{ title: 'Simplify condition', description: 'Return the result directly.', reason: 'Avoid a temporary.' }],
        general_feedback: null,
      },
    });

    await startTutor(requests);
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
      diagnoses: [{ status: 'correct' }],
    });

    await startTutor(requests);
    const submittedCode = 'public static boolean isOvenReady(int temperature) { return true; }';
    editor.setValue(submittedCode);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(1));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1);

    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(2));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1);

    editor.setValue(`${submittedCode}\n// edited`);
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(requests.filter(({ url }) => url === '/correct_feedback')).toHaveLength(3));
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(2);
  });

  it('clears the loading spinner when diagnosis requests fail', async () => {
    const { requests } = mockBackend({
      diagnosisFailures: ['Diagnosis service unavailable'],
    });

    await startTutor(requests);
    editor.setValue('changed code');
    document.getElementById('runBtn').click();

    await vi.waitFor(() => {
      expect(document.getElementById('feedbackContainer').textContent).toContain(
        'Server error: Diagnosis service unavailable',
      );
    });

    expect(document.getElementById('loadingSpinner').style.display).toBe('none');
    expect(requests.filter(({ url }) => url === '/diagnose')).toHaveLength(1);
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
        {
          status: 'notequiv',
          call: 'isOvenReady(150)',
          expected: 'true',
          actual: 'false',
          reason: 'Values differ',
        },
      ],
      notEquivalentFeedback: { summary: hostileFeedback },
    });

    await initializeRefactoringTutor();
    editor.setValue('changed code');
    document.getElementById('runBtn').click();
    await vi.waitFor(() => expect(document.querySelector('.feedback-prose')).not.toBeNull());

    const markdown = document.querySelector('.feedback-prose');
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