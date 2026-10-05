/**
 * Admin Logic (Simulated Interactions for Heatmaps & Dashboards)
 */
document.addEventListener('DOMContentLoaded', () => {

    // ---- Auth guard: redirect non-admins to login ----
    const _token = localStorage.getItem('token');
    const _role  = localStorage.getItem('user_role');
    if (!_token || _role !== 'ADMIN') {
        localStorage.clear();
        const _isNative = (window.Capacitor && window.Capacitor.isNativePlatform()) || window.location.protocol === 'file:';
        window.location.href = _isNative ? '../Login Screen/index.html' : '/app/Login%20Screen/index.html';
        return;
    }

    // Mount toast.js listeners onto static admin buttons to make them feel interactive
    
    // 1. Dropdown Filters
    const filterChips = document.querySelectorAll('.rounded-full.border-outline-variant');
    filterChips.forEach(chip => {
        if (chip.textContent.includes('District:') || chip.textContent.includes('Type:') || chip.textContent.includes('Time:')) {
            chip.style.cursor = 'pointer';
            chip.addEventListener('click', () => {
                window.showToast('Filter options opened', 'info');
            });
        }
    });

    // 2. Action Buttons
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
        const text = btn.textContent.trim();
        
        if (text.includes('By Ward') || text.includes('By Waste Type') || text.includes('Live Alerts')) {
            btn.addEventListener('click', () => {
                window.showToast(`Switched view to ${text}`, 'success');
                // Basic visual toggle for active state
                btn.parentElement.querySelectorAll('button').forEach(b => {
                    b.classList.remove('bg-primary', 'text-on-primary');
                    b.classList.add('text-on-surface-variant');
                });
                btn.classList.add('bg-primary', 'text-on-primary');
                btn.classList.remove('text-on-surface-variant');
            });
        }
        
        if (text.includes('Dispatch Team') || text.includes('Assign Fleet')) {
            btn.addEventListener('click', () => {
                window.showToast('Dispatching rapid response unit...', 'warning');
            });
        }
        
        if (text.includes('Resolve') && text.includes('False Alarm')) {
            btn.addEventListener('click', () => {
                window.showToast('Incident marked as False Alarm', 'success');
            });
        }
    });
    
    // 3. Notifications Bell & Profile
    const notifBtn = document.querySelector('header button');
    if (notifBtn && notifBtn.textContent.includes('notifications')) {
        notifBtn.addEventListener('click', () => {
            window.showToast('No critical system alerts.', 'info');
        });
    }

    const profilePic = document.querySelector('header img');
    if (profilePic) {
        profilePic.style.cursor = 'pointer';
        profilePic.addEventListener('click', () => {
            if (confirm("Logout from Admin console?")) {
                localStorage.clear();
                window.location.href = '../Login Screen/index.html';
            }
        });
    }
    
    // 4. Universal Admin Navigation (Role Aware for shared Heatmaps)
    const role = localStorage.getItem('user_role') || 'ADMIN';
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
                if (role === 'CITIZEN') {
                    if (iconName === 'home') window.location.href = '../Citizen Dashboard/index.html';
                    else if (iconName === 'map' || iconName === 'explore') window.location.href = '../Waste Heatmap/index.html';
                    else if (iconName === 'assignment') window.location.href = '../Complaint History/index.html';
                    else if (iconName === 'history') window.location.href = '../Report Waste/index.html';
                    else if (iconName === 'leaderboard') window.location.href = '../Cleanliness Heatmap/index.html';
                } else if (role === 'DRIVER') {
                    if (iconName === 'home') window.location.href = '../Driver Dashboard/index.html';
                    else if (iconName === 'assignment') window.location.href = '../Assigned Pickups/index.html';
                    else if (iconName === 'map' || iconName === 'explore') window.location.href = '../Navigation Screen/index.html';
                    else window.showToast('Feature coming soon!', 'info');
                } else {
                    // Admin defaults
                    if (iconName === 'home') window.location.href = '../Waste Heatmap/index.html';
                    else if (iconName === 'map' || iconName === 'explore') window.location.href = '../Waste Heatmap/index.html';
                    else if (iconName === 'assignment') window.location.href = '../Illegal Dumping/index.html';
                    else if (iconName === 'history') window.location.href = '../Cleanliness Heatmap/index.html';
                    else if (iconName === 'leaderboard') window.showToast('Stats view loading...', 'info');
                }
            });
        }
    });

    // ---- Dynamic Admin Data Fetching ----
    
    // Safely update text if a preceding label matches
    const updateStatByLabel = (labelText, value) => {
        const elements = document.querySelectorAll('p.text-label-sm');
        elements.forEach(el => {
            if (el.textContent.includes(labelText)) {
                if (el.nextElementSibling) {
                    el.nextElementSibling.textContent = value;
                }
            }
        });
    };

    const loadAdminData = async () => {
        const path = window.location.pathname;
        
        try {
            if (path.includes('Waste Heatmap') || path.includes('Cleanliness Heatmap')) {
                const stats = await API.fetchAdminOverview();
                
                const totalBins = document.getElementById('admin-total-bins');
                const criticalBins = document.getElementById('admin-critical-bins');
                const efficiencyEl = document.getElementById('admin-collection-efficiency');
                const efficiencyBar = document.getElementById('admin-collection-bar');

                if (totalBins) totalBins.textContent = stats.total_complaints * 12; // Simulated total
                if (criticalBins) criticalBins.textContent = stats.pending_complaints || 0;
                if (efficiencyEl) efficiencyEl.textContent = `${stats.collection_rate || 0}%`;
                if (efficiencyBar) efficiencyBar.style.width = `${stats.collection_rate || 0}%`;
                
                const heatmapData = await API.fetchAdminHeatmap();
                // Optionally update heatmap UI if specific lists exist
            }
            
            if (path.includes('Illegal Dumping')) {
                const dumpData = await API.fetchIllegalDumping();
                
                const activeEl = document.getElementById('dumping-active-count');
                const highRiskEl = document.getElementById('dumping-high-risk');
                const avgClearEl = document.getElementById('dumping-avg-clear');

                if (activeEl) activeEl.textContent = dumpData.active_count || dumpData.active_incidents || 0;
                if (highRiskEl) highRiskEl.textContent = dumpData.high_risk_count || "0";
                if (avgClearEl) avgClearEl.textContent = `${dumpData.avg_clear_time || dumpData.avg_clear_hours || "2.4"}h`;
            }
            
        } catch (err) {
            console.error("Failed to fetch live admin stats:", err);
            // Non-blocking failure, keeps existing UI intact
        }
    };
    
    loadAdminData();

    // ---- Admin Complaints Management Panel ----
    // Only runs on the Waste Heatmap page (where the panel is embedded)
    if (window.location.pathname.includes('Waste Heatmap')) {
        loadAdminComplaints();
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
                  drivers.map(d => `<option value="${d.id}">${d.name} (${d.email})</option>`).join('');
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
            const assignBtn = canAssign
                ? `<button
                       onclick="openAssignModal(${c.id}, '${(c.waste_type || 'General').replace(/'/g, '')}', '${(c.area || 'Unknown').replace(/'/g, '')}')"
                       class="px-4 py-2 bg-primary text-on-primary text-sm font-medium rounded-full active:scale-95 transition-transform">
                       Assign Driver
                   </button>`
                : `<span class="text-xs text-on-surface-variant">${c.status === 'RESOLVED' ? 'Resolved' : 'Assigned'}</span>`;

            return `
            <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-4 flex items-center justify-between gap-4">
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                        <span class="text-xs font-medium px-2 py-0.5 rounded-full border ${statusColor}">${c.status}</span>
                        <span class="text-xs text-on-surface-variant">#${c.id}</span>
                    </div>
                    <h4 class="font-medium text-on-surface truncate">${c.waste_type || 'General'} — ${c.area || 'Unknown Area'}</h4>
                    <p class="text-xs text-on-surface-variant">${c.zone || ''} · ${c.created_at ? new Date(c.created_at).toLocaleString() : 'Unknown date'}</p>
                </div>
                <div class="shrink-0">${assignBtn}</div>
            </div>`;
        }).join('');

    } catch (err) {
        console.error('Failed to load admin complaints:', err);
        if (listEl) listEl.innerHTML = `<p class="text-error text-sm p-4">Error loading complaints: ${err.message}</p>`;
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
