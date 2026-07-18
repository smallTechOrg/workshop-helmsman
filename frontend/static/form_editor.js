/**
 * Phase 4 — Form field editor
 * Reads/writes schema to #fields-json hidden input as JSON.
 * Doesn't depend on any framework. Pure DOM.
 */
(function () {
  const container = document.getElementById('form-fields');
  const addTextBtn = document.getElementById('add-text');
  const addDropdownBtn = document.getElementById('add-dropdown');
  const out = document.getElementById('fields-json');
  if (!container || !out) return;

  function indexRows() {
    return Array.from(container.querySelectorAll('.form-row'));
  }

  function rowField(row) {
    const data = {};
    row.querySelectorAll('[data-bind]').forEach((el) => {
      const k = el.dataset.bind;
      if (el.type === 'checkbox') data[k] = !!el.checked;
      else data[k] = (el.value || '').trim();
    });
    return data;
  }

  function serialize() {
    const fields = indexRows().map(rowField);
    out.value = JSON.stringify(fields);
  }

  function toggleDropdownVisibility(row) {
    const isDrop = row.querySelector('[data-bind="type"]').value === 'dropdown';
    const opts = row.querySelector('.form-row-options');
    if (opts) opts.hidden = !isDrop;
  }

  function slugify(s) {
    return (s || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40);
  }

  function nextKey() {
    const existing = new Set(indexRows().map(r => rowField(r).key).filter(Boolean));
    let base = 'field_1';
    let n = 1;
    while (existing.has(base)) { n++; base = `field_${n}`; }
    return base;
  }

  function makeRow(type, label) {
    const row = document.createElement('div');
    row.className = 'form-row';
    row.innerHTML = `
      <div class="form-row-head">
        <strong class="row-label-text">${label || 'New field'}</strong>
        <button type="button" class="btn-row-remove" data-action="remove" aria-label="Remove field">×</button>
      </div>
      <div class="form-row-grid">
        <label><span>Key</span><input data-bind="key" placeholder="snake_case_key" /></label>
        <label><span>Label</span><input data-bind="label" placeholder="Display label" /></label>
        <label><span>Placeholder</span><input data-bind="placeholder" placeholder="(text fields only)" /></label>
        <label class="chk"><input type="checkbox" data-bind="required" /> Required</label>
      </div>
      <div class="form-row-options" data-show="dropdown" hidden>
        <label>
          <span>Dropdown options (one per line)</span>
          <textarea data-bind="options" rows="3" placeholder="Option A&#10;Option B"></textarea>
        </label>
      </div>
      <input type="hidden" data-bind="type" value="${type}" />
    `;
    // Auto-generate a key from the labelled thing.
    const labelInput = row.querySelector('[data-bind="label"]');
    const keyInput = row.querySelector('[data-bind="key"]');
    labelInput.value = label || '';
    keyInput.value = nextKey();
    toggleDropdownVisibility(row);

    // Live update row title.
    labelInput.addEventListener('input', () => {
      row.querySelector('.row-label-text').textContent =
        labelInput.value || keyInput.value || 'New field';
    });

    // Remove.
    row.querySelector('[data-action="remove"]').addEventListener('click', () => {
      row.remove();
      serialize();
    });

    // Any input change → serialize.
    row.querySelectorAll('[data-bind]').forEach((el) => {
      el.addEventListener('input', serialize);
      el.addEventListener('change', serialize);
    });

    return row;
  }

  function add(type) {
    const row = makeRow(type, type === 'dropdown' ? 'New dropdown' : 'New field');
    container.appendChild(row);
    serialize();
  }

  addTextBtn.addEventListener('click', () => add('text'));
  addDropdownBtn.addEventListener('click', () => add('dropdown'));

  // Existing rows: wire remove + serialize hooks.
  indexRows().forEach((row) => {
    const keyInput = row.querySelector('[data-bind="key"]');
    const labelInput = row.querySelector('[data-bind="label"]');
    if (labelInput) {
      labelInput.addEventListener('input', () => {
        row.querySelector('.row-label-text').textContent =
          labelInput.value || (keyInput && keyInput.value) || 'Field';
      });
    }
    row.querySelector('[data-action="remove"]').addEventListener('click', () => {
      row.remove();
      serialize();
    });
    row.querySelectorAll('[data-bind]').forEach((el) => {
      el.addEventListener('input', serialize);
      el.addEventListener('change', serialize);
    });
    toggleDropdownVisibility(row);
  });

  // Submit-time serialize is also automatic via input hooks, but ensure.
  document.getElementById('form-editor').addEventListener('submit', serialize);

  // Initial serialize so hidden input reflects loaded state.
  serialize();
})();