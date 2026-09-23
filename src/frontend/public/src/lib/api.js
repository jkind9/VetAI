/**
 * The browser client's one-shot HTTP call, mirroring `frontend/local/api_client.py`.
 *
 * Both clients speak the same JSON contract and map the same status codes to the same owner-facing
 * text, so a reviewer comparing them sees one API and two presentations.
 */

export const REQUEST_ERROR_TEXT = 'Please correct the request and try again.';
export const SERVICE_ERROR_TEXT =
  'The assistant could not complete this response. Please try again or contact a veterinarian if concerned.';

export const REPLY_KINDS = ['question', 'assessment', 'emergency_notice'];

// A kind in this set ends the chat.
export const ENDING_KINDS = ['assessment', 'emergency_notice'];

const OUTCOMES = ['possible_problem', 'nothing_flagged'];

function isString(value) {
  return typeof value === 'string' && value.trim() !== '';
}

function isStringList(value) {
  return Array.isArray(value) && value.length > 0 && value.every(isString);
}

function isGroundedItem(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    isString(value.text) &&
    isStringList(value.source_ids)
  );
}

function isGroundedList(value, { allowEmpty = false } = {}) {
  return (
    Array.isArray(value) &&
    (allowEmpty || value.length > 0) &&
    value.every(isGroundedItem)
  );
}

function isSource(value) {
  return (
    value !== null &&
    typeof value === 'object' &&
    isString(value.source_id) &&
    isString(value.title) &&
    isHttpsUrl(value.url) &&
    isString(value.organisation)
  );
}

function isHttpsUrl(value) {
  if (!isString(value)) return false;
  try {
    return new URL(value).protocol === 'https:';
  } catch {
    return false;
  }
}

function isAssessment(value) {
  if (value === null || typeof value !== 'object' || !OUTCOMES.includes(value.outcome)) {
    return false;
  }

  const possibleAreasValid =
    isGroundedList(value.possible_areas, { allowEmpty: true }) &&
    (value.outcome === 'possible_problem'
      ? value.possible_areas.length > 0
      : value.possible_areas.length === 0);

  return (
    isString(value.outcome_wording) &&
    isStringList(value.what_you_reported) &&
    possibleAreasValid &&
    isGroundedList(value.suggested_actions) &&
    isGroundedList(value.questions_for_veterinarian) &&
    Array.isArray(value.sources) &&
    value.sources.length > 0 &&
    value.sources.every(isSource) &&
    isString(value.disclaimer)
  );
}

/** Parse only the public contract; an unexpected body never reaches the owner. */
export function parseResponse(status, payload) {
  if (payload === null || typeof payload !== 'object') {
    return { error: SERVICE_ERROR_TEXT };
  }

  if (status === 200) {
    const { kind } = payload;
    if (kind === 'assessment' && isAssessment(payload.assessment)) {
      return { kind, assessment: payload.assessment };
    }
    if (
      (kind === 'question' || kind === 'emergency_notice') &&
      isString(payload.reply)
    ) {
      return { kind, reply: payload.reply };
    }
    return { error: SERVICE_ERROR_TEXT };
  }

  if (status === 422) {
    const issues = Array.isArray(payload.issues)
      ? payload.issues.filter(
          (item) =>
            item && typeof item.field === 'string' && typeof item.message === 'string',
        )
      : [];
    return issues.length > 0 ? { issues } : { error: REQUEST_ERROR_TEXT };
  }

  return { error: SERVICE_ERROR_TEXT };
}

/** Describe a no-response failure without guessing whether the backend processed the turn. */
export function connectionError({ isTimeout }) {
  return isTimeout
    ? 'The request timed out. Please try again.'
    : 'Could not reach the assistant service. Please try again.';
}

/**
 * Post one turn. The caller decides if and when a failed turn is retried; there is no auto-retry.
 * The page is served from the same origin as the API, so the path is relative.
 */
export async function sendTurn(turn, { timeoutMs = 65_000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch('/v1/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(turn),
      signal: controller.signal,
    });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      return { error: SERVICE_ERROR_TEXT };
    }
    return parseResponse(response.status, payload);
  } catch (error) {
    return { error: connectionError({ isTimeout: error.name === 'AbortError' }) };
  } finally {
    clearTimeout(timer);
  }
}
