/**
 * MedTracker - iOS Style Frontend
 * Apple-like interface for FastAPI backend
 */

// Disable browser scroll restoration so refresh always starts at the top
if ('scrollRestoration' in history) {
    history.scrollRestoration = 'manual';
}
window.scrollTo(0, 0);

// ============================================
// STATE MANAGEMENT
// ============================================
const state = {
    currentView: 'home',
    medications: [],
    logs: [],
    stats: null,
    chatbotInitialized: false,
    chatHistory: [],
    userMedications: []
};

// ============================================
// API ENDPOINTS
// ============================================
const API = {
    base: '',
    
    // Health
    health: () => fetch('/api/health').then(r => r.json()),
    
    // Medications
    getMedications: () => fetch('/medications/').then(r => r.json()),
    createMedication: (data) => fetch('/medications/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),
    updateMedication: (id, data) => fetch(`/medications/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),
    deleteMedication: (id) => fetch(`/medications/${id}`, {
        method: 'DELETE'
    }).then(r => r.json()),
    toggleMedication: (id) => fetch(`/medications/${id}/toggle`, {
        method: 'POST'
    }).then(r => r.json()),
    
    // Logs
    getLogs: () => fetch('/logs/').then(r => r.json()),
    getLogsByMedication: (medId) => fetch(`/logs/medication/${medId}`).then(r => r.json()),
    logDose: (medicationId, status = 'taken') => fetch('/logs/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            medication_id: medicationId,
            scheduled_time: new Date().toISOString(),
            taken_time: status === 'taken' ? new Date().toISOString() : null,
            status: status,
            notes: ''
        })
    }).then(r => r.json()),
    
    // Schedule (time-based NOW/LATER/MISSED/TAKEN buckets)
    getSchedule: () => fetch('/schedule/today').then(r => r.json()),
    snoozeMedication: (id, minutes = 60) => fetch(`/schedule/snooze/${id}?minutes=${minutes}`, {
        method: 'POST'
    }).then(r => r.json()),
    unsnoozeMedication: (id) => fetch(`/schedule/unsnooze/${id}`, {
        method: 'POST'
    }).then(r => r.json()),
    
    // Stats
    getStats: (period = 'weekly') => fetch(`/stats/adherence?period=${period}`).then(r => r.json()),
    getTodayStatus: () => fetch('/stats/today').then(r => r.json()),
    
    // Autocomplete
    searchMedications: (query) => fetch(`/autocomplete/medications?q=${encodeURIComponent(query)}`).then(r => r.json()),
    getSpelling: (query) => fetch(`/autocomplete/spelling?q=${encodeURIComponent(query)}`).then(r => r.json()),
    getDrugInfo: (name) => fetch(`/medications/drug-info/${encodeURIComponent(name)}`).then(r => r.json()),
    
    // CRUD Operations
    updateMedication: (id, data) => fetch(`/medications/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }).then(r => r.json()),
    deleteMedication: (id) => fetch(`/medications/${id}`, {
        method: 'DELETE'
    }).then(r => r.json()),
    
    // Chatbot
    initChatbot: () => fetch('/chatbot/langgraph/initialize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: 'llama3' })
    }).then(r => r.json()),
    
    askChatbot: (question) => fetch('/chatbot/langgraph/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question })
    }).then(r => r.json()),
    
    syncChatbotMeds: () => fetch('/chatbot/langgraph/update-medications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    }).then(r => r.json()),
    
    // Undo
    undoDose: (medicationId) => fetch(`/logs/undo/${medicationId}`, {
        method: 'POST'
    }).then(r => r.json()),
    
    // Debug
    clearLogs: () => fetch('/debug/clear-logs', { method: 'POST' }).then(r => r.json())
};

// ============================================
// UTILITY FUNCTIONS
// ============================================
function formatTime(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

function formatDate(dateStr) {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('exit');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function showLoading(show = true) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

function getMedicationIcon(name) {
    const icons = ['💊', '💉', '🧪', '🏥', '🩺', '💊', '💊', '💊'];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return icons[Math.abs(hash) % icons.length];
}

// ============================================
// NAVIGATION
// ============================================
function showView(viewName) {
    // Hide all views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.remove('active');
    });
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.tab === viewName) {
            btn.classList.add('active');
        }
    });
    
    // Show selected view
    const viewId = viewName + 'View';
    const view = document.getElementById(viewId);
    if (view) {
        view.classList.add('active');
        state.currentView = viewName;
        
        // Load view data
        if (viewName === 'home') {
            loadHomeData();
        } else if (viewName === 'schedule') {
            loadSchedule();
        } else if (viewName === 'medications') {
            loadMedications();
        } else if (viewName === 'stats') {
            loadStats();
        }
    }
    
    // Show/hide FAB
    const fab = document.getElementById('fabBtn');
    if (viewName === 'home' || viewName === 'medications') {
        fab.classList.remove('hidden');
    } else {
        fab.classList.add('hidden');
    }
    
    // Update header title
    const titles = {
        home: 'MedTracker',
        schedule: 'Today\'s Schedule',
        medications: 'My Medications',
        stats: 'My Progress',
        chatbot: 'Med Assistant'
    };
    document.querySelector('.header-title').textContent = titles[viewName] || 'MedTracker';
}

// ============================================
// HOME VIEW
// ============================================
async function loadHomeData() {
    try {
        console.log('🏠 Loading home data...');
        
        // Fetch all data including schedule with NOW/LATER/MISSED buckets
        const [medications, stats, schedule] = await Promise.all([
            API.getMedications(),
            API.getStats(),
            API.getSchedule()  // Use new schedule endpoint
        ]);
        
        console.log('✅ Data loaded:', { medications: medications?.length, stats, schedule });
        
        state.medications = medications;
        state.stats = stats;
        state.schedule = schedule;
        
        // Update stats cards
        const activeMeds = medications.filter(m => m.is_active);
        document.getElementById('medCount').textContent = activeMeds.length;
        document.getElementById('todayCount').textContent = (schedule?.taken || []).length;
        document.getElementById('streakCount').textContent = stats?.current_streak || 0;
        document.getElementById('adherenceRate').textContent = (stats?.adherence_rate || 0) + '%';
        
        // Update upcoming medications (show NOW + LATER buckets)
        const upcoming = [
            ...(schedule?.now || []).map(d => ({...d, bucket: 'now', urgent: true})),
            ...(schedule?.later || []).map(d => ({...d, bucket: 'later'}))
        ];
        updateUpNext(upcoming);
        
        // Update welcome text based on time
        updateWelcomeText();
        
    } catch (error) {
        console.error('❌ Error loading home data:', error);
        console.error('Stack:', error.stack);
        showToast('Failed to load data: ' + error.message, 'error');
    }
}

function updateUpNext(pendingMeds) {
    const container = document.getElementById('upNextContainer');
    const totalMeds = state.medications?.filter(m => m.is_active).length || 0;
    
    if (!pendingMeds || pendingMeds.length === 0) {
        // Check if there are any medications at all
        if (totalMeds === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">💊</div>
                    <p>No medications added yet.</p>
                    <button class="ios-btn ios-btn-primary" onclick="openAddModal()">Add Your First Medication</button>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">✅</div>
                    <p>All caught up! You've taken all your medications for today.</p>
                    <button class="ios-btn ios-btn-secondary" onclick="showView('schedule')">View Schedule</button>
                </div>
            `;
        }
        return;
    }
    
    // Show pending medications with time buckets
    container.innerHTML = pendingMeds.map(dose => {
        const icon = getMedicationIcon(dose.name);
        const isNow = dose.bucket === 'now';
        const timeLabel = dose.scheduled_time ? `· ${dose.scheduled_time}` : '';
        
        return `
            <div class="up-next-item glass-card ${isNow ? 'urgent' : ''}" onclick="logDose(${dose.medication_id}, 'taken')">
                <div class="med-icon">${icon}</div>
                <div class="up-next-info">
                    <div class="up-next-name">
                        ${dose.name}
                        ${isNow ? '<span class="badge-now">NOW</span>' : ''}
                    </div>
                    <div class="up-next-dosage">${dose.dosage || ''} ${timeLabel}</div>
                </div>
                <div class="up-next-actions">
                    ${isNow ? `
                    <button class="action-btn action-btn-snooze" onclick="event.stopPropagation(); snoozeDose(${dose.medication_id})" title="Snooze 1 hour">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"/>
                            <polyline points="12 6 12 12 16 14"/>
                        </svg>
                    </button>
                    ` : ''}
                    <button class="action-btn action-btn-take" onclick="event.stopPropagation(); logDose(${dose.medication_id}, 'taken')" title="Mark as taken">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                            <polyline points="20 6 9 17 4 12"/>
                        </svg>
                    </button>
                    <button class="action-btn action-btn-miss" onclick="event.stopPropagation(); logDose(${dose.medication_id}, 'missed')" title="Mark as missed">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <line x1="18" y1="6" x2="6" y2="18"/>
                            <line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

function getScheduledTime(frequency) {
    const times = {
        'once_daily': '9:00 AM',
        'twice_daily': '9:00 AM',
        'three_times_daily': '9:00 AM',
        'every_morning': '8:00 AM',
        'every_night': '9:00 PM',
        'as_needed': 'As needed'
    };
    return times[frequency] || '9:00 AM';
}

function formatFrequency(freq) {
    const labels = {
        'once_daily': 'Once daily',
        'twice_daily': 'Twice daily',
        'three_times_daily': '3x daily',
        'every_morning': 'Every morning',
        'every_night': 'Every night',
        'as_needed': 'As needed',
        'weekly': 'Weekly'
    };
    return labels[freq] || freq;
}

function updateWelcomeText() {
    const hour = new Date().getHours();
    let greeting = 'Good Morning';
    if (hour >= 12) greeting = 'Good Afternoon';
    if (hour >= 17) greeting = 'Good Evening';
    
    document.querySelector('.welcome-subtitle').textContent = greeting;
}

// ============================================
// SCHEDULE VIEW (Time-based buckets: NOW/LATER/MISSED/TAKEN)
// ============================================
async function loadSchedule() {
    document.getElementById('currentDate').textContent = formatDate(new Date());
    
    try {
        const schedule = await API.getSchedule();
        const list = document.getElementById('scheduleList');
        
        // Check if any medications scheduled
        const totalDoses = schedule.now.length + schedule.later.length + 
                          schedule.missed.length + schedule.taken.length;
        
        if (totalDoses === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📅</div>
                    <p>No medications scheduled for today</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        // NOW section - urgent medications
        if (schedule.now.length > 0) {
            html += `
                <div class="schedule-section">
                    <div class="schedule-section-header urgent">
                        <span class="section-icon">⏰</span>
                        <span class="section-title">NOW</span>
                        <span class="section-count">${schedule.now.length}</span>
                    </div>
                    <div class="schedule-section-content">
                        ${schedule.now.map(dose => renderDoseItem(dose, 'now')).join('')}
                    </div>
                </div>
            `;
        }
        
        // LATER section - upcoming medications
        if (schedule.later.length > 0) {
            html += `
                <div class="schedule-section">
                    <div class="schedule-section-header">
                        <span class="section-icon">📅</span>
                        <span class="section-title">LATER</span>
                        <span class="section-count">${schedule.later.length}</span>
                    </div>
                    <div class="schedule-section-content">
                        ${schedule.later.map(dose => renderDoseItem(dose, 'later')).join('')}
                    </div>
                </div>
            `;
        }
        
        // MISSED section - past medications
        if (schedule.missed.length > 0) {
            html += `
                <div class="schedule-section">
                    <div class="schedule-section-header missed">
                        <span class="section-icon">⚠️</span>
                        <span class="section-title">MISSED</span>
                        <span class="section-count">${schedule.missed.length}</span>
                    </div>
                    <div class="schedule-section-content">
                        ${schedule.missed.map(dose => renderDoseItem(dose, 'missed')).join('')}
                    </div>
                </div>
            `;
        }
        
        // TAKEN section - completed medications
        if (schedule.taken.length > 0) {
            html += `
                <div class="schedule-section">
                    <div class="schedule-section-header taken">
                        <span class="section-icon">✅</span>
                        <span class="section-title">TAKEN</span>
                        <span class="section-count">${schedule.taken.length}</span>
                    </div>
                    <div class="schedule-section-content">
                        ${schedule.taken.map(dose => renderDoseItem(dose, 'taken')).join('')}
                    </div>
                </div>
            `;
        }
        
        // SNOOZED section
        if (schedule.snoozed && schedule.snoozed.length > 0) {
            html += `
                <div class="schedule-section">
                    <div class="schedule-section-header snoozed">
                        <span class="section-icon">💤</span>
                        <span class="section-title">SNOOZED</span>
                        <span class="section-count">${schedule.snoozed.length}</span>
                    </div>
                    <div class="schedule-section-content">
                        ${schedule.snoozed.map(dose => renderDoseItem(dose, 'snoozed')).join('')}
                    </div>
                </div>
            `;
        }
        
        list.innerHTML = html;
        
    } catch (error) {
        console.error('Error loading schedule:', error);
        showToast('Failed to load schedule', 'error');
    }
}

function renderDoseItem(dose, bucket) {
    const icon = getMedicationIcon(dose.name);
    const isTaken = bucket === 'taken';
    const isMissed = bucket === 'missed';
    const isNow = bucket === 'now';
    const isSnoozed = bucket === 'snoozed';
    
    let actions = '';
    
    if (isTaken) {
        actions = `
            <span class="dose-status taken">✓ Taken</span>
            <button class="action-btn action-btn-undo" onclick="undoDose(${dose.medication_id})" title="Undo - mark as not taken">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M3 7v6h6"/>
                    <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>
                </svg>
            </button>
        `;
    } else if (isMissed) {
        actions = `
            <button class="action-btn action-btn-take" onclick="logDose(${dose.medication_id}, 'taken')" title="Take now">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
            </button>
        `;
    } else if (isSnoozed) {
        actions = `
            <button class="action-btn" onclick="unsnoozeDose(${dose.medication_id})" title="Wake up">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>
                </svg>
            </button>
        `;
    } else {
        // Now or Later
        actions = `
            ${isNow ? `<button class="action-btn action-btn-snooze" onclick="snoozeDose(${dose.medication_id})" title="Snooze 1 hour">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
            </button>` : ''}
            <button class="action-btn action-btn-take" onclick="logDose(${dose.medication_id}, 'taken')" title="Mark as taken">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
            </button>
            <button class="action-btn action-btn-miss" onclick="logDose(${dose.medication_id}, 'missed')" title="Mark as missed">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        `;
    }
    
    return `
        <div class="schedule-item ${bucket}">
            <div class="schedule-time">
                <div class="schedule-time-main">${dose.scheduled_time || '--'}</div>
            </div>
            <div class="schedule-divider"></div>
            <div class="schedule-content">
                <div class="schedule-med-name">
                    ${icon} ${dose.name}
                    ${isNow ? '<span class="badge-urgent">NOW</span>' : ''}
                </div>
                <div class="schedule-dosage">${dose.dosage || ''}</div>
            </div>
            <div class="schedule-actions">
                ${actions}
            </div>
        </div>
    `;
}

// Snooze a dose for 1 hour
async function snoozeDose(medicationId) {
    try {
        showLoading(true);
        await API.snoozeMedication(medicationId, 60);
        showToast('Snoozed for 1 hour', 'success');
        loadHomeData();
        loadSchedule();
    } catch (error) {
        console.error('Error snoozing:', error);
        showToast('Failed to snooze', 'error');
    } finally {
        showLoading(false);
    }
}

// Unsnooze a dose
async function unsnoozeDose(medicationId) {
    try {
        showLoading(true);
        await API.unsnoozeMedication(medicationId);
        showToast('Snooze removed', 'success');
        loadHomeData();
        loadSchedule();
    } catch (error) {
        console.error('Error unsnoozing:', error);
        showToast('Failed to remove snooze', 'error');
    } finally {
        showLoading(false);
    }
}

// ============================================
// MEDICATIONS VIEW
// ============================================
async function loadMedications() {
    try {
        const medications = await API.getMedications();
        state.medications = medications;
        
        const list = document.getElementById('medicationsList');
        
        if (medications.length === 0) {
            list.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">💊</div>
                    <p>No medications yet</p>
                    <button class="ios-btn ios-btn-primary" onclick="openAddModal()">Add Your First</button>
                </div>
            `;
            return;
        }
        
        list.innerHTML = medications.map(med => {
            const icon = renderPillIcon(med);
            const statusClass = med.is_active ? '' : 'inactive';
            const statusBadge = med.is_active ? '' : '<span class="inactive-badge">Archived</span>';

            return `
                <div class="med-card ${statusClass}">
                    <div class="med-icon">${icon}</div>
                    <div class="med-info">
                        <div class="med-name">${med.name} ${statusBadge}</div>
                        <div class="med-details">${med.dosage} · ${formatFrequency(med.frequency)}</div>
                    </div>
                    <div class="med-actions">
                        <button class="ios-btn ios-btn-small" onclick="openEditModal(${med.id})" title="Edit">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                        </button>
                        ${med.is_active ? `
                        <button class="ios-btn ios-btn-small archive-btn" onclick="archiveMedication(${med.id})" title="Archive">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="21 8 21 21 3 21 3 8"/>
                                <rect x="1" y="3" width="22" height="5"/>
                                <line x1="10" y1="12" x2="14" y2="12"/>
                            </svg>
                        </button>
                        ` : `
                        <button class="ios-btn ios-btn-small activate-btn" onclick="unarchiveMedication(${med.id})" title="Restore">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 14 4 9 9 4"/>
                                <path d="M4 9h10a6 6 0 0 1 6 6v0"/>
                            </svg>
                        </button>
                        `}
                        <button class="ios-btn ios-btn-small delete-btn" onclick="deleteMedication(${med.id})" title="Delete">
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Error loading medications:', error);
        showToast('Failed to load medications', 'error');
    }
}

// ============================================
// MEDICATION CRUD OPERATIONS
// ============================================

// Edit Medication
let currentEditingMed = null;

function openEditModal(medId) {
    const med = state.medications.find(m => m.id === medId);
    if (!med) {
        showToast('Medication not found', 'error');
        return;
    }
    
    currentEditingMed = med;
    
    // Populate form
    document.getElementById('editMedId').value = med.id;
    document.getElementById('editMedName').value = med.name;
    document.getElementById('editMedDosage').value = med.dosage;
    document.getElementById('editMedNotes').value = med.notes || '';
    document.getElementById('editMedFrequency').value = med.frequency;
    
    // Set frequency button active
    const freqButtons = document.querySelectorAll('#editFrequencyControl .segment-btn');
    freqButtons.forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.value === med.frequency) {
            btn.classList.add('active');
        }
    });
    
    // Generate time inputs
    const countMap = {'once_daily': 1, 'twice_daily': 2, 'three_times_daily': 3};
    const count = countMap[med.frequency] || 1;
    updateEditTimeInputs(count, med.reminder_times);
    
    // Show modal
    const modal = document.getElementById('editModal');
    modal.classList.add('active');
}

function closeEditModal() {
    const modal = document.getElementById('editModal');
    modal.classList.remove('active');
    currentEditingMed = null;
}

function updateEditTimeInputs(count, existingTimes = []) {
    const container = document.getElementById('editTimeInputsContainer');
    const defaults = ['08:00', '14:00', '20:00'];
    
    container.innerHTML = '';
    
    for (let i = 1; i <= count; i++) {
        const timeValue = existingTimes[i-1] || defaults[i-1] || '08:00';
        const row = document.createElement('div');
        row.className = 'time-input-row';
        row.innerHTML = `
            <span class="time-label">Dose ${i}</span>
            <input type="time" class="time-input" id="editTimeDose${i}" value="${timeValue}">
        `;
        container.appendChild(row);
    }
}

function getEditReminderTimes() {
    const frequency = document.getElementById('editMedFrequency').value;
    const countMap = {'once_daily': 1, 'twice_daily': 2, 'three_times_daily': 3};
    const count = countMap[frequency] || 1;
    const times = [];
    
    for (let i = 1; i <= count; i++) {
        const timeInput = document.getElementById(`editTimeDose${i}`);
        if (timeInput) {
            times.push(timeInput.value);
        }
    }
    
    return times;
}

async function submitEditMedication(e) {
    e.preventDefault();
    
    const medId = document.getElementById('editMedId').value;
    const reminderTimes = getEditReminderTimes();
    
    const data = {
        name: document.getElementById('editMedName').value,
        dosage: document.getElementById('editMedDosage').value,
        frequency: document.getElementById('editMedFrequency').value,
        notes: document.getElementById('editMedNotes').value,
        reminder_times: reminderTimes
    };
    
    try {
        showLoading(true);
        await API.updateMedication(medId, data);
        showToast('Medication updated!', 'success');
        closeEditModal();
        loadMedications();
        loadHomeData();
    } catch (error) {
        console.error('Error updating medication:', error);
        showToast('Failed to update medication', 'error');
    } finally {
        showLoading(false);
    }
}

// Archive Medication (Soft Delete)
async function archiveMedication(id) {
    if (!confirm('Archive this medication? It will be hidden from your active list but kept for records.')) {
        return;
    }
    
    try {
        showLoading(true);
        await API.updateMedication(id, { is_active: false });
        showToast('Medication archived', 'success');
        loadMedications();
        loadHomeData();
    } catch (error) {
        console.error('Error archiving medication:', error);
        showToast('Failed to archive medication', 'error');
    } finally {
        showLoading(false);
    }
}

// Unarchive Medication (Restore)
async function unarchiveMedication(id) {
    try {
        showLoading(true);
        await API.updateMedication(id, { is_active: true });
        showToast('Medication restored', 'success');
        loadMedications();
        loadHomeData();
    } catch (error) {
        console.error('Error restoring medication:', error);
        showToast('Failed to restore medication', 'error');
    } finally {
        showLoading(false);
    }
}

// Hard Delete Medication
async function deleteMedication(id) {
    const med = state.medications.find(m => m.id === id);
    const medName = med ? med.name : 'this medication';
    
    if (!confirm(`⚠️ PERMANENTLY DELETE "${medName}"?\n\nThis will remove all history and cannot be undone.`)) {
        return;
    }
    
    if (!confirm(`Final confirmation: Delete ${medName} permanently?`)) {
        return;
    }
    
    try {
        showLoading(true);
        await API.deleteMedication(id);
        showToast('Medication deleted', 'success');
        loadMedications();
        loadHomeData();
    } catch (error) {
        console.error('Error deleting medication:', error);
        showToast('Failed to delete medication', 'error');
    } finally {
        showLoading(false);
    }
}

// Legacy toggle function (keep for compatibility)
async function toggleMedication(id) {
    const med = state.medications.find(m => m.id === id);
    if (med && med.is_active) {
        await archiveMedication(id);
    } else {
        await unarchiveMedication(id);
    }
}

// Guard against double-taps: tracks medication IDs currently being logged
const _loggingInProgress = new Set();

async function logDose(medicationId, status) {
    if (_loggingInProgress.has(medicationId)) return;
    _loggingInProgress.add(medicationId);

    try {
        showLoading(true);
        const result = await API.logDose(medicationId, status);

        if (result.already_logged) {
            showToast('Already logged today!', 'info');
        } else {
            showToast(status === 'taken' ? 'Dose logged!' : 'Marked as missed', 'success');
        }

        await Promise.all([loadHomeData(), loadSchedule(), loadStats()]);
    } catch (error) {
        console.error('Error logging dose:', error);
        showToast('Failed to log dose', 'error');
    } finally {
        showLoading(false);
        _loggingInProgress.delete(medicationId);
    }
}

// Undo a taken dose (mark as not taken)
async function undoDose(medicationId) {
    try {
        showLoading(true);
        const result = await API.undoDose(medicationId);
        showToast('Dose entry removed - medication is pending again', 'success');
        loadHomeData();
        loadSchedule();
        loadStats();
    } catch (error) {
        console.error('Error undoing dose:', error);
        showToast('Failed to undo dose: ' + (error.message || ''), 'error');
    } finally {
        showLoading(false);
    }
}

// ============================================
// ADD MEDICATION MODAL
// ============================================
function openAddModal() {
    const modal = document.getElementById('addModal');
    modal.classList.add('active');
    document.getElementById('medName').focus();
}

function closeAddModal() {
    const modal = document.getElementById('addModal');
    modal.classList.remove('active');
    document.getElementById('addMedForm').reset();
    document.getElementById('addMedForm').style.display = 'block';
    document.getElementById('pillStep').style.display = 'none';
    autocompleteList.style.display = 'none';
    _newMedId = null;
}

// Segmented control - Frequency (Add Modal)
document.querySelectorAll('#addModal .segment-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        this.parentElement.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('medFrequency').value = this.dataset.value;
        
        // Update time inputs based on frequency
        const doseCount = parseInt(this.dataset.count);
        updateTimeInputs(doseCount);
    });
});

// Segmented control - Frequency (Edit Modal)
document.querySelectorAll('#editModal .segment-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        this.parentElement.querySelectorAll('.segment-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');
        document.getElementById('editMedFrequency').value = this.dataset.value;
        
        // Update time inputs based on frequency
        const doseCount = parseInt(this.dataset.count);
        updateEditTimeInputs(doseCount);
    });
});

// Default times for different frequencies
const defaultTimes = {
    1: ['08:00'],
    2: ['08:00', '20:00'],
    3: ['08:00', '14:00', '20:00']
};

function updateTimeInputs(count) {
    const container = document.getElementById('timeInputsContainer');
    const times = defaultTimes[count] || defaultTimes[1];
    
    container.innerHTML = '';
    
    for (let i = 1; i <= count; i++) {
        const row = document.createElement('div');
        row.className = 'time-input-row';
        row.innerHTML = `
            <span class="time-label">Dose ${i}</span>
            <input type="time" class="time-input" id="timeDose${i}" value="${times[i-1]}">
        `;
        container.appendChild(row);
    }
}

// Get all reminder times from form
function getReminderTimes() {
    const frequency = document.getElementById('medFrequency').value;
    const countMap = {
        'once_daily': 1,
        'twice_daily': 2,
        'three_times_daily': 3
    };
    const count = countMap[frequency] || 1;
    const times = [];
    
    for (let i = 1; i <= count; i++) {
        const timeInput = document.getElementById(`timeDose${i}`);
        if (timeInput) {
            times.push(timeInput.value);
        }
    }
    
    return times;
}

// ============================================
// AUTOCOMPLETE WITH SPELL-CHECK
// ============================================
let autocompleteTimeout;
let currentSpellingSuggestions = [];

const medNameInput = document.getElementById('medName');
const autocompleteList = document.getElementById('autocompleteList');

medNameInput.addEventListener('input', function() {
    clearTimeout(autocompleteTimeout);
    const query = this.value.trim();
    
    if (query.length < 2) {
        autocompleteList.style.display = 'none';
        return;
    }
    
    autocompleteTimeout = setTimeout(async () => {
        try {
            console.log('🔍 Autocomplete search for:', query);
            const data = await API.searchMedications(query);
            console.log('📦 API Response:', data);
            
            // Check debug info if available
            if (data.debug) {
                console.log('🐛 Debug info:', data.debug);
            }
            
            // Render medication suggestions (if any)
            if (data.suggestions && data.suggestions.length > 0) {
                console.log(`✅ Found ${data.suggestions.length} medications`);
                renderAutocompleteSuggestions(data.suggestions, query);
            } 
            // Otherwise show spelling suggestions (if any)
            else if (data.spelling_suggestions && data.spelling_suggestions.length > 0) {
                console.log(`✓ No meds, showing ${data.spelling_suggestions.length} spelling suggestions`);
                renderSpellingSuggestions(data.spelling_suggestions);
            }
            // Nothing found
            else {
                console.log('⚠️ No results found');
                autocompleteList.style.display = 'none';
            }
        } catch (error) {
            console.error('❌ Autocomplete error:', error);
            autocompleteList.style.display = 'none';
        }
    }, 300)
});

function renderAutocompleteSuggestions(suggestions, query) {
    // The agent already filtered and deduplicated
    console.log('Rendering suggestions:', suggestions);
    
    autocompleteList.innerHTML = suggestions.map((item, index) => {
        const strengthHtml = item.strength ? 
            `<span class="suggestion-strength">${item.strength}</span>` : '';
        const formHtml = item.form ? 
            `<span class="suggestion-form">${item.form}</span>` : '';
        
        return `
            <div class="autocomplete-item" 
                 data-index="${index}" role="button" tabindex="0">
                <div class="suggestion-main">
                    <span class="suggestion-name">${highlightMatch(item.base_name, query)}</span>
                </div>
                <div class="suggestion-meta">
                    ${strengthHtml}
                    ${formHtml}
                </div>
            </div>
        `;
    }).join('');
    
    // Add click handlers
    autocompleteList.querySelectorAll('.autocomplete-item').forEach((el, idx) => {
        el.addEventListener('click', () => {
            const item = suggestions[idx];
            console.log('🖱️ Selected medication:', item);
            selectMedication(item.base_name, item.strength || '');
        });
    });
    
    autocompleteList.style.display = 'block';
}

function renderSpellingSuggestions(suggestions) {
    console.log('Rendering spelling suggestions:', suggestions);
    
    autocompleteList.innerHTML = `
        <div class="autocomplete-header">
            <span class="spelling-icon">💡</span>
            <span>Did you mean:</span>
        </div>
        ${suggestions.map((s, idx) => `
            <div class="autocomplete-item spelling-suggestion" 
                 data-spelling-idx="${idx}" role="button" tabindex="0">
                <span class="suggestion-name">${escapeHtml(s)}</span>
                <span class="spelling-badge">Correct spelling</span>
            </div>
        `).join('')}
    `;
    
    // Add click handlers
    autocompleteList.querySelectorAll('[data-spelling-idx]').forEach((el) => {
        const idx = parseInt(el.dataset.spellingIdx);
        el.addEventListener('click', () => {
            console.log('🖱️ Selected spelling:', suggestions[idx]);
            selectMedication(suggestions[idx], '');
        });
    });
    
    autocompleteList.style.display = 'block';
}



async function selectMedication(name, strength) {
    console.log('🎯 Medication selected:', name, 'Strength:', strength);
    medNameInput.value = name;
    
    // Auto-fill dosage if available
    if (strength) {
        const dosageInput = document.getElementById('medDosage');
        // Only auto-fill if dosage field is empty
        if (!dosageInput.value) {
            dosageInput.value = strength;
            // Add a visual indicator that it was auto-filled
            dosageInput.style.background = 'rgba(0, 122, 255, 0.05)';
            setTimeout(() => {
                dosageInput.style.background = '';
            }, 500);
        }
    }
    
    autocompleteList.style.display = 'none';
    
    // Fetch FDA drug information
    console.log('🔄 Fetching FDA info for:', name);
    await fetchDrugInfo(name);
    
    // Move focus to dosage field for convenience
    if (!document.getElementById('medDosage').value) {
        document.getElementById('medDosage').focus();
    }
}

// ============================================
// FDA DRUG INFORMATION
// ============================================
async function fetchDrugInfo(drugName) {
    try {
        showLoading(true);
        console.log('🔍 Fetching FDA data for:', drugName);
        
        const data = await API.getDrugInfo(drugName);
        console.log('📊 FDA Response:', data);
        
        if (data.success) {
            // Display drug info card
            displayDrugInfoCard(data);
            
            // Auto-fill notes with key information
            const notesInput = document.getElementById('medNotes');
            const indications = data.taken_for || data.indications;
            if (!notesInput.value && indications) {
                const shortIndication = indications.substring(0, 100);
                notesInput.value = `For: ${shortIndication}${indications.length > 100 ? '...' : ''}`;
                notesInput.style.background = 'rgba(0, 122, 255, 0.05)';
                setTimeout(() => {
                    notesInput.style.background = '';
                }, 500);
            }
            
            showToast('FDA drug information loaded', 'success');
        } else {
            console.log('⚠️ No FDA data available:', data.error || data.message);
            // Show a minimal card indicating FDA lookup was attempted
            displayNoDrugInfoCard(drugName, data.message || 'Not found in FDA database');
        }
    } catch (error) {
        console.error('❌ Error fetching drug info:', error);
        displayNoDrugInfoCard(drugName, 'Unable to fetch FDA data');
    } finally {
        showLoading(false);
    }
}

function displayNoDrugInfoCard(drugName, reason) {
    hideDrugInfoCard();
    
    const form = document.getElementById('addMedForm');
    const card = document.createElement('div');
    card.id = 'drugInfoCard';
    card.className = 'drug-info-card-ios drug-info-missing';
    
    card.innerHTML = `
        <div class="drug-info-header-ios">
            <div class="drug-info-title-ios">
                <span class="fda-badge">🏥 FDA</span>
                <span>Drug Information</span>
            </div>
            <button type="button" class="close-drug-info" onclick="hideDrugInfoCard()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
        
        <div class="drug-info-missing-content">
            <div class="missing-icon">🔍</div>
            <div class="missing-text">
                <strong>${escapeHtml(drugName)}</strong><br>
                ${escapeHtml(reason)}
            </div>
        </div>
        
        <div class="drug-info-section-ios">
            <div class="drug-info-label-ios">
                <span>⚠️</span>
                <span>Common Side Effects</span>
            </div>
            <div class="no-data">See FDA label for side effects</div>
        </div>
        
        <div class="drug-info-section-ios">
            <div class="drug-info-label-ios">
                <span>🚫</span>
                <span>Do Not Mix With</span>
            </div>
            <div class="no-data">Check FDA label for interactions</div>
        </div>
        
        <div class="drug-info-footer-ios">
            <div class="fda-source">Source: OpenFDA Drug Label Database</div>
            <div class="fda-disclaimer">For reference only. Consult your pharmacist for Rx questions</div>
        </div>
    `;
    
    const nameField = medNameInput.closest('.form-group');
    nameField.parentNode.insertBefore(card, nameField.nextSibling);
    
    setTimeout(() => card.classList.add('show'), 10);
}

function displayDrugInfoCard(data) {
    // Remove existing card if any
    hideDrugInfoCard();
    
    const form = document.getElementById('addMedForm');
    
    // Create drug info card
    const card = document.createElement('div');
    card.id = 'drugInfoCard';
    card.className = 'drug-info-card-ios';
    
    // Handle both old and new API response formats
    const sideEffects = data.common_side_effects || data.side_effects || [];
    const interactions = data.do_not_mix_with || data.interactions_summary || [];
    
    const sideEffectsHtml = sideEffects.length > 0 
        ? sideEffects.slice(0, 5).map(e => `<span class="side-effect-chip">${e}</span>`).join('')
        : '<span class="no-data">See FDA label for side effects</span>';
    
    const interactionsHtml = interactions.length > 0
        ? interactions.slice(0, 4).map(i => `<span class="interaction-chip">${i}</span>`).join('')
        : '<span class="no-data">Check FDA label for interactions</span>';
    
    card.innerHTML = `
        <div class="drug-info-header-ios">
            <div class="drug-info-title-ios">
                <span class="fda-badge">🏥 FDA</span>
                <span>Drug Information</span>
            </div>
            <button type="button" class="close-drug-info" onclick="hideDrugInfoCard()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
        
        ${(data.taken_for || data.indications) ? `
        <div class="drug-info-section-ios">
            <div class="drug-info-label-ios">
                <span>📋</span>
                <span>Used For</span>
            </div>
            <div class="drug-info-content-ios">${(data.taken_for || data.indications).substring(0, 150)}${(data.taken_for || data.indications).length > 150 ? '...' : ''}</div>
        </div>
        ` : ''}
        
        <div class="drug-info-section-ios">
            <div class="drug-info-label-ios">
                <span>⚠️</span>
                <span>Common Side Effects</span>
            </div>
            <div class="side-effects-list-ios">${sideEffectsHtml}</div>
        </div>
        
        <div class="drug-info-section-ios">
            <div class="drug-info-label-ios">
                <span>🚫</span>
                <span>Do Not Mix With</span>
            </div>
            <div class="interactions-list-ios">${interactionsHtml}</div>
        </div>
        
        ${(data.important_warning || data.warnings) ? `
        <div class="drug-info-warning-ios">
            <div class="drug-info-label-ios">
                <span>⚡</span>
                <span>Important Warning</span>
            </div>
            <div class="drug-info-content-ios">${(data.important_warning || data.warnings).substring(0, 120)}${(data.important_warning || data.warnings).length > 120 ? '...' : ''}</div>
        </div>
        ` : ''}
        
        <div class="drug-info-footer-ios">
            <div class="fda-source">Source: OpenFDA Drug Label Database</div>
            <div class="fda-disclaimer">For reference only. Consult your pharmacist for Rx questions</div>
        </div>
    `;
    
    // Insert after the medication name field
    const nameField = medNameInput.closest('.form-group');
    nameField.parentNode.insertBefore(card, nameField.nextSibling);
    
    // Animate in
    setTimeout(() => card.classList.add('show'), 10);
}

function hideDrugInfoCard() {
    const existingCard = document.getElementById('drugInfoCard');
    if (existingCard) {
        existingCard.classList.remove('show');
        setTimeout(() => existingCard.remove(), 300);
    }
}

function highlightMatch(text, query) {
    if (!query) return escapeHtml(text);
    const regex = new RegExp(`(${escapeRegex(query)})`, 'gi');
    return escapeHtml(text).replace(regex, '<mark>$1</mark>');
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function escapeRegex(string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// Close autocomplete when clicking outside
document.addEventListener('click', function(e) {
    if (!medNameInput.contains(e.target) && !autocompleteList.contains(e.target)) {
        autocompleteList.style.display = 'none';
    }
});

// Keyboard navigation for autocomplete
medNameInput.addEventListener('keydown', function(e) {
    const items = autocompleteList.querySelectorAll('.autocomplete-item');
    let activeIndex = Array.from(items).findIndex(item => item.classList.contains('selected'));
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (items.length > 0) {
            if (activeIndex >= 0) items[activeIndex].classList.remove('selected');
            activeIndex = (activeIndex + 1) % items.length;
            items[activeIndex].classList.add('selected');
            items[activeIndex].scrollIntoView({ block: 'nearest' });
        }
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (items.length > 0) {
            if (activeIndex >= 0) items[activeIndex].classList.remove('selected');
            activeIndex = activeIndex <= 0 ? items.length - 1 : activeIndex - 1;
            items[activeIndex].classList.add('selected');
            items[activeIndex].scrollIntoView({ block: 'nearest' });
        }
    } else if (e.key === 'Enter') {
        if (activeIndex >= 0 && items[activeIndex]) {
            e.preventDefault();
            items[activeIndex].click();
        }
    } else if (e.key === 'Escape') {
        autocompleteList.style.display = 'none';
    }
});

// ============================================
// PILL IDENTIFICATION (Step 2 of Add Medication)
// ============================================
let _newMedId = null;

function _initPillSelectors() {
    document.querySelectorAll('#shapeSelector .pill-opt').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#shapeSelector .pill-opt').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            updatePillPreview();
        });
    });
    document.querySelectorAll('#colorSelector .color-swatch').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#colorSelector .color-swatch').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            updatePillPreview();
        });
    });
    document.querySelectorAll('#sizeSelector .pill-opt').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#sizeSelector .pill-opt').forEach(b => b.classList.remove('selected'));
            btn.classList.add('selected');
            updatePillPreview();
        });
    });
}

function updatePillPreview() {
    const shape = document.querySelector('#shapeSelector .pill-opt.selected')?.dataset.shape || 'oval';
    const color = document.querySelector('#colorSelector .color-swatch.selected')?.dataset.color || 'white';
    const size  = document.querySelector('#sizeSelector .pill-opt.selected')?.dataset.size  || 'medium';
    document.getElementById('pillPreview').className =
        `pill-preview pill-${shape} pill-color-${color} pill-size-${size}`;
}

function _initPillStep() {
    // Reset selectors to defaults
    document.querySelectorAll('#shapeSelector .pill-opt').forEach(b => b.classList.remove('selected'));
    document.querySelector('#shapeSelector [data-shape="oval"]').classList.add('selected');
    document.querySelectorAll('#colorSelector .color-swatch').forEach(b => b.classList.remove('selected'));
    document.querySelector('#colorSelector [data-color="white"]').classList.add('selected');
    document.querySelectorAll('#sizeSelector .pill-opt').forEach(b => b.classList.remove('selected'));
    document.querySelector('#sizeSelector [data-size="medium"]').classList.add('selected');
    updatePillPreview();
}

async function savePillStep() {
    const shape = document.querySelector('#shapeSelector .pill-opt.selected')?.dataset.shape;
    const color = document.querySelector('#colorSelector .color-swatch.selected')?.dataset.color;
    const size  = document.querySelector('#sizeSelector .pill-opt.selected')?.dataset.size;
    if (_newMedId) {
        try {
            await API.updateMedication(_newMedId, { pill_shape: shape, pill_color: color, pill_size: size });
        } catch (err) {
            console.error('Failed to save pill appearance:', err);
        }
    }
    _finishAddModal();
}

function skipPillStep() {
    _finishAddModal();
}

function _finishAddModal() {
    _newMedId = null;
    closeAddModal();
    loadHomeData();
    loadMedications();
}

function renderPillIcon(med) {
    if (med.pill_shape && med.pill_color) {
        const size = med.pill_size || 'medium';
        return `<div class="pill-icon pill-${med.pill_shape} pill-color-${med.pill_color} pill-size-${size}"></div>`;
    }
    // Fallback: emoji hash (existing behavior)
    const icons = ['💊', '💉', '🧪', '🏥', '🩺', '💊', '💊', '💊'];
    let hash = 0;
    for (let i = 0; i < med.name.length; i++) {
        hash = med.name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return `<span>${icons[Math.abs(hash) % icons.length]}</span>`;
}

async function submitMedication(e) {
    e.preventDefault();

    // Get reminder times
    const reminderTimes = getReminderTimes();

    const data = {
        name: document.getElementById('medName').value,
        dosage: document.getElementById('medDosage').value,
        frequency: document.getElementById('medFrequency').value,
        notes: document.getElementById('medNotes').value,
        is_active: true,
        reminder_times: reminderTimes  // Array of times like ["08:00", "20:00"]
    };

    console.log('Submitting medication:', data);

    try {
        showLoading(true);
        const response = await API.createMedication(data);
        showToast('Medication added!', 'success');
        showLoading(false);

        if (response && response.id) {
            // Transition to Step 2: pill identification
            _newMedId = response.id;
            document.getElementById('addMedForm').style.display = 'none';
            document.getElementById('pillStep').style.display = 'block';
            _initPillStep();
        } else {
            // No ID returned — close normally
            closeAddModal();
            loadHomeData();
            loadMedications();
        }
    } catch (error) {
        console.error('Error adding medication:', error);
        showToast('Failed to add medication', 'error');
        showLoading(false);
    }
}

// ============================================
// STATS VIEW
// ============================================
async function loadStats() {
    try {
        const stats = await API.getStats('weekly');
        state.stats = stats;
        
        console.log('📊 Stats loaded:', stats);
        
        // Update adherence circle
        const rate = stats.adherence_rate || 0;
        document.getElementById('adherencePercent').textContent = rate + '%';
        document.getElementById('adherenceGrade').textContent = getAdherenceGrade(rate);
        
        // Animate progress ring
        const circumference = 2 * Math.PI * 42;
        const offset = circumference - (rate / 100) * circumference;
        setTimeout(() => {
            document.getElementById('adherenceProgress').style.strokeDashoffset = offset;
        }, 100);
        
        // Update weekly chart with real data
        if (stats.weekly_breakdown) {
            updateWeeklyChart(stats.weekly_breakdown);
        }
        
        // Update medication stats
        if (stats.by_medication) {
            updateMedicationStats(stats.by_medication);
        }
        
    } catch (error) {
        console.error('Error loading stats:', error);
        showToast('Failed to load stats', 'error');
    }
}

function getAdherenceGrade(rate) {
    if (rate >= 95) return 'Excellent';
    if (rate >= 80) return 'Good';
    if (rate >= 60) return 'Fair';
    return 'Needs Work';
}

function updateWeeklyChart(dailyData) {
    const container = document.getElementById('weeklyChart');
    
    if (!dailyData || dailyData.length === 0) {
        container.innerHTML = '<div class="empty-state">No data available</div>';
        return;
    }
    
    // Use real data from API
    container.innerHTML = dailyData.map(d => `
        <div class="chart-bar-wrapper">
            <div class="chart-percent">${Math.round(d.rate)}%</div>
            <div class="chart-bar-bg">
                <div class="chart-bar-fill" style="height: ${Math.min(100, d.rate)}%"></div>
            </div>
            <div class="chart-day">${d.day_name}</div>
        </div>
    `).join('');
}

function updateMedicationStats(medsData) {
    const container = document.getElementById('medStatsList');
    
    if (!medsData || medsData.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📊</div>
                <p>No data available yet</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = medsData.map(med => `
        <div class="med-stat-item">
            <div class="med-name" style="flex: 1;">${med.name}</div>
            <div class="med-stat-bar">
                <div class="med-stat-fill" style="width: ${med.adherence}%"></div>
            </div>
            <div class="med-adherence-score" style="min-width: 50px; text-align: right; font-weight: 700;">${med.adherence}%</div>
        </div>
    `).join('');
}

// ============================================
// CHATBOT
// ============================================
async function initChatbot() {
    try {
        showLoading(true);
        const result = await API.initChatbot();
        
        if (result.success) {
            state.chatbotInitialized = true;
            showToast('Chatbot ready!', 'success');
            
            // Add system message
            addChatMessage('bot', '👋 Hello! I\'m your medication assistant. I can help you with:\n\n• Drug interactions\n• Side effects\n• Dosage reminders\n• General medication questions\n\nWhat would you like to know?');
        } else {
            showToast('Failed to initialize chatbot', 'error');
        }
    } catch (error) {
        console.error('Chatbot init error:', error);
        showToast('Chatbot not available', 'error');
    } finally {
        showLoading(false);
    }
}

function addChatMessage(sender, text) {
    const container = document.getElementById('chatMessages');
    const message = document.createElement('div');
    message.className = `chat-message ${sender}-message`;
    message.innerHTML = `
        <div class="message-avatar">${sender === 'bot' ? '🤖' : '👤'}</div>
        <div class="message-content">
            <p>${text.replace(/\n/g, '<br>')}</p>
        </div>
    `;
    container.appendChild(message);
    container.scrollTop = container.scrollHeight;
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    
    if (!question) return;
    
    if (!state.chatbotInitialized) {
        showToast('Please initialize the chatbot first', 'error');
        return;
    }
    
    // Add user message
    addChatMessage('user', question);
    input.value = '';
    
    try {
        showLoading(true);
        const result = await API.askChatbot(question);
        
        if (result.success) {
            addChatMessage('bot', result.answer);
        } else {
            addChatMessage('bot', 'Sorry, I had trouble processing your question. Please try again.');
        }
    } catch (error) {
        console.error('Chat error:', error);
        addChatMessage('bot', 'Sorry, I\'m having trouble connecting. Please try again later.');
    } finally {
        showLoading(false);
    }
}

// Enter key to send
document.getElementById('chatInput')?.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
        sendChatMessage();
    }
});

// ============================================
// INITIALIZATION
// ============================================
async function init() {
    // Check API health
    try {
        const health = await API.health();
        console.log('MedTracker API:', health.status);
    } catch (error) {
        console.error('API not available:', error);
        showToast('Cannot connect to server', 'error');
        return;
    }
    
    // Load initial data
    await loadHomeData();
    
    // Update status bar time
    setInterval(() => {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { 
            hour: 'numeric', 
            minute: '2-digit',
            hour12: false 
        });
        document.querySelector('.status-time').textContent = timeStr;
    }, 60000);
    
    // Set initial time
    const now = new Date();
    document.querySelector('.status-time').textContent = now.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: false 
    });
    
    console.log('MedTracker iOS app initialized');
}

// Start the app
document.addEventListener('DOMContentLoaded', () => {
    init();
    _initPillSelectors();
});

// Close modal on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAddModal();
        closeSettingsModal();
    }
});

// ============================================
// SETTINGS MODAL
// ============================================
function openSettingsModal() {
    const modal = document.getElementById('settingsModal');
    modal.classList.add('active');
    
    // Load saved preferences
    loadSettings();
}

function closeSettingsModal() {
    const modal = document.getElementById('settingsModal');
    modal.classList.remove('active');
}

function loadSettings() {
    // Load saved settings from localStorage
    const settings = JSON.parse(localStorage.getItem('medtracker_settings') || '{}');
    
    // Apply saved values
    document.getElementById('reminderToggle').checked = settings.reminders !== false;
    document.getElementById('refillToggle').checked = settings.refillAlerts === true;
    document.getElementById('interactionToggle').checked = settings.interactions !== false;
    document.getElementById('darkModeToggle').checked = settings.darkMode === true;
}

function saveSettings() {
    const settings = {
        reminders: document.getElementById('reminderToggle').checked,
        refillAlerts: document.getElementById('refillToggle').checked,
        interactions: document.getElementById('interactionToggle').checked,
        darkMode: document.getElementById('darkModeToggle').checked
    };
    
    localStorage.setItem('medtracker_settings', JSON.stringify(settings));
    return settings;
}

// ============================================
// PUSH NOTIFICATIONS
// ============================================

let _pushSubscription = null;

/**
 * Convert a VAPID public key from URL-safe base64 to a Uint8Array,
 * as required by PushManager.subscribe({ applicationServerKey }).
 */
function _urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
}

/**
 * Register the service worker, request the VAPID key from the server,
 * subscribe the browser to Web Push, and POST the subscription to /push/subscribe.
 * Returns true on success, false on any failure.
 */
async function initPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        showToast('Push notifications are not supported in this browser', 'error');
        return false;
    }

    try {
        // Register (or get the existing) service worker
        const reg = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });
        await navigator.serviceWorker.ready;

        // Fetch VAPID public key — 503 means server not configured
        const keyRes = await fetch('/push/vapid-key');
        if (!keyRes.ok) {
            console.warn('Push not configured on server (VAPID keys missing)');
            showToast('Push not configured on server', 'error');
            return false;
        }
        const { public_key } = await keyRes.json();

        // Reuse existing subscription or create a new one
        _pushSubscription = await reg.pushManager.getSubscription();
        if (!_pushSubscription) {
            _pushSubscription = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: _urlBase64ToUint8Array(public_key),
            });
        }

        // Store subscription on the server
        const subRes = await fetch('/push/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(_pushSubscription.toJSON()),
        });

        return subRes.ok;
    } catch (err) {
        if (err.name === 'NotAllowedError') {
            showToast('Notification permission was denied', 'error');
        } else {
            console.error('Push init error:', err);
            showToast('Could not enable push notifications', 'error');
        }
        return false;
    }
}

/**
 * Unsubscribe from Web Push and notify the server to deactivate the subscription.
 */
async function disablePushNotifications() {
    if (!_pushSubscription) {
        // Try to get the current subscription from the browser
        if ('serviceWorker' in navigator) {
            const reg = await navigator.serviceWorker.ready;
            _pushSubscription = await reg.pushManager.getSubscription();
        }
    }

    if (_pushSubscription) {
        try {
            await fetch('/push/unsubscribe?endpoint=' + encodeURIComponent(_pushSubscription.endpoint), {
                method: 'DELETE',
            });
            await _pushSubscription.unsubscribe();
        } catch (err) {
            console.error('Push unsubscribe error:', err);
        }
        _pushSubscription = null;
    }
}

// Handle messages posted from the Service Worker (notification action clicks)
if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', async (event) => {
        const { type, medicationId } = event.data || {};

        if (type === 'OPEN_SCHEDULE') {
            showView('schedule');
        } else if (type === 'MARK_TAKEN' && medicationId) {
            try {
                await API.logDose(medicationId, 'taken');
                await loadDashboard();
                showView('schedule');
                showToast('Dose marked as taken', 'success');
            } catch (err) {
                console.error('Mark taken from notification failed:', err);
            }
        }
    });
}

// Settings toggle listeners
document.getElementById('reminderToggle')?.addEventListener('change', async (e) => {
    const enabled = e.target.checked;

    if (enabled) {
        // Request OS-level notification permission first
        if ('Notification' in window) {
            const permission = await Notification.requestPermission();
            if (permission !== 'granted') {
                e.target.checked = false;
                showToast('Please allow notifications in your browser settings', 'error');
                return;
            }
        }

        const success = await initPushNotifications();
        if (success) {
            showToast('Push reminders enabled!', 'success');
        } else {
            e.target.checked = false;
        }
    } else {
        await disablePushNotifications();
        showToast('Push reminders disabled', 'success');
    }

    saveSettings();
});

document.getElementById('refillToggle')?.addEventListener('change', () => {
    saveSettings();
    showToast('Refill alert settings saved', 'success');
});

document.getElementById('interactionToggle')?.addEventListener('change', () => {
    saveSettings();
    showToast('Interaction warning settings saved', 'success');
});

document.getElementById('darkModeToggle')?.addEventListener('change', () => {
    saveSettings();
    const isDark = document.getElementById('darkModeToggle').checked;
    if (isDark) {
        document.body.classList.add('dark-mode');
    } else {
        document.body.classList.remove('dark-mode');
    }
    showToast(isDark ? 'Dark mode enabled' : 'Light mode enabled', 'success');
});

function exportData() {
    // Get all medication data
    const data = {
        medications: state.medications,
        logs: state.logs,
        exportDate: new Date().toISOString(),
        app: 'MedTracker',
        version: '2.0.0'
    };
    
    // Create downloadable file
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `medtracker-backup-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Data exported successfully', 'success');
}

async function clearAllData() {
    if (!confirm('⚠️ WARNING: This will delete ALL your medications and logs. This cannot be undone.\n\nAre you sure you want to continue?')) {
        return;
    }
    
    if (!confirm('Final confirmation: Type "DELETE" to confirm permanent deletion of all data.')) {
        return;
    }
    
    try {
        showLoading(true);
        
        // Delete all medications
        for (const med of state.medications) {
            await API.deleteMedication(med.id);
        }
        
        // Clear local storage except settings
        const settings = localStorage.getItem('medtracker_settings');
        localStorage.clear();
        if (settings) {
            localStorage.setItem('medtracker_settings', settings);
        }
        
        showToast('All data cleared', 'success');
        closeSettingsModal();
        
        // Reload the app
        setTimeout(() => {
            location.reload();
        }, 1000);
        
    } catch (error) {
        console.error('Error clearing data:', error);
        showToast('Error clearing data', 'error');
    } finally {
        showLoading(false);
    }
}

// Connect settings button
document.getElementById('settingsBtn').addEventListener('click', openSettingsModal);

// Load dark mode preference on startup
const savedSettings = JSON.parse(localStorage.getItem('medtracker_settings') || '{}');
if (savedSettings.darkMode) {
    document.body.classList.add('dark-mode');
}

// ============================================
// DEBUG FUNCTIONS
// ============================================
async function debugClearLogs() {
    if (!confirm('Clear all medication logs? This will reset all "taken" status.')) {
        return;
    }
    
    try {
        showLoading(true);
        const result = await API.clearLogs();
        
        if (result.success) {
            showToast(`Cleared ${result.cleared_count} log entries`, 'success');
            // Reload data to show fresh state
            loadHomeData();
            loadSchedule();
        } else {
            showToast('Failed to clear logs: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Error clearing logs:', error);
        showToast('Error clearing logs', 'error');
    } finally {
        showLoading(false);
    }
}

async function testAgents() {
    try {
        showLoading(true);
        const result = await fetch('/debug/agents').then(r => r.json());
        console.log('Agent test results:', result);
        
        // Format results for display
        const status = Object.entries(result).map(([name, data]) => {
            const icon = data.status === 'ok' ? '✅' : '❌';
            return `${icon} ${name}: ${data.status}`;
        }).join('\n');
        
        alert(`Agent System Test Results:\n\n${status}`);
    } catch (error) {
        console.error('Error testing agents:', error);
        showToast('Error testing agents', 'error');
    } finally {
        showLoading(false);
    }
}
