<script>
  /**
   * The opening form. Only species and concern are collected here: the duration, whether it has
   * happened before, and whether it is constant are asked as standard questions in the chat, so the
   * owner is not made to fill in a form before anything responds to them.
   */
  let { species = $bindable('dog'), concern = $bindable(''), disabled = false } = $props();
</script>

<fieldset {disabled}>
  <label>
    <span>Species</span>
    <select bind:value={species}>
      <option value="dog">Dog</option>
      <option value="cat">Cat</option>
    </select>
  </label>
  <label class="grow">
    <span>What is worrying you?</span>
    <input
      type="text"
      bind:value={concern}
      maxlength="1000"
      placeholder="My dog has been scratching one ear since this morning"
    />
  </label>
</fieldset>

<style>
  fieldset {
    display: flex;
    gap: 0.75rem;
    align-items: flex-end;
    border: 0;
    padding: 0;
    margin: 0;
    flex-wrap: wrap;
  }
  fieldset[disabled] {
    opacity: 0.55;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    font-size: 0.82rem;
    color: var(--text-quiet);
  }
  label.grow {
    flex: 1 1 18rem;
  }

  select,
  input {
    font: inherit;
    padding: 0.55rem 0.65rem;
    border-radius: 0.5rem;
    border: 1px solid var(--line);
    background: var(--surface-input);
    color: var(--text);
  }
  select:focus-visible,
  input:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 1px;
  }
</style>
