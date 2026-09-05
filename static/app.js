const state = {
  jobs: [], selectedId: null, poller: null, logOpen: false, primeTool: 'prime-check'
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
  return data;
}

function shortNumber(value, size = 36) {
  if (value.length <= size) return value;
  const side = Math.floor((size - 1) / 2);
  return `${value.slice(0, side)}…${value.slice(-side)}`;
}

function statusLabel(status) {
  return status.charAt(0).toUpperCase() + status.slice(1);
}

async function loadCapabilities() {
  try {
    const data = await api('/api/capabilities');
    const online = Object.entries(data.engines)
      .filter(([, item]) => item.available)
      .map(([name]) => name.toUpperCase());
    $('#engine-status').innerHTML = `<span class="online">●</span> ${online.join(' · ')} ready`;
    $('#threads').max = data.cpu_count;
    $('#threads').value = data.cpu_count;
    document.querySelectorAll('.zeta-threads').forEach((input) => {
      input.max = data.cpu_count;
      input.value = data.cpu_count;
    });
    const select = $('#cado-parameter');
    select.innerHTML = '<option value="">Choose automatically</option>';
    data.cado_parameters.forEach((parameter) => {
      const option = document.createElement('option');
      option.value = parameter.size;
      option.textContent = `c${parameter.size} · ${parameter.size}-digit tuning`;
      select.appendChild(option);
    });
    renderSetup(data.setup);
  } catch (error) {
    $('#engine-status').textContent = `Engine check failed: ${error.message}`;
  }
}

function renderSetup(setup) {
  const banner = $('#setup-banner');
  if (!setup || setup.state === 'ready') {
    banner.classList.add('hidden');
    return;
  }
  const missing = (setup.missing || []).join(', ');
  banner.innerHTML = `<strong>Engine setup: ${escapeHtml(setup.state || 'checking')}</strong> · ${escapeHtml(setup.message || '')}${missing ? `<br>Missing: ${escapeHtml(missing)}` : ''}`;
  banner.classList.remove('hidden');
}

function renderJobs() {
  const container = $('#job-list');
  if (!state.jobs.length) {
    container.innerHTML = '<div class="empty">No jobs yet.</div>';
    return;
  }
  container.innerHTML = state.jobs.map((job) => `
    <button class="job-card ${job.id === state.selectedId ? 'selected' : ''}" data-id="${job.id}">
      <span class="job-card-top">
        <span><i class="status-dot ${job.status}"></i>${statusLabel(job.status)}</span>
        <small>${job.digits} digits · ${escapeHtml(job.selected_backend)}</small>
      </span>
      <code>${escapeHtml(shortNumber(job.number))}</code>
    </button>
  `).join('');
  container.querySelectorAll('.job-card').forEach((button) => {
    button.addEventListener('click', () => selectJob(button.dataset.id));
  });
}

async function loadJobs() {
  state.jobs = await api('/api/jobs');
  renderJobs();
  if (state.selectedId) await refreshSelected();
}

function renderFactors(job) {
  const container = $('#factor-list');
  if (!job.factors?.length) {
    container.innerHTML = '<div class="empty">Factors will appear when verified.</div>';
    $('#copy-result').classList.add('hidden');
    $('#download-result').classList.add('hidden');
    $('#factor-equation').classList.add('hidden');
    return;
  }
  container.innerHTML = job.factors.map((factor) => `
    <div class="factor-row">
      <code>${escapeHtml(factor.value)}</code>
      <span class="factor-kind">${escapeHtml(factor.status.replace('_', ' '))} · ${factor.digits}d</span>
    </div>
  `).join('');
  $('#copy-result').classList.remove('hidden');
  const equation = $('#factor-equation');
  equation.innerHTML = `<span>${job.negative ? '−' : ''}${escapeHtml(shortNumber(job.number, 52))}</span><span class="equals">=</span>${job.factors.map((factor, index) => `${index ? '<span class="multiply">×</span>' : ''}<span>${escapeHtml(factor.value)}</span>`).join('')}`;
  equation.classList.remove('hidden');
  const download = $('#download-result');
  download.classList.toggle('hidden', !job.result_path);
  download.href = `/api/jobs/${job.id}/export`;
}

function renderDetail(job) {
  $('#empty-detail').classList.add('hidden');
  $('#job-detail').classList.remove('hidden');
  $('#detail-id').textContent = `JOB ${job.id.slice(0, 10)} · ${job.selected_backend.toUpperCase()}`;
  $('#detail-status').textContent = statusLabel(job.status);
  $('#detail-number').textContent = `${job.negative ? '−' : ''}${job.number}`;
  $('#detail-digits').textContent = `${job.digits} DIGITS`;
  $('#progress-bar').style.width = `${job.progress}%`;
  $('#progress-value').textContent = `${Math.round(job.progress)}%`;
  $('#detail-phase').textContent = job.phase;

  const warning = $('#job-warning');
  warning.textContent = job.warning || '';
  warning.classList.toggle('hidden', !job.warning);
  const error = $('#job-error');
  error.textContent = job.error || '';
  error.classList.toggle('hidden', !job.error);

  const active = ['queued', 'running', 'cancelling'].includes(job.status);
  $('#cancel-job').classList.toggle('hidden', !active);
  $('#resume-job').classList.toggle('hidden', active || job.status === 'completed');
  renderFactors(job);
}

async function refreshLog() {
  if (!state.selectedId || !state.logOpen) return;
  const data = await api(`/api/jobs/${state.selectedId}/log`);
  const log = $('#job-log');
  const nearBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 80;
  log.textContent = `${data.truncated ? '… earlier output omitted …\n' : ''}${data.text}`;
  if (nearBottom) log.scrollTop = log.scrollHeight;
}

async function refreshSelected() {
  if (!state.selectedId) return;
  try {
    const job = await api(`/api/jobs/${state.selectedId}`);
    renderDetail(job);
    const index = state.jobs.findIndex((item) => item.id === job.id);
    if (index >= 0) state.jobs[index] = job;
    renderJobs();
    await refreshLog();
  } catch (error) {
    console.error(error);
  }
}

async function selectJob(id) {
  state.selectedId = id;
  renderJobs();
  await refreshSelected();
}

$('#factor-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  const errorBox = $('#form-error');
  errorBox.classList.add('hidden');
  button.disabled = true;
  try {
    const parameter = $('#cado-parameter').value;
    const job = await api('/api/jobs', {
      method: 'POST',
      body: JSON.stringify({
        expression: $('#expression').value,
        backend: $('#backend').value,
        threads: Number($('#threads').value),
        pretest_level: Number($('#pretest-level').value),
        cado_parameter_size: parameter ? Number(parameter) : null,
      }),
    });
    state.selectedId = job.id;
    await loadJobs();
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove('hidden');
  } finally {
    button.disabled = false;
  }
});

$('#cancel-job').addEventListener('click', async () => {
  if (!state.selectedId) return;
  await api(`/api/jobs/${state.selectedId}/cancel`, { method: 'POST' });
  await refreshSelected();
});

$('#resume-job').addEventListener('click', async () => {
  if (!state.selectedId) return;
  await api(`/api/jobs/${state.selectedId}/resume`, { method: 'POST' });
  await refreshSelected();
});

$('#copy-result').addEventListener('click', async () => {
  const job = await api(`/api/jobs/${state.selectedId}`);
  const factors = job.factors.map((factor) => factor.value).join(' × ');
  await navigator.clipboard.writeText(`${job.negative ? '-' : ''}${job.number} = ${factors}`);
  $('#copy-result').textContent = 'Copied';
  setTimeout(() => { $('#copy-result').textContent = 'Copy'; }, 1000);
});

$('#toggle-log').addEventListener('click', async () => {
  state.logOpen = !state.logOpen;
  $('#job-log').classList.toggle('hidden', !state.logOpen);
  $('#toggle-log').textContent = state.logOpen ? 'Hide log' : 'Show log';
  await refreshLog();
});

$('#refresh-jobs').addEventListener('click', loadJobs);
$('#expression').addEventListener('input', (event) => {
  const compact = event.target.value.replace(/[\s_]/g, '');
  $('#digit-preview').textContent = /^[-+]?\d+$/.test(compact)
    ? `${compact.replace(/^[-+]/, '').length.toLocaleString()} digits`
    : 'Expression will be evaluated safely';
});

const primeSections = {
  essentials: {
    label: 'Primality & navigation',
    forms: ['prime-check-form', 'prime-batch-form', 'prime-classify-form', 'prime-nearby-form', 'prime-range-form', 'prime-nth-form', 'prime-count-form'],
  },
  generation: {
    label: 'Prime generation',
    forms: ['prime-generate-form', 'prime-special-form', 'prime-progression-form', 'random-range-form', 'digit-constrained-form', 'perfect-number-form', 'primorial-form'],
  },
  patterns: {
    label: 'Patterns & distribution',
    forms: ['prime-gaps-form', 'prime-tuples-form', 'gap-statistics-form', 'prime-distribution-form', 'goldbach-form'],
  },
  structures: {
    label: 'Prime structures',
    forms: ['prime-reciprocal-form', 'absolute-prime-form', 'paterson-prime-form', 'reptend-prime-form', 'gaussian-check-form', 'gaussian-range-form', 'modular-wheel-form'],
  },
  arithmetic: {
    label: 'Arithmetic & factors',
    forms: ['integer-profile-form', 'prime-modular-form', 'coprime-profile-form', 'factor-count-distribution-form', 'witness-form', 'prime-constant-form'],
  },
  explorations: {
    label: 'Advanced explorations',
    forms: ['prime-pyramid-form', 'special-number-form', 'contiguous-digits-form', 'prime-problem-form', 'prime-polynomial-form', 'palindrome-derived-form'],
  },
};

const primeTools = new Map();
const legacyPrimeRoutes = {
  essentials: 'prime-check', generation: 'prime-generate', patterns: 'prime-gaps',
  structures: 'prime-reciprocal', arithmetic: 'integer-profile', explorations: 'prime-pyramid',
};

function primeToolSlug(formId) {
  return formId.replace(/-form$/, '');
}

function initializePrimeTools() {
  const grid = $('#prime-page-grid');
  const navigation = $('#prime-tool-navigation');
  const select = $('#prime-tool-select');
  let index = 0;

  Object.entries(primeSections).forEach(([section, details]) => {
    const group = document.createElement('section');
    group.className = 'tool-nav-group';
    group.dataset.primeSection = section;
    const heading = document.createElement('h3');
    heading.textContent = details.label;
    group.appendChild(heading);

    const options = document.createElement('optgroup');
    options.label = details.label;
    details.forms.forEach((formId) => {
      const form = document.getElementById(formId);
      if (!form) throw new Error(`Prime tool form is missing: ${formId}`);
      const slug = primeToolSlug(formId);
      const title = form.querySelector('h2').textContent.trim();
      const description = form.querySelector(':scope > p:not(.eyebrow)')?.textContent.trim() || '';
      const eyebrow = form.querySelector(':scope > .eyebrow')?.textContent.trim() || details.label;
      const tool = { slug, formId, title, description, eyebrow, section, index };
      primeTools.set(slug, tool);
      form.dataset.primeTool = slug;
      grid.appendChild(form);

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'prime-tool-link';
      button.dataset.primeTool = slug;
      button.textContent = title;
      button.addEventListener('click', () => activatePrimeTool(slug, true, true));
      group.appendChild(button);

      const option = document.createElement('option');
      option.value = slug;
      option.textContent = title;
      options.appendChild(option);
      index += 1;
    });
    navigation.appendChild(group);
    select.appendChild(options);
  });

  $('#prime-operation-total').textContent = `${primeTools.size} native-engine analyses`;
  $('#prime-tool-search').addEventListener('input', (event) => {
    const query = event.target.value.trim().toLocaleLowerCase();
    document.querySelectorAll('.tool-nav-group').forEach((group) => {
      let visible = 0;
      group.querySelectorAll('.prime-tool-link').forEach((button) => {
        const tool = primeTools.get(button.dataset.primeTool);
        const match = !query || `${tool.title} ${tool.description} ${tool.eyebrow}`.toLocaleLowerCase().includes(query);
        button.classList.toggle('prime-page-hidden', !match);
        if (match) visible += 1;
      });
      group.classList.toggle('prime-page-hidden', visible === 0);
    });
  });

  select.addEventListener('change', (event) => activatePrimeTool(event.target.value, true, true));
}

function activatePrimeTool(slug, updateHash = true, focusPage = false) {
  const selected = primeTools.get(slug) || primeTools.values().next().value;
  state.primeTool = selected.slug;
  document.querySelectorAll('.prime-tool-link').forEach((button) => {
    const active = button.dataset.primeTool === selected.slug;
    button.classList.toggle('active', active);
    if (active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
    if (active) {
      const sidebar = button.closest('.tool-sidebar');
      const top = button.offsetTop;
      const bottom = top + button.offsetHeight;
      if (top < sidebar.scrollTop) sidebar.scrollTop = Math.max(0, top - 16);
      else if (bottom > sidebar.scrollTop + sidebar.clientHeight) {
        sidebar.scrollTop = bottom - sidebar.clientHeight + 16;
      }
    }
  });
  document.querySelectorAll('#prime-page-grid > form').forEach((form) => {
    form.classList.toggle('prime-page-hidden', form.id !== selected.formId);
  });
  $('#prime-tool-select').value = selected.slug;
  $('#prime-tool-section').textContent = primeSections[selected.section].label;
  $('#prime-page-title').textContent = selected.title;
  $('#prime-page-description').textContent = selected.description;
  $('#prime-page-count').textContent = `Operation ${selected.index + 1} of ${primeTools.size}`;
  document.title = `${selected.title} · Prime Tools · Numerisect`;

  const resultPanel = $('#prime-result-panel');
  resultPanel.classList.toggle('prime-page-hidden', Boolean(resultPanel.dataset.ownerForm && resultPanel.dataset.ownerForm !== selected.formId));
  if (updateHash && !$('#prime-view').classList.contains('hidden')) {
    history.pushState(null, '', `#primes/${selected.slug}`);
  }
  if (focusPage) $('#prime-tool-page').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function activateView(button, updateHash = true) {
  document.querySelectorAll('.mode-tab').forEach((tab) => tab.classList.remove('active'));
  document.querySelectorAll('.tool-view').forEach((view) => view.classList.add('hidden'));
  button.classList.add('active');
  $(`#${button.dataset.view}`).classList.remove('hidden');
  document.body.dataset.activeView = button.dataset.view;
  if (button.dataset.view === 'prime-view') activatePrimeTool(state.primeTool, false);
  if (button.dataset.view === 'factor-view') document.title = 'Integer Factorization · Numerisect';
  if (button.dataset.view === 'zeta-view') document.title = 'Riemann Zeta · Numerisect';
  if (updateHash) {
    const hashes = {
      'factor-view': '#factor',
      'prime-view': `#primes/${state.primeTool}`,
      'zeta-view': '#zeta',
    };
    history.replaceState(null, '', hashes[button.dataset.view]);
  }
}

document.querySelectorAll('.mode-tab').forEach((button) => {
  button.addEventListener('click', () => activateView(button));
});

function applyHashRoute() {
  const [section, primeTool] = location.hash.replace(/^#/, '').split('/');
  if (section === 'primes') {
    const route = legacyPrimeRoutes[primeTool] || primeTool;
    if (primeTools.has(route)) state.primeTool = route;
    activateView(document.querySelector('[data-view="prime-view"]'), false);
    activatePrimeTool(state.primeTool, false);
  } else if (section === 'zeta') {
    activateView(document.querySelector('[data-view="zeta-view"]'), false);
  } else {
    activateView(document.querySelector('[data-view="factor-view"]'), false);
  }
}

initializePrimeTools();
applyHashRoute();
window.addEventListener('hashchange', applyHashRoute);
window.addEventListener('popstate', applyHashRoute);

function placePrimeResult(form) {
  const panel = $('#prime-result-panel');
  panel.dataset.ownerForm = form.id;
  form.insertAdjacentElement('afterend', panel);
  panel.classList.remove('prime-page-hidden');
}

function showPrimeResult(title, data, type, form) {
  placePrimeResult(form);
  const panel = $('#prime-result-panel');
  const content = $('#prime-result-content');
  $('#prime-result-title').textContent = title;
  let note = data.note || '';
  if (data.truncated) note += `${note ? ' ' : ''}Display/export stopped at the requested limit.${data.next_start ? ` Continue from ${data.next_start}.` : ''}`;
  if (data.output_file) note += `${note ? ' ' : ''}✓ Result saved automatically to output/${data.output_file}.`;
  const noteElement = $('#prime-result-note');
  noteElement.textContent = note;
  noteElement.classList.toggle('saved-output-note', Boolean(data.output_file));
  if (type === 'table') {
    const metrics = Object.entries(data.metrics || {}).map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join('');
    const rows = data.rows.slice(0, 2000).map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`).join('');
    content.innerHTML = `${metrics ? `<div class="reciprocal-summary">${metrics}</div>` : ''}<div class="result-table-wrap"><table class="result-table"><thead><tr>${data.columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>${data.rows.length ? '' : '<p class="empty">No values found. See the result note above.</p>'}</div>`;
    if (data.rows.length > 2000) $('#prime-result-note').textContent += ' Showing the first 2,000 rows; the report contains all returned rows.';
  } else if (type === 'check') {
    content.innerHTML = `<div class="prime-verdict"><strong>${escapeHtml(data.classification)}</strong><code>${escapeHtml(data.number)}</code>${data.certificate_included ? '<span class="proof-badge">Certificate saved</span>' : ''}</div>`;
  } else if (type === 'classify') {
    const summary = `<div class="classification-summary"><span>${escapeHtml(data.classification)}</span><code>${escapeHtml(data.number)}</code><small>${data.is_prime ? `${data.matches.length} matched · ${data.not_matched} not matched · ${data.inconclusive.length} inconclusive` : 'Prime classes were not evaluated'}</small></div>`;
    const matches = data.matches.map((item) => `<article class="classification-card"><strong>${escapeHtml(item.name)}</strong>${item.detail ? `<code>${escapeHtml(item.detail)}</code>` : ''}<p>${escapeHtml(item.description)}</p></article>`).join('');
    const unknown = data.inconclusive.length
      ? `<details class="classification-unknown"><summary>${data.inconclusive.length} inconclusive classification${data.inconclusive.length === 1 ? '' : 's'}</summary>${data.inconclusive.map((item) => `<p><strong>${escapeHtml(item.name)}</strong> · ${escapeHtml(item.detail)}</p>`).join('')}</details>`
      : '';
    content.innerHTML = summary + (matches ? `<div class="classification-grid">${matches}</div>` : (data.is_prime ? '<div class="empty">No supported special class matched.</div>' : '')) + unknown;
  } else if (type === 'reciprocal') {
    const decimal = data.decimal_digits
      ? `0.${escapeHtml(data.decimal_digits)}${data.digits_complete ? '' : '…'}`
      : 'Decimal digits were not requested.';
    const decimalKind = data.terminating ? 'Terminating' : 'Repeating';
    const primitive = data.terminating ? 'Not applicable' : (data.primitive_root_10 ? 'Yes' : 'No');
    const fullReptend = data.terminating ? 'Not applicable' : (data.full_reptend ? 'Yes' : 'No');
    const digitLabel = data.terminating
      ? (data.digits_complete ? 'Complete decimal expansion' : 'Decimal digits')
      : (data.digits_complete ? 'Complete repetend' : `First ${Number(data.digits_generated).toLocaleString()} decimal digits`);
    content.innerHTML = `<div class="reciprocal-summary">
      <article><span>Period length</span><strong>${escapeHtml(data.period)}</strong></article>
      <article><span>Decimal type</span><strong>${decimalKind}</strong></article>
      <article><span>10 primitive modulo p</span><strong>${primitive}</strong></article>
      <article><span>Full-reptend prime</span><strong>${fullReptend}</strong></article>
    </div><div class="reciprocal-decimal"><span>${digitLabel}</span><code>${decimal}</code></div>`;
  } else if (type === 'metric') {
    content.innerHTML = `<div class="prime-metric"><span>${escapeHtml(data.label)}</span><strong>${escapeHtml(data.value)}</strong></div>`;
  } else if (type === 'gaps') {
    const largest = data.largest
      ? `<div class="gap-highlight"><span>Largest displayed gap</span><strong>${data.largest.gap}</strong><code>${escapeHtml(data.largest.from)} → ${escapeHtml(data.largest.to)}</code></div>`
      : '';
    const shown = data.gaps.slice(0, 2000);
    const chart = shown.length ? '<canvas id="gap-sequence-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Prime gap sequence chart"></canvas>' : '';
    content.innerHTML = largest + chart + (shown.map((gap) => `<div class="gap-row"><code>${escapeHtml(gap.from)}</code><span>+${gap.gap}</span><code>${escapeHtml(gap.to)}</code></div>`).join('') || '<div class="empty">Fewer than two primes occur in this interval.</div>');
    if (shown.length) drawGapSequence($('#gap-sequence-canvas'), shown);
    if (data.gaps.length > shown.length) $('#prime-result-note').textContent += ` Showing the first ${shown.length.toLocaleString()} gaps in the browser.`;
  } else if (type === 'tuples') {
    const shown = data.tuples.slice(0, 2000);
    content.innerHTML = shown.map((tuple) => `<div class="prime-chip tuple">${tuple.map(escapeHtml).join(' &nbsp; · &nbsp; ')}</div>`).join('') || '<div class="empty">No matching tuples in this interval.</div>';
    if (data.tuples.length > shown.length) $('#prime-result-note').textContent += ` Showing the first ${shown.length.toLocaleString()} in the browser.`;
  } else if (type === 'absolute') {
    content.innerHTML = data.groups.map((group) => `<article class="structure-card"><span>Orbit representative</span><strong>${escapeHtml(group.representative)}</strong><code>${group.rotations.map(escapeHtml).join(' → ')}</code></article>`).join('') || '<div class="empty">No absolute primes found.</div>';
  } else if (type === 'paterson') {
    content.innerHTML = data.values.map((item) => `<article class="structure-card"><span>Prime ${escapeHtml(item.prime)}</span><strong>${escapeHtml(item.base4)}<small>₄</small></strong><code>decimal companion ${escapeHtml(item.decimal_companion)}</code></article>`).join('') || '<div class="empty">No Paterson primes found.</div>';
  } else if (type === 'gaussian') {
    const factors = data.factors.length ? `<p>Axis factor pair: ${data.factors.map((item) => { const negative = String(item.imaginary).startsWith('-'); return `${escapeHtml(item.real)} ${negative ? '−' : '+'} ${escapeHtml(negative ? String(item.imaginary).slice(1) : item.imaginary)}i`; }).join(' and ')}</p>` : '';
    content.innerHTML = `<div class="prime-verdict"><strong>${data.is_gaussian_prime ? 'Gaussian prime' : 'Not Gaussian prime'}</strong><code>${escapeHtml(data.real)} + (${escapeHtml(data.imaginary)})i</code><p>Norm ${escapeHtml(data.norm)} · rational prime: ${data.norm_is_rational_prime ? 'yes' : 'no'}</p>${factors}</div>`;
  } else if (type === 'gaussian-list') {
    content.innerHTML = '<canvas id="gaussian-canvas" class="math-canvas" width="760" height="620" aria-label="Gaussian prime lattice"></canvas>';
    drawGaussianLattice($('#gaussian-canvas'), data.points, data.bound);
  } else if (type === 'perfect') {
    content.innerHTML = data.values.map((item, index) => `<article class="perfect-card"><span>#${index + 1} · Mersenne exponent ${escapeHtml(item.exponent)}</span><code>${escapeHtml(item.value)}</code><small>2^${escapeHtml(item.exponent)} − 1 = ${escapeHtml(item.mersenne_prime)}</small></article>`).join('');
  } else if (type === 'wheel') {
    content.innerHTML = '<canvas id="wheel-canvas" class="math-canvas" width="760" height="760" aria-label="Modular prime wheel"></canvas><div class="canvas-legend"><span class="legend-prime">Prime</span><span class="legend-coprime">Coprime to modulus</span><span>Composite/non-coprime</span></div>';
    drawModularWheel($('#wheel-canvas'), data.cells, data.modulus);
  } else if (type === 'reptend') {
    content.innerHTML = data.values.map((item) => `<article class="structure-card"><span>Full-reptend prime</span><strong>${escapeHtml(item.prime)}</strong><code>period ${escapeHtml(item.period)}</code></article>`).join('') || '<div class="empty">No full-reptend primes found.</div>';
  } else if (type === 'witness') {
    const verdict = data.is_prime ? 'Proven prime' : (data.is_witness ? 'Composite witness' : 'Passing base / strong liar');
    const distribution = data.distribution_complete
      ? `<div class="reciprocal-summary"><article><span>Candidate bases</span><strong>${escapeHtml(data.base_count)}</strong></article><article><span>Witnesses</span><strong>${escapeHtml(data.witness_count)}</strong></article><article><span>Passing bases</span><strong>${escapeHtml(data.passing_count)}</strong></article><article><span>Selected gcd</span><strong>${escapeHtml(data.gcd)}</strong></article></div><div class="witness-lists"><p><strong>Witness preview</strong><code>${data.witnesses.map(escapeHtml).join(', ') || 'none'}</code></p><p><strong>Passing-base preview</strong><code>${data.passing_bases.map(escapeHtml).join(', ') || 'none'}</code></p></div>`
      : '';
    content.innerHTML = `<div class="prime-verdict"><strong>${verdict}</strong><code>${escapeHtml(data.number)} = 2^${escapeHtml(data.s)} × ${escapeHtml(data.d)} + 1</code><p>Selected base ${escapeHtml(data.base)} ${data.passes ? 'passes' : 'fails'} the strong Miller–Rabin test.</p></div>${distribution}`;
  } else if (type === 'pyramid') {
    if (data.kind === 'insertion') {
      content.innerHTML = `<div class="pyramid-output">${data.levels.map((item) => `<div><span>${item.level}</span><code>${escapeHtml(item.value)}</code><small>inserted sum ${item.inserted_sum}</small></div>`).join('')}</div>`;
    } else {
      content.innerHTML = `<div class="pyramid-output multiplication">${data.rows.map((row) => `<div>${row.map((cell) => `<code class="${cell.is_prime ? 'is-prime' : ''}">${escapeHtml(cell.value)}</code>`).join('')}</div>`).join('')}</div>`;
    }
  } else if (type === 'special-numbers') {
    content.innerHTML = data.values.map((item) => `<article class="structure-card"><span>${escapeHtml(item.detail.replaceAll('_', ' '))}</span><strong>${escapeHtml(item.value)}</strong></article>`).join('') || '<div class="empty">No matching values found.</div>';
  } else if (type === 'gap-statistics') {
    if (!Number(data.count)) {
      content.innerHTML = '<div class="empty">Fewer than two primes occur in the scanned interval.</div>';
    } else {
      content.innerHTML = `<div class="reciprocal-summary"><article><span>Minimum</span><strong>${escapeHtml(data.minimum)}</strong></article><article><span>Maximum</span><strong>${escapeHtml(data.maximum)}</strong></article><article><span>Mean</span><strong>${escapeHtml(data.mean.numerator)}/${escapeHtml(data.mean.denominator)}</strong></article><article><span>Median</span><strong>${escapeHtml(data.median.numerator)}/${escapeHtml(data.median.denominator)}</strong></article></div><div class="chart-stack"><div><span>Frequency</span><canvas id="gap-frequency-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Prime gap frequency chart"></canvas></div><div><span>Log₁₀ frequency</span><canvas id="gap-log-frequency-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Log prime gap frequency chart"></canvas></div></div>`;
      drawGapFrequencies($('#gap-frequency-canvas'), data.frequencies);
      drawGapFrequencies($('#gap-log-frequency-canvas'), data.frequencies, true);
    }
  } else if (type === 'primorials') {
    content.innerHTML = data.values.map((item) => `<article class="perfect-card"><span>#${escapeHtml(item.index)} · ending prime ${escapeHtml(item.prime)}</span><code>${escapeHtml(item.value)}</code></article>`).join('');
  } else if (type === 'goldbach') {
    content.innerHTML = data.partitions.map((item) => `<div class="prime-chip tuple">${escapeHtml(data.number)} = ${escapeHtml(item.left)} + ${escapeHtml(item.right)}</div>`).join('') || '<div class="empty">No partition was found within the complete requested search.</div>';
  } else if (type === 'prime-problem') {
    content.innerHTML = data.values.map((item) => {
      if (data.kind === 'square_sum') return `<div class="prime-chip tuple">${escapeHtml(item.p)}² + 1 = ${escapeHtml(item.q)}² + ${escapeHtml(item.r)}²</div>`;
      if (data.kind === 'quartan') return `<div class="prime-chip tuple">${escapeHtml(item.prime)} = ${escapeHtml(item.a)}⁴ + ${escapeHtml(item.b)}⁴</div>`;
      if (data.kind === 'three_factors') return `<div class="prime-chip tuple">n=${escapeHtml(item.n)} · n²−1=${escapeHtml(item.value)} · ${escapeHtml(item.factorization)}</div>`;
      return `<div class="prime-chip tuple">p=${escapeHtml(item.prime)} · σ(p⁴)=${escapeHtml(item.sigma)}=${escapeHtml(item.root)}²</div>`;
    }).join('') || '<div class="empty">No solutions found within the requested finite search.</div>';
  } else if (type === 'integer-profile') {
    const factorCards = data.factors.map((item) => `<code class="prime-chip">${escapeHtml(item.prime)}<sup>${item.exponent === '1' ? '' : escapeHtml(item.exponent)}</sup></code>`).join('') || '<code class="prime-chip">1</code>';
    const divisors = data.divisors.slice(0, 2000).map((value) => `<code class="prime-chip">${escapeHtml(value)}</code>`).join('');
    content.innerHTML = `<div class="prime-verdict"><strong>${escapeHtml(data.divisor_class)} ${data.is_semiprime ? 'semiprime' : (data.is_prime ? 'prime' : 'integer')}</strong><code>${escapeHtml(data.number)} = ${escapeHtml(data.factorization)}</code></div><div class="reciprocal-summary"><article><span>ω(n) distinct factors</span><strong>${escapeHtml(data.omega)}</strong></article><article><span>Ω(n) with multiplicity</span><strong>${escapeHtml(data.big_omega)}</strong></article><article><span>τ(n) divisors</span><strong>${escapeHtml(data.divisor_count)}</strong></article><article><span>σ(n)</span><strong>${escapeHtml(data.divisor_sum)}</strong></article><article><span>φ(n)</span><strong>${escapeHtml(data.totient)}</strong></article><article><span>λ(n)</span><strong>${escapeHtml(data.carmichael)}</strong></article><article><span>μ(n)</span><strong>${escapeHtml(data.mobius)}</strong></article><article><span>rad(n)</span><strong>${escapeHtml(data.radical)}</strong></article></div><div class="result-group"><span>Prime-power factorization</span><div>${factorCards}</div></div><div class="result-group"><span>Divisor preview</span><div>${divisors || '<div class="empty">No divisors requested.</div>'}</div></div>`;
    if (!data.divisors_complete) $('#prime-result-note').textContent += ` Showing ${data.divisors.length.toLocaleString()} of ${Number(data.divisor_count).toLocaleString()} divisors.`;
  } else if (type === 'coprimes') {
    content.innerHTML = `<div class="prime-metric"><span>Euler totient φ(${escapeHtml(data.modulus)})</span><strong>${escapeHtml(data.totient)}</strong></div><div class="result-group"><span>Coprimes strictly after ${escapeHtml(data.start)}</span><div>${data.after.map((value) => `<code class="prime-chip">${escapeHtml(value)}</code>`).join('')}</div></div><div class="result-group"><span>Reduced residue system${data.residues_complete ? '' : ' preview'}</span><div>${data.residues.map((value) => `<code class="prime-chip">${escapeHtml(value)}</code>`).join('') || '<div class="empty">No residues requested.</div>'}</div></div>`;
  } else if (type === 'distribution') {
    content.innerHTML = `<div class="reciprocal-summary"><article><span>Prime count</span><strong>${Number(data.count).toLocaleString()}</strong></article><article><span>Twin pairs</span><strong>${Number(data.twin_count).toLocaleString()}</strong></article><article><span>Largest internal gap</span><strong>${escapeHtml(data.maximum_gap)}</strong></article><article><span>Gap begins at</span><strong>${escapeHtml(data.maximum_gap_at)}</strong></article></div><div class="chart-stack"><div><span>Prime counts by interval</span><canvas id="distribution-bin-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Prime counts by interval"></canvas></div><div><span>Residues modulo ${data.modulus}</span><canvas id="distribution-residue-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Prime residue counts"></canvas></div></div>`;
    drawCountBars($('#distribution-bin-canvas'), data.bins.map((item) => ({ label: `${item.start}–${item.end}`, count: item.count })));
    drawCountBars($('#distribution-residue-canvas'), data.residues.map((item) => ({ label: item.residue, count: item.count })));
  } else if (type === 'factor-distribution') {
    content.innerHTML = `<div class="prime-metric"><span>Integers factored</span><strong>${Number(data.total).toLocaleString()}</strong></div><div class="chart-stack"><div><span>ω(n) · distinct prime factors</span><canvas id="factor-distinct-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Distinct prime factor counts"></canvas></div><div><span>Ω(n) · factors with multiplicity</span><canvas id="factor-multiplicity-canvas" class="math-canvas chart-canvas" width="1000" height="420" aria-label="Prime factor counts with multiplicity"></canvas></div></div>`;
    drawCountBars($('#factor-distinct-canvas'), data.distribution.map((item) => ({ label: item.factor_count, count: item.distinct_count })));
    drawCountBars($('#factor-multiplicity-canvas'), data.distribution.map((item) => ({ label: item.factor_count, count: item.multiplicity_count })));
  } else if (type === 'polynomial') {
    const shown = data.values.slice(0, 2000);
    const roots = data.obstructions.slice(0, 1000).map((item) => `<div class="gap-row"><code>mod ${escapeHtml(item.prime)}</code><span>n ≡</span><code>${item.residues.map(escapeHtml).join(', ')}</code></div>`).join('');
    content.innerHTML = `<div class="reciprocal-summary"><article><span>Prime values</span><strong>${Number(data.count).toLocaleString()}</strong></article><article><span>Longest run</span><strong>${Number(data.longest_run).toLocaleString()}</strong></article><article><span>Run starts at n</span><strong>${escapeHtml(data.longest_run_start)}</strong></article><article><span>Constant k</span><strong>${escapeHtml(data.k)}</strong></article></div><div class="result-group"><span>Prime values of n² − n + k</span><div>${shown.map((item) => `<code class="prime-chip">n=${escapeHtml(item.n)} → ${escapeHtml(item.value)}</code>`).join('') || '<div class="empty">No prime values found.</div>'}</div></div><div class="result-group"><span>Small-prime divisibility classes</span><div>${roots || '<div class="empty">No modular roots through the selected bound.</div>'}</div></div>`;
  } else if (type === 'palindrome-derived') {
    content.innerHTML = data.values.slice(0, 2000).map((item) => `<div class="prime-chip tuple">n=${escapeHtml(item.n)} · reverse=${escapeHtml(item.reverse)} · result=${escapeHtml(item.prime)}</div>`).join('') || '<div class="empty">No prime values found.</div>';
  } else if (type === 'prime-constant') {
    content.innerHTML = `<div class="prime-verdict constant-result"><strong>${Number(data.decimal_digits).toLocaleString()} certified decimal digits</strong><code>${escapeHtml(data.value)}</code><p>${Number(data.terms).toLocaleString()} primality-indicator bits · tail &lt; ${escapeHtml(data.error_bound)}</p></div>`;
  } else {
    const shown = data.primes.slice(0, 2000);
    content.innerHTML = shown.map((prime) => `<code class="prime-chip">${escapeHtml(prime)}</code>`).join('') || '<div class="empty">No primes found.</div>';
    if (data.primes.length > shown.length) $('#prime-result-note').textContent += ` Showing the first ${shown.length.toLocaleString()} in the browser.`;
  }
  const download = $('#prime-download');
  download.href = `/api/outputs/${encodeURIComponent(data.output_file)}`;
  download.classList.toggle('hidden', !data.output_file);
  panel.classList.remove('hidden');
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function prepareCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const logicalWidth = Number(canvas.getAttribute('width'));
  const logicalHeight = Number(canvas.getAttribute('height'));
  canvas.width = logicalWidth * ratio;
  canvas.height = logicalHeight * ratio;
  canvas.getContext('2d').scale(ratio, ratio);
  return { context: canvas.getContext('2d'), width: logicalWidth, height: logicalHeight };
}

function drawGaussianLattice(canvas, points, bound) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const pad = 34, scale = Math.min((width - pad * 2), (height - pad * 2)) / (bound * 2 || 1);
  const x = (value) => width / 2 + value * scale;
  const y = (value) => height / 2 - value * scale;
  ctx.strokeStyle = '#35404a'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, y(0)); ctx.lineTo(width - pad, y(0)); ctx.moveTo(x(0), pad); ctx.lineTo(x(0), height - pad); ctx.stroke();
  const radius = Math.max(1.5, Math.min(4.5, scale * 0.18));
  ctx.fillStyle = '#4f9cf9';
  points.forEach((point) => { ctx.beginPath(); ctx.arc(x(Number(point.real)), y(Number(point.imaginary)), radius, 0, Math.PI * 2); ctx.fill(); });
}

function drawModularWheel(canvas, cells, modulus) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const centerX = width / 2, centerY = height / 2;
  const rings = Math.max(...cells.map((cell) => cell.ring), 1) + 1;
  const spacing = Math.min(width, height) * 0.44 / rings;
  cells.forEach((cell) => {
    const angle = -Math.PI / 2 + (cell.residue / modulus) * Math.PI * 2;
    const radius = (cell.ring + 1) * spacing;
    const x = centerX + Math.cos(angle) * radius;
    const y = centerY + Math.sin(angle) * radius;
    ctx.fillStyle = cell.is_prime ? '#4f9cf9' : (cell.coprime ? '#d6a34a' : '#46515b');
    ctx.beginPath(); ctx.arc(x, y, cell.is_prime ? 3.2 : 2, 0, Math.PI * 2); ctx.fill();
  });
  ctx.fillStyle = '#8d9aa5'; ctx.font = '11px sans-serif'; ctx.textAlign = 'center';
  for (let residue = 0; residue < modulus; residue += Math.max(1, Math.ceil(modulus / 30))) {
    const angle = -Math.PI / 2 + (residue / modulus) * Math.PI * 2;
    const radius = Math.min(width, height) * 0.475;
    ctx.fillText(String(residue), centerX + Math.cos(angle) * radius, centerY + Math.sin(angle) * radius + 4);
  }
}

function drawGapFrequencies(canvas, frequencies, logarithmic = false) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  if (!frequencies.length) return;
  const display = (frequency) => logarithmic ? Math.log10(Math.max(1, frequency)) : frequency;
  const pad = 45, maximum = Math.max(...frequencies.map((item) => display(item.frequency)), 1);
  const barWidth = (width - pad * 2) / frequencies.length;
  frequencies.forEach((item, index) => {
    const barHeight = display(item.frequency) / maximum * (height - pad * 2);
    ctx.fillStyle = '#4f9cf9';
    ctx.fillRect(pad + index * barWidth + 1, height - pad - barHeight, Math.max(1, barWidth - 2), barHeight);
  });
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(`gap ${frequencies[0].gap}`, pad, height - 15);
  ctx.fillText(`gap ${frequencies[frequencies.length - 1].gap}`, width - 100, height - 15);
  ctx.fillText(`${logarithmic ? 'log₁₀ ' : ''}maximum ${maximum.toPrecision(5)}`, pad, 25);
}

function drawGapSequence(canvas, gaps) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const pad = 40, maximum = Math.max(...gaps.map((item) => item.gap), 1);
  ctx.strokeStyle = '#4f9cf9'; ctx.lineWidth = 1.5; ctx.beginPath();
  gaps.forEach((item, index) => {
    const x = pad + index / Math.max(1, gaps.length - 1) * (width - pad * 2);
    const y = height - pad - item.gap / maximum * (height - pad * 2);
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText('consecutive gap index', width / 2 - 55, height - 12);
  ctx.fillText(`max ${maximum}`, 8, 20);
}

function drawCountBars(canvas, values) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  if (!values.length) return;
  const pad = 45, maximum = Math.max(...values.map((item) => Number(item.count)), 1);
  const barWidth = (width - pad * 2) / values.length;
  values.forEach((item, index) => {
    const barHeight = Number(item.count) / maximum * (height - pad * 2);
    ctx.fillStyle = '#4f9cf9';
    ctx.fillRect(pad + index * barWidth + 1, height - pad - barHeight, Math.max(1, barWidth - 2), barHeight);
  });
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(String(values[0].label), pad, height - 15);
  ctx.fillText(String(values[values.length - 1].label), Math.max(pad, width - 150), height - 15);
  ctx.fillText(`maximum ${maximum.toLocaleString()}`, pad, 25);
}

async function submitPrimeForm(form, path, payload, title, type) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const oldText = button.firstElementChild.textContent;
  button.firstElementChild.textContent = 'Working…';
  try {
    const data = await api(path, { method: 'POST', body: JSON.stringify(payload) });
    showPrimeResult(title(data), data, type, form);
  } catch (error) {
    placePrimeResult(form);
    $('#prime-result-title').textContent = 'Could not complete request';
    $('#prime-result-note').textContent = error.message;
    $('#prime-result-note').classList.remove('saved-output-note');
    $('#prime-result-content').innerHTML = '';
    $('#prime-result-panel').classList.remove('hidden');
    $('#prime-download').classList.add('hidden');
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = oldText;
  }
}

$('#prime-result-close').addEventListener('click', () => {
  $('#prime-result-panel').classList.add('hidden');
});

$('#prime-check-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/check',
    {
      expression: $('#prime-check-input').value,
      mode: $('#prime-check-mode').value,
      certificate: $('#prime-certificate').checked,
    },
    (data) => `${data.digits}-digit input`, 'check');
});

$('#prime-check-mode').addEventListener('change', (event) => {
  const fast = event.target.value === 'fast';
  $('#prime-certificate').disabled = fast;
  if (fast) $('#prime-certificate').checked = false;
});

$('#prime-classify-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/classify', {
    expression: $('#prime-classify-input').value,
    per_test_seconds: Number($('#prime-classify-budget').value),
  }, (data) => data.is_prime
    ? `${data.matches.length} of ${data.tested} prime classifications matched`
    : 'Composite input', 'classify');
});

$('#prime-reciprocal-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/reciprocal', {
    expression: $('#prime-reciprocal-input').value,
    digit_limit: Number($('#prime-reciprocal-digits').value),
    timeout_seconds: Number($('#prime-reciprocal-timeout').value),
  }, (data) => `Decimal analysis of 1/${shortNumber(data.number, 24)}`, 'reciprocal');
});

$('#prime-generate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/generate', {
    count: Number($('#prime-count').value), digits: Number($('#prime-digits').value)
  }, (data) => `${data.count.toLocaleString()} generated primes`, 'list');
});

$('#prime-batch-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/batch-check', {
    integers: $('#prime-batch-input').value, mode: $('#prime-batch-mode').value,
    timeout_seconds: Number($('#prime-batch-timeout').value),
  }, () => 'Batch primality results', 'table');
});

$('#prime-progression-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/progression', {
    start: $('#prime-progression-start').value, end: $('#prime-progression-end').value,
    modulus: $('#prime-progression-modulus').value, residue: $('#prime-progression-residue').value,
    limit: Number($('#prime-progression-limit').value),
    timeout_seconds: Number($('#prime-progression-timeout').value),
  }, () => 'Primes in a residue class', 'table');
});

$('#prime-modular-operation').addEventListener('change', (event) => {
  const generator = event.target.value === 'generator';
  const power = event.target.value === 'power';
  $('#prime-modular-value-field').classList.toggle('hidden', generator);
  $('#prime-modular-value').disabled = generator;
  $('#prime-modular-exponent-field').classList.toggle('hidden', !power);
  $('#prime-modular-exponent').disabled = !power;
});
$('#prime-modular-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const operation = $('#prime-modular-operation').value;
  submitPrimeForm(event.currentTarget, '/api/primes/modular', {
    modulus: $('#prime-modular-modulus').value, operation,
    value: operation === 'generator' ? '1' : $('#prime-modular-value').value,
    exponent: operation === 'power' ? $('#prime-modular-exponent').value : '2',
    timeout_seconds: Number($('#prime-modular-timeout').value),
  }, () => 'Arithmetic modulo a prime', 'table');
});

$('#prime-nearby-result').addEventListener('change', (event) => {
  $('#prime-nearby-count-label').textContent = event.target.value === 'nth' ? 'Position (n)' : 'Count';
});

$('#prime-nearby-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const direction = $('#prime-nearby-direction').value;
  if ($('#prime-nearby-result').value === 'nth') {
    submitPrimeForm(event.currentTarget, '/api/primes/nth-near', {
      start: $('#prime-nearby-start').value,
      index: Number($('#prime-after-count').value), direction,
    }, () => 'Indexed nearby prime', 'metric');
    return;
  }
  submitPrimeForm(event.currentTarget, `/api/primes/${direction}`, {
    start: $('#prime-nearby-start').value, count: Number($('#prime-after-count').value)
  }, (data) => `${data.count.toLocaleString()} primes ${direction} ${shortNumber(data.start, 24)}`, 'list');
});

$('#prime-range-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/range', {
    start: $('#prime-range-start').value,
    end: $('#prime-range-end').value,
    limit: Number($('#prime-range-limit').value)
  }, (data) => `${data.count.toLocaleString()} primes in range`, 'list');
});

$('#prime-special-kind').addEventListener('change', (event) => {
  document.querySelectorAll('.modular-only').forEach((field) => {
    field.classList.toggle('hidden', event.target.value !== 'congruence');
  });
});

$('#prime-special-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const kind = $('#prime-special-kind').value;
  submitPrimeForm(event.currentTarget, '/api/primes/generate-special', {
    kind,
    count: Number($('#prime-special-count').value),
    digits: Number($('#prime-special-digits').value),
    modulus: kind === 'congruence' ? Number($('#prime-modulus').value) : null,
    remainder: kind === 'congruence' ? Number($('#prime-remainder').value) : null,
  }, (data) => `${data.count.toLocaleString()} ${data.kind.replace('_', ' ')} primes`, 'list');
});

$('#prime-nth-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/nth', {
    index: Number($('#prime-index').value),
  }, (data) => `${data.label} · ${data.digits} digits`, 'metric');
});

$('#prime-count-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/count', {
    expression: $('#prime-count-through').value,
  }, () => 'Exact prime count', 'metric');
});

$('#prime-gaps-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/gaps', {
    start: $('#prime-gaps-start').value,
    end: $('#prime-gaps-end').value,
    limit: Number($('#prime-gaps-limit').value),
  }, (data) => `${data.count.toLocaleString()} consecutive prime gaps`, 'gaps');
});

$('#tuple-pattern').addEventListener('change', (event) => {
  const custom = event.target.value === 'custom';
  $('#tuple-offsets').disabled = !custom;
  if (!custom) $('#tuple-offsets').value = event.target.value;
});

$('#prime-tuples-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const offsets = $('#tuple-offsets').value.split(',').map((value) => Number(value.trim()));
  submitPrimeForm(event.currentTarget, '/api/primes/tuples', {
    start: $('#tuple-start').value,
    end: $('#tuple-end').value,
    offsets,
    limit: Number($('#tuple-limit').value)
  }, (data) => `${data.count.toLocaleString()} prime tuples`, 'tuples');
});

$('#absolute-prime-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/absolute', {
    start: $('#absolute-start').value, end: $('#absolute-end').value,
    limit: Number($('#absolute-limit').value),
  }, (data) => `${data.count.toLocaleString()} absolute-prime orbits`, 'absolute');
});

$('#paterson-prime-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/paterson', {
    start: $('#paterson-start').value, end: $('#paterson-end').value,
    limit: Number($('#paterson-limit').value),
  }, (data) => `${data.count.toLocaleString()} Paterson primes`, 'paterson');
});

$('#gaussian-check-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/gaussian/check', {
    real: $('#gaussian-real').value, imaginary: $('#gaussian-imaginary').value,
  }, () => 'Gaussian-prime analysis', 'gaussian');
});

$('#gaussian-range-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/gaussian/range', {
    bound: Number($('#gaussian-bound').value), limit: Number($('#gaussian-limit').value),
  }, (data) => `${data.count.toLocaleString()} Gaussian prime points`, 'gaussian-list');
});

$('#perfect-number-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/perfect', {
    count: Number($('#perfect-count').value), timeout_seconds: Number($('#perfect-timeout').value),
  }, (data) => `${data.count} even perfect numbers`, 'perfect');
});

$('#modular-wheel-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/modular-wheel', {
    modulus: Number($('#wheel-modulus').value), maximum: Number($('#wheel-maximum').value),
  }, (data) => `Modular wheel · modulus ${data.modulus}`, 'wheel');
});

$('#reptend-prime-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/reptend', {
    start: $('#reptend-start').value, end: $('#reptend-end').value,
    limit: Number($('#reptend-limit').value),
  }, (data) => `${data.count.toLocaleString()} full-reptend primes`, 'reptend');
});

$('#witness-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/miller-rabin-witnesses', {
    expression: $('#witness-number').value, base: $('#witness-base').value,
    preview_limit: Number($('#witness-limit').value),
  }, () => 'Miller–Rabin witness analysis', 'witness');
});

$('#pyramid-kind').addEventListener('change', (event) => {
  $('#pyramid-size').max = event.target.value === 'insertion' ? 30 : 100;
});

$('#prime-pyramid-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/pyramid', {
    kind: $('#pyramid-kind').value, size: Number($('#pyramid-size').value),
  }, (data) => `${data.kind === 'insertion' ? 'Digit-insertion' : 'Multiplication'} prime pyramid`, 'pyramid');
});

$('#special-number-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/special-numbers', {
    kind: $('#special-number-kind').value,
    start: $('#special-number-start').value, end: $('#special-number-end').value,
    limit: Number($('#special-number-limit').value),
  }, (data) => `${data.count.toLocaleString()} special values`, 'special-numbers');
});

$('#gap-statistics-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/gap-statistics', {
    start: $('#gap-stats-start').value, end: $('#gap-stats-end').value,
    limit: Number($('#gap-stats-limit').value),
  }, (data) => `${Number(data.count).toLocaleString()} prime gaps · exact distribution`, 'gap-statistics');
});

$('#primorial-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/primorials', {
    count: Number($('#primorial-count').value),
  }, (data) => `${data.count} primorials`, 'primorials');
});

$('#random-range-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/random-range', {
    start: $('#random-range-start').value, end: $('#random-range-end').value,
    count: Number($('#random-range-count').value),
  }, (data) => `${data.count} random proven primes`, 'list');
});

$('#contiguous-digits-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/contiguous-digits', {
    expression: $('#contiguous-number').value,
  }, (data) => `${data.count} distinct contiguous-digit primes`, 'list');
});

$('#goldbach-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/goldbach', {
    expression: $('#goldbach-number').value, limit: Number($('#goldbach-limit').value),
  }, (data) => `${data.count} Goldbach partitions`, 'goldbach');
});

$('#prime-problem-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/problems', {
    kind: $('#prime-problem-kind').value, start: $('#prime-problem-start').value,
    end: $('#prime-problem-end').value, limit: Number($('#prime-problem-limit').value),
  }, (data) => `${data.count} bounded-search solutions`, 'prime-problem');
});

$('#integer-profile-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/integer-profile', {
    expression: $('#integer-profile-number').value,
    divisor_limit: Number($('#integer-profile-limit').value),
  }, () => 'Integer arithmetic profile', 'integer-profile');
});

$('#coprime-profile-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/coprimes', {
    modulus: $('#coprime-modulus').value, start: $('#coprime-start').value,
    count: Number($('#coprime-count').value),
    residue_limit: Number($('#coprime-residue-limit').value),
  }, (data) => `Coprimes modulo ${shortNumber(data.modulus, 24)}`, 'coprimes');
});

$('#prime-distribution-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/distribution', {
    start: $('#distribution-start').value, end: $('#distribution-end').value,
    bins: Number($('#distribution-bins').value),
    modulus: Number($('#distribution-modulus').value),
  }, (data) => `${Number(data.count).toLocaleString()} primes · exact distribution`, 'distribution');
});

$('#factor-count-distribution-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/factor-count-distribution', {
    start: $('#factor-distribution-start').value,
    end: $('#factor-distribution-end').value,
  }, (data) => `${Number(data.total).toLocaleString()} integers · factor-count distribution`, 'factor-distribution');
});

$('#digit-constrained-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/digit-constrained', {
    allowed_digits: $('#constrained-digits').value,
    minimum_digits: Number($('#constrained-min').value),
    maximum_digits: Number($('#constrained-max').value),
    limit: Number($('#constrained-limit').value),
  }, (data) => `${data.count.toLocaleString()} digit-constrained primes`, 'list');
});

$('#prime-polynomial-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/polynomial', {
    k: $('#polynomial-k').value, start: $('#polynomial-start').value,
    end: $('#polynomial-end').value, limit: Number($('#polynomial-limit').value),
    obstruction_bound: Number($('#polynomial-obstruction').value),
  }, (data) => `${Number(data.count).toLocaleString()} prime polynomial values`, 'polynomial');
});

$('#palindrome-derived-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/palindrome-derived', {
    start: $('#palindrome-derived-start').value,
    end: $('#palindrome-derived-end').value,
    limit: Number($('#palindrome-derived-limit').value),
  }, (data) => `${Number(data.count).toLocaleString()} palindrome-derived prime values`, 'palindrome-derived');
});

$('#prime-constant-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/indicator-constant', {
    decimal_digits: Number($('#prime-constant-digits').value),
  }, () => 'Prime-indicator constant', 'prime-constant');
});

function showZetaResult(title, data, type) {
  const panel = $('#zeta-result-panel');
  const content = $('#zeta-result-content');
  $('#zeta-result-title').textContent = title;
  let note = data.note || '';
  if (data.output_file) note += `${note ? ' ' : ''}✓ Result saved automatically to output/${data.output_file}.`;
  $('#zeta-result-note').textContent = note;
  $('#zeta-result-note').classList.toggle('saved-output-note', Boolean(data.output_file));
  if (type === 'value') {
    content.innerHTML = `<div class="zeta-value-grid">
      <article><span>Real enclosure</span><code>${escapeHtml(data.real)}</code></article>
      <article><span>Imaginary enclosure</span><code>${escapeHtml(data.imaginary)}</code></article>
      <article><span>Magnitude enclosure</span><code>${escapeHtml(data.magnitude)}</code></article>
      <article><span>Argument enclosure</span><code>${escapeHtml(data.argument)}</code></article>
    </div>`;
  } else if (type === 'count') {
    content.innerHTML = `<div class="prime-metric"><span>${escapeHtml(data.label)}</span><strong>${escapeHtml(data.value)}</strong><small>Certified enclosure ${escapeHtml(data.interval)}</small></div>`;
  } else if (type === 'zeros') {
    content.innerHTML = data.zeros.map((zero) => `<article class="zero-row"><strong>#${escapeHtml(zero.index)}</strong><code>${escapeHtml(zero.ordinate)}</code><small>${escapeHtml(zero.interval)}</small></article>`).join('');
  } else if (type === 'line') {
    content.innerHTML = '<canvas id="zeta-line-canvas" class="math-canvas chart-canvas" width="1000" height="560" aria-label="Riemann zeta plot"></canvas>';
    drawZetaLine($('#zeta-line-canvas'), data.points, $('#zeta-line-component').value);
  } else if (type === 'heatmap') {
    content.innerHTML = '<canvas id="zeta-heatmap-canvas" class="math-canvas heatmap-canvas" width="1000" height="650" aria-label="Riemann zeta heatmap"></canvas><div class="canvas-legend"><span>Hue = phase</span><span>Lightness = log magnitude</span><span>Black = pole/undefined</span></div>';
    drawZetaHeatmap($('#zeta-heatmap-canvas'), data.points, data.width, data.height);
  }
  const download = $('#zeta-download');
  download.href = `/api/outputs/${encodeURIComponent(data.output_file)}`;
  download.classList.toggle('hidden', !data.output_file);
  panel.classList.remove('hidden');
  panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function submitZetaForm(form, path, payload, title, type) {
  const button = form.querySelector('button[type="submit"]');
  const oldText = button.firstElementChild.textContent;
  button.disabled = true; button.firstElementChild.textContent = 'Working…';
  try {
    const data = await api(path, { method: 'POST', body: JSON.stringify(payload) });
    showZetaResult(title(data), data, type);
  } catch (error) {
    $('#zeta-result-title').textContent = 'Could not complete request';
    $('#zeta-result-note').textContent = error.message;
    $('#zeta-result-note').classList.remove('saved-output-note');
    $('#zeta-result-content').innerHTML = '';
    $('#zeta-result-panel').classList.remove('hidden');
    $('#zeta-download').classList.add('hidden');
  } finally {
    button.disabled = false; button.firstElementChild.textContent = oldText;
  }
}

function drawZetaLine(canvas, points, component) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const argand = component === 'argand';
  const valid = points.filter((point) => Number.isFinite(argand ? point.real : point[component]) && Number.isFinite(argand ? point.imaginary : point.t));
  if (!valid.length) return;
  const xs = valid.map((point) => argand ? point.real : point.t);
  const ys = valid.map((point) => argand ? point.imaginary : point[component]);
  let xMin = Math.min(...xs), xMax = Math.max(...xs), yMin = Math.min(...ys), yMax = Math.max(...ys);
  if (xMin === xMax) { xMin -= 1; xMax += 1; }
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const pad = 44, x = (value) => pad + (value - xMin) / (xMax - xMin) * (width - pad * 2);
  const y = (value) => height - pad - (value - yMin) / (yMax - yMin) * (height - pad * 2);
  ctx.strokeStyle = '#35404a'; ctx.lineWidth = 1; ctx.strokeRect(pad, pad, width - pad * 2, height - pad * 2);
  if (xMin <= 0 && xMax >= 0) { ctx.beginPath(); ctx.moveTo(x(0), pad); ctx.lineTo(x(0), height - pad); ctx.stroke(); }
  if (yMin <= 0 && yMax >= 0) { ctx.beginPath(); ctx.moveTo(pad, y(0)); ctx.lineTo(width - pad, y(0)); ctx.stroke(); }
  ctx.strokeStyle = '#4f9cf9'; ctx.lineWidth = 2; ctx.beginPath();
  valid.forEach((point, index) => { const px = x(argand ? point.real : point.t), py = y(argand ? point.imaginary : point[component]); index ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
  ctx.stroke();
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(xMin.toPrecision(4), pad, height - 15); ctx.fillText(xMax.toPrecision(4), width - pad - 30, height - 15);
  ctx.fillText(yMax.toPrecision(4), 5, pad); ctx.fillText(yMin.toPrecision(4), 5, height - pad);
}

function drawZetaHeatmap(canvas, points, gridWidth, gridHeight) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  const cellWidth = width / gridWidth, cellHeight = height / gridHeight;
  points.forEach((point, index) => {
    const x = (index % gridWidth) * cellWidth;
    const y = height - (Math.floor(index / gridWidth) + 1) * cellHeight;
    if (!Number.isFinite(point.magnitude) || !Number.isFinite(point.argument)) {
      ctx.fillStyle = '#000';
    } else {
      const hue = ((point.argument / (Math.PI * 2)) * 360 + 360) % 360;
      const lightness = Math.max(12, Math.min(75, 35 + Math.log10(Math.max(point.magnitude, 1e-12)) * 12));
      ctx.fillStyle = `hsl(${hue}, 78%, ${lightness}%)`;
    }
    ctx.fillRect(x, y, Math.ceil(cellWidth) + 1, Math.ceil(cellHeight) + 1);
  });
}

$('#zeta-evaluate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/evaluate', {
    sigma: $('#zeta-sigma').value, ordinate: $('#zeta-ordinate').value,
    precision: Number($('#zeta-evaluate-precision').value),
  }, (data) => `ζ(${data.sigma} + ${data.ordinate}i)`, 'value');
});

$('#zeta-count-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/count', {
    height: $('#zeta-count-height').value, precision: Number($('#zeta-count-precision').value),
    threads: Number($('#zeta-count-threads').value),
  }, () => 'Certified zero count', 'count');
});

$('#zeta-zeros-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/zeros', {
    start_index: $('#zeta-zero-start').value, count: Number($('#zeta-zero-count').value),
    precision: Number($('#zeta-zero-precision').value), threads: Number($('#zeta-zero-threads').value),
  }, (data) => `${data.count} certified critical-line zeros`, 'zeros');
});

$('#zeta-line-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/line', {
    lower: $('#zeta-line-lower').value, upper: $('#zeta-line-upper').value,
    samples: Number($('#zeta-line-samples').value), precision: 30,
    threads: Number($('#zeta-line-threads').value),
  }, () => 'Critical-line zeta plot', 'line');
});

$('#zeta-heatmap-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/heatmap', {
    sigma_min: $('#zeta-heat-sigma-min').value, sigma_max: $('#zeta-heat-sigma-max').value,
    t_min: $('#zeta-heat-t-min').value, t_max: $('#zeta-heat-t-max').value,
    width: Number($('#zeta-heat-width').value), height: Number($('#zeta-heat-height').value),
    precision: 20, threads: Number($('#zeta-heat-threads').value),
  }, () => 'Complex-plane zeta heatmap', 'heatmap');
});

loadCapabilities();
loadJobs();
state.poller = setInterval(async () => {
  await loadJobs();
}, 1200);
setInterval(async () => {
  try { renderSetup(await api('/api/setup')); } catch (_) { /* server may be restarting */ }
}, 4000);
