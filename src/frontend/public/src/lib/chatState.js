/**
 * The visible chat state, mirroring `ChatState` in `frontend/local/app.py`.
 *
 * Every function returns a new state rather than editing one in place, so a stale reply can never
 * half-apply to the chat the owner is now looking at. The rule the desktop client also follows: an
 * answer is only committed to history once the backend has accepted it.
 */

import { ENDING_KINDS } from './api.js';

export function newChat() {
  return {
    intake: null,
    history: [],
    currentQuestion: null,
    draftAnswer: '',
    error: null,
    ended: false,
    pending: false,
    transcript: [],
  };
}

/** Start a fresh concern, keeping nothing from a previous chat. */
export function startChat(intake) {
  return { ...newChat(), intake: { ...intake } };
}

/** A snapshot that includes the current draft but has not accepted it yet. */
export function requestBody(state) {
  if (state.intake === null) {
    throw new Error('chat intake has not been started');
  }
  const history = [...state.history];
  if (state.currentQuestion !== null) {
    history.push(
      { role: 'assistant', content: state.currentQuestion },
      { role: 'user', content: state.draftAnswer },
    );
  }
  return { intake: { ...state.intake }, history };
}

/** Advance only after a successful reply. A question commits the pair it was answering. */
export function accept(state, result) {
  if (result.kind === 'question' && typeof result.reply === 'string') {
    const answered = state.currentQuestion !== null;
    return {
      ...state,
      history: answered
        ? [
            ...state.history,
            { role: 'assistant', content: state.currentQuestion },
            { role: 'user', content: state.draftAnswer },
          ]
        : state.history,
      transcript: [
        ...state.transcript,
        ...(answered ? [{ author: 'owner', text: state.draftAnswer }] : []),
        { author: 'vetai', kind: 'question', text: result.reply },
      ],
      currentQuestion: result.reply,
      draftAnswer: '',
      error: null,
      pending: false,
    };
  }

  if (ENDING_KINDS.includes(result.kind)) {
    const answered = state.currentQuestion !== null;
    const finalMessage =
      result.kind === 'assessment'
        ? { author: 'vetai', kind: result.kind, assessment: result.assessment }
        : { author: 'vetai', kind: result.kind, text: result.reply };
    return {
      ...state,
      transcript: [
        ...state.transcript,
        ...(answered ? [{ author: 'owner', text: state.draftAnswer }] : []),
        finalMessage,
      ],
      currentQuestion: null,
      error: null,
      ended: true,
      pending: false,
    };
  }

  throw new Error('only successful replies can be accepted');
}

/** Keep the draft exactly as typed so the owner can edit it or retry unchanged. */
export function reject(state, error) {
  return { ...state, error, pending: false };
}
