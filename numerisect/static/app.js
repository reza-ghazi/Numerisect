const state = {
  jobs: [], selectedId: null, poller: null, setupPoller: null,
  logOpen: false, primeTool: 'prime-check', zetaTool: 'zeta-evaluate', requestToken: null, batchJobIds: [],
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (char) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
}[char]));

async function api(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (state.requestToken) headers['X-Numerisect-Token'] = state.requestToken;
  const response = await fetch(path, {
    headers,
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
    document.querySelectorAll('.native-threads').forEach((input) => {
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
  const canInstall = missing && setup.state !== 'installing';
  banner.innerHTML = `<strong>Engine setup: ${escapeHtml(setup.state || 'not installed')}</strong> · ${escapeHtml(setup.message || 'Optional native engines are missing.')}${missing ? `<br>Missing: ${escapeHtml(missing)}` : ''}${canInstall ? '<br><button id="install-engines" class="secondary" type="button">Review and install missing engines</button>' : ''}`;
  banner.classList.remove('hidden');
  if (canInstall) {
    $('#install-engines').addEventListener('click', async () => {
      const approved = window.confirm(
        `Numerisect will download and compile these pinned native engines in your user data directory:\n\n${missing}\n\nThis can take substantial time and disk space. Continue?`,
      );
      if (!approved) return;
      $('#install-engines').disabled = true;
      try {
        renderSetup(await api('/api/setup/install', {
          method: 'POST', body: JSON.stringify({ confirm: true }),
        }));
      } catch (error) {
        banner.textContent = `Engine installation could not start: ${error.message}`;
      }
    });
  }
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
  if (typeof announceFinishedJobs === 'function') announceFinishedJobs(state.jobs);
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
    $('#factor-tree').classList.add('hidden');
    return;
  }
  container.innerHTML = job.factors.map((factor, index) => `
    <div class="factor-row">
      <code>${escapeHtml(factor.value)}</code>
      <span class="factor-kind">${escapeHtml(factor.status.replace('_', ' '))} · ${factor.digits}d · ${escapeHtml(factor.engine || job.selected_backend)}${['composite', 'unknown'].includes(factor.status) ? `<button class="cofactor-continue secondary" type="button" data-factor-index="${index}">Continue cofactor</button>` : ''}</span>
    </div>
  `).join('');
  container.querySelectorAll('.cofactor-continue').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      try {
        const child = await api(`/api/jobs/${job.id}/continue-cofactor`, {
          method: 'POST',
          body: JSON.stringify({
            factor_index: Number(button.dataset.factorIndex),
            backend: 'auto', threads: Number($('#threads').value),
            pretest_level: Number($('#pretest-level').value),
            trial_bound: Number($('#trial-bound').value),
          }),
        });
        state.selectedId = child.id;
        await loadJobs();
      } catch (error) {
        $('#job-error').textContent = error.message;
        $('#job-error').classList.remove('hidden');
        button.disabled = false;
      }
    });
  });
  $('#copy-result').classList.remove('hidden');
  const equation = $('#factor-equation');
  equation.innerHTML = `<span>${job.negative ? '−' : ''}${escapeHtml(shortNumber(job.number, 52))}</span><span class="equals">=</span>${job.factors.map((factor, index) => `${index ? '<span class="multiply">×</span>' : ''}<span>${escapeHtml(factor.value)}</span>`).join('')}`;
  equation.classList.remove('hidden');
  const download = $('#download-result');
  download.classList.toggle('hidden', !job.result_available);
  download.href = `/api/jobs/${job.id}/export`;
  const manifest = $('#download-manifest');
  manifest.classList.toggle('hidden', !job.manifest_file);
  manifest.href = job.manifest_file ? `/api/outputs/${encodeURIComponent(job.manifest_file)}` : '#';

  const grouped = new Map();
  job.factors.forEach((factor) => {
    const key = `${factor.value}|${factor.status}|${factor.engine || job.selected_backend}`;
    const current = grouped.get(key) || { ...factor, exponent: 0 };
    current.exponent += 1;
    grouped.set(key, current);
  });
  const elapsed = job.started_at && job.finished_at
    ? Math.max(0, (new Date(job.finished_at) - new Date(job.started_at)) / 1000)
    : null;
  const tree = $('#factor-tree');
  tree.innerHTML = `<div class="factor-tree-root"><span>Input</span><code>${job.negative ? '−' : ''}${escapeHtml(shortNumber(job.number, 64))}</code><small>${job.digits} digits${elapsed === null ? '' : ` · ${elapsed.toFixed(3)} s total`}</small></div><div class="factor-tree-branches">${[...grouped.values()].map((factor) => `<article class="factor-tree-leaf ${escapeHtml(factor.status)}"><span>${escapeHtml(factor.status.replace('_', ' '))}</span><code>${escapeHtml(shortNumber(factor.value, 64))}${factor.exponent > 1 ? `<sup>${factor.exponent}</sup>` : ''}</code><small>${factor.digits} digits · ${escapeHtml(factor.engine || job.selected_backend)}</small></article>`).join('')}</div>`;
  tree.classList.remove('hidden');
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
        trial_bound: Number($('#trial-bound').value),
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

document.querySelectorAll('[data-factor-page]').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-factor-page]').forEach((item) => item.classList.toggle('active', item === button));
    document.querySelectorAll('.factor-page').forEach((page) => page.classList.toggle('hidden', page.id !== button.dataset.factorPage));
  });
});

$('#batch-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const message = $('#batch-factor-message');
  try {
    const text = await file.text();
    let values;
    if (file.name.toLowerCase().endsWith('.json')) {
      const parsed = JSON.parse(text);
      if (!Array.isArray(parsed)) throw new Error('JSON batch input must be an array.');
      values = parsed.map((value) => String(value));
    } else {
      values = text.split(/[\n,;]+/).map((value) => value.trim()).filter(Boolean);
    }
    $('#batch-expressions').value = values.join('\n');
    message.textContent = `Imported ${values.length.toLocaleString()} expressions from ${file.name}.`;
    message.className = 'message';
  } catch (error) {
    message.textContent = `Could not import file: ${error.message}`;
    message.className = 'message error';
  }
});

$('#batch-factor-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const button = event.currentTarget.querySelector('button[type="submit"]');
  const message = $('#batch-factor-message');
  button.disabled = true;
  try {
    const expressions = $('#batch-expressions').value.split(/\n+/).map((value) => value.trim()).filter(Boolean);
    const data = await api('/api/jobs/batch', {
      method: 'POST',
      body: JSON.stringify({
        expressions, backend: $('#batch-backend').value,
        threads: Number($('#threads').value),
        pretest_level: Number($('#pretest-level').value),
        trial_bound: Number($('#trial-bound').value),
      }),
    });
    state.batchJobIds = data.jobs.map((job) => job.id);
    state.selectedId = state.batchJobIds[0] || null;
    message.textContent = `${data.count.toLocaleString()} validated jobs were added to the queue.`;
    message.className = 'message';
    $('#batch-export').classList.remove('hidden');
    $('#batch-download').classList.add('hidden');
    await loadJobs();
  } catch (error) {
    message.textContent = error.message;
    message.className = 'message error';
  } finally {
    button.disabled = false;
  }
});

$('#batch-export').addEventListener('click', async () => {
  const message = $('#batch-factor-message');
  try {
    const data = await api('/api/jobs/batch-export', {
      method: 'POST', body: JSON.stringify({ job_ids: state.batchJobIds }),
    });
    message.textContent = `✓ Consolidated result saved automatically to output/${data.output_file}.`;
    message.className = 'message saved-output-note';
    const download = $('#batch-download');
    download.href = `/api/outputs/${encodeURIComponent(data.output_file)}`;
    download.classList.remove('hidden');
  } catch (error) {
    message.textContent = error.message;
    message.className = 'message error';
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
    forms: ['prime-check-form', 'prime-batch-form', 'prime-classify-form', 'prime-nearby-form', 'prime-range-form', 'prime-nth-form', 'prime-count-form', 'verify-count-form', 'verify-primality-form', 'sieve-interval-form'],
  },
  proofs: {
    label: 'Primality laboratories',
    forms: ['certificate-verify-form', 'primality-lab-form', 'special-form-test-form', 'primality-compare-form', 'deterministic-witness-form', 'pocklington-proof-form', 'pratt-certificate-form', 'primality-certificate-form', 'proth-test-form', 'lucas-sequence-form', 'pseudoprime-taxonomy-form', 'carmichael-analysis-form', 'covering-set-form', 'lucas-lehmer-steps-form', 'ecpp-steps-form'],
  },
  generation: {
    label: 'Prime generation',
    forms: ['prime-generate-form', 'prime-special-form', 'special-prime-family-form', 'ntt-primes-form', 'prime-progression-form', 'random-range-form', 'digit-constrained-form', 'perfect-number-form', 'primorial-form', 'proth-search-form', 'chernick-carmichael-form', 'repunit-search-form', 'sierpinski-riesel-form', 'bitwin-chain-form', 'prime-ladder-form', 'constrained-prime-form'],
  },
  patterns: {
    label: 'Patterns & distribution',
    forms: ['prime-gaps-form', 'prime-tuples-form', 'cunningham-chain-form', 'gap-statistics-form', 'prime-distribution-form', 'goldbach-form'],
  },
  analytic: {
    label: 'Analytic prime distribution',
    forms: ['prime-approximation-form', 'summatory-functions-form', 'approximation-error-form', 'pnt-convergence-form', 'nth-prime-bounds-form', 'prime-race-form', 'progression-deviation-form', 'singular-series-form', 'tuple-prediction-form', 'bateman-horn-form', 'maximal-gap-form', 'short-interval-form', 'density-surface-form', 'counting-comparison-form', 'counting-phi-form', 'counting-inverse-form'],
  },
  structures: {
    label: 'Prime structures',
    forms: ['prime-reciprocal-form', 'absolute-prime-form', 'paterson-prime-form', 'reptend-prime-form', 'gaussian-check-form', 'gaussian-range-form', 'modular-wheel-form'],
  },
  arithmetic: {
    label: 'Arithmetic & factors',
    forms: ['factor-strategy-form', 'integer-profile-form', 'extended-arithmetic-form', 'divisor-classification-form', 'aliquot-sequence-form', 'perfect-power-form', 'prime-modular-form', 'coprime-profile-form', 'factor-count-distribution-form', 'witness-form', 'prime-constant-form', 'divisor-lattice-form', 'smoothness-profile-form', 'record-numbers-form', 'weird-number-form', 'sociable-cycle-form', 'cornacchia-form', 'integer-structure-form', 'lenstra-divisors-form', 'factorint-strategy-form'],
  },
  modular: {
    label: 'Modular & polynomial algebra',
    forms: ['character-symbol-form', 'tonelli-shanks-form', 'crt-form', 'modular-roots-form', 'hensel-roots-form', 'discrete-log-form', 'unit-group-form', 'order-distribution-form', 'power-residues-form', 'p-adic-valuation-form', 'polynomial-factor-form', 'cyclotomic-form', 'reciprocity-trace-form', 'congruence-solver-form', 'dlog-lab-form', 'finite-field-form'],
  },
  algebraic: {
    label: 'Algebraic primes',
    forms: ['eisenstein-prime-form', 'quadratic-decomposition-form', 'quadratic-ring-form', 'number-field-form', 'chebotarev-form', 'quadratic-form-reduce-form', 'quadratic-form-compose-form', 'quadratic-form-primeform-form', 'quadratic-form-class-group-form', 'quadratic-form-enumerate-form', 'quadratic-form-represent-form', 'continued-fraction-form', 'pell-equation-form'],
  },
  explorations: {
    label: 'Advanced explorations',
    forms: ['prime-pyramid-form', 'special-number-form', 'contiguous-digits-form', 'prime-problem-form', 'prime-polynomial-form', 'palindrome-derived-form'],
  },
  visual: {
    label: 'Visualization & education',
    forms: ['visual-spiral-form', 'visual-eisenstein-form', 'visual-wheel-form', 'visual-heatmap-form', 'visual-gap-timeline-form', 'visual-prime-race-form', 'visual-sieve-form', 'visual-complexity-form'],
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

const zetaSections = {
  functions: { label: 'Rigorous functions', forms: ['zeta-evaluate-form', 'zeta-hardy-form', 'zeta-xi-eta-form', 'zeta-functional-form', 'zeta-stieltjes-form'] },
  zeros: { label: 'Zeros & Gram geometry', forms: ['zeta-count-form', 'zeta-zeros-form', 'zeta-gram-form', 'zeta-gram-blocks-form', 'zeta-backlund-form'] },
  explicit: { label: 'Explicit formulas & zero statistics', forms: ['zeta-explicit-pi-form', 'zeta-psi-form', 'zeta-riemann-siegel-form', 'zeta-euler-product-form', 'zeta-spacing-form', 'zeta-pair-correlation-form'] },
  lfunctions: { label: 'Dirichlet & Dedekind L-functions', forms: ['zeta-characters-form', 'zeta-lfunction-form', 'zeta-lzeros-form', 'zeta-dedekind-form'] },
  visualization: { label: 'Exploratory plots', forms: ['zeta-line-form', 'zeta-heatmap-form'] },
};
const zetaTools = new Map();

function initializeZetaTools() {
  const navigation = $('#zeta-tool-navigation');
  const select = $('#zeta-tool-select');
  let index = 0;
  Object.entries(zetaSections).forEach(([section, details]) => {
    const group = document.createElement('section');
    group.className = 'tool-nav-group';
    const heading = document.createElement('h3'); heading.textContent = details.label; group.appendChild(heading);
    const options = document.createElement('optgroup'); options.label = details.label;
    details.forms.forEach((formId) => {
      const form = document.getElementById(formId);
      if (!form) throw new Error(`Zeta tool form is missing: ${formId}`);
      const slug = formId.replace(/-form$/, '');
      const title = form.querySelector('h2').textContent.trim();
      const description = form.querySelector(':scope > p:not(.eyebrow)')?.textContent.trim() || '';
      zetaTools.set(slug, { slug, formId, title, description, section, index });
      const button = document.createElement('button'); button.type = 'button'; button.className = 'prime-tool-link'; button.textContent = title;
      button.addEventListener('click', () => activateZetaTool(slug, true));
      button.dataset.zetaTool = slug; group.appendChild(button);
      const option = document.createElement('option'); option.value = slug; option.textContent = title; options.appendChild(option);
      index += 1;
    });
    navigation.appendChild(group); select.appendChild(options);
  });
  select.addEventListener('change', (event) => activateZetaTool(event.target.value, true));
}

function activateZetaTool(slug, updateHash = true) {
  const selected = zetaTools.get(slug) || zetaTools.values().next().value;
  state.zetaTool = selected.slug;
  document.querySelectorAll('[data-zeta-tool]').forEach((button) => {
    const active = button.dataset.zetaTool === selected.slug;
    button.classList.toggle('active', active);
    active ? button.setAttribute('aria-current', 'page') : button.removeAttribute('aria-current');
  });
  document.querySelectorAll('#zeta-page-grid > form').forEach((form) => form.classList.toggle('prime-page-hidden', form.id !== selected.formId));
  $('#zeta-tool-select').value = selected.slug;
  $('#zeta-tool-section').textContent = zetaSections[selected.section].label;
  $('#zeta-page-title').textContent = selected.title;
  $('#zeta-page-description').textContent = selected.description;
  $('#zeta-page-count').textContent = `Operation ${selected.index + 1} of ${zetaTools.size}`;
  const panel = $('#zeta-result-panel');
  panel.classList.toggle('prime-page-hidden', Boolean(panel.dataset.ownerForm && panel.dataset.ownerForm !== selected.formId));
  document.title = `${selected.title} · Riemann Zeta · Numerisect`;
  if (updateHash) history.pushState(null, '', `#zeta/${selected.slug}`);
}

function activateView(button, updateHash = true) {
  document.querySelectorAll('.mode-tab').forEach((tab) => tab.classList.remove('active'));
  document.querySelectorAll('.tool-view').forEach((view) => view.classList.add('hidden'));
  button.classList.add('active');
  $(`#${button.dataset.view}`).classList.remove('hidden');
  document.body.dataset.activeView = button.dataset.view;
  if (button.dataset.view === 'prime-view') activatePrimeTool(state.primeTool, false);
  if (button.dataset.view === 'factor-view') document.title = 'Integer Factorization · Numerisect';
  if (button.dataset.view === 'zeta-view') activateZetaTool(state.zetaTool, false);
  if (button.dataset.view === 'diagnostic-view') document.title = 'System Diagnostics · Numerisect';
  if (updateHash) {
    const hashes = {
      'factor-view': '#factor',
      'prime-view': `#primes/${state.primeTool}`,
      'zeta-view': `#zeta/${state.zetaTool}`,
      'diagnostic-view': '#diagnostics',
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
    if (zetaTools.has(primeTool)) state.zetaTool = primeTool;
    activateView(document.querySelector('[data-view="zeta-view"]'), false);
  } else if (section === 'diagnostics') {
    activateView(document.querySelector('[data-view="diagnostic-view"]'), false);
  } else if (section === 'workspaces' || section === 'history') {
    activateView(document.querySelector('[data-view="workspace-view"]'), false);
    loadWorkspaces();
  } else {
    activateView(document.querySelector('[data-view="factor-view"]'), false);
  }
}

initializePrimeTools();
initializeZetaTools();
applyHashRoute();
window.addEventListener('hashchange', applyHashRoute);
window.addEventListener('popstate', applyHashRoute);

$('#run-diagnostics').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  const result = $('#diagnostic-result');
  button.disabled = true;
  result.classList.remove('hidden');
  result.innerHTML = '<div class="empty">Inspecting local engines and prerequisites…</div>';
  try {
    const data = await api('/api/diagnostics', { method: 'POST', body: '{}' });
    const metrics = Object.entries(data.metrics).map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join('');
    const engines = data.rows.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`).join('');
    const prerequisites = data.prerequisites.map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`).join('');
    result.innerHTML = `<p class="saved-output-note">${escapeHtml(data.note)} ✓ Report saved automatically to output/${escapeHtml(data.output_file)}.</p><div class="reciprocal-summary">${metrics}</div><div class="result-table-wrap"><table class="result-table"><thead><tr>${data.columns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${engines}</tbody></table></div><h3>Build prerequisites</h3><div class="result-table-wrap"><table class="result-table"><thead><tr><th>Command</th><th>Status</th></tr></thead><tbody>${prerequisites}</tbody></table></div><a class="secondary button-link" href="/api/outputs/${encodeURIComponent(data.output_file)}">Review diagnostic bundle</a>`;
  } catch (error) {
    result.innerHTML = `<div class="message error">${escapeHtml(error.message)}</div>`;
  } finally {
    button.disabled = false;
  }
});

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
  // Values too long for a JSON response are abbreviated on screen; this file has them whole.
  if (data.export_file) note += `${note ? ' ' : ''}✓ Every value at full precision saved to output/${data.export_file}.`;
  const noteElement = $('#prime-result-note');
  noteElement.textContent = note;
  noteElement.classList.toggle('saved-output-note', Boolean(data.output_file));
  if (type === 'table') {
    const metrics = Object.entries(data.metrics || {}).map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join('');
    const rows = data.rows.slice(0, 2000).map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`).join('');
    content.innerHTML = `${metrics ? `<div class="reciprocal-summary">${metrics}</div>` : ''}<div class="result-table-wrap"><table class="result-table"><thead><tr>${data.columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table>${data.rows.length ? '' : '<p class="empty">No values found. See the result note above.</p>'}</div>`;
    if (data.rows.length > 2000) $('#prime-result-note').textContent += ' Showing the first 2,000 rows; the report contains all returned rows.';
  } else if (type === 'distribution') {
    content.innerHTML = distributionMarkup(data);
    drawDistributionChart(data);
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
    content.innerHTML = `<div class="prime-verdict"><strong>${escapeHtml(data.divisor_class)} ${data.is_semiprime ? 'semiprime' : (data.is_prime ? 'prime' : 'integer')}</strong><code>${escapeHtml(data.number)} = ${escapeHtml(data.factorization)}</code></div><div class="reciprocal-summary"><article><span>ω(n) distinct factors</span><strong>${escapeHtml(data.omega)}</strong></article><article><span>Ω(n) with multiplicity</span><strong>${escapeHtml(data.big_omega)}</strong></article><article><span>τ(n) divisors</span><strong>${escapeHtml(data.divisor_count)}</strong></article><article><span>σ(n)</span><strong>${escapeHtml(data.divisor_sum)}</strong></article><article><span>φ(n)</span><strong>${escapeHtml(data.totient)}</strong></article><article><span>λ(n)</span><strong>${escapeHtml(data.carmichael)}</strong></article><article><span>μ(n)</span><strong>${escapeHtml(data.mobius)}</strong></article><article><span>rad(n)</span><strong>${escapeHtml(data.radical)}</strong></article><article><span>Prime power</span><strong>${data.is_prime_power ? `${escapeHtml(data.prime_power_base)}^${escapeHtml(data.prime_power_exponent)}` : 'no'}</strong></article><article><span>Powerful</span><strong>${data.is_powerful ? 'yes' : 'no'}</strong></article><article><span>Totient value</span><strong>${data.is_totient ? `φ(${escapeHtml(data.totient_witness)})` : 'no'}</strong></article><article><span>Fundamental discriminant</span><strong>${data.is_fundamental_discriminant ? 'yes' : 'no'}</strong></article></div><div class="result-group"><span>Prime-power factorization</span><div>${factorCards}</div></div><div class="result-group"><span>Divisor preview</span><div>${divisors || '<div class="empty">No divisors requested.</div>'}</div></div>`;
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
    limit: Number($('#prime-range-limit').value),
    threads: Number($('#prime-range-threads').value),
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
    index: $('#prime-index').value,
    threads: Number($('#prime-index-threads').value),
  }, (data) => `${data.label} · ${data.digits} digits`, 'metric');
});

$('#prime-count-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/count', {
    expression: $('#prime-count-through').value,
    threads: Number($('#prime-count-threads').value),
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

// --- Visualization & education workbench -----------------------------------
// Every mathematical quantity below arrives from a library routine (primesieve,
// or PARI forprime/isprime/gcd/eulerphi) through /api/visual/*. This code maps
// engine-supplied integers and flags to canvas coordinates, colours, and
// playback frames and does nothing else: it never decides primality, evaluates
// a membership test, counts, totals, or derives an axis scale. Spiral and grid
// coordinates are pure layout; every count and maximum is read from the
// response, never recomputed here.

const visualState = { race: null, sieve: null };
const VISUAL_KIND_COLOURS = { 1: '#4f9cf9', 2: '#d6a34a', 3: '#e0685f' };
const VISUAL_LINE_COLOURS = ['#4f9cf9', '#d6a34a', '#7fd0a2', '#e0685f', '#b98cf0', '#63c7d6', '#e8a0c4', '#9aa7b2'];

function visualTable(columns, rows) {
  const head = columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join('');
  const body = rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('');
  return `<div class="result-table-wrap"><table class="result-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function visualMetrics(entries) {
  return `<div class="reciprocal-summary">${entries.map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join('')}</div>`;
}

function showVisualResult(title, data, form, html) {
  placePrimeResult(form);
  $('#prime-result-title').textContent = title;
  let note = data.note || '';
  if (data.truncated || data.event_truncated) note += `${note ? ' ' : ''}Display/export stopped at the requested limit.`;
  if (data.output_file) note += `${note ? ' ' : ''}✓ Result saved automatically to output/${data.output_file}.`;
  const noteElement = $('#prime-result-note');
  noteElement.textContent = note;
  noteElement.classList.toggle('saved-output-note', Boolean(data.output_file));
  $('#prime-result-content').innerHTML = html;
  const download = $('#prime-download');
  download.href = `/api/outputs/${encodeURIComponent(data.output_file)}`;
  download.classList.toggle('hidden', !data.output_file);
  $('#prime-result-panel').classList.remove('hidden');
}

async function submitVisualForm(form, path, payload, title, render) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const oldText = button.firstElementChild.textContent;
  button.firstElementChild.textContent = 'Working…';
  try {
    const data = await api(path, { method: 'POST', body: JSON.stringify(payload) });
    showVisualResult(title(data), data, form, render(data, form));
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

function visualBackground(canvas) {
  const prepared = prepareCanvas(canvas);
  prepared.context.fillStyle = '#0c0f11';
  prepared.context.fillRect(0, 0, prepared.width, prepared.height);
  return prepared;
}

function visualEmpty(ctx, width, height, message) {
  ctx.fillStyle = '#8d9aa5';
  ctx.font = '13px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(message, width / 2, height / 2);
  ctx.textAlign = 'left';
}

// Square-spiral coordinate of the 0-based offset i: purely geometric, verified
// to visit every lattice cell exactly once in unit steps.
function ulamPoint(i) {
  const k = Math.ceil((Math.sqrt(i + 1) - 1) / 2);
  let t = 2 * k + 1;
  let m = t * t;
  t -= 1;
  if (i >= m - t) return [k - (m - 1 - i), -k];
  m -= t;
  if (i >= m - t) return [-k, -k + (m - 1 - i)];
  m -= t;
  if (i >= m - t) return [-k + (m - 1 - i), k];
  return [k, k - (m - 1 - i - t)];
}

function drawVisualSpiral(canvas, data) {
  const { context: ctx, width, height } = visualBackground(canvas);
  const base = Number(data.start);
  if (!Number.isFinite(base) || !Number.isSafeInteger(base)) {
    visualEmpty(ctx, width, height, 'The range starts beyond the exact drawing range; see the saved report.');
    return;
  }
  const highlighted = new Set(data.highlighted);
  const offsets = data.primes.map((prime) => Number(prime) - base).filter((offset) => Number.isFinite(offset));
  if (!offsets.length) {
    visualEmpty(ctx, width, height, 'PARI/GP found no primes in this range.');
    return;
  }
  const last = data.count - 1;
  const points = offsets.map((offset) => {
    if (data.layout === 'ulam') return ulamPoint(offset);
    if (data.layout === 'sacks') {
      const radius = Math.sqrt(offset);
      const angle = 2 * Math.PI * radius;
      return [radius * Math.cos(angle), radius * Math.sin(angle)];
    }
    return [offset * Math.cos(offset), offset * Math.sin(offset)];
  });
  let extent = 1;
  if (data.layout === 'ulam') extent = Math.ceil((Math.sqrt(last + 1) - 1) / 2) + 1;
  else if (data.layout === 'sacks') extent = Math.sqrt(last) + 1;
  else extent = last + 1;
  const pad = 18;
  const scale = (Math.min(width, height) / 2 - pad) / extent;
  const dot = Math.max(0.6, Math.min(4, scale * 0.45));
  points.forEach((point, index) => {
    ctx.fillStyle = highlighted.has(data.primes[index]) ? '#d6a34a' : '#4f9cf9';
    ctx.beginPath();
    ctx.arc(width / 2 + point[0] * scale, height / 2 - point[1] * scale, dot, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.fillStyle = '#8d9aa5';
  ctx.font = '12px sans-serif';
  ctx.fillText(`${data.layout} spiral · ${data.prime_count.toLocaleString()} primes · ${data.highlight_count.toLocaleString()} highlighted`, 12, 20);
}

function drawVisualEisenstein(canvas, points) {
  const { context: ctx, width, height } = visualBackground(canvas);
  if (!points.length) {
    visualEmpty(ctx, width, height, 'PARI/GP found no Eisenstein primes within this norm bound.');
    return;
  }
  // omega = exp(2*pi*i/3), so a + b*omega sits at (a - b/2, b*sqrt(3)/2).
  const placed = points.map((point) => [point.a - point.b / 2, point.b * Math.sqrt(3) / 2]);
  const extent = Math.max(...placed.map(([x, y]) => Math.max(Math.abs(x), Math.abs(y))), 1);
  const pad = 24;
  const scale = (Math.min(width, height) / 2 - pad) / extent;
  const dot = Math.max(1.2, Math.min(4.5, scale * 0.35));
  ctx.strokeStyle = '#35404a';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, height / 2); ctx.lineTo(width - pad, height / 2);
  ctx.moveTo(width / 2, pad); ctx.lineTo(width / 2, height - pad);
  ctx.stroke();
  placed.forEach(([x, y], index) => {
    ctx.fillStyle = VISUAL_KIND_COLOURS[points[index].kind] || '#46515b';
    ctx.beginPath();
    ctx.arc(width / 2 + x * scale, height / 2 - y * scale, dot, 0, Math.PI * 2);
    ctx.fill();
  });
}

function drawVisualHeatmap(canvas, data) {
  const { context: ctx, width, height } = visualBackground(canvas);
  const pad = 46;
  const columns = data.bins.length;
  const rows = data.modulus;
  const cellWidth = (width - pad * 2) / columns;
  const cellHeight = (height - pad * 2) / rows;
  const maximum = Math.max(Number(data.max_cell), 1);
  data.bins.forEach((bin, column) => {
    bin.counts.forEach((count, residue) => {
      const intensity = Number(count) / maximum;
      ctx.fillStyle = data.residues[residue].coprime
        ? `hsl(${210 - 170 * intensity}, ${45 + 40 * intensity}%, ${12 + 46 * intensity}%)`
        : '#191d21';
      ctx.fillRect(pad + column * cellWidth, pad + residue * cellHeight, Math.max(1, cellWidth), Math.max(1, cellHeight));
    });
  });
  ctx.fillStyle = '#8d9aa5';
  ctx.font = '12px sans-serif';
  ctx.fillText(`${data.start} → ${data.end}`, pad, height - 18);
  ctx.fillText(`residue ${data.residues[0].residue} … ${data.residues[data.residues.length - 1].residue} (mod ${data.modulus})`, pad, 26);
  ctx.fillText(`maximum cell ${Number(data.max_cell).toLocaleString()} primes`, Math.max(pad, width - 250), 26);
}

function drawVisualGapTimeline(canvas, data) {
  const { context: ctx, width, height } = visualBackground(canvas);
  if (!data.gaps.length) {
    visualEmpty(ctx, width, height, 'Fewer than two primes occur in this range.');
    return;
  }
  const records = new Set(data.records.map((record) => record.from));
  const pad = 46;
  const maximum = Number(data.max_gap) || 1;
  const barWidth = (width - pad * 2) / data.gaps.length;
  data.gaps.forEach((item, index) => {
    const barHeight = item.gap / maximum * (height - pad * 2);
    ctx.fillStyle = records.has(item.prime) ? '#d6a34a' : '#4f9cf9';
    ctx.fillRect(pad + index * barWidth, height - pad - barHeight, Math.max(1, barWidth - 0.5), barHeight);
  });
  ctx.fillStyle = '#8d9aa5';
  ctx.font = '12px sans-serif';
  ctx.fillText(String(data.first_prime), pad, height - 18);
  ctx.fillText(String(data.last_prime), Math.max(pad, width - 140), height - 18);
  ctx.fillText(`largest gap ${data.max_gap} after ${data.max_gap_at}`, pad, 26);
}

function drawVisualRace(canvas, data, frames) {
  const { context: ctx, width, height } = visualBackground(canvas);
  const shown = Math.max(1, Math.min(frames, data.checkpoints.length));
  const pad = 50;
  const maximum = Number(data.max_count) || 1;
  ctx.strokeStyle = '#35404a';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, height - pad); ctx.lineTo(width - pad, height - pad);
  ctx.moveTo(pad, pad); ctx.lineTo(pad, height - pad);
  ctx.stroke();
  data.classes.forEach((residue, series) => {
    ctx.strokeStyle = VISUAL_LINE_COLOURS[series % VISUAL_LINE_COLOURS.length];
    ctx.lineWidth = 1.8;
    ctx.beginPath();
    for (let frame = 0; frame < shown; frame += 1) {
      const x = pad + (shown === 1 ? 0 : frame / (data.checkpoints.length - 1 || 1)) * (width - pad * 2);
      const y = height - pad - Number(data.checkpoints[frame].counts[series]) / maximum * (height - pad * 2);
      frame ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    }
    ctx.stroke();
  });
  ctx.font = '12px sans-serif';
  data.classes.forEach((residue, series) => {
    ctx.fillStyle = VISUAL_LINE_COLOURS[series % VISUAL_LINE_COLOURS.length];
    ctx.fillText(`${residue} mod ${data.modulus}: ${Number(data.checkpoints[shown - 1].counts[series]).toLocaleString()}`, width - 210, 26 + series * 16);
  });
  ctx.fillStyle = '#8d9aa5';
  ctx.fillText(`up to ${data.checkpoints[shown - 1].x} · leader ${data.checkpoints[shown - 1].leader < 0 ? 'none yet' : data.checkpoints[shown - 1].leader}`, pad, 26);
}

function visualSieveStates(data, upto) {
  // Playback of the trace PARI/GP recorded and verified: this only reads the
  // step codes back and sets a colour flag per cell. It performs no sieving,
  // no divisibility test, and no primality decision of its own.
  const states = new Array(data.n + 1).fill(0);
  let segment = null;
  for (let index = 0; index < upto && index < data.steps.length; index += 1) {
    const [kind, value, a, , flag] = data.steps[index];
    if (kind === 1 || kind === 3) states[value] = 2;
    else if (kind === 2 || kind === 4 || kind === 8) states[value] = 1;
    else if (kind === 5 || kind === 6 || kind === 7) states[value] = flag ? 3 : 0;
    else if (kind === 9) segment = [value, a];
  }
  return { states, segment, current: upto > 0 ? data.steps[Math.min(upto, data.steps.length) - 1] : null };
}

function drawVisualSieve(canvas, data, upto) {
  const { context: ctx, width, height } = visualBackground(canvas);
  const { states, segment, current } = visualSieveStates(data, upto);
  const pad = 34;
  const columns = Math.max(1, Math.ceil(Math.sqrt(data.n * (width - pad * 2) / (height - pad * 2))));
  const rows = Math.ceil(data.n / columns);
  const cell = Math.min((width - pad * 2) / columns, (height - pad * 2) / rows);
  for (let value = 1; value <= data.n; value += 1) {
    const column = (value - 1) % columns;
    const row = Math.floor((value - 1) / columns);
    const x = pad + column * cell;
    const y = pad + row * cell;
    const state = states[value];
    ctx.fillStyle = state === 2 ? '#4f9cf9' : (state === 3 ? '#7fd0a2' : (state === 1 ? '#46515b' : '#171b1f'));
    if (segment && value >= segment[0] && value <= segment[1] && state === 0) ctx.fillStyle = '#22303a';
    ctx.fillRect(x + 0.5, y + 0.5, Math.max(1, cell - 1.5), Math.max(1, cell - 1.5));
    if (current && current[1] === value) {
      ctx.strokeStyle = '#d6a34a';
      ctx.lineWidth = 1.6;
      ctx.strokeRect(x + 0.5, y + 0.5, Math.max(1, cell - 1.5), Math.max(1, cell - 1.5));
    }
  }
  ctx.fillStyle = '#8d9aa5';
  ctx.font = '12px sans-serif';
  const label = current ? `${data.step_kinds[current[0]]} · value ${current[1]}` : 'ready';
  ctx.fillText(`step ${Math.min(upto, data.steps.length).toLocaleString()} of ${data.steps.length.toLocaleString()} · ${label}`, pad, 22);
}

function visualPlay(key, total, speed, draw) {
  if (visualState[key]) window.clearInterval(visualState[key]);
  let frame = 0;
  draw(frame);
  visualState[key] = window.setInterval(() => {
    frame += 1;
    draw(frame);
    if (frame >= total) {
      window.clearInterval(visualState[key]);
      visualState[key] = null;
    }
  }, Math.max(8, 1000 / Math.max(1, speed)));
}

$('#visual-spiral-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/spiral', {
    start: $('#visual-spiral-start').value,
    count: Number($('#visual-spiral-count').value),
    layout: $('#visual-spiral-layout').value,
    highlight: $('#visual-spiral-highlight').value,
    a: Number($('#visual-spiral-a').value),
    b: Number($('#visual-spiral-b').value),
    c: Number($('#visual-spiral-c').value),
    modulus: Number($('#visual-spiral-modulus').value),
    residue: Number($('#visual-spiral-residue').value),
    timeout_seconds: Number($('#visual-spiral-timeout').value),
  }, (data) => `${Number(data.prime_count).toLocaleString()} primes on a ${data.layout} spiral`, (data) => {
    drawVisualSpiral($('#visual-spiral-canvas'), data);
    return visualMetrics([
      ['Range', `${data.start} → ${data.end}`],
      ['Primes', Number(data.prime_count).toLocaleString()],
      ['Highlighted', Number(data.highlight_count).toLocaleString()],
      ['Highlight rule', data.highlight_description],
      ['Engine', data.engine],
    ]);
  });
});

$('#visual-eisenstein-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/eisenstein-lattice', {
    norm_bound: Number($('#visual-eisenstein-bound').value),
    limit: Number($('#visual-eisenstein-limit').value),
    timeout_seconds: Number($('#visual-eisenstein-timeout').value),
  }, (data) => `${Number(data.count).toLocaleString()} Eisenstein primes of norm ≤ ${data.norm_bound}`, (data) => {
    drawVisualEisenstein($('#visual-eisenstein-canvas'), data.points);
    return visualMetrics([
      ['Norm bound', String(data.norm_bound)],
      ['Lattice points', Number(data.count).toLocaleString()],
    ]) + visualTable(['Kind', 'Meaning', 'Points'], Object.keys(data.kinds).map((kind) => [kind, data.kinds[kind], String(data.kind_counts[kind])]));
  });
});

$('#visual-wheel-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/modular-wheel', {
    modulus: Number($('#visual-wheel-modulus').value),
    start: Number($('#visual-wheel-start').value),
    count: Number($('#visual-wheel-count').value),
    timeout_seconds: Number($('#visual-wheel-timeout').value),
  }, (data) => `Modular wheel · base ${data.modulus}`, (data) => {
    drawModularWheel($('#visual-wheel-canvas'), data.cells, data.modulus);
    return visualMetrics([
      ['Wheel base', String(data.modulus)],
      ['Range', `${data.start} → ${data.end}`],
      ['Rings', Number(data.ring_count).toLocaleString()],
      ['Primes', Number(data.prime_count).toLocaleString()],
      ['φ(m)', String(data.totient)],
      ['Spokes carrying primes', String(data.spokes_with_primes)],
    ]) + visualTable(['Spoke', 'Coprime to base', 'Primes'], data.spokes.filter((spoke) => spoke.prime_count).slice(0, 500).map((spoke) => [String(spoke.residue), spoke.coprime ? 'yes' : 'no', String(spoke.prime_count)]));
  });
});

$('#visual-heatmap-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/residue-heatmap', {
    start: $('#visual-heatmap-start').value,
    end: $('#visual-heatmap-end').value,
    modulus: Number($('#visual-heatmap-modulus').value),
    bins: Number($('#visual-heatmap-bins').value),
    timeout_seconds: Number($('#visual-heatmap-timeout').value),
  }, (data) => `Residue heatmap modulo ${data.modulus}`, (data) => {
    drawVisualHeatmap($('#visual-heatmap-canvas'), data);
    return visualMetrics([
      ['Range', `${data.start} → ${data.end}`],
      ['Primes counted', Number(data.prime_count).toLocaleString()],
      ['Bins', String(data.bin_count)],
      ['Busiest cell', Number(data.max_cell).toLocaleString()],
    ]) + visualTable(['Residue', 'Coprime to modulus', 'Primes in range'], data.residues.map((item) => [String(item.residue), item.coprime ? 'yes' : 'no', Number(item.total).toLocaleString()]));
  });
});

$('#visual-gap-timeline-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/gap-timeline', {
    start: $('#visual-gap-start').value,
    end: $('#visual-gap-end').value,
    limit: Number($('#visual-gap-limit').value),
    timeout_seconds: Number($('#visual-gap-timeout').value),
  }, (data) => `${Number(data.gap_count).toLocaleString()} prime gaps · ${data.records.length} records`, (data) => {
    drawVisualGapTimeline($('#visual-gap-canvas'), data);
    return visualMetrics([
      ['First prime', String(data.first_prime)],
      ['Last prime', String(data.last_prime)],
      ['Gaps measured', Number(data.gap_count).toLocaleString()],
      ['Largest gap', `${data.max_gap} after ${data.max_gap_at}`],
    ]) + visualTable(['From', 'To', 'Gap', 'Merit g/ln p'], data.records.map((record) => [record.from, record.to, String(record.gap), record.merit]));
  });
});

$('#visual-prime-race-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/prime-race', {
    start: $('#visual-race-start').value,
    end: $('#visual-race-end').value,
    modulus: Number($('#visual-race-modulus').value),
    checkpoints: Number($('#visual-race-checkpoints').value),
    timeout_seconds: Number($('#visual-race-timeout').value),
  }, (data) => `Prime race modulo ${data.modulus} · leader ${data.leader}`, (data) => {
    $('#visual-race-play').dataset.ready = 'yes';
    visualState.raceData = data;
    visualPlay('race', data.checkpoints.length, Number($('#visual-race-speed').value), (frame) => drawVisualRace($('#visual-race-canvas'), data, frame));
    return visualMetrics([
      ['Range', `${data.start} → ${data.end}`],
      ['Primes counted', Number(data.prime_count).toLocaleString()],
      ['Lead changes', Number(data.event_count).toLocaleString()],
      ['Final leader', data.leader < 0 ? 'none' : `${data.leader} mod ${data.modulus}`],
    ]) + visualTable(['Residue class', 'Primes'], data.final.map((item) => [`${item.residue} mod ${data.modulus}`, Number(item.count).toLocaleString()]))
      + visualTable(['Lead change at prime', 'New leader'], data.events.slice(0, 500).map((event) => [event.prime, String(event.leader)]));
  });
});

$('#visual-race-play').addEventListener('click', () => {
  const data = visualState.raceData;
  if (!data) return;
  visualPlay('race', data.checkpoints.length, Number($('#visual-race-speed').value), (frame) => drawVisualRace($('#visual-race-canvas'), data, frame));
});

$('#visual-sieve-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const segment = $('#visual-sieve-segment').value;
  submitVisualForm(event.currentTarget, '/api/visual/sieve-trace', {
    kind: $('#visual-sieve-kind').value,
    n: Number($('#visual-sieve-n').value),
    segment_size: segment === '' ? null : Number(segment),
    timeout_seconds: Number($('#visual-sieve-timeout').value),
  }, (data) => `${data.kind} sieve · ${Number(data.step_count).toLocaleString()} steps to ${data.n}`, (data) => {
    visualState.sieveData = data;
    visualPlay('sieve', data.steps.length, Number($('#visual-sieve-speed').value), (frame) => drawVisualSieve($('#visual-sieve-canvas'), data, frame));
    return visualMetrics([
      ['Sieve', data.kind],
      ['Limit n', String(data.n)],
      ['Segment size', data.segment_size === null ? 'not applicable' : String(data.segment_size)],
      ['Recorded steps', Number(data.step_count).toLocaleString()],
      ['Survivors', Number(data.prime_count).toLocaleString()],
      ['Verified against PARI', data.verified ? 'yes' : 'no'],
    ]) + visualTable(['Step code', 'Meaning'], Object.keys(data.step_kinds).map((code) => [code, data.step_kinds[code]]));
  });
});

$('#visual-sieve-play').addEventListener('click', () => {
  const data = visualState.sieveData;
  if (!data) return;
  visualPlay('sieve', data.steps.length, Number($('#visual-sieve-speed').value), (frame) => drawVisualSieve($('#visual-sieve-canvas'), data, frame));
});

$('#visual-complexity-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitVisualForm(event.currentTarget, '/api/visual/complexity', {
    job_limit: Number($('#visual-complexity-limit').value),
  }, (data) => `${data.reference.length} reference algorithms · ${data.groups.length} measured groups`, (data) => {
    drawCountBars($('#visual-complexity-canvas'), data.groups.map((group) => ({ label: `${group.engine} ${group.digits}`, count: group.median_seconds })));
    return visualMetrics([
      ['Reference algorithms', String(data.reference.length)],
      ['Completed jobs measured', Number(data.measured_jobs).toLocaleString()],
      ['Measured groups', String(data.groups.length)],
    ]) + visualTable(['Algorithm', 'Category', 'Time', 'Memory', 'Source'], data.reference.map((row) => [row.algorithm, row.category, row.time, row.memory, row.source]))
      + visualTable(['Engine', 'Digits', 'Runs', 'Min s', 'Median s', 'Mean s', 'Max s'], data.groups.map((group) => [group.engine, group.digits, String(group.runs), String(group.min_seconds), String(group.median_seconds), String(group.mean_seconds), String(group.max_seconds)]));
  });
});

$('#prime-constant-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/indicator-constant', {
    decimal_digits: Number($('#prime-constant-digits').value),
  }, () => 'Prime-indicator constant', 'prime-constant');
});

const integerTokens = (value) => value.trim().split(/[\s,;]+/).filter(Boolean);

$('#certificate-verify-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/verify-certificate', {
    certificate_data: $('#certificate-data').value,
  }, (data) => data.valid ? 'Valid ECPP certificate' : 'Invalid certificate', 'table');
});

$('#prime-approximation-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/prime-approximations', {
    x: $('#approximation-x').value,
    threads: Number($('#approximation-threads').value),
  }, () => 'Prime-counting approximations', 'table');
});

$('#summatory-functions-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/summatory-functions', {
    x: $('#summatory-x').value,
  }, () => 'Summatory arithmetic functions', 'table');
});

const distributionPalette = ['#4f9cf9', '#d6a34a', '#7fd18b', '#e0705f', '#a98cf0', '#5ec8d8', '#f08fc0', '#9fb4c7'];

function distributionTable(columns, rows) {
  const body = rows.slice(0, 2000).map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(value)}</td>`).join('')}</tr>`).join('');
  return `<div class="result-table-wrap"><table class="result-table"><thead><tr>${columns.map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table>${rows.length ? '' : '<p class="empty">No rows were returned. See the result note above.</p>'}</div>`;
}

function distributionMarkup(data) {
  const metrics = Object.entries(data.metrics || {}).map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join('');
  const sections = (data.sections || []).filter((section) => section.rows.length)
    .map((section) => `<h3 class="distribution-heading">${escapeHtml(section.title)}</h3>${distributionTable(section.columns, section.rows)}`).join('');
  let chart = '';
  if (data.chart === 'density-surface') {
    chart = '<canvas id="distribution-heatmap" class="math-canvas heatmap-canvas" width="1000" height="560" aria-label="Prime density surface"></canvas><div class="canvas-legend"><span class="legend-sparse">Low density</span><span class="legend-dense">High density</span><span>1.0 is the density predicted by the prime-number theorem</span></div>';
  } else if (data.chart) {
    chart = '<canvas id="distribution-canvas" class="math-canvas chart-canvas" width="1000" height="440" aria-label="Analytic prime-distribution chart"></canvas><div id="distribution-legend" class="canvas-legend"></div>';
  }
  return `${metrics ? `<div class="reciprocal-summary">${metrics}</div>` : ''}${chart}${distributionTable(data.columns, data.rows)}${sections}`;
}

function drawDistributionSeries(canvas, series, labels, signedLog) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const scale = (value) => (signedLog ? Math.sign(value) * Math.log10(1 + Math.abs(value)) : value);
  const points = series.flatMap((line) => line.values.filter(Number.isFinite).map(scale));
  if (!points.length) return;
  let yMin = Math.min(...points, 0), yMax = Math.max(...points, 0);
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const count = Math.max(...series.map((line) => line.values.length));
  const pad = 52;
  const x = (index) => pad + (count > 1 ? index / (count - 1) : 0.5) * (width - pad * 2);
  const y = (value) => height - pad - (scale(value) - yMin) / (yMax - yMin) * (height - pad * 2);
  ctx.strokeStyle = '#35404a'; ctx.lineWidth = 1;
  ctx.strokeRect(pad, pad, width - pad * 2, height - pad * 2);
  if (yMin <= 0 && yMax >= 0) { ctx.beginPath(); ctx.moveTo(pad, y(0)); ctx.lineTo(width - pad, y(0)); ctx.stroke(); }
  series.forEach((line, index) => {
    ctx.strokeStyle = distributionPalette[index % distributionPalette.length];
    ctx.lineWidth = 2; ctx.beginPath();
    line.values.forEach((value, position) => {
      if (!Number.isFinite(value)) return;
      const px = x(position), py = y(value);
      position ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    });
    ctx.stroke();
  });
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(String(labels[0] ?? ''), pad, height - 18);
  ctx.fillText(String(labels[labels.length - 1] ?? ''), Math.max(pad, width - 220), height - 18);
  ctx.fillText(`${signedLog ? 'signed log₁₀ ' : ''}max ${yMax.toPrecision(4)}`, 6, pad - 12);
  ctx.fillText(`${signedLog ? 'signed log₁₀ ' : ''}min ${yMin.toPrecision(4)}`, 6, height - pad + 22);
  const legend = $('#distribution-legend');
  if (legend) legend.innerHTML = series.map((line, index) => `<span style="color:${distributionPalette[index % distributionPalette.length]}">${escapeHtml(line.label)}</span>`).join('');
}

function drawDistributionBars(canvas, values, baseline) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  if (!values.length) return;
  const numbers = values.map((item) => Number(item.value)).filter(Number.isFinite);
  if (!numbers.length) return;
  const pad = 52;
  let low = Math.min(...numbers, baseline), high = Math.max(...numbers, baseline);
  if (low === high) { low -= 1; high += 1; }
  const y = (value) => height - pad - (value - low) / (high - low) * (height - pad * 2);
  const barWidth = (width - pad * 2) / values.length;
  values.forEach((item, index) => {
    const value = Number(item.value);
    if (!Number.isFinite(value)) return;
    ctx.fillStyle = value >= baseline ? '#4f9cf9' : '#e0705f';
    const top = Math.min(y(value), y(baseline));
    const size = Math.abs(y(value) - y(baseline));
    ctx.fillRect(pad + index * barWidth + 1, top, Math.max(1, barWidth - 2), Math.max(1, size));
  });
  ctx.strokeStyle = '#35404a'; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(pad, y(baseline)); ctx.lineTo(width - pad, y(baseline)); ctx.stroke();
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(String(values[0].label), pad, height - 18);
  ctx.fillText(String(values[values.length - 1].label), Math.max(pad, width - 160), height - 18);
  ctx.fillText(`max ${high.toPrecision(5)}`, 6, pad - 12);
  ctx.fillText(`min ${low.toPrecision(5)} · baseline ${baseline}`, 6, height - pad + 22);
}

function drawDensitySurface(canvas, rows, blocks, classes) {
  const { context: ctx, width, height } = prepareCanvas(canvas);
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const densities = rows.map((row) => Number(row[3])).filter(Number.isFinite);
  if (!densities.length || !blocks || !classes) return;
  const low = Math.min(...densities), high = Math.max(...densities);
  const spread = high - low || 1;
  const cellWidth = width / blocks, cellHeight = height / classes;
  rows.forEach((row, position) => {
    const block = Number(row[0]) - 1;
    const index = position % classes;
    const shade = (Number(row[3]) - low) / spread;
    const hue = 210 - shade * 175;
    ctx.fillStyle = `hsl(${hue}, 72%, ${28 + shade * 34}%)`;
    ctx.fillRect(block * cellWidth, height - (index + 1) * cellHeight, Math.ceil(cellWidth) + 1, Math.ceil(cellHeight) + 1);
  });
}

function drawDistributionChart(data) {
  if (data.chart === 'density-surface') {
    drawDensitySurface($('#distribution-heatmap'), data.rows, Number(data.blocks), Number(data.classes));
    return;
  }
  const canvas = $('#distribution-canvas');
  if (!canvas) return;
  const rows = data.rows;
  if (data.chart === 'approximation-error') {
    drawDistributionSeries(canvas, [
      { label: 'x/log x relative error (%)', values: rows.map((row) => Number(row[8])) },
      { label: 'li(x) relative error (%)', values: rows.map((row) => Number(row[9])) },
      { label: 'R(x) relative error (%)', values: rows.map((row) => Number(row[10])) },
    ], rows.map((row) => row[0]), true);
  } else if (data.chart === 'pnt-convergence') {
    drawDistributionSeries(canvas, [
      { label: 'π(x)/(x/log x)', values: rows.map((row) => Number(row[2])) },
      { label: 'π(x)/li(x)', values: rows.map((row) => Number(row[3])) },
    ], rows.map((row) => row[0]), false);
  } else if (data.chart === 'prime-race') {
    const classes = Number(data.classes) || 1;
    const series = [];
    for (let index = 0; index < classes; index += 1) {
      series.push({
        label: `a ≡ ${rows[index] ? rows[index][1] : index}`,
        values: rows.filter((row, position) => position % classes === index).map((row) => Number(row[2])),
      });
    }
    drawDistributionSeries(canvas, series, rows.filter((row, position) => position % classes === 0).map((row) => row[0]), false);
  } else if (data.chart === 'progression-deviation') {
    drawDistributionBars(canvas, rows.map((row) => ({ label: row[0], value: row[3] })), 0);
  } else if (data.chart === 'maximal-gaps') {
    drawDistributionSeries(canvas, [
      { label: 'merit g/log p', values: rows.map((row) => Number(row[3])) },
      { label: 'Cramér–Shanks g/log²p', values: rows.map((row) => Number(row[4])) },
      { label: 'Granville g/(2e^−γ log²p)', values: rows.map((row) => Number(row[5])) },
    ], rows.map((row) => row[0]), false);
  } else if (data.chart === 'short-interval') {
    drawDistributionBars(canvas, rows.map((row) => ({ label: row[0], value: row[5] })), 1);
  }
}

const distributionOffsets = (value) => value.trim().split(/[\s,;]+/).filter(Boolean).map(Number);

$('#approximation-error-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/approximation-error', {
    exponent_from: Number($('#approximation-error-from').value),
    exponent_to: Number($('#approximation-error-to').value),
    points: Number($('#approximation-error-points').value),
    threads: Number($('#approximation-error-threads').value),
  }, () => 'Prime-counting approximation error', 'distribution');
});

$('#pnt-convergence-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/pnt-convergence', {
    exponent_from: Number($('#pnt-convergence-from').value),
    exponent_to: Number($('#pnt-convergence-to').value),
    points: Number($('#pnt-convergence-points').value),
    threads: Number($('#pnt-convergence-threads').value),
  }, (data) => `Prime-number-theorem convergence · ${data.sign_changes} sign change${data.sign_changes === 1 ? '' : 's'}`, 'distribution');
});

$('#nth-prime-bounds-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/nth-prime-bounds', {
    exponent_from: Number($('#nth-prime-bounds-from').value),
    exponent_to: Number($('#nth-prime-bounds-to').value),
    points: Number($('#nth-prime-bounds-points').value),
    threads: Number($('#nth-prime-bounds-threads').value),
  }, (data) => `Explicit n-th prime bounds · ${data.violations} violation${data.violations === 1 ? '' : 's'}`, 'distribution');
});

$('#prime-race-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/prime-race', {
    modulus: $('#prime-race-modulus').value,
    endpoint: $('#prime-race-endpoint').value,
    checkpoints: Number($('#prime-race-checkpoints').value),
  }, (data) => `Prime race modulo ${$('#prime-race-modulus').value} · ${data.lead_changes} lead change${data.lead_changes === 1 ? '' : 's'}`, 'distribution');
});

$('#progression-deviation-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/progressions', {
    modulus: $('#progression-deviation-modulus').value,
    endpoint: $('#progression-deviation-endpoint').value,
  }, (data) => `π(x; q, a) across ${data.classes} reduced classes`, 'distribution');
});

$('#singular-series-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/singular-series', {
    offsets: distributionOffsets($('#singular-series-offsets').value),
    cutoff: Number($('#singular-series-cutoff').value),
  }, (data) => data.admissible ? 'Admissible pattern · singular series' : 'Inadmissible pattern', 'distribution');
});

$('#tuple-prediction-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/tuple-prediction', {
    offsets: distributionOffsets($('#tuple-prediction-offsets').value),
    start: $('#tuple-prediction-start').value,
    end: $('#tuple-prediction-end').value,
    cutoff: Number($('#tuple-prediction-cutoff').value),
  }, (data) => `${Number(data.observed).toLocaleString()} constellations counted by ${data.counted_by}`, 'distribution');
});

$('#bateman-horn-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/bateman-horn', {
    polynomials: $('#bateman-horn-polynomials').value.split(/\n+/).map((line) => line.trim()).filter(Boolean)
      .map((line) => line.split(/[\s,;]+/).filter(Boolean)),
    start: $('#bateman-horn-start').value,
    end: $('#bateman-horn-end').value,
    cutoff: Number($('#bateman-horn-cutoff').value),
  }, (data) => `${Number(data.observed).toLocaleString()} prime values observed`, 'distribution');
});

$('#maximal-gap-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/maximal-gaps', {
    start: $('#maximal-gap-start').value,
    end: $('#maximal-gap-end').value,
    baseline: Number($('#maximal-gap-baseline').value),
    prime_cap: Number($('#maximal-gap-cap').value),
  }, (data) => `${data.rows.length} record gaps · ${data.mismatches} published-table mismatch${data.mismatches === 1 ? '' : 'es'}`, 'distribution');
});

$('#short-interval-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/short-interval', {
    modulus: $('#short-interval-modulus').value,
    first_row: $('#short-interval-row').value,
    rows: Number($('#short-interval-rows').value),
    length: Number($('#short-interval-length').value),
  }, (data) => `${data.rows.length} short intervals measured`, 'distribution');
});

$('#density-surface-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/distribution/density-surface', {
    start: $('#density-surface-start').value,
    end: $('#density-surface-end').value,
    blocks: Number($('#density-surface-blocks').value),
    modulus: $('#density-surface-modulus').value,
  }, (data) => `${data.blocks} × ${data.classes} prime-density surface`, 'distribution');
});

// Prime-counting algorithm comparison and integer-structure predicates.
// These handlers only read form controls and paint the strings the engines
// returned; primecount and PARI/GP compute every number shown.
const countingAlgorithmSlugs = ['legendre', 'meissel', 'lehmer', 'lmo', 'deleglise-rivat', 'gourdon'];
const factorintStrategyMasks = [0, 1, 2, 4, 8];

$('#counting-comparison-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/counting/algorithm-comparison', {
    x: $('#counting-comparison-x').value,
    algorithms: countingAlgorithmSlugs.filter((slug) => $(`#counting-comparison-${slug}`).checked),
    double_check: $('#counting-comparison-double').checked,
    include_pari: $('#counting-comparison-pari').checked,
    threads: Number($('#counting-comparison-threads').value),
  }, (data) => (data.disagreement
    ? `DISAGREEMENT · ${data.distinct_values} distinct values across ${data.rows.length} sources`
    : `${data.rows.length} independent sources agree on π(x) = ${data.consensus}`), 'table');
});

$('#counting-phi-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/counting/phi', {
    x: $('#counting-phi-x').value,
    a: Number($('#counting-phi-a').value),
    threads: Number($('#counting-phi-threads').value),
  }, (data) => `phi(x, a) = ${data.phi}`, 'table');
});

$('#counting-inverse-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/counting/nth-prime-inverses', {
    n: $('#counting-inverse-n').value,
    threads: Number($('#counting-inverse-threads').value),
  }, (data) => `Exact n-th prime ${data.exact}`, 'table');
});

$('#integer-structure-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/structure/predicates', {
    expression: $('#integer-structure-number').value,
    sides: Number($('#integer-structure-sides').value),
  }, () => 'Integer-structure predicates', 'table');
});

$('#lenstra-divisors-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/structure/lenstra-divisors', {
    expression: $('#lenstra-divisors-number').value,
    residue: $('#lenstra-divisors-residue').value,
    modulus: $('#lenstra-divisors-modulus').value,
  }, (data) => `${data.found} divisor${data.found === 1 ? '' : 's'} in the residue class`, 'table');
});

$('#factorint-strategy-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/structure/factorint-strategies', {
    expression: $('#factorint-strategy-number').value,
    flags: factorintStrategyMasks.filter((mask) => $(`#factorint-strategy-flag-${mask}`).checked),
  }, (data) => `${data.rows.length} factorint strategy mask${data.rows.length === 1 ? '' : 's'} compared`, 'table');
});

$('#primality-lab-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/primality-lab', {
    number: $('#primality-lab-number').value,
    base: $('#primality-lab-base').value,
    proof_mode: $('#primality-lab-proof').value,
    timeout_seconds: 300,
  }, () => 'Primality-test comparison', 'table');
});

$('#special-form-test-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/special-form-test', {
    kind: $('#special-form-kind').value,
    parameter: $('#special-form-parameter').value,
    timeout_seconds: 300,
  }, () => 'Special-form primality proof', 'table');
});

$('#primality-compare-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/compare', {
    number: $('#primality-compare-number').value,
    bases: integerTokens($('#primality-compare-bases').value),
    budget_seconds: Number($('#primality-compare-budget').value),
    timeout_seconds: Number($('#primality-compare-timeout').value),
  }, (data) => `Comparison verdict: ${data.verdict}`, 'table');
});

$('#deterministic-witness-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/deterministic-witnesses', {
    number: $('#deterministic-witness-number').value,
    timeout_seconds: Number($('#deterministic-witness-timeout').value),
  }, (data) => data.deterministic
    ? `Deterministic verdict: ${data.verdict}`
    : 'No sufficient witness set covers this magnitude', 'table');
});

$('#pocklington-proof-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/pocklington', {
    number: $('#pocklington-number').value,
    budget_seconds: Number($('#pocklington-budget').value),
    witness_limit: Number($('#pocklington-witness').value),
  }, (data) => `Pocklington N−1: ${data.verdict}`, 'table');
});

$('#pratt-certificate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/pratt', {
    number: $('#pratt-number').value,
    max_nodes: Number($('#pratt-nodes').value),
    budget_seconds: Number($('#pratt-budget').value),
  }, (data) => `Pratt certificate: ${data.verdict}`, 'table');
});

$('#primality-certificate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/verify-certificate', {
    kind: $('#primality-certificate-kind').value,
    certificate: $('#primality-certificate-data').value,
  }, (data) => data.valid ? 'Valid certificate' : 'Invalid certificate', 'table');
});

$('#proth-test-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/proth', {
    k: $('#proth-k').value,
    exponent: Number($('#proth-exponent').value),
    base: Number($('#proth-base').value),
    witness_limit: Number($('#proth-witness').value),
  }, (data) => `Proth criterion: ${data.verdict}`, 'table');
});

$('#proth-search-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/proth-search', {
    k: $('#proth-search-k').value,
    base: Number($('#proth-search-base').value),
    n_start: Number($('#proth-search-start').value),
    n_end: Number($('#proth-search-end').value),
    limit: Number($('#proth-search-limit').value),
  }, (data) => `${data.metrics['Hits reported']} generalized Proth results`, 'table');
});

$('#lucas-sequence-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/lucas-sequence', {
    number: $('#lucas-sequence-number').value,
    p: Number($('#lucas-sequence-p').value),
    q: Number($('#lucas-sequence-q').value),
    selfridge: $('#lucas-sequence-selfridge').value === '1',
    witness_limit: Number($('#lucas-sequence-witness').value),
    budget_seconds: Number($('#lucas-sequence-budget').value),
  }, (data) => `Lucas / N+1 verdict: ${data.verdict}`, 'table');
});

$('#pseudoprime-taxonomy-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const parameters = integerTokens($('#pseudoprime-pq').value);
  submitPrimeForm(event.currentTarget, '/api/primality-lab/taxonomy', {
    number: $('#pseudoprime-number').value,
    bases: integerTokens($('#pseudoprime-bases').value),
    p: Number(parameters[0]),
    q: Number(parameters[1]),
    selfridge: $('#pseudoprime-selfridge').value === '1',
  }, (data) => data.metrics['Pseudoprime families'], 'table');
});

$('#carmichael-analysis-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/carmichael', {
    number: $('#carmichael-number').value,
    base_limit: Number($('#carmichael-bases').value),
    budget_seconds: Number($('#carmichael-budget').value),
  }, (data) => `Carmichael number: ${data.carmichael}`, 'table');
});

$('#chernick-carmichael-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/chernick', {
    k_start: Number($('#chernick-start').value),
    k_end: Number($('#chernick-end').value),
    limit: Number($('#chernick-limit').value),
  }, (data) => `${data.metrics['Carmichael numbers found']} Chernick Carmichael numbers`, 'table');
});

$('#repunit-search-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/repunit', {
    base: Number($('#repunit-base').value),
    n_start: Number($('#repunit-start').value),
    n_end: Number($('#repunit-end').value),
    limit: Number($('#repunit-limit').value),
  }, (data) => `${data.metrics['Hits reported']} generalized repunit results`, 'table');
});

$('#sierpinski-riesel-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/sierpinski', {
    k: $('#sierpinski-k').value,
    kind: $('#sierpinski-kind').value,
    n_max: Number($('#sierpinski-max').value),
    budget_seconds: Number($('#sierpinski-budget').value),
  }, (data) => data.metrics.Outcome, 'table');
});

$('#covering-set-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/covering-set', {
    k: $('#covering-k').value,
    kind: $('#covering-kind').value,
    period: Number($('#covering-period').value),
    candidates: integerTokens($('#covering-primes').value),
  }, (data) => data.covered
    ? 'Covering set verified: every exponent class is covered'
    : 'This set leaves exponent classes uncovered', 'table');
});

$('#bitwin-chain-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/bitwin-chains', {
    start: $('#bitwin-start').value,
    end: $('#bitwin-end').value,
    min_length: Number($('#bitwin-length').value),
    limit: Number($('#bitwin-limit').value),
  }, (data) => `${data.metrics['Chains found']} bi-twin chains`, 'table');
});

$('#prime-ladder-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/prime-ladder', {
    start_prime: $('#ladder-start').value,
    end_prime: $('#ladder-end').value,
    max_steps: Number($('#ladder-steps').value),
  }, (data) => data.metrics.Outcome, 'table');
});

$('#constrained-prime-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const seed = $('#constrained-seed').value.trim();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/constrained-prime', {
    bits: Number($('#constrained-bits').value),
    kind: $('#constrained-kind').value,
    modulus: $('#constrained-modulus').value,
    residue: $('#constrained-residue').value,
    certificate: $('#constrained-certificate').checked,
    seed: seed === '' ? null : seed,
    candidate_limit: Number($('#constrained-limit').value),
    budget_seconds: Number($('#constrained-budget').value),
  }, (data) => data.metrics.Status, 'table');
});

$('#lucas-lehmer-steps-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/lucas-lehmer-steps', {
    exponent: Number($('#lucas-lehmer-exponent').value),
    show_limit: Number($('#lucas-lehmer-steps').value),
    timeout_seconds: Number($('#lucas-lehmer-timeout').value),
  }, (data) => `Lucas–Lehmer verdict: ${data.verdict}`, 'table');
});

$('#ecpp-steps-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primality-lab/ecpp-steps', {
    number: $('#ecpp-number').value,
    budget_seconds: Number($('#ecpp-budget').value),
  }, (data) => `ECPP verdict: ${data.verdict}`, 'table');
});

$('#special-prime-family-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/special-prime-family', {
    kind: $('#special-family-kind').value,
    start_index: Number($('#special-family-start').value),
    end_index: Number($('#special-family-end').value),
    limit: Number($('#special-family-limit').value),
    timeout_seconds: Number($('#special-family-timeout').value),
  }, (data) => `${data.metrics['Proven primes found']} proven ${data.metrics.Family} primes`, 'table');
});

$('#special-family-kind').addEventListener('change', (event) => {
  const end = $('#special-family-end');
  end.max = event.target.value === 'fermat' ? '20' : '10000';
  if (Number(end.value) > Number(end.max)) end.value = end.max;
});

$('#cunningham-chain-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/cunningham-chain', {
    start_prime: $('#cunningham-start').value,
    kind: Number($('#cunningham-kind').value),
    length: Number($('#cunningham-length').value),
    timeout_seconds: 300,
  }, (data) => data.complete ? 'Complete Cunningham chain' : 'Chain stopped at a composite', 'table');
});

$('#ntt-primes-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/ntt-primes', {
    bits: Number($('#ntt-bits').value),
    power_two: Number($('#ntt-power').value),
    count: Number($('#ntt-count').value),
    candidate_limit: Number($('#ntt-limit').value),
    timeout_seconds: Number($('#ntt-timeout').value),
  }, (data) => `${data.metrics.Found} proven NTT-friendly primes`, 'table');
});

$('#tonelli-shanks-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/tonelli-shanks', {
    value: $('#tonelli-value').value,
    prime: $('#tonelli-prime').value,
    trace_limit: Number($('#tonelli-limit').value),
  }, (data) => data.roots.length ? `Square roots: ${data.roots.join(', ')}` : 'Quadratic nonresidue', 'table');
});

$('#hensel-roots-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/hensel-roots', {
    coefficients: integerTokens($('#hensel-coefficients').value),
    prime: $('#hensel-prime').value,
    exponent: Number($('#hensel-exponent').value),
    limit: Number($('#hensel-limit').value),
  }, (data) => `${data.metrics['Root count']} p-adic roots`, 'table');
});

$('#order-distribution-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/order-distribution', {
    modulus: $('#order-modulus').value,
    limit: Number($('#order-limit').value),
  }, () => 'Multiplicative-order distribution', 'table');
});

$('#power-residues-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/power-residues', {
    modulus: $('#residue-prime').value,
    exponent: Number($('#residue-exponent').value),
    limit: Number($('#residue-limit').value),
  }, () => 'Power-residue distribution', 'table');
});

$('#p-adic-valuation-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/valuation', {
    number: $('#valuation-number').value,
    prime: $('#valuation-prime').value,
  }, () => 'p-adic valuation', 'table');
});

$('#cyclotomic-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/cyclotomic', {
    index: Number($('#cyclotomic-index').value),
    prime: $('#cyclotomic-prime').value,
  }, () => 'Cyclotomic-polynomial factorization', 'table');
});

// --- Algebra laboratory: modular, arithmetic, and algebraic workbenches ------
$('#reciprocity-trace-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/reciprocity', {
    a: $('#reciprocity-a').value,
    n: $('#reciprocity-n').value,
    trace_limit: Number($('#reciprocity-limit').value),
  }, () => 'Quadratic-reciprocity trace', 'table');
});

$('#congruence-solver-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/congruence', {
    coefficients: integerTokens($('#congruence-coefficients').value),
    modulus: $('#congruence-modulus').value,
    limit: Number($('#congruence-limit').value),
  }, (data) => data.complete ? 'Congruence solutions' : 'Congruence solutions (inconclusive)', 'table');
});

$('#dlog-lab-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/discrete-log', {
    target: $('#dlog-target').value,
    base: $('#dlog-base').value,
    modulus: $('#dlog-modulus').value,
    algorithm: $('#dlog-algorithm').value,
    step_limit: Number($('#dlog-steps').value),
    timeout_seconds: Number($('#dlog-timeout').value),
  }, (data) => `Discrete logarithm: ${data.status}`, 'table');
});

$('#finite-field-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/finite-field', {
    characteristic: $('#finite-field-p').value,
    degree: Number($('#finite-field-m').value),
    modulus_coefficients: integerTokens($('#finite-field-modulus').value),
    a_coefficients: integerTokens($('#finite-field-a').value),
    b_coefficients: integerTokens($('#finite-field-b').value),
    exponent: Number($('#finite-field-exponent').value),
  }, () => 'Finite-field arithmetic', 'table');
});

$('#divisor-lattice-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/divisor-lattice', {
    number: $('#divisor-lattice-number').value,
    divisor_limit: Number($('#divisor-lattice-limit').value),
    lattice_cap: Number($('#divisor-lattice-cap').value),
  }, () => 'Divisor enumeration and lattice', 'table');
});

$('#smoothness-profile-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/smoothness', {
    number: $('#smoothness-number').value,
    smooth_bound: $('#smoothness-bound').value,
    rough_bound: $('#smoothness-rough').value,
  }, () => 'Smoothness and roughness profile', 'table');
});

$('#record-numbers-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/record-numbers', {
    number: $('#record-numbers-number').value,
    bound: $('#record-numbers-bound').value,
    limit: Number($('#record-numbers-limit').value),
  }, () => 'Divisor-record analysis', 'table');
});

$('#weird-number-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/weird-numbers', {
    number: $('#weird-number-number').value,
    subset_cap: Number($('#weird-number-cap').value),
    witness_bits: Number($('#weird-number-bits').value),
  }, (data) => `Abundance analysis · weird: ${data.weird}`, 'table');
});

$('#sociable-cycle-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/sociable', {
    start: $('#sociable-start').value,
    end: $('#sociable-end').value,
    max_length: Number($('#sociable-length').value),
    term_bound: $('#sociable-term-bound').value,
    limit: Number($('#sociable-limit').value),
    timeout_seconds: Number($('#sociable-timeout').value),
  }, () => 'Amicable and sociable cycles', 'table');
});

$('#cornacchia-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/cornacchia', {
    d: $('#cornacchia-d').value,
    number: $('#cornacchia-n').value,
    trace_limit: Number($('#cornacchia-limit').value),
  }, (data) => data.complete ? 'Cornacchia representations' : 'Cornacchia search (inconclusive)', 'table');
});

$('#quadratic-ring-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/quadratic-ring', {
    radicand: $('#quadratic-ring-d').value,
    a: $('#quadratic-ring-a').value,
    b: $('#quadratic-ring-b').value,
    prime: $('#quadratic-ring-prime').value,
    certify_seconds: Number($('#quadratic-ring-certify').value),
    timeout_seconds: Number($('#quadratic-ring-timeout').value),
  }, () => 'Quadratic integer ring', 'table');
});

$('#number-field-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/number-field', {
    coefficients: integerTokens($('#number-field-coefficients').value),
    primes: integerTokens($('#number-field-primes').value),
    element_coefficients: integerTokens($('#number-field-element').value),
    class_seconds: Number($('#number-field-class').value),
    timeout_seconds: Number($('#number-field-timeout').value),
  }, () => 'Number-field prime decomposition', 'table');
});

$('#chebotarev-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/algebra/chebotarev', {
    coefficients: integerTokens($('#chebotarev-coefficients').value),
    bound: $('#chebotarev-bound').value,
    group_seconds: Number($('#chebotarev-group').value),
  }, (data) => data.predicted_available ? 'Chebotarev density experiment' : 'Chebotarev experiment (predictions inconclusive)', 'table');
});

// Binary quadratic forms, class groups, continued fractions and Pell equations.
// Every value below is read from the form, sent to /api/forms/*, and rendered; the
// PARI/GP driver numerisect/forms_lab.gp performs all of the mathematics.
const formTriple = (value) => {
  const parts = integerTokens(value);
  return { a: parts[0] ?? '', b: parts[1] ?? '', c: parts[2] ?? '' };
};

$('#quadratic-form-reduce-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/reduce', {
    a: $('#quadratic-form-reduce-a').value,
    b: $('#quadratic-form-reduce-b').value,
    c: $('#quadratic-form-reduce-c').value,
    step_limit: Number($('#quadratic-form-reduce-steps').value),
    cycle_limit: Number($('#quadratic-form-reduce-cycle').value),
    timeout_seconds: Number($('#quadratic-form-reduce-timeout').value),
  }, (data) => data.definite ? 'Reduced positive definite form' : 'Reduced indefinite form', 'table');
});

$('#quadratic-form-compose-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const left = formTriple($('#quadratic-form-compose-left').value);
  const right = formTriple($('#quadratic-form-compose-right').value);
  submitPrimeForm(event.currentTarget, '/api/forms/compose', {
    a1: left.a, b1: left.b, c1: left.c,
    a2: right.a, b2: right.b, c2: right.c,
    exponent: Number($('#quadratic-form-compose-exponent').value),
    order_limit: Number($('#quadratic-form-compose-order').value),
    cycle_limit: Number($('#quadratic-form-compose-cycle').value),
    timeout_seconds: Number($('#quadratic-form-compose-timeout').value),
  }, () => 'Form composition and powers', 'table');
});

$('#quadratic-form-primeform-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/prime-form', {
    discriminant: $('#quadratic-form-primeform-disc').value,
    primes: integerTokens($('#quadratic-form-primeform-primes').value),
  }, () => 'Prime forms of a discriminant', 'table');
});

$('#quadratic-form-class-group-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/class-group', {
    discriminant: $('#quadratic-form-class-group-disc').value,
    generator_limit: Number($('#quadratic-form-class-group-generators').value),
  }, () => 'Form class number and class group', 'table');
});

$('#quadratic-form-enumerate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/reduced-forms', {
    discriminant: $('#quadratic-form-enumerate-disc').value,
    form_limit: Number($('#quadratic-form-enumerate-limit').value),
    cycle_limit: Number($('#quadratic-form-enumerate-cycle').value),
  }, (data) => data.complete ? 'Reduced forms of a discriminant' : 'Reduced forms (enumeration inconclusive)', 'table');
});

$('#quadratic-form-represent-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const coefficients = formTriple($('#quadratic-form-represent-form-coefficients').value);
  submitPrimeForm(event.currentTarget, '/api/forms/represent', {
    a: coefficients.a, b: coefficients.b, c: coefficients.c,
    number: $('#quadratic-form-represent-number').value,
    solution_limit: Number($('#quadratic-form-represent-limit').value),
  }, (data) => data.represented ? 'Representation by a quadratic form' : 'Not represented by this form', 'table');
});

$('#continued-fraction-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/continued-fraction', {
    mode: $('#continued-fraction-mode').value,
    numerator: $('#continued-fraction-numerator').value,
    denominator: $('#continued-fraction-denominator').value,
    radicand: $('#continued-fraction-radicand').value,
    quotient_limit: Number($('#continued-fraction-quotients').value),
    convergent_limit: Number($('#continued-fraction-convergents').value),
    approximation_bound: $('#continued-fraction-bound').value,
    preview_digits: Number($('#continued-fraction-preview').value),
    timeout_seconds: Number($('#continued-fraction-timeout').value),
  }, (data) => data.complete ? 'Continued-fraction expansion' : 'Continued fraction (period inconclusive)', 'table');
});

$('#pell-equation-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/forms/pell', {
    d: $('#pell-d').value,
    solution_count: Number($('#pell-count').value),
    digit_limit: Number($('#pell-digits').value),
    unit_seconds: Number($('#pell-unit-seconds').value),
    timeout_seconds: Number($('#pell-timeout').value),
  }, (data) => data.available ? 'Pell equation solutions' : 'Pell equation (fundamental unit inconclusive)', 'table');
});

$('#character-symbol-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/symbols', {
    a: $('#symbol-a').value, n: $('#symbol-n').value,
  }, () => 'Quadratic character symbols', 'table');
});

$('#crt-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/crt', {
    residues: integerTokens($('#crt-residues').value),
    moduli: integerTokens($('#crt-moduli').value),
  }, (data) => data.compatible ? 'Compatible CRT system' : 'Incompatible CRT system', 'table');
});

$('#modular-roots-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/modular-roots', {
    value: $('#modroot-value').value,
    exponent: Number($('#modroot-exponent').value),
    modulus: $('#modroot-prime').value,
    limit: 10000,
  }, () => 'Power-congruence roots', 'table');
});

$('#discrete-log-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/discrete-log', {
    target: $('#dlog-target').value,
    base: $('#dlog-base').value,
    modulus: $('#dlog-modulus').value,
  }, () => 'Discrete logarithm', 'table');
});

$('#unit-group-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/unit-group', {
    modulus: $('#unit-group-modulus').value,
    limit: Number($('#unit-group-limit').value),
  }, () => 'Multiplicative-group structure', 'table');
});

$('#polynomial-factor-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/polynomial', {
    coefficients: integerTokens($('#polynomial-coefficients').value),
    prime_modulus: $('#polynomial-prime').value,
  }, () => 'Polynomial factorization', 'table');
});

$('#extended-arithmetic-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/arithmetic-functions', {
    number: $('#extended-number').value,
    divisor_exponent: Number($('#extended-k').value),
    smooth_bound: $('#extended-bound').value,
    quadratic_form_d: Number($('#extended-d').value),
    divisor_limit: Number($('#extended-divisor-limit').value),
  }, () => 'Extended arithmetic analysis', 'table');
});

$('#divisor-classification-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/divisor-classification', {
    number: $('#divisor-classification-number').value,
  }, (data) => `${data.metrics.Classification} integer`, 'table');
});

$('#aliquot-sequence-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/aliquot', {
    number: $('#aliquot-number').value,
    max_steps: Number($('#aliquot-steps').value),
    timeout_seconds: 300,
  }, (data) => `Aliquot sequence: ${data.metrics.Status}`, 'table');
});

$('#perfect-power-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/perfect-power', {
    number: $('#perfect-power-number').value,
  }, (data) => data.is_power ? 'Perfect-power decomposition' : 'Not a perfect power', 'table');
});

$('#factor-strategy-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/factor-strategy', {
    number: $('#factor-strategy-number').value,
    trial_bound: Number($('#factor-strategy-bound').value),
  }, () => 'Factorization strategy recommendation', 'table');
});

$('#eisenstein-prime-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/eisenstein', {
    a: $('#eisenstein-a').value, b: $('#eisenstein-b').value,
  }, () => 'Eisenstein-prime analysis', 'table');
});

$('#quadratic-decomposition-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/number-theory/quadratic-decomposition', {
    radicand: $('#quadratic-radicand').value,
    prime: $('#quadratic-prime').value,
  }, () => 'Quadratic-field decomposition', 'table');
});

function showZetaResult(title, data, type, form) {
  const panel = $('#zeta-result-panel');
  panel.dataset.ownerForm = form.id;
  form.insertAdjacentElement('afterend', panel);
  panel.classList.remove('prime-page-hidden');
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
  } else if (type === 'complex') {
    content.innerHTML = `<div class="zeta-value-grid"><article><span>Real enclosure</span><code>${escapeHtml(data.real)}</code></article><article><span>Imaginary enclosure</span><code>${escapeHtml(data.imaginary)}</code></article></div>`;
  } else if (type === 'gram') {
    content.innerHTML = `<div class="prime-metric"><span>${escapeHtml(data.label)}</span><strong>${escapeHtml(data.value)}</strong></div>`;
  } else if (type === 'functional') {
    content.innerHTML = `<div class="classification-summary"><span>${data.verified ? 'Verified overlap' : 'No overlap'}</span><small>Rigorous Arb enclosure comparison</small></div><div class="zeta-value-grid"><article><span>Left side</span><code>${escapeHtml(data.left_real)} + (${escapeHtml(data.left_imaginary)})i</code></article><article><span>Right side</span><code>${escapeHtml(data.right_real)} + (${escapeHtml(data.right_imaginary)})i</code></article><article><span>Residual enclosure</span><code>${escapeHtml(data.residual_real)} + (${escapeHtml(data.residual_imaginary)})i</code></article></div>`;
  } else if (type === 'heatmap') {
    content.innerHTML = '<canvas id="zeta-heatmap-canvas" class="math-canvas heatmap-canvas" width="1000" height="650" aria-label="Riemann zeta heatmap"></canvas><div class="canvas-legend"><span>Hue = phase</span><span>Lightness = log magnitude</span><span>Black = pole/undefined</span></div>';
    drawZetaHeatmap($('#zeta-heatmap-canvas'), data.points, data.width, data.height);
  } else if (zetaRenderers[type]) {
    content.innerHTML = zetaRenderers[type](data);
    if (zetaPainters[type]) zetaPainters[type](data);
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
    showZetaResult(title(data), data, type, form);
  } catch (error) {
    const panel = $('#zeta-result-panel');
    panel.dataset.ownerForm = form.id;
    form.insertAdjacentElement('afterend', panel);
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

$('#zeta-hardy-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/hardy', {
    ordinate: $('#zeta-hardy-t').value,
    precision: Number($('#zeta-hardy-precision').value),
  }, (data) => `Z(${data.input})`, 'complex');
});

$('#zeta-xi-eta-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/xi-eta', {
    kind: $('#zeta-special-kind').value,
    sigma: $('#zeta-special-sigma').value,
    ordinate: $('#zeta-special-t').value,
    precision: Number($('#zeta-special-precision').value),
  }, (data) => `${data.function} at ${data.sigma} + ${data.ordinate}i`, 'complex');
});

$('#zeta-functional-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/functional-equation', {
    sigma: $('#zeta-functional-sigma').value,
    ordinate: $('#zeta-functional-t').value,
    precision: Number($('#zeta-functional-precision').value),
  }, () => 'Functional-equation verification', 'functional');
});

$('#zeta-stieltjes-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/stieltjes', {
    index: $('#zeta-stieltjes-index').value,
    precision: Number($('#zeta-stieltjes-precision').value),
  }, (data) => `Stieltjes constant γ${data.index}`, 'complex');
});

$('#zeta-gram-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/gram', {
    index: $('#zeta-gram-index').value,
    precision: Number($('#zeta-gram-precision').value),
  }, (data) => `Gram point g${data.index}`, 'gram');
});

// Presentation helpers for the explicit-formula and L-function panels. These
// only format values that FLINT/Arb or PARI/GP already computed and map them to
// canvas coordinates; no mathematics is evaluated in the browser.
const zetaMetrics = (entries) => `<div class="reciprocal-summary">${entries
  .filter(([, value]) => value !== undefined && value !== null && value !== '')
  .map(([label, value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>`)
  .join('')}</div>`;

const zetaTable = (columns, rows) => `<div class="result-table-wrap"><table class="result-table"><thead><tr>${columns
  .map((column) => `<th scope="col">${escapeHtml(column)}</th>`).join('')}</tr></thead><tbody>${rows
  .slice(0, 2000)
  .map((row) => `<tr>${row.map((value) => `<td>${escapeHtml(String(value))}</td>`).join('')}</tr>`)
  .join('')}</tbody></table>${rows.length ? '' : '<p class="empty">No rows returned. See the result note above.</p>'}</div>`;

const zetaCanvas = (id, label, height = 420) => `<canvas id="${id}" class="math-canvas chart-canvas" width="1000" height="${height}" aria-label="${escapeHtml(label)}"></canvas>`;

function drawZetaCurve(canvas, points, key) {
  if (!canvas) return;
  drawZetaLine(canvas, points.map((point) => ({ t: point.x, magnitude: point[key] })), 'magnitude');
}

function drawZetaBars(canvas, bins) {
  const node = canvas && prepareCanvas(canvas);
  if (!node) return;
  const { context: ctx, width, height } = node;
  ctx.fillStyle = '#0c0f11'; ctx.fillRect(0, 0, width, height);
  const pad = 44;
  const peak = Math.max(...bins.map((bin) => Math.max(bin.observed || 0, bin.predicted || 0)), 1e-9);
  const span = bins.length;
  const barWidth = (width - pad * 2) / span;
  const y = (value) => height - pad - (value / peak) * (height - pad * 2);
  ctx.strokeStyle = '#35404a'; ctx.lineWidth = 1; ctx.strokeRect(pad, pad, width - pad * 2, height - pad * 2);
  bins.forEach((bin, index) => {
    const x = pad + index * barWidth;
    ctx.fillStyle = 'rgba(79, 156, 249, 0.65)';
    ctx.fillRect(x + 1, y(bin.observed || 0), Math.max(barWidth - 2, 1), height - pad - y(bin.observed || 0));
  });
  ctx.strokeStyle = '#f2b134'; ctx.lineWidth = 2; ctx.beginPath();
  bins.forEach((bin, index) => {
    const x = pad + (index + 0.5) * barWidth;
    const py = y(bin.predicted || 0);
    index ? ctx.lineTo(x, py) : ctx.moveTo(x, py);
  });
  ctx.stroke();
  ctx.fillStyle = '#8d9aa5'; ctx.font = '12px sans-serif';
  ctx.fillText(String(bins[0].lower.toPrecision(3)), pad, height - 15);
  ctx.fillText(String(bins[bins.length - 1].upper.toPrecision(3)), width - pad - 30, height - 15);
  ctx.fillText(peak.toPrecision(3), 5, pad);
}

const zetaRenderers = {
  convergence: (data) => `${zetaMetrics([
    ['Evaluation point x', data.bound],
    ['Exact value', data.exact],
    ['Certified zeros used', data.zeros],
    ['Möbius terms', data.moebius_terms],
  ])}${zetaCanvas('zeta-convergence-canvas', 'Explicit-formula convergence')}<p class="canvas-legend"><span>Signed error against the exact value as the number of certified zeros grows</span></p>${zetaTable(
    ['Zeros N', 'Estimate (Arb enclosure)', 'Error against the exact value'],
    data.terms.map((row) => [row.zeros, row.estimate, row.error]),
  )}`,
  rsanalysis: (data) => `${zetaMetrics([
    ['s', `${data.sigma} + ${data.ordinate}i`],
    ['Reference Re ζ(s)', data.reference_real],
    ['Reference Im ζ(s)', data.reference_imaginary],
  ])}${zetaTable(
    ['Correction terms K', 'Re (main sum + K terms)', 'Im', 'Deviation from ζ(s)', 'FLINT remainder bound'],
    data.rows.map((row) => [row.terms, row.real, row.imaginary, row.deviation, row.bound]),
  )}`,
  euler: (data) => `${zetaMetrics([
    ['s', `${data.sigma} + ${data.ordinate}i`],
    ['Reference Re ζ(s)', data.reference_real],
    ['FLINT certified Euler product', data.certified_euler || 'not applicable at this s'],
  ])}${zetaTable(
    ['Primes', 'Largest prime', 'Re (partial product)', 'Im', 'Deviation from ζ(s)', 'Rigorous truncation bound'],
    data.rows.map((row) => [row.primes, row.largest_prime, row.real, row.imaginary, row.deviation, row.truncation_bound]),
  )}`,
  histogram: (data) => `${zetaMetrics([
    ['Zeros sampled', data.samples],
    ['Pairs inside the window', data.pairs],
    ['Mean spacing', data.mean === undefined ? undefined : data.mean.toPrecision(8)],
    ['Variance', data.variance === undefined ? undefined : data.variance.toPrecision(6)],
    ['Smallest gap', data.minimum === undefined ? undefined : data.minimum.toPrecision(6)],
    ['Largest gap', data.maximum === undefined ? undefined : data.maximum.toPrecision(6)],
    ['Outside the window', data.overflow],
  ])}${zetaCanvas('zeta-histogram-canvas', 'Zero statistics against the GUE prediction')}<p class="canvas-legend"><span>Blue bars = observed</span><span>Amber line = GUE prediction</span></p>${zetaTable(
    ['Bin lower', 'Bin upper', 'Count', 'Observed density', 'GUE prediction'],
    data.bins.map((bin) => [bin.lower.toPrecision(4), bin.upper.toPrecision(4), bin.count, bin.observed.toPrecision(6), bin.predicted.toPrecision(6)]),
  )}`,
  gramblocks: (data) => `${zetaMetrics([
    ['Gram points examined', data.count],
    ["Gram's-law exceptions", data.exceptions.length],
    ['Gram blocks of length ≥ 2', data.blocks.length],
    ['Inconclusive enclosures', data.inconclusive],
  ])}${data.exceptions.length ? `<div class="result-group"><span>Certified exceptions</span><div>${data.exceptions.map((row) => `<code class="prime-chip">n=${escapeHtml(row.index)} · Z=${escapeHtml(row.hardy_z)}</code>`).join('')}</div></div>` : '<p class="empty">No exception to Gram\'s law in this range.</p>'}${data.blocks.length ? zetaTable(['Block start n', 'Length', 'Pattern'], data.blocks.map((block) => [block.start_index, block.length, block.pattern])) : ''}${zetaTable(
    ['n', 'Gram point gₙ', 'Z(gₙ)', "Gram's law"],
    data.points.map((row) => [row.index, row.gram_point.toPrecision(12), row.hardy_z.toPrecision(10), row.status]),
  )}`,
  backlund: (data) => `${zetaMetrics([
    ['S(T) enclosure', data.remainder],
    ['Rigorous |S(T)| bound', data.remainder_bound],
    ['θ(T) enclosure', data.theta],
    ['Certified N(T)', data.zero_count],
  ])}${zetaCanvas('zeta-backlund-canvas', 'Zero-counting remainder S(T)')}<p class="canvas-legend"><span>Exploratory midpoints of S(T); the endpoint values above are certified</span></p>`,
  chartable: (data) => `${zetaMetrics([
    ['Modulus q', data.modulus],
    ['Characters', data.group_order],
    ['Primitive characters', data.primitive_total],
    ['Listing truncated', data.truncated ? 'yes' : 'no'],
  ])}${zetaTable(
    ['Conrey label m', 'Conductor', 'Parity', 'Order', 'Primitive', 'Real', 'Principal'],
    data.characters.map((row) => [row.number, row.conductor, row.parity, row.order, row.primitive ? 'yes' : 'no', row.real ? 'yes' : 'no', row.principal ? 'yes' : 'no']),
  )}`,
  lvalue: (data) => `${zetaMetrics([
    ['Character', `χ_${data.modulus}(${data.number}, ·)`],
    ['Conductor', data.conductor],
    ['Parity', data.parity],
    ['Order', data.order],
    ['Primitive', data.primitive ? 'yes' : 'no'],
    ['Real character', data.real_character ? 'yes' : 'no'],
    ['Independent enclosures overlap', data.verified ? 'yes' : 'no'],
  ])}<div class="zeta-value-grid"><article><span>Re L(s, χ)</span><code>${escapeHtml(data.real)}</code></article><article><span>Im L(s, χ)</span><code>${escapeHtml(data.imaginary)}</code></article><article><span>Hurwitz cross-check Re</span><code>${escapeHtml(data.cross_real)}</code></article><article><span>Hurwitz cross-check Im</span><code>${escapeHtml(data.cross_imaginary)}</code></article>${data.root_number_real ? `<article><span>Root number</span><code>${escapeHtml(data.root_number_real)} + (${escapeHtml(data.root_number_imaginary)})i</code></article><article><span>Gauss sum</span><code>${escapeHtml(data.gauss_sum_real)} + (${escapeHtml(data.gauss_sum_imaginary)})i</code></article>` : ''}</div>`,
  lzeros: (data) => `${zetaMetrics([
    ['Character', `χ_${data.modulus}(${data.number}, ·)`],
    ['Mode', data.mode === 'sign-changes' ? 'certified sign changes' : 'exploratory |L| minima'],
    ['Certified sign changes', data.mode === 'sign-changes' ? data.sign_changes.length : undefined],
    ['Exploratory minima', data.mode === 'sign-changes' ? undefined : data.minima.length],
    ['Smooth θ(T,χ)/π count', data.smooth_count],
  ])}${zetaCanvas('zeta-lzeros-canvas', 'Critical-line curve for the Dirichlet L-function')}<p class="canvas-legend"><span>${data.mode === 'sign-changes' ? 'Hardy Z(t, χ) midpoints' : '|L(½+it, χ)| midpoints'}</span></p>${data.mode === 'sign-changes'
    ? zetaTable(['#', 'Certified bracket lower', 'Certified bracket upper'], data.sign_changes.map((row) => [row.index, row.lower.toPrecision(17), row.upper.toPrecision(17)]))
    : zetaTable(['#', 'Ordinate t', '|L(½+it, χ)|'], data.minima.map((row) => [row.index, row.t.toPrecision(12), row.magnitude.toPrecision(8)]))}`,
  dedekind: (data) => `${zetaMetrics([
    ['Defining polynomial', data.polynomial],
    ['Degree', data.degree],
    ['Signature', `(${data.real_places}, ${data.complex_places})`],
    ['Discriminant', data.discriminant],
    ['lfuncheckfeq (log₂ error)', data.functional_equation_log2_error],
    ['ζ_K(s) real part', data.value_real],
    ['ζ_K(s) imaginary part', data.value_imaginary],
    ['Class number', data.class_number],
    ['Regulator', data.regulator],
    ['Torsion units', data.torsion_units],
    ['Class-number-formula residue', data.class_number_formula_residue],
    ['Residue difference', data.residue_difference],
    ['Zeros located', data.zeros_found],
  ])}${data.poles.length ? zetaTable(['Pole at s', 'Residue'], data.poles.map((pole) => [pole.point, pole.residue])) : ''}${zetaTable(['#', 'Critical-line ordinate'], data.zeros.map((zero) => [zero.index, zero.ordinate]))}`,
};

const zetaPainters = {
  convergence: (data) => drawZetaCurve($('#zeta-convergence-canvas'), data.terms.map((row) => ({ x: row.zeros, error: row.error_value })), 'error'),
  histogram: (data) => drawZetaBars($('#zeta-histogram-canvas'), data.bins),
  backlund: (data) => drawZetaCurve($('#zeta-backlund-canvas'), data.points.map((point) => ({ x: point.t, s: point.s })), 's'),
  lzeros: (data) => drawZetaCurve($('#zeta-lzeros-canvas'), data.points.map((point) => ({ x: point.t, value: data.mode === 'sign-changes' ? point.hardy_z : point.magnitude })), 'value'),
};

$('#zeta-explicit-pi-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/explicit-prime-count', {
    bound: $('#zeta-explicit-bound').value,
    zeros: Number($('#zeta-explicit-zeros').value),
    precision: Number($('#zeta-explicit-precision').value),
    threads: Number($('#zeta-explicit-threads').value),
  }, (data) => `Riemann explicit formula for π(${data.bound})`, 'convergence');
});

$('#zeta-psi-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/chebyshev-psi', {
    bound: $('#zeta-psi-bound').value,
    zeros: Number($('#zeta-psi-zeros').value),
    precision: Number($('#zeta-psi-precision').value),
    threads: Number($('#zeta-psi-threads').value),
  }, (data) => `Chebyshev ψ(${data.bound}) from ${data.zeros} zeros`, 'convergence');
});

$('#zeta-riemann-siegel-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/riemann-siegel', {
    sigma: $('#zeta-rs-sigma').value, ordinate: $('#zeta-rs-t').value,
    terms: Number($('#zeta-rs-terms').value),
    precision: Number($('#zeta-rs-precision').value),
  }, (data) => `Riemann–Siegel remainder at ${data.sigma} + ${data.ordinate}i`, 'rsanalysis');
});

$('#zeta-euler-product-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/euler-product', {
    sigma: $('#zeta-euler-sigma').value, ordinate: $('#zeta-euler-t').value,
    primes: Number($('#zeta-euler-primes').value),
    precision: Number($('#zeta-euler-precision').value),
    threads: Number($('#zeta-euler-threads').value),
  }, (data) => `Euler product at ${data.sigma} + ${data.ordinate}i`, 'euler');
});

$('#zeta-spacing-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/zero-spacing', {
    start_index: $('#zeta-spacing-start').value,
    count: Number($('#zeta-spacing-count').value),
    bins: Number($('#zeta-spacing-bins').value),
    precision: Number($('#zeta-spacing-precision').value),
    threads: Number($('#zeta-spacing-threads').value),
  }, (data) => `Normalized spacings of ${data.samples + 1} certified zeros`, 'histogram');
});

$('#zeta-pair-correlation-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/pair-correlation', {
    start_index: $('#zeta-pair-start').value,
    count: Number($('#zeta-pair-count').value),
    bins: Number($('#zeta-pair-bins').value),
    window: Number($('#zeta-pair-window').value),
    precision: Number($('#zeta-pair-precision').value),
    threads: Number($('#zeta-pair-threads').value),
  }, (data) => `Pair correlation of ${data.samples} certified zeros`, 'histogram');
});

$('#zeta-gram-blocks-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/gram-blocks', {
    start_index: $('#zeta-blocks-start').value,
    count: Number($('#zeta-blocks-count').value),
    precision: Number($('#zeta-blocks-precision').value),
    threads: Number($('#zeta-blocks-threads').value),
  }, (data) => `Gram's law over ${data.count} indices`, 'gramblocks');
});

$('#zeta-backlund-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/backlund-s', {
    lower: $('#zeta-backlund-lower').value, upper: $('#zeta-backlund-upper').value,
    samples: Number($('#zeta-backlund-samples').value),
    precision: Number($('#zeta-backlund-precision').value),
    threads: Number($('#zeta-backlund-threads').value),
  }, (data) => `Zero-counting remainder S(${data.upper})`, 'backlund');
});

$('#zeta-characters-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/characters', {
    modulus: $('#zeta-characters-modulus').value,
    limit: Number($('#zeta-characters-limit').value),
  }, (data) => `Dirichlet characters modulo ${data.modulus}`, 'chartable');
});

$('#zeta-lfunction-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/l-function', {
    modulus: $('#zeta-lfunction-modulus').value,
    number: $('#zeta-lfunction-number').value,
    sigma: $('#zeta-lfunction-sigma').value,
    ordinate: $('#zeta-lfunction-t').value,
    precision: Number($('#zeta-lfunction-precision').value),
  }, (data) => `L(${data.sigma} + ${data.ordinate}i, χ_${data.modulus}(${data.number}))`, 'lvalue');
});

$('#zeta-lzeros-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/l-zeros', {
    modulus: $('#zeta-lzeros-modulus').value,
    number: $('#zeta-lzeros-number').value,
    lower: $('#zeta-lzeros-lower').value,
    upper: $('#zeta-lzeros-upper').value,
    samples: Number($('#zeta-lzeros-samples').value),
    precision: Number($('#zeta-lzeros-precision').value),
    threads: Number($('#zeta-lzeros-threads').value),
  }, (data) => `Critical-line search for χ_${data.modulus}(${data.number})`, 'lzeros');
});

$('#zeta-dedekind-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitZetaForm(event.currentTarget, '/api/zeta/dedekind', {
    family: $('#zeta-dedekind-family').value,
    parameter: $('#zeta-dedekind-parameter').value,
    polynomial: $('#zeta-dedekind-polynomial').value,
    sigma: $('#zeta-dedekind-sigma').value,
    ordinate: $('#zeta-dedekind-t').value,
    zero_height: Number($('#zeta-dedekind-height').value),
    zero_limit: Number($('#zeta-dedekind-limit').value),
    class_data: $('#zeta-dedekind-class').checked,
    precision: Number($('#zeta-dedekind-precision').value),
    timeout_seconds: Number($('#zeta-dedekind-timeout').value),
  }, (data) => `Dedekind zeta of ${data.polynomial}`, 'dedekind');
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


// --- Workspaces, searchable history, performance, notifications, cache ---------------
// Every number rendered here was computed by a native engine and stored locally;
// this code only formats and draws.

function renderRecordTable(target, columns, rows, emptyMessage) {
  const panel = $(target);
  panel.classList.remove('hidden');
  if (!rows.length) {
    panel.innerHTML = `<div class="empty">${escapeHtml(emptyMessage)}</div>`;
    return;
  }
  const head = columns.map((name) => `<th>${escapeHtml(name)}</th>`).join('');
  const body = rows
    .map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell ?? '')}</td>`).join('')}</tr>`)
    .join('');
  panel.innerHTML = `<table class="result-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

async function loadWorkspaces() {
  const container = $('#workspace-list');
  if (!container) return;
  try {
    const data = await api('/api/workspaces?limit=200');
    if (!data.workspaces.length) {
      container.innerHTML = '<div class="empty">No saved workspaces yet.</div>';
      return;
    }
    container.innerHTML = data.workspaces
      .map((row) => `
        <article class="workspace-card" data-workspace="${escapeHtml(row.id)}">
          <h3>${escapeHtml(row.name)}</h3>
          <p>${escapeHtml(row.notes || 'No notes')}</p>
          <p class="hint">${(row.job_ids || []).length} jobs · ${(row.report_files || []).length} reports · saved ${escapeHtml(row.created_at || '')}</p>
          <button type="button" class="workspace-delete" data-workspace="${escapeHtml(row.id)}">Delete</button>
        </article>`)
      .join('');
  } catch (error) {
    container.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
  }
}

if ($('#workspace-form')) {
  $('#workspace-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = $('#workspace-result');
    result.classList.remove('hidden');
    try {
      const payload = {
        name: $('#workspace-name').value.trim(),
        notes: $('#workspace-notes').value,
        job_ids: $('#workspace-include-jobs').checked ? state.jobs.map((job) => job.id) : [],
      };
      const saved = await api('/api/workspaces', { method: 'POST', body: JSON.stringify(payload) });
      result.innerHTML = `<div class="notice">Saved workspace “${escapeHtml(saved.name)}”.</div>`;
      $('#workspace-form').reset();
      await loadWorkspaces();
    } catch (error) {
      result.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });

  $('#workspace-list').addEventListener('click', async (event) => {
    const button = event.target.closest('.workspace-delete');
    if (!button) return;
    if (!window.confirm('Delete this workspace? Jobs and reports are not affected.')) return;
    try {
      await api(`/api/workspaces/${encodeURIComponent(button.dataset.workspace)}`, { method: 'DELETE' });
      await loadWorkspaces();
    } catch (error) {
      $('#workspace-result').classList.remove('hidden');
      $('#workspace-result').innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });
}

if ($('#history-search-form')) {
  $('#history-search-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const params = new URLSearchParams({ limit: '50' });
    const query = $('#history-query').value.trim();
    const status = $('#history-status').value;
    const engine = $('#history-engine').value.trim();
    if (query) params.set('q', query);
    if (status) params.set('status', status);
    if (engine) params.set('engine', engine);
    try {
      const [jobs, reports] = await Promise.all([
        api(`/api/jobs?${params.toString()}`),
        api(`/api/reports?${new URLSearchParams(query ? { q: query, limit: '50' } : { limit: '50' })}`),
      ]);
      const rows = jobs.map((job) => [
        job.id.slice(0, 12), job.expression, job.status, job.selected_backend || job.requested_backend,
        job.created_at,
      ]);
      const reportRows = (reports.reports || []).map((row) => [row.filename, row.kind, row.summary, row.created_at]);
      renderRecordTable('#history-search-result', ['job', 'input', 'status', 'engine', 'created'], rows,
        'No jobs matched.');
      if (reportRows.length) {
        const panel = $('#history-search-result');
        panel.insertAdjacentHTML('beforeend', '<h3>Saved reports</h3>');
        const table = document.createElement('div');
        panel.appendChild(table);
        const head = ['file', 'kind', 'summary', 'created'].map((n) => `<th>${escapeHtml(n)}</th>`).join('');
        const body = reportRows
          .map((row) => `<tr>${row.map((c) => `<td>${escapeHtml(c ?? '')}</td>`).join('')}</tr>`)
          .join('');
        table.innerHTML = `<table class="result-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
      }
    } catch (error) {
      $('#history-search-result').classList.remove('hidden');
      $('#history-search-result').innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });
}

function drawPerformance(buckets) {
  const canvas = $('#performance-canvas');
  if (!canvas) return;
  const context = canvas.getContext('2d');
  const style = getComputedStyle(document.body);
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!buckets.length) return;
  const margin = 48;
  const width = canvas.width - margin * 2;
  const height = canvas.height - margin * 2;
  const maxSeconds = Math.max(...buckets.map((row) => Number(row.average_seconds) || 0), 1);
  const barWidth = Math.max(6, Math.floor(width / Math.max(buckets.length, 1)) - 6);
  context.strokeStyle = style.getPropertyValue('--border') || '#888';
  context.beginPath();
  context.moveTo(margin, margin);
  context.lineTo(margin, margin + height);
  context.lineTo(margin + width, margin + height);
  context.stroke();
  context.fillStyle = style.getPropertyValue('--accent') || '#3b82f6';
  buckets.forEach((row, index) => {
    const value = Number(row.average_seconds) || 0;
    const barHeight = Math.round((value / maxSeconds) * height);
    const x = margin + index * (barWidth + 6) + 3;
    context.fillRect(x, margin + height - barHeight, barWidth, barHeight);
  });
  context.fillStyle = style.getPropertyValue('--text') || '#222';
  context.font = '12px system-ui, sans-serif';
  context.fillText(`peak mean ${maxSeconds.toFixed(2)} s`, margin, margin - 12);
}

if ($('#load-performance')) {
  $('#load-performance').addEventListener('click', async () => {
    try {
      const data = await api('/api/history/performance');
      const rows = data.buckets.map((row) => [
        row.engine, row.digit_bucket ?? row.bucket, row.jobs ?? row.count,
        Number(row.average_seconds ?? 0).toFixed(2), Number(row.total_seconds ?? 0).toFixed(2),
      ]);
      renderRecordTable('#performance-result',
        ['engine', 'digits', 'jobs', 'mean seconds', 'total seconds'], rows,
        'No completed jobs recorded yet.');
      $('#performance-result').insertAdjacentHTML('beforeend',
        `<p class="hint">${escapeHtml(data.note || '')}</p>`);
      drawPerformance(data.buckets);
    } catch (error) {
      $('#performance-result').classList.remove('hidden');
      $('#performance-result').innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });
}

const NOTIFY_KEY = 'numerisect-notify';
state.notifiedJobs = new Set();

function notifyStatus(message) {
  if ($('#notify-status')) $('#notify-status').textContent = message;
}

if ($('#notify-toggle')) {
  const toggle = $('#notify-toggle');
  const supported = 'Notification' in window;
  toggle.checked = supported && localStorage.getItem(NOTIFY_KEY) === '1';
  notifyStatus(supported
    ? (toggle.checked ? 'Notifications are on for this browser.' : 'Notifications are off.')
    : 'This browser does not support desktop notifications.');
  toggle.addEventListener('change', async () => {
    if (!supported) { toggle.checked = false; return; }
    if (toggle.checked) {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        toggle.checked = false;
        notifyStatus('The browser denied notification permission.');
        return;
      }
      localStorage.setItem(NOTIFY_KEY, '1');
      notifyStatus('Notifications are on for this browser.');
    } else {
      localStorage.removeItem(NOTIFY_KEY);
      notifyStatus('Notifications are off.');
    }
  });
}

function announceFinishedJobs(jobs) {
  if (!('Notification' in window)) return;
  if (localStorage.getItem(NOTIFY_KEY) !== '1' || Notification.permission !== 'granted') return;
  jobs.forEach((job) => {
    if (!['completed', 'failed', 'cancelled'].includes(job.status)) return;
    if (state.notifiedJobs.has(job.id)) return;
    state.notifiedJobs.add(job.id);
    new Notification(`Numerisect job ${job.status}`, {
      body: `${shortNumber(String(job.expression), 40)} · ${job.selected_backend || job.requested_backend || ''}`,
      tag: `numerisect-${job.id}`,
    });
  });
}

if ($('#cache-stats')) {
  $('#cache-stats').addEventListener('click', async () => {
    try {
      const data = await api('/api/cache');
      renderRecordTable('#cache-result', ['field', 'value'],
        Object.entries(data).map(([key, value]) => [key, String(value)]),
        'The cache is empty.');
    } catch (error) {
      $('#cache-result').classList.remove('hidden');
      $('#cache-result').innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });
  $('#cache-clear').addEventListener('click', async () => {
    try {
      const data = await api('/api/cache', { method: 'DELETE' });
      $('#cache-result').classList.remove('hidden');
      $('#cache-result').innerHTML = `<div class="notice">Removed ${escapeHtml(data.removed)} cached results.</div>`;
    } catch (error) {
      $('#cache-result').classList.remove('hidden');
      $('#cache-result').innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    }
  });
}

// --- Expert factorization laboratory --------------------------------------------------
// SQUFOF is computed by the numerisect-squfof C helper; every other operation here is
// computed by PARI/GP. This code only submits forms and renders returned values.

function renderFactorLab(title, rows, note, outputFile) {
  const panel = $('#factor-lab-result');
  panel.classList.remove('hidden');
  const table = rows.length
    ? `<table class="result-table"><tbody>${rows
        .map((row) => `<tr><th>${escapeHtml(row[0])}</th><td>${escapeHtml(row[1])}</td></tr>`)
        .join('')}</tbody></table>`
    : '<div class="empty">The engine returned no rows.</div>';
  const saved = outputFile
    ? `<p class="notice">Result saved automatically to <code>output/${escapeHtml(outputFile)}</code>
       · <a href="/api/outputs/${encodeURIComponent(outputFile)}" download>Download report</a></p>`
    : '';
  panel.innerHTML = `<h3>${escapeHtml(title)}</h3>${table}
    ${note ? `<p class="hint">${escapeHtml(note)}</p>` : ''}${saved}`;
}

function factorLabError(message) {
  const panel = $('#factor-lab-result');
  panel.classList.remove('hidden');
  panel.innerHTML = `<div class="error">${escapeHtml(message)}</div>`;
}

function bindFactorLab(formId, path, buildBody, buildRows, title) {
  const form = $(formId);
  if (!form) return;
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = form.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const data = await api(path, { method: 'POST', body: JSON.stringify(buildBody()) });
      renderFactorLab(title, buildRows(data), data.note, data.output_file);
    } catch (error) {
      factorLabError(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

bindFactorLab('#factor-lab-mersenne-form', '/api/factor-lab/mersenne-factors', () => ({
  exponent: Number($('#mersenne-exponent').value),
  k_limit: Number($('#mersenne-k').value),
  timeout_seconds: Number($('#mersenne-timeout').value),
}), (data) => Object.entries(data.metrics).concat(
  data.rows.map((row) => [`Factor q = ${row[0]}`, `k = ${row[1]}, ${row[2]} digits`]),
), 'Mersenne trial factoring');

const sieverForm = $('#factor-lab-sievers-form');
if (sieverForm) {
  sieverForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = sieverForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const data = await api('/api/factor-lab/sievers');
      const rows = Object.entries(data.metrics).concat(data.rows.map((row) => [row[0], row.slice(1).join(' · ')]));
      renderFactorLab('GGNFS lattice sievers', rows, data.note, data.output_file);
    } catch (error) {
      factorLabError(error.message);
    } finally {
      button.disabled = false;
    }
  });
}

bindFactorLab('#factor-lab-rsa-form', '/api/factor-lab/rsa-challenge', () => ({
  target: $('#rsa-target').value.trim(),
  prove_factors: $('#rsa-prove').value === '1',
  proof_seconds: Number($('#rsa-proof-seconds').value),
  timeout_seconds: Number($('#rsa-timeout').value),
}), (data) => data.rows, 'RSA Factoring Challenge');

// The catalogue is a plain listing rather than a computation, so it is a GET.
const rsaCatalogueButton = $('#rsa-catalogue-button');
if (rsaCatalogueButton) {
  rsaCatalogueButton.addEventListener('click', async () => {
    rsaCatalogueButton.disabled = true;
    try {
      const data = await api('/api/factor-lab/rsa-catalogue');
      renderFactorLab('RSA Factoring Challenge catalogue', data.rows, data.note, data.output_file);
    } catch (error) {
      factorLabError(error.message);
    } finally {
      rsaCatalogueButton.disabled = false;
    }
  });
}

bindFactorLab('#factor-lab-squfof-form', '/api/factor-lab/squfof', () => ({
  expression: $('#squfof-expression').value.trim(),
  max_iterations: Number($('#squfof-iterations').value),
  timeout_seconds: Number($('#squfof-timeout').value),
}), (data) => {
  const rows = [['Input', data.number], ['Status', data.status],
    ['Multiplier', data.multiplier], ['Iterations', data.iterations]];
  if (data.factor) rows.push(['Split', `${data.factor} × ${data.cofactor}`]);
  return rows;
}, 'SQUFOF');

bindFactorLab('#factor-lab-strategy-form', '/api/factor-lab/strategy', () => ({
  expression: $('#strategy-expression').value.trim(),
  pretest_level: Number($('#strategy-pretest').value),
  timeout_seconds: Number($('#strategy-timeout').value),
}), (data) => {
  const rows = [['Value', data.value], ['Digits', data.digits],
    ['Recommended engine', data.recommended_engine],
    ['Expected factor digits', data.expected_factor_digits || 'not estimated'],
    ['Basis', data.expected_basis]];
  (data.decision_path || []).forEach((step) => {
    rows.push([step.question, `${step.answer} — ${step.consequence}`]);
  });
  (data.small_factors || []).forEach((value) => rows.push(['Small factor', value]));
  return rows;
}, 'Strategy advice');

bindFactorLab('#factor-lab-special-form', '/api/factor-lab/special-form', () => ({
  expression: $('#special-form-expression').value.trim(),
  timeout_seconds: Number($('#special-form-timeout').value),
}), (data) => {
  const rows = [['Value', data.value], ['Digits', data.digits],
    ['SNFS suitable', data.snfs_suitable ? 'yes' : 'no']];
  if (data.snfs_polynomial) rows.push(['SNFS polynomial', data.snfs_polynomial]);
  if (data.snfs_difficulty) rows.push(['SNFS difficulty', data.snfs_difficulty]);
  (data.forms || []).forEach((row) => rows.push([`Form: ${row.kind}`, row.detail]));
  (data.algebraic_factors || []).forEach((row) =>
    rows.push(['Algebraic factor', `${row.factor} (${row.identity})`]));
  if (!data.complete) rows.push(['Search', 'incomplete — result is inconclusive']);
  return rows;
}, 'Special-form analysis');

bindFactorLab('#factor-lab-trace-form', '/api/factor-lab/trace', () => ({
  expression: $('#trace-expression').value.trim(),
  algorithm: $('#trace-algorithm').value,
  steps: Number($('#trace-steps').value),
  timeout_seconds: 120,
}), (data) => {
  const rows = [['Value', data.value], ['Algorithm', data.algorithm],
    ['Factor found', data.factor || 'none within the step limit']];
  if (data.truncated) rows.push(['Trace', 'truncated at the step limit']);
  (data.steps || []).forEach((step) =>
    rows.push([`Step ${step.step}`, `${step.state} · quantity ${step.quantity} · gcd ${step.gcd}`]));
  return rows;
}, 'Algorithm trace');

bindFactorLab('#factor-lab-certificates-form', '/api/factor-lab/certificates', () => ({
  factors: $('#certificate-factors').value.split(/\s+/).filter(Boolean),
  timeout_seconds: Number($('#certificate-timeout').value),
}), (data) => (data.certificates || []).map((row) => [
  row.factor,
  `prime: ${row.prime ? 'yes' : 'no'} · certified: ${row.certified ? 'yes' : 'no'} · independently verified: ${row.verified ? 'yes' : 'no'}`,
]), 'Batch primality certificates');


// --- Distributed CADO-NFS -------------------------------------------------------------
// CADO runs its own work-unit server and clients. This code only collects parameters,
// shows the exposure the engine's trust model implies, and starts the job.

function distributedRequest() {
  const lines = (id) => $(id).value.split(/\n+/).map((v) => v.trim()).filter(Boolean);
  const clientThreads = Number($('#dist-client-threads').value);
  return {
    expression: $('#dist-expression').value.trim(),
    address: $('#dist-address').value.trim(),
    port: Number($('#dist-port').value),
    whitelist: lines('#dist-whitelist'),
    ssl: $('#dist-ssl').checked,
    clients: Number($('#dist-clients').value),
    hostnames: lines('#dist-hostnames'),
    script_path: $('#dist-scriptpath').value.trim() || null,
    client_threads: clientThreads > 0 ? clientThreads : null,
  };
}

function renderExposure(payload, heading) {
  const exposure = payload.exposure || {};
  const rows = [
    ['Reaches other machines', exposure.local_only ? 'no, loopback only' : 'yes'],
    ['Bind address', `${exposure.bind_address}:${exposure.port}`],
    ['Transport', exposure.tls ? 'TLS, clients can pin the certificate' : 'clear text'],
    ['Client authentication', exposure.client_authentication],
    ['Whitelist', (exposure.whitelist || []).join(', ')],
    ['Worker hosts', (exposure.worker_hosts || []).join(', ') || 'this machine only'],
  ];
  const warnings = (payload.warnings || [])
    .map((w) => `<li>${escapeHtml(w)}</li>`).join('');
  const command = (payload.worker_command_template || []).join(' ');
  renderFactorLab(heading, rows, payload.note, payload.output_file);
  const panel = $('#factor-lab-result');
  if (warnings) {
    panel.insertAdjacentHTML('beforeend',
      `<div class="warning-note"><strong>Exposure warnings</strong><ul>${warnings}</ul></div>`);
  }
  if (command) {
    panel.insertAdjacentHTML('beforeend',
      `<p class="hint">Start a worker with:</p><pre><code>${escapeHtml(command)}</code></pre>`);
  }
}

if ($('#distributed-form')) {
  $('#dist-preview').addEventListener('click', async () => {
    try {
      const data = await api('/api/distributed/preview',
        { method: 'POST', body: JSON.stringify(distributedRequest()) });
      renderExposure(data, 'Distributed configuration preview');
    } catch (error) {
      factorLabError(error.message);
    }
  });

  $('#distributed-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    let preview;
    try {
      preview = await api('/api/distributed/preview',
        { method: 'POST', body: JSON.stringify(distributedRequest()) });
    } catch (error) {
      factorLabError(error.message);
      return;
    }
    const exposure = preview.exposure || {};
    const summary = exposure.local_only
      ? 'This run stays on this machine.'
      : `This run opens ${exposure.bind_address}:${exposure.port} to ${(exposure.whitelist || []).join(', ')}.`;
    const confirmed = window.confirm(
      `${summary}\n\nCADO clients do not authenticate to its server; the whitelist is `
      + `the only access control. Start the run?`);
    if (!confirmed) return;
    try {
      const data = await api('/api/distributed/factor', {
        method: 'POST',
        body: JSON.stringify({ ...distributedRequest(), confirm_network: true }),
      });
      renderExposure(data, 'Distributed run queued');
      await loadJobs();
    } catch (error) {
      factorLabError(error.message);
    }
  });
}


// --- Independent cross-engine verification and large-interval sieving ------------------
// The engines compute; this renders their answers side by side and makes any
// disagreement impossible to miss.

function showVerificationError(form, message) {
  placePrimeResult(form);
  $('#prime-result-title').textContent = 'Could not complete request';
  $('#prime-result-note').textContent = message;
  $('#prime-result-note').classList.remove('saved-output-note');
  $('#prime-result-content').innerHTML = '';
  $('#prime-result-panel').classList.remove('hidden');
  $('#prime-download').classList.add('hidden');
}

function renderAgreement(form, title, rows, payload) {
  placePrimeResult(form);
  $('#prime-result-title').textContent = title;
  $('#prime-result-note').textContent = payload.output_file
    ? `Result saved automatically to output/${payload.output_file}.` : '';
  $('#prime-result-note').classList.toggle('saved-output-note', Boolean(payload.output_file));
  $('#prime-result-panel').classList.remove('hidden');
  const panel = $('#prime-result-content');
  const table = `<table class="result-table"><thead><tr><th>Engine</th><th>Result</th><th>Seconds</th></tr></thead><tbody>${
    rows.map((r) => `<tr><td>${escapeHtml(r[0])}</td><td>${escapeHtml(r[1])}</td><td>${escapeHtml(r[2] ?? '')}</td></tr>`).join('')
  }</tbody></table>`;
  const banner = payload.agree
    ? `<div class="notice">${escapeHtml(payload.note)}</div>`
    : `<div class="error"><strong>Engines disagree.</strong> ${escapeHtml(payload.note)}</div>`;
  const saved = payload.output_file
    ? `<p class="notice">Result saved automatically to <code>output/${escapeHtml(payload.output_file)}</code>
       · <a href="/api/outputs/${encodeURIComponent(payload.output_file)}" download>Download report</a></p>`
    : '';
  panel.innerHTML = `<h3>${escapeHtml(title)}</h3>${banner}${table}${saved}`;
}

if ($('#verify-count-form')) {
  $('#verify-count-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const data = await api('/api/verify/prime-count', {
        method: 'POST',
        body: JSON.stringify({
          expression: $('#verify-count-x').value.trim(),
          threads: Number($('#verify-count-threads').value),
        }),
      });
      renderAgreement($('#verify-count-form'),
        `pi(${data.input}) from ${data.engines_answering} independent implementations`,
        data.sources.map((r) => [r.engine, r.value ?? (r.error || 'no answer'), r.seconds]),
        data);
    } catch (error) {
      showVerificationError($('#verify-count-form'), error.message);
    }
  });
}

if ($('#verify-primality-form')) {
  $('#verify-primality-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const data = await api('/api/verify/primality', {
        method: 'POST',
        body: JSON.stringify({ expression: $('#verify-primality-n').value.trim() }),
      });
      renderAgreement($('#verify-primality-form'),
        `Primality of ${data.input}`,
        data.sources.map((r) => [
          `${r.engine}${r.proof ? ' (proof)' : ' (probable)'}`,
          r.prime === null ? (r.error || 'no answer') : (r.prime ? 'prime' : 'composite'),
          r.seconds,
        ]),
        data);
    } catch (error) {
      showVerificationError($('#verify-primality-form'), error.message);
    }
  });
}

if ($('#sieve-interval-form')) {
  $('#sieve-interval-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const button = event.currentTarget.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      const data = await api('/api/primes/sieve-interval', {
        method: 'POST',
        body: JSON.stringify({
          start: $('#sieve-start').value.trim(),
          length: Number($('#sieve-length').value),
          threads: Number($('#sieve-threads').value),
          small_prime_bound: Number($('#sieve-bound').value),
          extra_rounds: Number($('#sieve-rounds').value),
          preview: 500,
        }),
      });
      placePrimeResult($('#sieve-interval-form'));
      $('#prime-result-title').textContent = 'Large-interval prime enumeration';
      $('#prime-result-note').textContent = `Result saved automatically to output/${data.output_file}.`;
      $('#prime-result-note').classList.add('saved-output-note');
      $('#prime-result-panel').classList.remove('hidden');
      const panel = $('#prime-result-content');
      const label = data.proven ? 'exact below 2^64' : 'probable primes (Baillie-PSW)';
      panel.innerHTML = `<h3>Primes in [${escapeHtml(data.start)}, +${escapeHtml(String(data.length))})</h3>
        <div class="${data.proven ? 'notice' : 'warning-note'}">${escapeHtml(data.note)}</div>
        <table class="result-table"><tbody>
          <tr><th>Found</th><td>${escapeHtml(String(data.count))} (${escapeHtml(label)})</td></tr>
          <tr><th>Survived presieve</th><td>${escapeHtml(String(data.candidates))}</td></tr>
          <tr><th>Threads</th><td>${escapeHtml(String(data.threads))}</td></tr>
        </tbody></table>
        <div class="prime-list">${data.primes.map((p) => `<code>${escapeHtml(p)}</code>`).join('')}</div>
        ${data.preview_truncated ? '<p class="hint">Showing the first results; the saved report holds every prime.</p>' : ''}
        <p class="notice">Result saved automatically to <code>output/${escapeHtml(data.output_file)}</code>
          · <a href="/api/outputs/${encodeURIComponent(data.output_file)}" download>Download report</a></p>`;
    } catch (error) {
      showVerificationError($('#sieve-interval-form'), error.message);
    } finally {
      button.disabled = false;
    }
  });
}

if ($('#run-self-test')) {
  $('#run-self-test').addEventListener('click', async (event) => {
    const button = event.currentTarget;
    const result = $('#diagnostic-result');
    button.disabled = true;
    result.classList.remove('hidden');
    result.innerHTML = '<div class="empty">Asking each engine its published test values…</div>';
    try {
      const data = await api('/api/verify/self-test', { method: 'POST', body: '{}' });
      const rows = data.results.map((r) => `<tr class="${r.status === 'FAIL' ? 'failed' : ''}">
        <td>${escapeHtml(r.engine)}</td><td>${escapeHtml(r.question)}</td>
        <td>${escapeHtml(r.status)}</td><td>${escapeHtml(r.expected)}</td>
        <td>${escapeHtml(r.actual)}</td><td>${escapeHtml(r.cites)}</td></tr>`).join('');
      result.innerHTML = `${data.healthy
        ? `<div class="notice">${escapeHtml(data.note)}</div>`
        : `<div class="error"><strong>${escapeHtml(data.note)}</strong></div>`}
        <table class="result-table"><thead><tr><th>Engine</th><th>Question</th><th>Status</th>
        <th>Expected</th><th>Actual</th><th>Published value</th></tr></thead>
        <tbody>${rows}</tbody></table>`;
    } catch (error) {
      result.innerHTML = `<div class="error">${escapeHtml(error.message)}</div>`;
    } finally {
      button.disabled = false;
    }
  });
}

async function initializeApplication() {
  const session = await api('/api/session');
  state.requestToken = session.request_token;
  await Promise.all([loadCapabilities(), loadJobs()]);
  state.poller = setInterval(async () => {
    await loadJobs();
  }, 1200);
  state.setupPoller = setInterval(async () => {
    try { renderSetup(await api('/api/setup')); } catch (_) { /* server may be restarting */ }
  }, 4000);
}

initializeApplication().catch((error) => {
  $('#engine-status').textContent = `Local session initialization failed: ${error.message}`;
});
