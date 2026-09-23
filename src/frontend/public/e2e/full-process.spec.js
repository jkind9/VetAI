import { expect, test } from '@playwright/test';

const STANDARD_QUESTIONS = [
  'How long has this been happening?',
  'Has this happened before?',
  'Is it happening constantly, or does it come and go?',
];

const ADAPTIVE_QUESTIONS = [
  'Have you noticed weakness, vomiting, or a change in breathing?',
  'Does the panting stop while your dog is asleep?',
  'Has your dog been exposed to unusual heat or exercise?',
];

const EMERGENCY_NOTICE =
  'This may be an emergency. Please contact an emergency veterinarian now. ' +
  'This demo cannot assess your pet or provide a diagnosis.';

async function sendConcern(page, concern) {
  await page.getByLabel('What is worrying you?').fill(concern);
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/v1/chat') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Send concern' }).click();
  expect((await responsePromise).ok()).toBe(true);
}

async function answer(page, answerText, expectedText) {
  await page.getByPlaceholder('Your answer').fill(answerText);
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/v1/chat') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Send answer' }).click();
  expect((await responsePromise).ok()).toBe(true);
  await expect(page.getByText(expectedText, { exact: true })).toBeVisible();
}

async function completeQuestions(page, concern) {
  await sendConcern(page, concern);
  await expect(page.getByText(STANDARD_QUESTIONS[0], { exact: true })).toBeVisible();
  await answer(page, 'Since yesterday evening.', STANDARD_QUESTIONS[1]);
  await answer(page, 'No, this is the first time.', STANDARD_QUESTIONS[2]);
  await answer(page, 'It comes and goes while resting.', ADAPTIVE_QUESTIONS[0]);
}

test('owner reaches the adaptive cap and receives a possible-problem assessment', async ({ page }) => {
  await page.goto('/');
  await completeQuestions(page, 'My dog has persistent panting while resting.');
  await answer(page, 'No vomiting, but she seems tired.', ADAPTIVE_QUESTIONS[1]);
  await answer(page, 'It stops briefly, then starts again.', ADAPTIVE_QUESTIONS[2]);
  await answer(page, 'No unusual heat or exercise.', 'Possible problem — see a veterinarian');

  await expect(page.getByText('What you reported', { exact: true })).toBeVisible();
  await expect(page.getByText('Possible areas', { exact: true })).toBeVisible();
  await expect(page.getByText('Suggested actions', { exact: true })).toBeVisible();
  await expect(page.getByText('Record a video if the panting happens again.')).toBeVisible();
  await expect(page.getByText('Questions for your veterinarian', { exact: true })).toBeVisible();
  await expect(page.getByRole('link', { name: 'MSD Veterinary Manual' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'New concern' })).toBeVisible();
});

test('owner completes every question and receives a nothing-flagged assessment', async ({ page }) => {
  await page.goto('/');
  await completeQuestions(page, 'My dog panted briefly after exercise and then settled.');
  await answer(page, 'No other changes and she is behaving normally now.', 'Nothing flagged');

  await expect(page.getByText('This review did not flag a specific problem.', { exact: false }))
    .toBeVisible();
  await expect(page.getByText('Suggested actions', { exact: true })).toBeVisible();
  await expect(page.getByText('Record a video if it happens again.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'New concern' })).toBeVisible();
});

test('deterministic emergency concern ends immediately with the fixed notice', async ({ page }) => {
  await page.goto('/');
  await sendConcern(page, 'My dog is struggling to breathe.');

  await expect(page.getByText(EMERGENCY_NOTICE, { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder('Your answer')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New concern' })).toBeVisible();
});

test('misspelled urgent concern escalates through the model decision path', async ({ page }) => {
  await page.goto('/');
  await sendConcern(page, 'I am worried my dog is dieing.');
  await expect(page.getByText(STANDARD_QUESTIONS[0], { exact: true })).toBeVisible();
  await answer(page, 'It started this morning.', STANDARD_QUESTIONS[1]);
  await answer(page, 'No, never before.', STANDARD_QUESTIONS[2]);
  await answer(page, 'It is constant.', EMERGENCY_NOTICE);

  await expect(page.getByPlaceholder('Your answer')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New concern' })).toBeVisible();
});

test('model failure preserves the final answer for an explicit retry', async ({ page }) => {
  await page.goto('/');
  await sendConcern(page, 'Exercise the provider failure path.');
  await expect(page.getByText(STANDARD_QUESTIONS[0], { exact: true })).toBeVisible();
  await answer(page, 'Since this morning.', STANDARD_QUESTIONS[1]);
  await answer(page, 'No, never before.', STANDARD_QUESTIONS[2]);

  const finalAnswer = 'It is happening constantly.';
  await page.getByPlaceholder('Your answer').fill(finalAnswer);
  const responsePromise = page.waitForResponse(
    (response) => response.url().endsWith('/v1/chat') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Send answer' }).click();
  expect((await responsePromise).status()).toBe(503);

  await expect(page.getByRole('alert')).toHaveText(
    'The assistant could not complete this response. Please try again or contact a veterinarian if concerned.',
  );
  await expect(page.getByPlaceholder('Your answer')).toHaveValue(finalAnswer);
  await expect(page.getByRole('button', { name: 'Try again' })).toBeVisible();

  const retryPromise = page.waitForResponse(
    (response) => response.url().endsWith('/v1/chat') && response.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Try again' }).click();
  expect((await retryPromise).ok()).toBe(true);
  await expect(page.getByText(ADAPTIVE_QUESTIONS[0], { exact: true })).toBeVisible();
  await expect(page.getByText(finalAnswer, { exact: true })).toBeVisible();
  await expect(page.getByPlaceholder('Your answer')).toHaveValue('');
});
