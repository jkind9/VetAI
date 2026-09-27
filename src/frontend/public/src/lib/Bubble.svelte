<script>
  /**
   * One message in the transcript. Owner text sits right, VetAI text sits left, and a pending
   * placeholder reads as VetAI but is visibly not a reply yet.
   */
  let {
    author = 'vetai',
    kind = 'question',
    text = '',
    assessment = null,
    pending = false,
  } = $props();

  const outcomeTitle = $derived(
    assessment?.outcome === 'possible_problem'
      ? 'Possible problem — see a veterinarian'
      : 'Nothing flagged',
  );
</script>

<div class="row" class:owner={author === 'owner'}>
  <div
    class="bubble"
    class:owner={author === 'owner'}
    class:emergency={kind === 'emergency_notice'}
    class:wide={kind === 'assessment' || kind === 'summary'}
    class:pending
  >
    {#if !pending}
      <span class="who">{author === 'owner' ? 'You' : 'VetAI'}</span>
    {/if}
    {#if kind === 'assessment' && assessment}
      <article class="assessment">
        <h2>{outcomeTitle}</h2>
        <p>{assessment.outcome_wording}</p>
        {#if assessment.search_notice}
          <p class="search-notice" role="note">{assessment.search_notice}</p>
        {/if}

        <section>
          <h3>What you reported</h3>
          <ul>
            {#each assessment.what_you_reported as item}
              <li>{item}</li>
            {/each}
          </ul>
        </section>

        {#if assessment.possible_areas.length > 0}
          <section>
            <h3>Possible areas</h3>
            <ul>
              {#each assessment.possible_areas as item}
                <li>{item.text}{#if item.source_ids.length > 0} <span class="citation">[{item.source_ids.join(', ')}]</span>{/if}</li>
              {/each}
            </ul>
          </section>
        {/if}

        <section>
          <h3>Suggested actions</h3>
          <ul>
            {#each assessment.suggested_actions as item}
              <li>{item.text}{#if item.source_ids.length > 0} <span class="citation">[{item.source_ids.join(', ')}]</span>{/if}</li>
            {/each}
          </ul>
        </section>

        <section>
          <h3>Questions for your veterinarian</h3>
          <ul>
            {#each assessment.questions_for_veterinarian as item}
              <li>{item.text}{#if item.source_ids.length > 0} <span class="citation">[{item.source_ids.join(', ')}]</span>{/if}</li>
            {/each}
          </ul>
        </section>

        {#if assessment.sources.length > 0}
          <section>
            <h3>Sources</h3>
            <ul>
              {#each assessment.sources as source}
                <li>
                  <span class="citation">[{source.source_id}]</span>
                  <a href={source.url} target="_blank" rel="noreferrer">{source.title}</a>
                  — {source.organisation}
                </li>
              {/each}
            </ul>
          </section>
        {/if}

        <p class="disclaimer">{assessment.disclaimer}</p>
      </article>
    {:else}
      <p>{text}</p>
    {/if}
  </div>
</div>

<style>
  .row {
    display: flex;
    justify-content: flex-start;
  }
  .row.owner {
    justify-content: flex-end;
  }

  .bubble {
    max-width: 78%;
    padding: 0.7rem 0.9rem;
    border-radius: var(--radius);
    border-bottom-left-radius: 0.25rem;
    background: var(--surface-vetai);
    border: 1px solid var(--line);
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .bubble.wide {
    max-width: 92%;
  }
  .bubble.owner {
    background: var(--surface-owner);
    border-color: transparent;
    color: var(--on-accent);
    border-bottom-left-radius: var(--radius);
    border-bottom-right-radius: 0.25rem;
  }
  .bubble.emergency {
    background: var(--surface-urgent);
    border-color: var(--line-urgent);
    color: var(--on-urgent);
  }
  .bubble.pending {
    color: var(--text-quiet);
    font-style: italic;
  }

  .who {
    display: block;
    font-size: 0.72rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    opacity: 0.65;
    margin-bottom: 0.2rem;
  }

  p {
    margin: 0;
    line-height: 1.5;
  }

  .assessment h2 {
    margin: 0 0 0.35rem;
    font-size: 1.15rem;
  }
  .assessment h3 {
    margin: 0;
    font-size: 0.92rem;
  }
  .assessment section {
    margin-top: 1rem;
  }
  .assessment ul {
    margin: 0.35rem 0 0;
    padding-left: 1.25rem;
  }
  .assessment li + li {
    margin-top: 0.3rem;
  }
  .assessment a {
    color: inherit;
  }
  .citation {
    color: var(--text-quiet);
    font-size: 0.82rem;
  }
  .search-notice {
    padding: 0.5rem 0.7rem;
    border-left: 3px solid var(--line-urgent);
    background: var(--surface);
    font-size: 0.9rem;
  }

  .disclaimer {
    margin-top: 1rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--line);
    color: var(--text-quiet);
    font-size: 0.85rem;
  }
</style>
