<script>
  /**
   * The browser presentation of one pet-concern chat.
   *
   * It owns visible state only. Every decision about what the owner sees next — the emergency
   * route, which question comes next, when the chat ends — is made by the backend, exactly as in
   * the desktop client. Late replies from an abandoned request are dropped by request id.
   */
  import Bubble from './lib/Bubble.svelte';
  import IntakeForm from './lib/IntakeForm.svelte';
  import { sendTurn } from './lib/api.js';
  import { accept, newChat, reject, requestBody, startChat } from './lib/chatState.js';

  let chat = $state(newChat());
  let species = $state('dog');
  let concern = $state('');
  let answer = $state('');
  let requestId = 0;

  const started = $derived(chat.intake !== null);
  const awaitingAnswer = $derived(chat.currentQuestion !== null && !chat.ended);
  const canSend = $derived(!chat.pending && !chat.ended);

  async function send() {
    if (!canSend) return;

    let next;
    if (!started) {
      if (concern.trim() === '') {
        chat = reject(chat, 'Enter a concern.');
        return;
      }
      next = { ...startChat({ species, concern }), pending: true };
    } else {
      if (answer.trim() === '') {
        chat = reject(chat, 'Enter an answer.');
        return;
      }
      next = { ...chat, draftAnswer: answer, pending: true, error: null };
    }

    chat = next;
    requestId += 1;
    const thisRequest = requestId;
    const result = await sendTurn(requestBody(next));

    // A reply that arrives after "New concern", or after a newer send, belongs to a chat that is
    // no longer on screen.
    if (thisRequest !== requestId) return;

    if (result.error) {
      chat = reject(chat, result.error);
    } else if (result.issues) {
      chat = reject(chat, result.issues.map((i) => `${i.field}: ${i.message}`).join('\n'));
    } else {
      chat = accept(chat, result);
      answer = '';
    }
  }

  function newConcern() {
    requestId += 1;
    chat = newChat();
    species = 'dog';
    concern = '';
    answer = '';
  }
</script>

<main>
  <header>
    <h1>VetAI</h1>
    <p>
      Getting ready to talk to a vet. This demo does not diagnose, prescribe, or tell you your pet
      is well.
    </p>
  </header>

  <IntakeForm bind:species bind:concern disabled={started} />

  <section class="transcript" aria-live="polite" aria-label="Conversation">
    {#if chat.transcript.length === 0 && !chat.pending}
      <p class="empty">Describe what you are seeing, then select Send concern.</p>
    {/if}
    {#each chat.transcript as message, index (index)}
      <Bubble
        author={message.author}
        kind={message.kind}
        text={message.text}
        assessment={message.assessment}
      />
    {/each}
    {#if chat.pending}
      <Bubble pending text="Thinking…" />
    {/if}
  </section>

  {#if chat.error}
    <p class="error" role="alert">{chat.error}</p>
  {/if}

  {#if awaitingAnswer}
    <textarea
      bind:value={answer}
      rows="3"
      maxlength="1000"
      disabled={chat.pending}
      placeholder="Your answer"
    ></textarea>
  {/if}

  <div class="actions">
    {#if chat.ended}
      <button class="primary" onclick={newConcern}>New concern</button>
    {:else}
      <button class="primary" onclick={send} disabled={!canSend}>
        {started ? 'Send answer' : 'Send concern'}
      </button>
      {#if chat.error}
        <button onclick={send} disabled={!canSend}>Try again</button>
      {/if}
    {/if}
  </div>
</main>

<style>
  :global(:root) {
    --bg: oklch(98% 0.005 250);
    --surface: oklch(100% 0 0);
    --surface-input: oklch(100% 0 0);
    --surface-vetai: oklch(96.5% 0.008 250);
    --surface-owner: oklch(52% 0.13 250);
    --surface-urgent: oklch(95% 0.05 25);
    --line: oklch(89% 0.01 250);
    --line-urgent: oklch(72% 0.14 25);
    --text: oklch(24% 0.02 250);
    --text-quiet: oklch(50% 0.02 250);
    --on-accent: oklch(99% 0 0);
    --on-urgent: oklch(32% 0.11 25);
    --accent: oklch(52% 0.13 250);
    --radius: 0.85rem;
  }

  @media (prefers-color-scheme: dark) {
    :global(:root) {
      --bg: oklch(19% 0.012 250);
      --surface: oklch(23% 0.014 250);
      --surface-input: oklch(26% 0.014 250);
      --surface-vetai: oklch(27% 0.014 250);
      --surface-owner: oklch(58% 0.12 250);
      --surface-urgent: oklch(32% 0.07 25);
      --line: oklch(34% 0.014 250);
      --line-urgent: oklch(55% 0.12 25);
      --text: oklch(94% 0.005 250);
      --text-quiet: oklch(72% 0.01 250);
      --on-accent: oklch(15% 0.02 250);
      --on-urgent: oklch(92% 0.04 25);
      --accent: oklch(70% 0.12 250);
    }
  }

  :global(body) {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: ui-sans-serif, system-ui, -apple-system, 'Segoe UI', sans-serif;
  }

  main {
    max-width: 46rem;
    margin: 0 auto;
    padding: 2rem 1rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  header h1 {
    margin: 0;
    font-size: 1.35rem;
    letter-spacing: -0.01em;
  }
  header p {
    margin: 0.3rem 0 0;
    color: var(--text-quiet);
    font-size: 0.88rem;
    max-width: 34rem;
  }

  .transcript {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    min-height: 12rem;
    padding: 1rem;
    border-radius: var(--radius);
    background: var(--surface);
    border: 1px solid var(--line);
  }

  .empty {
    margin: auto;
    color: var(--text-quiet);
    font-size: 0.88rem;
    text-align: center;
  }

  .error {
    margin: 0;
    padding: 0.6rem 0.8rem;
    border-radius: 0.5rem;
    background: var(--surface-urgent);
    border: 1px solid var(--line-urgent);
    color: var(--on-urgent);
    font-size: 0.88rem;
    white-space: pre-wrap;
  }

  textarea {
    font: inherit;
    padding: 0.6rem 0.7rem;
    border-radius: 0.6rem;
    border: 1px solid var(--line);
    background: var(--surface-input);
    color: var(--text);
    resize: vertical;
  }
  textarea:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }

  .actions {
    display: flex;
    gap: 0.6rem;
  }

  button {
    font: inherit;
    padding: 0.55rem 1.1rem;
    border-radius: 0.6rem;
    border: 1px solid var(--line);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
  }
  button.primary {
    background: var(--accent);
    border-color: transparent;
    color: var(--on-accent);
  }
  button:disabled {
    opacity: 0.5;
    cursor: default;
  }
  button:not(:disabled):hover {
    filter: brightness(1.06);
  }
  button:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
</style>
