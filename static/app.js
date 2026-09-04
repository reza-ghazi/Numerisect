const state = { jobs: [], selectedId: null, poller: null, logOpen: false };

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

document.querySelectorAll('.mode-tab').forEach((button) => {
  button.addEventListener('click', () => {
    document.querySelectorAll('.mode-tab').forEach((tab) => tab.classList.remove('active'));
    document.querySelectorAll('.tool-view').forEach((view) => view.classList.add('hidden'));
    button.classList.add('active');
    $(`#${button.dataset.view}`).classList.remove('hidden');
  });
});

function showPrimeResult(title, data, type) {
  const panel = $('#prime-result-panel');
  const content = $('#prime-result-content');
  $('#prime-result-title').textContent = title;
  let note = data.note || '';
  if (data.truncated) note += `${note ? ' ' : ''}Display/export stopped at the requested limit. Continue from ${data.next_start}.`;
  $('#prime-result-note').textContent = note;
  if (type === 'check') {
    content.innerHTML = `<div class="prime-verdict"><strong>${escapeHtml(data.classification)}</strong><code>${escapeHtml(data.number)}</code></div>`;
  } else if (type === 'tuples') {
    const shown = data.tuples.slice(0, 2000);
    content.innerHTML = shown.map((tuple) => `<div class="prime-chip tuple">${tuple.map(escapeHtml).join(' &nbsp; · &nbsp; ')}</div>`).join('') || '<div class="empty">No matching tuples in this interval.</div>';
    if (data.tuples.length > shown.length) $('#prime-result-note').textContent += ` Showing the first ${shown.length.toLocaleString()} in the browser.`;
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

async function submitPrimeForm(form, path, payload, title, type) {
  const button = form.querySelector('button[type="submit"]');
  button.disabled = true;
  const oldText = button.firstElementChild.textContent;
  button.firstElementChild.textContent = 'Working…';
  try {
    const data = await api(path, { method: 'POST', body: JSON.stringify(payload) });
    showPrimeResult(title(data), data, type);
  } catch (error) {
    $('#prime-result-title').textContent = 'Could not complete request';
    $('#prime-result-note').textContent = error.message;
    $('#prime-result-content').innerHTML = '';
    $('#prime-result-panel').classList.remove('hidden');
    $('#prime-download').classList.add('hidden');
  } finally {
    button.disabled = false;
    button.firstElementChild.textContent = oldText;
  }
}

$('#prime-check-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/check',
    { expression: $('#prime-check-input').value },
    (data) => `${data.digits}-digit input`, 'check');
});

$('#prime-generate-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/generate', {
    count: Number($('#prime-count').value), digits: Number($('#prime-digits').value)
  }, (data) => `${data.count.toLocaleString()} generated primes`, 'list');
});

$('#prime-after-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/after', {
    start: $('#prime-after-start').value, count: Number($('#prime-after-count').value)
  }, (data) => `${data.count.toLocaleString()} primes after ${shortNumber(data.start, 24)}`, 'list');
});

$('#prime-range-form').addEventListener('submit', (event) => {
  event.preventDefault();
  submitPrimeForm(event.currentTarget, '/api/primes/range', {
    start: $('#prime-range-start').value,
    end: $('#prime-range-end').value,
    limit: Number($('#prime-range-limit').value)
  }, (data) => `${data.count.toLocaleString()} primes in range`, 'list');
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

loadCapabilities();
loadJobs();
state.poller = setInterval(async () => {
  await loadJobs();
}, 1200);
setInterval(async () => {
  try { renderSetup(await api('/api/setup')); } catch (_) { /* server may be restarting */ }
}, 4000);
