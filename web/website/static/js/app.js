'use strict';

let authToken = null;
let currentProfile = null;   // last loaded { username, role, profile }

// ── Small helpers ────────────────────────────────────────────
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
    if (!el) return;
    el.textContent = '';
    el.className = 'msg';
}

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function initials(name) {
    return (name || '?').trim().slice(0, 2).toUpperCase();
}

async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    const data = await res.json().catch(() => ({}));
    return { ok: res.ok, data };
}

// ── Auth tab switching (login / register) ────────────────────
function showPanel(name) {
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelector(`.panel[data-panel="${name}"]`).classList.add('active');
    document.getElementById('card').dataset.view = name;
}
document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => showPanel(btn.dataset.target));
});

// ── Role toggle (register) ───────────────────────────────────
let selectedRole = 'player';
document.querySelectorAll('.role-toggle .role-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        selectedRole = btn.dataset.role;
        document.querySelectorAll('.role-toggle .role-btn').forEach(b => {
            const active = b === btn;
            b.classList.toggle('active', active);
            b.setAttribute('aria-checked', active ? 'true' : 'false');
        });
        document.getElementById('player-fields').hidden = selectedRole !== 'player';
        document.getElementById('scout-fields').hidden = selectedRole !== 'scout';
        clearMsg('register-msg');
    });
});

function collectPlayerProfile() {
    const profile = {};
    document.querySelectorAll('#player-fields [data-field]').forEach(el => {
        const field = el.dataset.field;
        if (field === 'position') {
            profile[field] = el.value;
        } else {
            const v = el.value.trim();
            profile[field] = v === '' ? null : Number(v);
        }
    });
    return profile;
}

function collectScoutProfile() {
    return {
        org: document.getElementById('reg-org').value.trim(),
        need: document.getElementById('reg-need').value.trim(),
    };
}

// ── Auth modal open / close ──────────────────────────────────
function openAuth() {
    showPanel('login');
    document.getElementById('auth-modal').hidden = false;
    setTimeout(() => document.getElementById('login-username').focus(), 50);
}

function closeAuth() {
    document.getElementById('auth-modal').hidden = true;
    clearMsg('login-msg');
    clearMsg('register-msg');
}

// Reflect signed-in vs signed-out across the shell. The Feed stays the landing
// page in both states; only the sign-in button, profile content and status
// badge change.
function setAuthed(on) {
    document.getElementById('signin-btn').hidden = on;
    document.getElementById('profile-guest').hidden = on;
    document.getElementById('profile-authed').hidden = !on;
    if (on) showStatus(); else hideStatus();
}

document.getElementById('signin-btn').addEventListener('click', openAuth);
document.getElementById('profile-signin-btn').addEventListener('click', openAuth);
document.getElementById('auth-close').addEventListener('click', closeAuth);
document.getElementById('auth-backdrop').addEventListener('click', closeAuth);
document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && !document.getElementById('auth-modal').hidden) closeAuth();
});

// ── Persistent nav ───────────────────────────────────────────
const PAGE_TITLES = { feed: 'Feed', search: 'Search', dm: 'Messages', profile: 'Profile' };

function navigate(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.dataset.page === page));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.nav === page));
    document.getElementById('page-title').textContent = PAGE_TITLES[page] || '';
    document.querySelector('.app-content').scrollTop = 0;

    if (page === 'search') {
        // Focusing the field pops the mobile keyboard — "search opens, then type".
        setTimeout(() => document.getElementById('search-input').focus(), 50);
    }
    if (page === 'profile') {
        exitEditMode();
    }
}

document.querySelectorAll('.nav-item').forEach(btn => {
    btn.addEventListener('click', () => navigate(btn.dataset.nav));
});

// ── Login ────────────────────────────────────────────────────
document.getElementById('login-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('login-btn');
    const username = document.getElementById('login-username').value.trim();
    const password = document.getElementById('login-password').value;

    clearMsg('login-msg');
    setLoading(btn, true);
    try {
        const { ok, data } = await apiFetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
        });
        if (!ok) {
            showMsg('login-msg', data?.error?.message ?? 'Login failed.', true);
            return;
        }
        authToken = data.token;
        await loadProfile();
        setAuthed(true);
        closeAuth();
        navigate('profile');
    } catch {
        showMsg('login-msg', 'Network error — please try again.', true);
    } finally {
        setLoading(btn, false);
    }
});

// ── Register ─────────────────────────────────────────────────
document.getElementById('register-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('register-btn');
    const username = document.getElementById('reg-username').value.trim();
    const password = document.getElementById('reg-password').value;
    const profile = selectedRole === 'player' ? collectPlayerProfile() : collectScoutProfile();

    clearMsg('register-msg');
    setLoading(btn, true);
    try {
        const { ok, data } = await apiFetch('/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, role: selectedRole, profile }),
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
            method: 'POST',
            headers: { 'Authorization': `Bearer ${authToken}` },
        });
    } catch {
        // sign out locally even on network failure
    } finally {
        authToken = null;
        currentProfile = null;
        document.getElementById('login-username').value = '';
        document.getElementById('login-password').value = '';
        document.getElementById('profile-view').innerHTML = '';
        document.getElementById('composer-avatar').textContent = '?';
        exitEditMode();
        setAuthed(false);
        navigate('feed');
        setLoading(btn, false);
    }
});

// ── Profile: view rendering ──────────────────────────────────
function row(label, value) {
    return `<div class="profile-row">
        <span class="profile-key">${escapeHtml(label)}</span>
        <span class="profile-val">${escapeHtml(String(value))}</span>
    </div>`;
}

function renderPlayerProfile(p) {
    const stats = p.stats || {};
    const order = ['PTS', 'REB', 'AST', 'FG_pct', '3PT_pct', 'usage', 'defensive_rating'];
    const labels = {
        PTS: 'PTS', REB: 'REB', AST: 'AST', FG_pct: 'FG%',
        '3PT_pct': '3PT%', usage: 'Usage', defensive_rating: 'Def. rating',
    };
    let html = '';
    if (p.archetype) {
        html += `<div class="archetype-badge">
            <span class="archetype-label">Archetype</span>
            <span class="archetype-name">${escapeHtml(p.archetype)}</span>
        </div>`;
    }
    html += '<div class="profile-rows">';
    if (p.position) html += row('Position', p.position);
    if ('height' in stats) html += row('Height', stats.height);
    order.forEach(k => { if (k in stats) html += row(labels[k], stats[k]); });
    html += '</div>';
    return html;
}

function renderScoutProfile(p) {
    let html = '<div class="profile-rows">';
    if (p.org) html += row('Organization', p.org);
    if (p.need) html += row('Saved need', p.need);
    html += '</div>';
    return html;
}

async function loadProfile() {
    const { ok, data } = await apiFetch('/profile', {
        headers: { 'Authorization': `Bearer ${authToken}` },
    });
    if (!ok) {
        document.getElementById('profile-view').innerHTML =
            '<p class="msg msg--error">Could not load profile.</p>';
        return;
    }
    renderProfileData(data);
}

function renderProfileData(data) {
    currentProfile = data;

    document.getElementById('username-display').textContent = data.username;
    document.getElementById('profile-avatar').textContent = initials(data.username);
    document.getElementById('composer-avatar').textContent = initials(data.username);
    const chip = document.getElementById('role-chip');
    chip.textContent = data.role;
    chip.dataset.role = data.role;

    const p = data.profile || {};
    document.getElementById('profile-view').innerHTML =
        data.role === 'scout' ? renderScoutProfile(p) : renderPlayerProfile(p);

    const extra = document.getElementById('profile-extra');
    if (data.role === 'player') {
        extra.innerHTML = '';
        loadExtras();
    } else {
        extra.innerHTML = '';   // comparables/interest are player-only
    }
}

// Reverse-match interest + KNN comparables (players only). Fetched together and
// rendered under the profile stats.
async function loadExtras() {
    const extra = document.getElementById('profile-extra');
    const [interest, comps] = await Promise.all([
        apiFetch('/profile/interest', { headers: { 'Authorization': `Bearer ${authToken}` } }),
        apiFetch('/profile/comparables', { headers: { 'Authorization': `Bearer ${authToken}` } }),
    ]);

    let html = '';
    if (interest.ok) {
        const n = interest.data.count;
        html += `<div class="interest-callout">
            <span class="interest-num">${n}</span>
            scout${n === 1 ? '' : 's'} ${n === 1 ? 'is' : 'are'} looking for a profile like yours
        </div>`;
    }
    if (comps.ok && Array.isArray(comps.data.comparables)) {
        html += '<p class="section-label">Comparable players</p><div class="profile-rows">';
        comps.data.comparables.forEach(c => {
            html += `<div class="profile-row">
                <span class="profile-key">${escapeHtml(c.name)}</span>
                <span class="profile-val">${Number(c.distance).toFixed(2)}</span>
            </div>`;
        });
        html += '</div>';
    }
    extra.innerHTML = html;
}

// Collect edit-form fields (data-edit) back into a profile payload for PATCH.
function collectEditProfile(role) {
    if (role === 'scout') {
        return {
            org: document.querySelector('[data-edit="org"]').value.trim(),
            need: document.querySelector('[data-edit="need"]').value.trim(),
        };
    }
    const profile = {};
    document.querySelectorAll('#edit-player-fields [data-edit]').forEach(el => {
        const f = el.dataset.edit;
        if (f === 'position') {
            profile[f] = el.value;
        } else {
            const v = el.value.trim();
            profile[f] = v === '' ? null : Number(v);
        }
    });
    return profile;
}

// ── Profile: edit mode (interface only — Save does not persist yet) ──
function enterEditMode() {
    if (!currentProfile) return;
    const isScout = currentProfile.role === 'scout';
    document.getElementById('edit-player-fields').hidden = isScout;
    document.getElementById('edit-scout-fields').hidden = !isScout;

    const p = currentProfile.profile || {};
    if (isScout) {
        setEdit('org', p.org ?? '');
        setEdit('need', p.need ?? '');
    } else {
        const stats = p.stats || {};
        setEdit('position', p.position ?? 'SF');
        ['height', 'PTS', 'REB', 'AST', 'FG_pct', '3PT_pct', 'usage', 'defensive_rating']
            .forEach(k => setEdit(k, stats[k] ?? ''));
    }
    clearMsg('edit-msg');
    document.getElementById('profile-view-wrap').hidden = true;
    document.getElementById('profile-edit').hidden = false;
}

function exitEditMode() {
    document.getElementById('profile-edit').hidden = true;
    document.getElementById('profile-view-wrap').hidden = false;
}

function setEdit(field, value) {
    const el = document.querySelector(`[data-edit="${field}"]`);
    if (el) el.value = value;
}

document.getElementById('edit-profile-btn').addEventListener('click', enterEditMode);
document.getElementById('cancel-edit-btn').addEventListener('click', exitEditMode);
document.getElementById('profile-edit').addEventListener('submit', async e => {
    e.preventDefault();
    if (!currentProfile) return;
    const btn = document.getElementById('save-profile-btn');
    const payload = collectEditProfile(currentProfile.role);

    clearMsg('edit-msg');
    setLoading(btn, true);
    try {
        const { ok, data } = await apiFetch('/profile', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${authToken}` },
            body: JSON.stringify(payload),
        });
        if (!ok) {
            showMsg('edit-msg', data?.error?.message ?? 'Could not save changes.', true);
            return;
        }
        renderProfileData(data);   // refresh view + comparables/interest
        exitEditMode();
    } catch {
        showMsg('edit-msg', 'Network error — please try again.', true);
    } finally {
        setLoading(btn, false);
    }
});

// ── Status badge ─────────────────────────────────────────────
const statusBadge = document.getElementById('status-badge');
const statusDot = document.getElementById('status-dot');
const statusHealth = document.getElementById('status-health');
const statUptime = document.getElementById('stat-uptime');
const statSuccess = document.getElementById('stat-success');
const statFail = document.getElementById('stat-fail');
const statusRefresh = document.getElementById('status-refresh');

function formatUptime(secs) {
    const s = Math.floor(secs);
    if (s < 60) return `${s}s`;
    if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60}s`;
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    return `${h}h ${m}m`;
}

async function fetchStatus() {
    statusDot.className = 'status-dot fetching';
    statusRefresh.classList.add('refreshing');
    try {
        const { ok, data } = await apiFetch('/status');
        if (!ok || !data.status) {
            statusDot.className = 'status-dot error';
            statusHealth.textContent = 'error';
            return;
        }
        const s = data.status;
        const healthy = s.health === 'ok';
        statusDot.className = `status-dot ${healthy ? 'ok' : 'error'}`;
        statusHealth.textContent = s.health;
        statUptime.textContent = formatUptime(s.uptime);
        statSuccess.textContent = `✓ ${s.processed.success}`;
        statFail.textContent = `✗ ${s.processed.fail}`;
    } catch {
        statusDot.className = 'status-dot error';
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
    statusBadge.style.animation = 'none';
    requestAnimationFrame(() => { statusBadge.style.animation = ''; });
}

statusRefresh.addEventListener('click', fetchStatus);

// ── Initial state: signed-out, landing on Feed ───────────────
setAuthed(false);
navigate('feed');
