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

    // ---- Notification Bell Trigger ----
    const notifBtn = document.querySelector('header button');
    if (notifBtn) {
        notifBtn.addEventListener('click', async () => {
            try {
                const overview = await API.fetchAdminOverview();
                const pending = overview.pending_complaints || 0;
                const activeIncidents = overview.active_incidents_count || 0;
                if (pending > 0 || activeIncidents > 0) {
                    window.showToast(`${pending} pending complaint(s), ${activeIncidents} high-priority item(s) in system.`, 'warning');
                } else {
                    window.showToast('All monitored sectors clear. No pending complaints.', 'success');
                }
            } catch (e) {
                window.showToast('No active system alerts.', 'info');
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

                const proofPopupBtn = (p.status === 'RESOLVED' && p.proof_photo_url) ? `
                    <div class="pt-1.5 border-t border-slate-200 mt-1">
                        <button type="button"
                                data-action="view-admin-proof"
                                data-proof-url="${escapeHtml(p.proof_photo_url)}"
                                data-complaint-id="${p.id || 0}"
                                data-waste-type="${escapeHtml(p.waste_type || 'General')}"
                                data-area="${escapeHtml(p.zone || 'Unknown')}"
                                class="w-full text-center px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium text-[11px] flex items-center justify-center gap-1 shadow-sm active:scale-95 transition-all">
                            <span class="material-symbols-outlined text-[13px]">photo_camera</span>
                            <span>View Proof</span>
                        </button>
                    </div>
                ` : '';

                marker.bindPopup(`
                    <div class="text-xs space-y-1">
                        <strong class="text-sm font-semibold">${escapeHtml(p.waste_type || 'General')} Waste</strong>
                        <p class="text-slate-600">Zone: ${escapeHtml(p.zone || 'Unknown')}</p>
                        <span class="inline-block px-2 py-0.5 rounded text-[10px] font-bold text-white" style="background-color: ${color}">
                            ${escapeHtml(p.status)}
                        </span>
                        ${proofPopupBtn}
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
 * Loads high-priority complaints for municipal administrative review
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
        const highRiskCount = dumpData.high_risk_count ?? incidents.filter(i => i.severity === 'HIGH' || i.severity === 'CRITICAL').length;

        // Count unique zones/areas
        const uniqueClusters = new Set(incidents.map(i => i.area || i.zone || 'Central')).size;

        if (activeEl) activeEl.textContent = activeCount;
        if (highRiskEl) highRiskEl.textContent = highRiskCount;
        if (clustersEl) clustersEl.textContent = uniqueClusters;

        if (!listEl) return;

        if (incidents.length === 0) {
            listEl.innerHTML = '<p class="text-on-surface-variant text-sm py-8 text-center bg-slate-50 dark:bg-slate-800 rounded-2xl">No high-priority complaints pending review.</p>';
            return;
        }

        listEl.innerHTML = incidents.map(inc => {
            const severityStyles = {
                CRITICAL: 'bg-error-container text-on-error-container border-error/30',
                HIGH: 'bg-error-container text-on-error-container border-error/30',
                MEDIUM: 'bg-amber-100 text-amber-800 border-amber-300',
                LOW: 'bg-surface-container text-on-surface-variant border-outline-variant/30'
            };
            const sevBadge = severityStyles[inc.severity] || severityStyles.HIGH;

            const detectedDate = inc.detected_at ? new Date(inc.detected_at).toLocaleString() : 'Recent';

            return `
            <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-2xl p-5 space-y-3 hover:shadow-sm transition-all">
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <div class="flex items-center gap-2 mb-1">
                            <span class="text-xs font-bold px-2.5 py-0.5 rounded-full border ${sevBadge}">${escapeHtml(inc.severity)} PRIORITY</span>
                            <span class="text-xs text-on-surface-variant font-mono">Sector: ${escapeHtml(inc.area || inc.zone || 'Central')}</span>
                        </div>
                        <h4 class="font-title-md font-bold text-on-surface">${escapeHtml(inc.description || 'Priority waste collection required')}</h4>
                        <p class="text-xs text-on-surface-variant mt-0.5">Location: ${escapeHtml(inc.zone || 'Municipal Perimeter')} · Reported: ${detectedDate}</p>
                    </div>
                    <span class="text-xs font-semibold px-2.5 py-1 rounded-lg bg-primary/10 text-primary uppercase">${escapeHtml(inc.status || 'PENDING')}</span>
                </div>
                <div class="flex items-center justify-between pt-2 border-t border-slate-100 dark:border-slate-800/60 text-xs">
                    <span class="text-on-surface-variant">Waste Type: <strong class="text-on-surface">${escapeHtml(inc.waste_type || 'General')}</strong></span>
                    <a href="../Waste Heatmap/index.html" class="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                        <span>Manage in Operations</span>
                        <span class="material-symbols-outlined text-[14px]">arrow_forward</span>
                    </a>
                </div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error("Failed to load priority complaints:", err);
        if (listEl) listEl.innerHTML = `<p class="text-error text-sm p-4">Error loading priority complaints: ${escapeHtml(err.message)}</p>`;
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

            let actionBtn = '';
            if (canAssign) {
                actionBtn = `<button
                       onclick="openAssignModal(${c.id}, '${safeWasteType}', '${safeArea}')"
                       class="px-4 py-2 bg-primary text-on-primary text-sm font-medium rounded-full active:scale-95 transition-transform">
                       Assign Driver
                   </button>`;
            } else if (c.status === 'RESOLVED' && c.proof_photo_url) {
                actionBtn = `<button
                       type="button"
                       data-action="view-admin-proof"
                       data-proof-url="${escapeHtml(c.proof_photo_url)}"
                       data-complaint-id="${c.id}"
                       data-waste-type="${safeWasteType}"
                       data-area="${safeArea}"
                       class="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold rounded-full flex items-center gap-1 active:scale-95 transition-all shadow-sm">
                       <span class="material-symbols-outlined text-[16px]">photo_camera</span>
                       <span>View Proof</span>
                   </button>`;
            } else {
                actionBtn = `<span class="text-xs text-on-surface-variant font-medium">${c.status === 'RESOLVED' ? 'Resolved' : 'Assigned'}</span>`;
            }

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
                <div class="shrink-0">${actionBtn}</div>
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

// ---- Collection Proof Photo Viewer Functions (Admin) ----
let _adminProofObjectUrl = null;
let _adminAbortController = null;
let _adminRequestGen = 0;

function ensureAdminProofModal() {
    let modal = document.getElementById('admin-proof-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'admin-proof-modal';
        modal.className = 'fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4 hidden backdrop-blur-sm';
        modal.innerHTML = `
          <div class="bg-white dark:bg-slate-900 rounded-3xl w-full max-w-lg p-6 space-y-4 shadow-2xl border border-slate-100 dark:border-slate-800">
            <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-emerald-600 text-2xl">photo_library</span>
                <h3 class="font-title-md font-bold text-on-surface">Collection Proof Photo</h3>
              </div>
              <button id="admin-proof-modal-close" class="p-1.5 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                <span class="material-symbols-outlined text-2xl">close</span>
              </button>
            </div>
            <div id="admin-proof-info" class="text-xs text-on-surface-variant font-medium"></div>
            <div class="relative w-full aspect-video bg-slate-100 dark:bg-slate-800 rounded-2xl overflow-hidden flex items-center justify-center border border-outline-variant/30">
              <div id="admin-proof-loading" class="flex flex-col items-center justify-center text-slate-400 gap-2">
                <span class="material-symbols-outlined text-3xl animate-spin">sync</span>
                <span class="text-xs font-medium">Retrieving collection proof photo...</span>
              </div>
              <div id="admin-proof-error" class="hidden flex flex-col items-center justify-center text-error p-4 text-center gap-2">
                <span class="material-symbols-outlined text-3xl">broken_image</span>
                <span id="admin-proof-error-msg" class="text-xs font-medium">Unable to load collection proof photo.</span>
              </div>
              <img id="admin-proof-img" class="w-full h-full object-contain hidden" alt="Collection Proof Photo">
            </div>
            <div class="flex justify-end pt-2">
              <button id="admin-proof-modal-dismiss" class="px-5 py-2.5 bg-primary text-on-primary text-sm font-medium rounded-full active:scale-95 transition-transform">
                Done
              </button>
            </div>
          </div>
        `;
        document.body.appendChild(modal);
    }

    const closeBtn = document.getElementById('admin-proof-modal-close');
    const dismissBtn = document.getElementById('admin-proof-modal-dismiss');
    if (closeBtn && !closeBtn._bound) {
        closeBtn._bound = true;
        closeBtn.addEventListener('click', closeAdminProofModal);
    }
    if (dismissBtn && !dismissBtn._bound) {
        dismissBtn._bound = true;
        dismissBtn.addEventListener('click', closeAdminProofModal);
    }
    if (!modal._boundBackdrop) {
        modal._boundBackdrop = true;
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeAdminProofModal();
        });
    }
    return modal;
}

function closeAdminProofModal() {
    _adminRequestGen++;
    if (_adminAbortController) {
        _adminAbortController.abort();
        _adminAbortController = null;
    }
    const modal = document.getElementById('admin-proof-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    if (_adminProofObjectUrl) {
        URL.revokeObjectURL(_adminProofObjectUrl);
        _adminProofObjectUrl = null;
    }
    const imgEl = document.getElementById('admin-proof-img');
    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.removeAttribute('src');
        imgEl.classList.add('hidden');
    }
}

async function viewAdminProofPhoto(proofUrl, complaintId, wasteType, area) {
    if (!proofUrl) {
        if (typeof window.showToast === 'function') {
            window.showToast('No proof photo is available for this complaint.', 'info');
        }
        return;
    }

    const currentGen = ++_adminRequestGen;
    if (_adminAbortController) {
        _adminAbortController.abort();
        _adminAbortController = null;
    }
    if (_adminProofObjectUrl) {
        URL.revokeObjectURL(_adminProofObjectUrl);
        _adminProofObjectUrl = null;
    }

    const modal = ensureAdminProofModal();
    const infoEl = document.getElementById('admin-proof-info');
    const loadingEl = document.getElementById('admin-proof-loading');
    const errorEl = document.getElementById('admin-proof-error');
    const errorMsgEl = document.getElementById('admin-proof-error-msg');
    const imgEl = document.getElementById('admin-proof-img');

    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.removeAttribute('src');
        imgEl.classList.add('hidden');
    }

    const taskId = proofUrl.split('/').filter(Boolean).pop();
    if (infoEl) {
        infoEl.textContent = `Complaint #${complaintId} (Task #${taskId}) · ${wasteType || 'General'} Waste in ${area || 'Municipal Area'}`;
    }

    loadingEl?.classList.remove('hidden');
    errorEl?.classList.add('hidden');
    modal.classList.remove('hidden');

    _adminAbortController = new AbortController();

    try {
        const blob = await API.fetchProofPhotoBlob(proofUrl, { signal: _adminAbortController.signal });
        if (currentGen !== _adminRequestGen) {
            return;
        }
        _adminProofObjectUrl = URL.createObjectURL(blob);
        if (imgEl) {
            imgEl.onload = () => {
                if (currentGen !== _adminRequestGen) return;
                loadingEl?.classList.add('hidden');
                imgEl.classList.remove('hidden');
            };
            imgEl.onerror = () => {
                if (currentGen !== _adminRequestGen) return;
                loadingEl?.classList.add('hidden');
                errorEl?.classList.remove('hidden');
                if (errorMsgEl) errorMsgEl.textContent = 'Failed to render retrieved image.';
            };
            imgEl.src = _adminProofObjectUrl;
        }
    } catch (err) {
        if (currentGen !== _adminRequestGen || err.name === 'AbortError') {
            return;
        }
        console.error('Failed to retrieve proof photo:', err);
        loadingEl?.classList.add('hidden');
        errorEl?.classList.remove('hidden');
        if (errorMsgEl) {
            errorMsgEl.textContent = err.message || 'Unable to retrieve proof photo.';
        }
    }
}

// Delegated click handler for admin proof buttons (both list and Leaflet popups)
if (!window._adminProofDelegationBound) {
    window._adminProofDelegationBound = true;
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action="view-admin-proof"]');
        if (btn) {
            e.stopPropagation();
            const { proofUrl, complaintId, wasteType, area } = btn.dataset;
            viewAdminProofPhoto(proofUrl, complaintId, wasteType, area);
        }
    });
}

window.viewAdminProofPhoto = viewAdminProofPhoto;
window.closeAdminProofModal = closeAdminProofModal;
window.addEventListener('beforeunload', () => {
    _adminRequestGen++;
    if (_adminAbortController) {
        _adminAbortController.abort();
        _adminAbortController = null;
    }
    if (_adminProofObjectUrl) {
        URL.revokeObjectURL(_adminProofObjectUrl);
        _adminProofObjectUrl = null;
    }
});
