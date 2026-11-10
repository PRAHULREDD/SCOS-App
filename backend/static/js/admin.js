/**
 * Admin Operations & Surveillance Logic (Waste Heatmap, Incidents & Dispatch)
 */

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

document.addEventListener('DOMContentLoaded', () => {

    // ---- Auth guard: redirect non-admins to login ----
    const _token = localStorage.getItem('token');
    const _role  = localStorage.getItem('user_role');
    if (!_token || _role !== 'ADMIN') {
        localStorage.removeItem('token');
        localStorage.removeItem('user_role');
        window.location.href = '../Login Screen/index.html';
        return;
    }

    // ---- Notification Bell Trigger (Clearly labelled as Simulated/Demo) ----
    const notifBtn = document.querySelector('header button');
    if (notifBtn) {
        notifBtn.addEventListener('click', async () => {
            try {
                const overview = await API.fetchAdminOverview();
                const pending = overview.pending_complaints || 0;
                const activeIncidents = overview.active_incidents_count || 0;
                if (pending > 0 || activeIncidents > 0) {
                    window.showToast(`[Demo Notification] ${pending} pending complaint(s), ${activeIncidents} active incident(s) in system.`, 'warning');
                } else {
                    window.showToast('[Demo Notification] All monitored sectors clear. No pending complaints.', 'success');
                }
            } catch (e) {
                window.showToast('[Demo Notification] No active system alerts.', 'info');
            }
        });
    }

    // ---- Profile Logout Trigger ----
    const profilePic = document.querySelector('header img');
    if (profilePic) {
        profilePic.style.cursor = 'pointer';
        profilePic.addEventListener('click', () => {
            if (confirm("Logout from Admin console?")) {
                localStorage.removeItem('token');
                localStorage.removeItem('user_role');
                window.location.href = '../Login Screen/index.html';
            }
        });
    }
    
    // ---- Universal Admin Navigation ----
    const navAnchors = document.querySelectorAll('nav.fixed.bottom-0 a, nav.fixed.bottom-0 button');
    navAnchors.forEach(anchor => {
        const iconSpan = anchor.querySelector('.material-symbols-outlined');
        let iconName = '';
        if (iconSpan) {
            iconName = iconSpan.getAttribute('data-icon') || iconSpan.textContent.trim().toLowerCase();
        }
        
        if (iconName) {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                if (iconName === 'dashboard' || iconName === 'home') {
                    window.location.href = '../Waste Heatmap/index.html';
                } else if (iconName === 'warning' || iconName === 'assignment') {
                    window.location.href = '../Illegal Dumping/index.html';
                } else {
                    window.location.href = '../Waste Heatmap/index.html';
                }
            });
        }
    });

    // ---- Dynamic Admin Page Router ----
    const path = decodeURIComponent(window.location.pathname);
    if (path.includes('Waste Heatmap')) {
        loadAdminOperations();
        loadAdminComplaints();
        loadWasteHeatmap();
    } else if (path.includes('Illegal Dumping')) {
        loadIllegalDumping();
    }

    // Modal confirm handler
    const confirmBtn = document.getElementById('modal-confirm-btn');
    if (confirmBtn) {
        confirmBtn.addEventListener('click', async () => {
            const complaintId = parseInt(document.getElementById('modal-complaint-id').value);
            const driverId = parseInt(document.getElementById('modal-driver-select').value);
            const wasteType = document.getElementById('modal-waste-type').value;
            const address = document.getElementById('modal-address').value;

            if (!driverId) {
                window.showToast('Please select a driver.', 'error');
                return;
            }

            confirmBtn.disabled = true;
            confirmBtn.textContent = 'Assigning…';
            try {
                await API.assignTask(complaintId, driverId, wasteType, address);
                window.showToast('Driver assigned successfully!', 'success');
                document.getElementById('assign-modal').classList.add('hidden');
                loadAdminComplaints(); // refresh list
                loadAdminOperations(); // refresh KPIs
                loadWasteHeatmap();    // refresh heatmap points
            } catch (err) {
                window.showToast(err.message || 'Assignment failed', 'error');
            } finally {
                confirmBtn.disabled = false;
                confirmBtn.textContent = 'Assign';
            }
        });
    }
});

/**
 * Loads real KPI stats on the Operations Dashboard
 */
async function loadAdminOperations() {
    try {
        const stats = await API.fetchAdminOverview();

        const totalComplaintsEl = document.getElementById('admin-total-bins');
        const pendingComplaintsEl = document.getElementById('admin-critical-bins');
        const efficiencyEl = document.getElementById('admin-collection-efficiency');
        const efficiencyBar = document.getElementById('admin-collection-bar');

        // Use real count, no simulated multiplier
        if (totalComplaintsEl) totalComplaintsEl.textContent = stats.total_complaints ?? 0;
        if (pendingComplaintsEl) pendingComplaintsEl.textContent = stats.pending_complaints ?? 0;
        if (efficiencyEl) efficiencyEl.textContent = `${stats.collection_rate ?? 0}%`;
        if (efficiencyBar) efficiencyBar.style.width = `${stats.collection_rate ?? 0}%`;
    } catch (err) {
        console.error("Failed to fetch live admin stats:", err);
    }
}

/**
 * Integrates /api/admin/waste_heatmap into interactive Leaflet map
 */
let _adminMapInstance = null;
async function loadWasteHeatmap() {
    const mapContainer = document.getElementById('admin-heatmap-container');
    const badgeEl = document.getElementById('heatmap-points-count');
    if (!mapContainer) return;

    try {
        const data = await API.fetchAdminHeatmap();
        const points = data.heatmap_points || [];

        if (badgeEl) {
            badgeEl.textContent = `${points.length} Locations Plotted`;
        }

        // Check if Leaflet is available
        if (typeof window.L === 'undefined') {
            mapContainer.innerHTML = `
                <div class="h-full flex flex-col items-center justify-center p-6 text-center bg-slate-50">
                    <span class="material-symbols-outlined text-4xl text-primary mb-2">map</span>
                    <p class="font-medium text-on-surface">Live Heatmap Data: ${points.length} complaints recorded.</p>
                    <p class="text-xs text-on-surface-variant mt-1">Leaflet library loading...</p>
                </div>`;
            return;
        }

        // Initialize or reuse map
        if (!_adminMapInstance) {
            _adminMapInstance = L.map('admin-heatmap-container').setView([12.9716, 77.5946], 12);
            window._adminMapInstance = _adminMapInstance;
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 18
            }).addTo(_adminMapInstance);
        } else {
            // Clear existing markers
            _adminMapInstance.eachLayer(layer => {
                if (layer instanceof L.CircleMarker) {
                    _adminMapInstance.removeLayer(layer);
                }
            });
        }

        if (points.length === 0) {
            return;
        }

        const bounds = [];
        points.forEach(p => {
            if (typeof p.lat === 'number' && typeof p.lng === 'number') {
                const colorMap = {
                    PENDING: '#dc2626',
                    IN_PROGRESS: '#f59e0b',
                    RESOLVED: '#059669'
                };
                const color = colorMap[p.status] || '#dc2626';

                const marker = L.circleMarker([p.lat, p.lng], {
                    radius: 8,
                    fillColor: color,
                    color: '#ffffff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.85
                }).addTo(_adminMapInstance);

                marker.bindPopup(`
                    <div class="text-xs space-y-1">
                        <strong class="text-sm font-semibold">${escapeHtml(p.waste_type || 'General')} Waste</strong>
                        <p class="text-slate-600">Zone: ${escapeHtml(p.zone || 'Unknown')}</p>
                        <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white" style="background-color: ${color}">
                            ${escapeHtml(p.status)}
                        </span>
                    </div>
                `);

                bounds.push([p.lat, p.lng]);
            }
        });

        if (bounds.length > 0) {
            _adminMapInstance.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
        }

    } catch (err) {
        console.error("Failed to load waste heatmap:", err);
        if (badgeEl) badgeEl.textContent = 'Map unavailable';
    }
}

/**
 * Loads real illegal dumping incidents and distinguishes AI predictions
 */
async function loadIllegalDumping() {
    const listEl = document.getElementById('dumping-incidents-list');
    const activeEl = document.getElementById('dumping-active-count');
    const highRiskEl = document.getElementById('dumping-high-risk');
    const clustersEl = document.getElementById('dumping-clusters-count');

    try {
        const dumpData = await API.fetchIllegalDumping();
        const incidents = dumpData.incidents || [];

        const activeCount = dumpData.active_count ?? incidents.length;
        const highRiskCount = dumpData.high_risk_count ?? incidents.filter(i => i.severity === 'HIGH').length;

        // Count unique zones/clusters
        const uniqueClusters = new Set(incidents.map(i => i.zone || i.cluster_id || 'Default')).size;

        if (activeEl) activeEl.textContent = activeCount;
        if (highRiskEl) highRiskEl.textContent = highRiskCount;
        if (clustersEl) clustersEl.textContent = uniqueClusters;

        if (!listEl) return;

        if (incidents.length === 0) {
            listEl.innerHTML = '<p class="text-on-surface-variant text-sm py-8 text-center bg-slate-50 dark:bg-slate-800 rounded-2xl">No illegal dumping incidents reported currently.</p>';
            return;
        }

        listEl.innerHTML = incidents.map(inc => {
            const severityStyles = {
                HIGH: 'bg-error-container text-on-error-container border-error/30',
                MEDIUM: 'bg-amber-100 text-amber-800 border-amber-300',
                LOW: 'bg-surface-container text-on-surface-variant border-outline-variant/30'
            };
            const sevBadge = severityStyles[inc.severity] || severityStyles.MEDIUM;

            const detectedDate = inc.detected_at ? new Date(inc.detected_at).toLocaleString() : 'Recent';

            return `
            <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-2xl p-5 space-y-3 hover:shadow-sm transition-all">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs font-bold px-2.5 py-0.5 rounded-full border ${sevBadge}">${escapeHtml(inc.severity)} RISK</span>
                            <span class="text-xs text-on-surface-variant font-mono">Cluster: ${escapeHtml(inc.cluster_id || inc.zone || 'A')}</span>
                        </div>
                        <h4 class="font-title-md font-bold text-on-surface">${escapeHtml(inc.description || 'Unauthorized waste dumping detected')}</h4>
                        <p class="text-xs text-on-surface-variant mt-0.5">Location: ${escapeHtml(inc.zone || 'Municipal Perimeter')} · Detected: ${detectedDate}</p>
                    </div>
                    <span class="text-xs font-semibold px-2.5 py-1 rounded-lg bg-primary/10 text-primary uppercase">${escapeHtml(inc.status || 'ACTIVE')}</span>
                </div>

                <!-- Explicitly labeled AI Prediction Section -->
                <div class="bg-slate-50 dark:bg-slate-800/60 p-3 rounded-xl border border-slate-200 dark:border-slate-700/50 text-xs space-y-1">
                    <div class="flex items-center gap-1.5 text-primary font-semibold">
                        <span class="material-symbols-outlined text-[16px]">psychology</span>
                        <span>AI Pattern Prediction (Hypothesis)</span>
                    </div>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-on-surface-variant pt-1">
                        <div>
                            <span class="text-slate-400">Predicted Source:</span>
                            <strong class="text-on-surface ml-1">${escapeHtml(inc.predicted_culprit || 'Under Investigation')}</strong>
                        </div>
                        ${inc.common_time ? `<div><span class="text-slate-400">Common Time Window:</span> <strong class="text-on-surface ml-1">${escapeHtml(inc.common_time)}</strong></div>` : ''}
                    </div>
                    ${typeof inc.confidence === 'number' ? `
                    <div class="flex items-center gap-2 pt-1 text-[11px] text-slate-500">
                        <span>Pattern Match Confidence:</span>
                        <div class="flex-1 bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden max-w-[120px]">
                            <div class="bg-primary h-full rounded-full" style="width: ${Math.round(inc.confidence * 100)}%"></div>
                        </div>
                        <span class="font-bold text-primary">${Math.round(inc.confidence * 100)}%</span>
                    </div>` : ''}
                </div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error("Failed to load illegal dumping data:", err);
        if (listEl) listEl.innerHTML = `<p class="text-error text-sm p-4">Error loading surveillance data: ${escapeHtml(err.message)}</p>`;
    }
}

/**
 * Loads all complaints into the admin complaint management panel
 * and populates the driver dropdown for assignment.
 */
async function loadAdminComplaints() {
    const listEl = document.getElementById('complaints-list-admin');
    if (!listEl) return;

    try {
        const [compData, driverData] = await Promise.all([
            API.fetchAdminComplaints(),
            API.fetchDrivers()
        ]);

        const complaints = compData.complaints || [];
        const drivers = driverData.drivers || [];

        // Populate driver dropdown for the modal
        const driverSelect = document.getElementById('modal-driver-select');
        if (driverSelect) {
            driverSelect.innerHTML = drivers.length === 0
                ? '<option value="">No drivers registered</option>'
                : '<option value="">-- Select Driver --</option>' +
                  drivers.map(d => `<option value="${d.id}">${escapeHtml(d.name)} (${escapeHtml(d.email)})</option>`).join('');
        }

        if (complaints.length === 0) {
            listEl.innerHTML = '<p class="text-on-surface-variant text-sm py-4 text-center">No complaints submitted yet.</p>';
            return;
        }

        listEl.innerHTML = complaints.map(c => {
            const statusColors = {
                PENDING:     'bg-error/10 text-error border-error/20',
                IN_PROGRESS: 'bg-secondary-container text-on-secondary-container border-secondary/20',
                RESOLVED:    'bg-surface-container text-on-surface-variant border-outline-variant',
            };
            const statusColor = statusColors[c.status] || statusColors.PENDING;

            const canAssign = c.status === 'PENDING';
            const safeWasteType = escapeHtml(c.waste_type || 'General');
            const safeArea = escapeHtml(c.area || 'Unknown Area');

            const assignBtn = canAssign
                ? `<button
                       onclick="openAssignModal(${c.id}, '${safeWasteType}', '${safeArea}')"
                       class="px-4 py-2 bg-primary text-on-primary text-sm font-medium rounded-full active:scale-95 transition-transform">
                       Assign Driver
                   </button>`
                : `<span class="text-xs text-on-surface-variant font-medium">${c.status === 'RESOLVED' ? 'Resolved' : 'Assigned'}</span>`;

            return `
            <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-4 flex items-center justify-between gap-4">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-medium px-2 py-0.5 rounded-full border ${statusColor}">${escapeHtml(c.status)}</span>
                        <span class="text-xs text-on-surface-variant font-mono">#${c.id}</span>
                    </div>
                    <h4 class="font-medium text-on-surface truncate">${safeWasteType} — ${safeArea}</h4>
                    <p class="text-xs text-on-surface-variant">${escapeHtml(c.zone || '')} · ${c.created_at ? new Date(c.created_at).toLocaleString() : 'Unknown date'}</p>
                </div>
                <div class="shrink-0">${assignBtn}</div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error('Failed to load admin complaints:', err);
        if (listEl) listEl.innerHTML = `<p class="text-error text-sm p-4">Error loading complaints: ${escapeHtml(err.message)}</p>`;
    }
}

/**
 * Opens the assign-driver modal pre-filled for the selected complaint.
 */
function openAssignModal(complaintId, wasteType, address) {
    document.getElementById('modal-complaint-id').value = complaintId;
    document.getElementById('modal-waste-type').value = wasteType;
    document.getElementById('modal-address').value = address;
    document.getElementById('modal-complaint-desc').textContent =
        `#${complaintId} · ${wasteType} in ${address}`;
    document.getElementById('assign-modal').classList.remove('hidden');
}

window.openAssignModal = openAssignModal;
