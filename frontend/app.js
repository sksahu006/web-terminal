/**
 * Virtual Workspace Platform - Frontend Application
 * Handles authentication, workspace management, and admin functionality
 */

// Configuration
const CONFIG = {
    API_BASE: window.location.origin,
    STORAGE_TOKEN_KEY: 'workspace_token',
    POLL_INTERVAL: 30000, // 30 seconds - less frequent to avoid terminal interference
};

// State
const state = {
    user: null,
    workspace: null,
    isAdmin: false,
    pollTimer: null,
    terminalUrl: null, // Track loaded terminal URL to prevent reloads
};

// DOM Elements
const elements = {
    // Sections
    loginSection: document.getElementById('login-section'),
    dashboardSection: document.getElementById('dashboard-section'),
    adminSection: document.getElementById('admin-section'),

    // Navigation
    navbar: document.getElementById('navbar'),
    navUser: document.getElementById('nav-user'),

    // Login
    btnLogin: document.getElementById('btn-login'),

    // Dashboard
    userWelcome: document.getElementById('user-welcome'),
    statusBadge: document.getElementById('status-badge'),
    noWorkspace: document.getElementById('no-workspace'),
    startingWorkspace: document.getElementById('starting-workspace'),
    runningWorkspace: document.getElementById('running-workspace'),
    btnStart: document.getElementById('btn-start'),
    btnStop: document.getElementById('btn-stop'),
    btnOpenTerminal: document.getElementById('btn-open-terminal'),
    containerName: document.getElementById('container-name'),
    timeRemaining: document.getElementById('time-remaining'),
    accessUrl: document.getElementById('access-url'),

    // Terminal
    terminalContainer: document.getElementById('terminal-container'),
    terminalIframe: document.getElementById('terminal-iframe'),
    btnFullscreen: document.getElementById('btn-fullscreen'),

    // Limits
    limitCpu: document.getElementById('limit-cpu'),
    limitMemory: document.getElementById('limit-memory'),
    limitDisk: document.getElementById('limit-disk'),
    limitRuntime: document.getElementById('limit-runtime'),

    // Admin
    statUsers: document.getElementById('stat-users'),
    statActive: document.getElementById('stat-active'),
    statToday: document.getElementById('stat-today'),
    usersTbody: document.getElementById('users-tbody'),

    // Modal
    editLimitsModal: document.getElementById('edit-limits-modal'),
    editLimitsForm: document.getElementById('edit-limits-form'),
    modalClose: document.getElementById('modal-close'),
    modalCancel: document.getElementById('modal-cancel'),
    editUserId: document.getElementById('edit-user-id'),
    editCpu: document.getElementById('edit-cpu'),
    editMemory: document.getElementById('edit-memory'),
    editDisk: document.getElementById('edit-disk'),
    editRuntime: document.getElementById('edit-runtime'),

    // Toast
    toastContainer: document.getElementById('toast-container'),
};

// API Functions
const api = {
    async request(endpoint, options = {}) {
        const token = localStorage.getItem(CONFIG.STORAGE_TOKEN_KEY);
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers,
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(`${CONFIG.API_BASE}${endpoint}`, {
                ...options,
                headers,
            });

            if (response.status === 401) {
                // Unauthorized - clear token and redirect to login
                localStorage.removeItem(CONFIG.STORAGE_TOKEN_KEY);
                showSection('login');
                throw new Error('Session expired');
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Request failed');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Auth
    async getMe() {
        return this.request('/auth/me');
    },

    async logout() {
        return this.request('/auth/logout', { method: 'POST' });
    },

    // Workspace
    async getWorkspaceStatus() {
        return this.request('/workspace/status');
    },

    async startWorkspace() {
        return this.request('/workspace/start', { method: 'POST', body: JSON.stringify({}) });
    },

    async stopWorkspace(force = false) {
        return this.request('/workspace/stop', { method: 'POST', body: JSON.stringify({ force }) });
    },

    // Admin
    async getAdminStats() {
        return this.request('/admin/stats');
    },

    async getUsers() {
        return this.request('/admin/users');
    },

    async getUserDetail(userId) {
        return this.request(`/admin/users/${userId}`);
    },

    async updateUserLimits(userId, limits) {
        return this.request(`/admin/users/${userId}/limits`, {
            method: 'PUT',
            body: JSON.stringify(limits),
        });
    },
};

// UI Functions
function showSection(section) {
    elements.loginSection.classList.add('hidden');
    elements.dashboardSection.classList.add('hidden');
    elements.adminSection.classList.add('hidden');

    switch (section) {
        case 'login':
            elements.loginSection.classList.remove('hidden');
            break;
        case 'dashboard':
            elements.dashboardSection.classList.remove('hidden');
            break;
        case 'admin':
            elements.adminSection.classList.remove('hidden');
            break;
    }
}

function updateNavbar() {
    if (state.user) {
        elements.navUser.innerHTML = `
            <div class="nav-links">
                <a href="#" class="nav-link active" data-section="dashboard">Dashboard</a>
                ${state.user.is_admin ? '<a href="#" class="nav-link" data-section="admin">Admin</a>' : ''}
            </div>
            <img src="${state.user.avatar_url || 'https://github.com/identicons/default.png'}" 
                 alt="Avatar" class="user-avatar">
            <span class="user-name">${state.user.github_username}</span>
            <button class="btn btn-secondary" id="btn-logout">Logout</button>
        `;

        // Add event listeners
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
                link.classList.add('active');
                showSection(link.dataset.section);

                if (link.dataset.section === 'admin') {
                    loadAdminData();
                }
            });
        });

        document.getElementById('btn-logout')?.addEventListener('click', handleLogout);
    } else {
        elements.navUser.innerHTML = '';
    }
}

function updateWorkspaceUI(status) {
    // Hide all states
    elements.noWorkspace.classList.add('hidden');
    elements.startingWorkspace.classList.add('hidden');
    elements.runningWorkspace.classList.add('hidden');
    elements.terminalContainer.classList.add('hidden');

    if (!status.has_active_workspace) {
        // No active workspace
        elements.statusBadge.textContent = 'Stopped';
        elements.statusBadge.className = 'status-badge stopped';
        elements.noWorkspace.classList.remove('hidden');
    } else {
        const workspace = status.workspace;
        state.workspace = workspace;

        if (workspace.status === 'starting') {
            elements.statusBadge.textContent = 'Starting...';
            elements.statusBadge.className = 'status-badge starting';
            elements.startingWorkspace.classList.remove('hidden');
        } else if (workspace.status === 'running') {
            elements.statusBadge.textContent = 'Running';
            elements.statusBadge.className = 'status-badge running';
            elements.runningWorkspace.classList.remove('hidden');
            elements.terminalContainer.classList.remove('hidden');

            // Update workspace info
            elements.containerName.textContent = workspace.container_name;
            elements.timeRemaining.textContent = formatTime(workspace.time_remaining_seconds);
            elements.accessUrl.href = workspace.access_url;
            elements.accessUrl.textContent = 'Open Terminal ↗';

            // Set terminal iframe source - only set once to avoid reload warnings
            if (!state.terminalUrl || state.terminalUrl !== workspace.access_url) {
                state.terminalUrl = workspace.access_url;
                elements.terminalIframe.src = workspace.access_url;
            }
        }
    }
}

function formatTime(seconds) {
    if (!seconds || seconds <= 0) return '0:00';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
        return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    }
    return `${minutes}:${String(secs).padStart(2, '0')}`;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 5000);
}

// Admin Functions
async function loadAdminData() {
    try {
        const [stats, usersData] = await Promise.all([
            api.getAdminStats(),
            api.getUsers(),
        ]);

        // Update stats
        elements.statUsers.textContent = stats.total_users;
        elements.statActive.textContent = stats.active_workspaces;
        elements.statToday.textContent = stats.total_workspaces_today;

        // Update users table
        elements.usersTbody.innerHTML = usersData.users.map(user => `
            <tr>
                <td>
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <img src="${user.avatar_url || 'https://github.com/identicons/default.png'}" 
                             style="width: 32px; height: 32px; border-radius: 50%;">
                        ${user.github_username}
                        ${user.is_admin ? '<span style="color: var(--accent-primary);">(Admin)</span>' : ''}
                    </div>
                </td>
                <td>${user.github_id}</td>
                <td data-user-cpu="${user.id}">--</td>
                <td data-user-memory="${user.id}">--</td>
                <td data-user-runtime="${user.id}">--</td>
                <td>
                    <button class="btn btn-secondary" onclick="openEditLimits('${user.id}')">
                        Edit Limits
                    </button>
                </td>
            </tr>
        `).join('');

        // Load limits for each user
        for (const user of usersData.users) {
            loadUserLimits(user.id);
        }
    } catch (error) {
        showToast('Failed to load admin data', 'error');
    }
}

async function loadUserLimits(userId) {
    try {
        const detail = await api.getUserDetail(userId);
        if (detail.limits) {
            const cpuCell = document.querySelector(`[data-user-cpu="${userId}"]`);
            const memCell = document.querySelector(`[data-user-memory="${userId}"]`);
            const runtimeCell = document.querySelector(`[data-user-runtime="${userId}"]`);

            if (cpuCell) cpuCell.textContent = detail.limits.cpu;
            if (memCell) memCell.textContent = `${detail.limits.memory} MB`;
            if (runtimeCell) runtimeCell.textContent = formatTime(detail.limits.max_runtime);
        }
    } catch (error) {
        console.error('Failed to load limits for user:', userId);
    }
}

window.openEditLimits = async function (userId) {
    try {
        const detail = await api.getUserDetail(userId);
        if (detail.limits) {
            elements.editUserId.value = userId;
            elements.editCpu.value = detail.limits.cpu;
            elements.editMemory.value = detail.limits.memory;
            elements.editDisk.value = detail.limits.disk;
            elements.editRuntime.value = detail.limits.max_runtime;
            elements.editLimitsModal.classList.remove('hidden');
        }
    } catch (error) {
        showToast('Failed to load user limits', 'error');
    }
};

function closeModal() {
    elements.editLimitsModal.classList.add('hidden');
}

// Event Handlers
async function handleLogin() {
    window.location.href = `${CONFIG.API_BASE}/auth/github`;
}

async function handleLogout() {
    try {
        await api.logout();
    } catch (error) {
        // Ignore errors
    }

    localStorage.removeItem(CONFIG.STORAGE_TOKEN_KEY);
    state.user = null;
    state.workspace = null;
    stopPolling();
    updateNavbar();
    showSection('login');
    showToast('Logged out successfully', 'success');
}

async function handleStartWorkspace() {
    try {
        elements.noWorkspace.classList.add('hidden');
        elements.startingWorkspace.classList.remove('hidden');
        elements.statusBadge.textContent = 'Starting...';
        elements.statusBadge.className = 'status-badge starting';

        const result = await api.startWorkspace();

        if (result.success) {
            showToast('Workspace started successfully!', 'success');
            await refreshWorkspaceStatus();
        } else {
            showToast(result.message || 'Failed to start workspace', 'error');
            await refreshWorkspaceStatus();
        }
    } catch (error) {
        showToast(error.message || 'Failed to start workspace', 'error');
        await refreshWorkspaceStatus();
    }
}

async function handleStopWorkspace() {
    if (!confirm('Are you sure you want to stop the workspace? Unsaved changes may be lost.')) {
        return;
    }

    try {
        const result = await api.stopWorkspace(false);

        if (result.success) {
            showToast('Workspace stopped', 'success');
            if (result.had_unsaved_changes) {
                showToast('Warning: There were uncommitted changes', 'warning');
            }
        }

        elements.terminalIframe.src = 'about:blank';
        state.terminalUrl = null;
        await refreshWorkspaceStatus();
    } catch (error) {
        showToast(error.message || 'Failed to stop workspace', 'error');
        await refreshWorkspaceStatus();
    }
}

async function handleEditLimitsSubmit(e) {
    e.preventDefault();

    const userId = elements.editUserId.value;
    const limits = {
        cpu: parseFloat(elements.editCpu.value),
        memory: parseInt(elements.editMemory.value),
        disk: parseInt(elements.editDisk.value),
        max_runtime: parseInt(elements.editRuntime.value),
    };

    try {
        await api.updateUserLimits(userId, limits);
        showToast('Limits updated successfully', 'success');
        closeModal();
        loadAdminData();
    } catch (error) {
        showToast(error.message || 'Failed to update limits', 'error');
    }
}

// Polling
async function refreshWorkspaceStatus() {
    try {
        const status = await api.getWorkspaceStatus();
        updateWorkspaceUI(status);
    } catch (error) {
        console.error('Failed to refresh workspace status:', error);
    }
}

function startPolling() {
    if (state.pollTimer) return;

    state.pollTimer = setInterval(async () => {
        if (state.workspace?.status === 'running' || state.workspace?.status === 'starting') {
            await refreshWorkspaceStatus();
        }
    }, CONFIG.POLL_INTERVAL);
}

function stopPolling() {
    if (state.pollTimer) {
        clearInterval(state.pollTimer);
        state.pollTimer = null;
    }
}

// Initialize
async function init() {
    // Check for OAuth callback
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');

    if (token) {
        localStorage.setItem(CONFIG.STORAGE_TOKEN_KEY, token);
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    // Try to load user
    const storedToken = localStorage.getItem(CONFIG.STORAGE_TOKEN_KEY);

    if (storedToken) {
        try {
            state.user = await api.getMe();
            updateNavbar();
            showSection('dashboard');

            // Load workspace status
            await refreshWorkspaceStatus();
            startPolling();

            // Update welcome message
            elements.userWelcome.textContent = `Welcome back, ${state.user.github_username}!`;

            // Load user limits display (we don't have a direct endpoint, so use default values)
            elements.limitCpu.textContent = '1.0';
            elements.limitMemory.textContent = '1024 MB';
            elements.limitDisk.textContent = '5 GB';
            elements.limitRuntime.textContent = '1 hour';

        } catch (error) {
            console.error('Failed to load user:', error);
            localStorage.removeItem(CONFIG.STORAGE_TOKEN_KEY);
            showSection('login');
        }
    } else {
        showSection('login');
    }

    // Event listeners
    elements.btnLogin.addEventListener('click', handleLogin);
    elements.btnStart.addEventListener('click', handleStartWorkspace);
    elements.btnStop.addEventListener('click', handleStopWorkspace);
    elements.btnOpenTerminal.addEventListener('click', () => {
        if (state.workspace?.access_url) {
            window.open(state.workspace.access_url, '_blank');
        }
    });
    elements.btnFullscreen.addEventListener('click', () => {
        elements.terminalIframe.requestFullscreen?.();
    });

    elements.modalClose.addEventListener('click', closeModal);
    elements.modalCancel.addEventListener('click', closeModal);
    elements.editLimitsForm.addEventListener('submit', handleEditLimitsSubmit);
    elements.editLimitsModal.querySelector('.modal-backdrop').addEventListener('click', closeModal);
}

// Handle auth callback path
if (window.location.pathname === '/auth/callback') {
    init();
} else {
    document.addEventListener('DOMContentLoaded', init);
}
