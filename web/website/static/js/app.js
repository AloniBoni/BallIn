'use strict';

let authToken    = null;
let selectedFile = null;
let previewURL   = null;

// ── Panel switching ──────────────────────────────────────────
function showPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelector(`.panel[data-panel="${name}"]`).classList.add('active');
    document.getElementById('card').dataset.view = name;
}

document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => showPanel(btn.dataset.target));
});

// ── UI helpers ───────────────────────────────────────────────
function setLoading(btn, on) {
    btn.disabled = on;
    btn.classList.toggle('loading', on);
}

function showMsg(id, text, isError) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = 'msg ' + (isError ? 'msg--error' : 'msg--ok');
}

function clearMsg(id) {
    const el = document.getElementById(id);
    el.textContent = '';
    el.className = 'msg';
}

// ── API helper (no token logging) ────────────────────────────
async function apiFetch(url, options = {}) {
    const res  = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
}

// ── Login ────────────────────────────────────────────────────
document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn      = document.getElementById('login-btn');
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    clearMsg('login-msg');
    setLoading(btn, true);
    try {
        const { ok, data } = await apiFetch('/login', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ username, password }),
        });
        if (!ok) {
            showMsg('login-msg', data?.error?.message ?? 'Login failed.', true);
            return;
        }
        authToken = data.token;
        document.getElementById('username-display').textContent = username;
        showPanel('loggedin');
        showStatus();          // fetch + show status badge on login
    } catch {
        showMsg('login-msg', 'Network error — please try again.', true);
    } finally {
        setLoading(btn, false);
    }
});

// ── Register ─────────────────────────────────────────────────
document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn      = document.getElementById('register-btn');
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;

    clearMsg('register-msg');
    setLoading(btn, true);
    try {
        const { ok, data } = await apiFetch('/register', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ username, password }),
        });
        if (!ok) {
            showMsg('register-msg', data?.error?.message ?? 'Registration failed.', true);
            return;
        }
        showMsg('register-msg', 'Account created — sign in below.', false);
        setTimeout(() => { clearMsg('register-msg'); showPanel('login'); }, 1400);
    } catch {
        showMsg('register-msg', 'Network error — please try again.', true);
    } finally {
        setLoading(btn, false);
    }
});

// ── Logout ───────────────────────────────────────────────────
document.getElementById('logout-btn').addEventListener('click', async () => {
    const btn = document.getElementById('logout-btn');
    setLoading(btn, true);
    try {
        await apiFetch('/logout', {
            method:  'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
    } catch {
        // sign out locally even on network failure
    } finally {
        authToken = null;
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
        resetClassifier();
        hideStatus();          // remove badge on logout
        showPanel('login');
        setLoading(btn, false);
    }
});

// ── Classifier: file handling ────────────────────────────────
const dropZone     = document.getElementById('drop-zone');
const fileInput    = document.getElementById('file-input');
const placeholder  = document.getElementById('drop-placeholder');
const preview      = document.getElementById('drop-preview');
const previewThumb = document.getElementById('preview-thumb');
const classifyBtn  = document.getElementById('classify-btn');

const ALLOWED_TYPES = new Set(['image/png', 'image/jpeg']);

function handleFile(file) {
    if (previewURL) URL.revokeObjectURL(previewURL);
    selectedFile = file;
    previewURL   = URL.createObjectURL(file);

    previewThumb.src   = previewURL;
    placeholder.hidden = true;
    preview.hidden     = false;

    classifyBtn.disabled = false;
    clearResults();

    // The server is the authoritative validator: unsupported files are still
    // sent so they produce a real failure (counted in /status). Hint, don't block.
    if (!ALLOWED_TYPES.has(file.type)) {
        showMsg('classify-msg',
            'This is not a .png/.jpeg image — the server will reject it (failure case).',
            true);
    } else {
        clearMsg('classify-msg');
    }
}

dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) handleFile(fileInput.files[0]);
    fileInput.value = '';
});

dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});

dropZone.addEventListener('dragleave', e => {
    if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove('drag-over');
});

dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
});

// ── Classifier: results ──────────────────────────────────────
function clearResults() {
    const r = document.getElementById('results');
    r.innerHTML = '';
    r.hidden    = true;
    document.getElementById('analyzing').hidden = true;
}

function resetClassifier() {
    clearResults();
    clearMsg('classify-msg');
    if (previewURL) { URL.revokeObjectURL(previewURL); previewURL = null; }
    selectedFile         = null;
    placeholder.hidden   = false;
    preview.hidden       = true;
    previewThumb.src     = '';
    classifyBtn.disabled = true;
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function renderResults(matches) {
    const container = document.getElementById('results');
    container.innerHTML = '';

    const sorted = [...matches].sort((a, b) => b.score - a.score).slice(0, 5);

    const heading = document.createElement('p');
    heading.className   = 'results-heading';
    heading.textContent = 'Top matches';
    container.appendChild(heading);

    sorted.forEach((m, i) => {
        const pct = (m.score * 100).toFixed(1);
        const row = document.createElement('div');
        row.className = 'result-row';
        row.style.setProperty('--delay', `${i * 0.07}s`);
        row.innerHTML = `
            <div class="result-meta">
                <span class="result-label">${escapeHtml(m.name)}</span>
                <span class="result-pct">${pct}%</span>
            </div>
            <div class="result-track">
                <div class="result-bar" style="--w:${pct}%"></div>
            </div>`;
        container.appendChild(row);
    });

    container.hidden = false;
}

// ── Classifier: submit ───────────────────────────────────────
classifyBtn.addEventListener('click', async () => {
    if (!selectedFile) return;

    clearMsg('classify-msg');
    clearResults();
    document.getElementById('analyzing').hidden = false;
    setLoading(classifyBtn, true);

    try {
        const form = new FormData();
        form.append('image', selectedFile);

        const { ok, data } = await apiFetch('/classifier', {
            method:  'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
            body:    form,
        });

        document.getElementById('analyzing').hidden = true;

        if (!ok) {
            showMsg('classify-msg', data?.error?.message ?? 'Classification failed.', true);
        } else {
            renderResults(data.matches ?? []);
        }
    } catch {
        document.getElementById('analyzing').hidden = true;
        showMsg('classify-msg', 'Network error — please try again.', true);
    } finally {
        setLoading(classifyBtn, false);
        fetchStatus();         // always refresh counts after a classify attempt
    }
});

// ── Status panel ─────────────────────────────────────────────
const statusBadge   = document.getElementById('status-badge');
const statusDot     = document.getElementById('status-dot');
const statusHealth  = document.getElementById('status-health');
const statUptime    = document.getElementById('stat-uptime');
const statSuccess   = document.getElementById('stat-success');
const statFail      = document.getElementById('stat-fail');
const statusRefresh = document.getElementById('status-refresh');

function formatUptime(secs) {
    const s = Math.floor(secs);
    if (s < 60)   return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
}

async function fetchStatus() {
    statusDot.className = 'status-dot fetching';
    statusRefresh.classList.add('refreshing');
    try {
        const { ok, data } = await apiFetch('/status', {
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
        if (!ok || !data.status) {
            statusDot.className      = 'status-dot error';
            statusHealth.textContent = 'error';
            return;
        }
        const s       = data.status;
        const healthy = s.health === 'ok';
        statusDot.className      = `status-dot ${healthy ? 'ok' : 'error'}`;
        statusHealth.textContent = s.health;
        statUptime.textContent   = formatUptime(s.uptime);
        statSuccess.textContent  = `✓ ${s.processed.success}`;
        statFail.textContent     = `✗ ${s.processed.fail}`;
    } catch {
        statusDot.className      = 'status-dot error';
        statusHealth.textContent = 'offline';
    } finally {
        statusRefresh.classList.remove('refreshing');
    }
}

function showStatus() {
    statusBadge.removeAttribute('hidden');
    fetchStatus();
}

function hideStatus() {
    statusBadge.setAttribute('hidden', '');
    // re-arm the entrance animation for next login
    statusBadge.style.animation = 'none';
    requestAnimationFrame(() => { statusBadge.style.animation = ''; });
}

statusRefresh.addEventListener('click', fetchStatus);
