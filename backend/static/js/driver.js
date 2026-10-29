/**
 * Driver Logic (Dashboard, Tasks, GPS Tracking & Pickup Verification)
 */
document.addEventListener('DOMContentLoaded', () => {

    // ---- Auth guard: redirect non-drivers to login ----
    const _token = localStorage.getItem('token');
    const _role  = localStorage.getItem('user_role');
    if (!_token || _role !== 'DRIVER') {
        localStorage.clear();
        const _isNative = (window.Capacitor && window.Capacitor.isNativePlatform()) || window.location.protocol === 'file:';
        window.location.href = _isNative ? '../Login Screen/index.html' : '/app/Login%20Screen/index.html';
        return;
    }

    const isDriverPage = window.location.pathname.includes('Driver Dashboard') ||
        window.location.pathname.includes('Pickup Verification') ||
        window.location.pathname.includes('Assigned Pickups');

    if (isDriverPage && localStorage.getItem('user_role') === 'DRIVER') {
        // ---- Real-time GPS Tracking ----
        let gpsInterval = setInterval(() => {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    async (pos) => {
                        try {
                            await API.updateDriverLocation(pos.coords.latitude, pos.coords.longitude);
                            console.log("GPS Location updated");
                        } catch (err) {
                            console.error("Failed to update GPS:", err);
                        }
                    },
                    (err) => console.warn("GPS tracking error:", err)
                );
            }
        }, 5000); // Update every 5 seconds

        // Clean up interval on page hide to prevent leaks
        window.addEventListener('pagehide', () => {
            clearInterval(gpsInterval);
        });
        
        // ---- Real-time WebSocket Push Notifications ----
        const userId = localStorage.getItem('user_id');
        const wsToken = localStorage.getItem('token');
            let wsUrl = null;
            if (window.SCOS_CONFIG && typeof window.SCOS_CONFIG.getWsUrl === 'function') {
                wsUrl = window.SCOS_CONFIG.getWsUrl(`/api/ws/driver/${userId}?token=${encodeURIComponent(wsToken)}`);
            } else {
                const protocol = window.location.protocol === 'https:' || window.location.href.includes('onrender') ? 'wss:' : 'ws:';
                const isNative = (window.Capacitor && window.Capacitor.isNativePlatform()) || window.location.protocol === 'file:';
                const wsBaseUrl = isNative ? 'scos-app.onrender.com' : window.location.host;
                wsUrl = `${protocol}//${wsBaseUrl}/api/ws/driver/${userId}?token=${encodeURIComponent(wsToken)}`;
            }

            if (!wsUrl) {
                console.warn("[Driver] WebSocket connection skipped: backend URL is not configured.");
                return;
            }

            const ws = new WebSocket(wsUrl);

            ws.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'NEW_TASK') {
                    if (window.Capacitor && window.Capacitor.isNativePlatform()) {
                        try {
                            const { LocalNotifications } = window.Capacitor.Plugins;
                            const { Haptics, ImpactStyle } = window.Capacitor.Plugins;
                            if (Haptics) await Haptics.impact({ style: ImpactStyle.Heavy });
                            if (LocalNotifications) {
                                let perm = await LocalNotifications.checkPermissions();
                                if (perm.display !== 'granted') {
                                    perm = await LocalNotifications.requestPermissions();
                                }
                                if (perm.display === 'granted') {
                                    await LocalNotifications.schedule({
                                        notifications: [{
                                            title: "New Pickup Assigned! 🚨",
                                            body: data.message,
                                            id: new Date().getTime(),
                                            schedule: { at: new Date(Date.now() + 100) },
                                            sound: null,
                                            attachments: null,
                                            actionTypeId: "",
                                            extra: null
                                        }]
                                    });
                                }
                            }
                        } catch (e) {
                            console.error("Capacitor Native Alert Failed", e);
                        }
                    } else {
                        window.showToast("🚨 New Pickup Assigned: " + data.message, "error");
                    }
                    if (window.location.pathname.includes('Driver Dashboard')) loadDriverDashboard();
                    if (window.location.pathname.includes('Assigned Pickups')) loadAssignedTasks();
                }
            };
            ws.onopen = () => console.log("Live WebSocket connection established");
            ws.onerror = (e) => console.log("WebSocket error", e);

            // Close WebSocket cleanly on page hide
            window.addEventListener('pagehide', () => {
                ws.close();
            });
        }
    }



    // Route logic based on current page
    if (window.location.pathname.includes('Driver Dashboard')) {
        loadDriverDashboard();
    } else if (window.location.pathname.includes('Assigned Pickups')) {
        loadAssignedTasks();
    } else if (window.location.pathname.includes('Pickup Verification')) {
        setupPickupVerification();
    }

    setupDriverBottomNav();
    setupDriverHeader();
});

// Helper for fallback toast
window.showToast = window.showToast || function (msg, type) {
    alert(msg);
};

/**
 * Populates the driver dashboard with dynamic stats
 */
async function loadDriverDashboard() {
    try {
        const stats = await API.fetchDriverDashboard();

        // Update greeting
        const greetingEl = document.getElementById('driver-welcome-text');
        if (greetingEl) greetingEl.textContent = `Good Morning, ${stats.driver_name}`;

        // Update "24 of 32 Pickups" Progress
        const progressEl = document.getElementById('driver-progress-text');
        if (progressEl) {
            progressEl.textContent = `${stats.completed_today} of ${stats.total_tasks} Pickups`;
        }

        // Update percentage badge
        let percentage = stats.total_tasks > 0 ? Math.round((stats.completed_today / stats.total_tasks) * 100) : 0;
        const percentageBadge = document.getElementById('driver-progress-percent');
        if (percentageBadge) percentageBadge.textContent = `${percentage}% Complete`;

        // Update progress bar
        const progressBar = document.getElementById('driver-progress-bar');
        if (progressBar) progressBar.style.width = `${percentage}%`;

        // Load Alerts
        const alertsList = document.getElementById('driver-alerts-list');
        if (alertsList) {
            const complaints = await API.request('/api/driver/active_complaints', { method: 'GET' });
            if (!complaints || complaints.length === 0) {
                alertsList.innerHTML = `<div class="py-4 text-center opacity-50"><span class="material-symbols-outlined text-4xl mb-2">check_circle</span><p>No active alerts.</p></div>`;
            } else {
                alertsList.innerHTML = complaints.slice(0, 2).map(c => `
                    <div class="flex items-start gap-4 p-4 bg-white rounded-xl border-l-4 border-error shadow-sm">
                        <div class="p-2 bg-error-container text-error rounded-lg">
                            <span class="material-symbols-outlined">priority_high</span>
                        </div>
                        <div class="flex-1">
                            <div class="flex justify-between items-start">
                                <h4 class="text-title-md font-title-md text-on-surface">${c.waste_type || 'Urgent'} - ${c.area}</h4>
                            </div>
                            <p class="text-body-md font-body-md text-on-surface-variant mt-1">Requires immediate dispatch.</p>
                            <div class="flex gap-2 mt-3">
                                <button onclick="this.closest('.flex.items-start')?.remove(); window.showToast('Incident acknowledged', 'success')" class="px-4 py-2 font-label-lg text-error hover:bg-error/10 rounded-lg transition-colors active:scale-95">Acknowledge</button>
                            </div>
                        </div>
                    </div>
                `).join('');
            }
        }

    } catch (e) {
        console.error("Error loading driver dashboard:", e);
    }
}

/**
 * Loads dynamic tasks into Assigned Pickups list
 */
async function loadAssignedTasks() {
    try {
        const tasksList = document.getElementById('tasks-list');
        if (!tasksList) return;

        const response = await API.fetchAssignedTasks();
        // Backend returns { tasks: [...] }
        const tasks = response.tasks || [];
        tasksList.innerHTML = ''; // clear mock entries

        const assignedCountEl = document.getElementById('assigned-count');
        if (assignedCountEl) assignedCountEl.textContent = tasks.length;

        if (tasks.length === 0) {
            tasksList.innerHTML = '<p class="text-center text-outline p-md font-body-md">No tasks assigned currently. Have a great day!</p>';
            return;
        }

        tasks.forEach(task => {
            let priorityClass = 'bg-surface-container-high text-on-surface-variant';
            let priorityIcon = 'keyboard_arrow_down';
            let priorityText = 'LOW';

            if (task.priority === 'HIGH') {
                priorityClass = 'bg-error-container text-on-error-container';
                priorityIcon = 'priority_high';
                priorityText = 'HIGH';
            } else if (task.priority === 'MEDIUM') {
                priorityClass = 'bg-secondary-container text-on-secondary-container';
                priorityIcon = 'drag_handle';
                priorityText = 'MED';
            }

            const taskHtml = `
            <div class="bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-md shadow-sm hover:shadow-md transition-all">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-md">
                    <div class="flex gap-md">
                        <div class="flex flex-col items-center justify-center ${priorityClass} w-16 h-16 rounded-xl shrink-0">
                            <span class="material-symbols-outlined">${priorityIcon}</span>
                            <span class="font-label-sm text-label-sm uppercase font-bold">${priorityText}</span>
                        </div>
                        <div>
                            <div class="flex items-center gap-sm mb-xs">
                                <span class="bg-surface-variant text-on-surface-variant font-label-sm text-label-sm px-sm py-[2px] rounded-full uppercase">${task.waste_type}</span>
                                <span class="font-body-md text-body-md text-primary font-semibold">${task.distance_km} km away</span>
                            </div>
                            <h3 class="font-title-md text-title-md text-on-surface mb-xs">${task.address}</h3>
                            <div class="flex items-center gap-base text-on-surface-variant">
                                <span class="material-symbols-outlined text-[18px]">inventory_2</span>
                                <span class="font-body-md text-body-md">Bin • ${task.bin_fill_percent}% Full</span>
                            </div>
                        </div>
                    </div>
                    <div class="flex items-center gap-sm">
                        <button class="flex-1 md:flex-none bg-primary text-on-primary px-lg py-sm rounded-full font-label-lg text-label-lg flex items-center justify-center gap-sm active:scale-95 transition-transform" onclick="window.location.href='../Pickup Verification/index.html?id=${task.complaint_id}'">
                            <span class="material-symbols-outlined text-[18px]">verified</span>
                            Verify Pickup
                        </button>
                    </div>
                </div>
            </div>`;
            tasksList.innerHTML += taskHtml;
        });
    } catch (e) {
        console.error("Error loading tasks:", e);
    }
}

/**
 * Completes the pickup transaction
 */
function setupPickupVerification() {
    const urlParams = new URLSearchParams(window.location.search);
    const complaintId = urlParams.get('id');
    const complaintInput = document.getElementById('complaint-id');
    if (complaintInput && complaintId) {
        complaintInput.value = complaintId;
    }
    const titleEl = document.getElementById('pickup-bin-title');
    if (titleEl && complaintId) {
        titleEl.textContent = `Complaint #${complaintId}`;
    }

    const pickupForm = document.getElementById('pickup-verification-form');
    if (pickupForm) {
        pickupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = pickupForm.querySelector('button[type="submit"]');

            const imageInput = document.getElementById('proof-image');
            const targetComplaintId = document.getElementById('complaint-id')?.value || complaintId || 1;

            if (!targetComplaintId) {
                window.showToast("No complaint ID found. Please navigate from the task list.", "error");
                return;
            }

            const formData = new FormData();
            // Include photo if selected (optional — backend does not store it)
            if (imageInput && imageInput.files[0]) {
                formData.append('proof_photo', imageInput.files[0]);
            }
            formData.append('complaint_id', targetComplaintId);

            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Verifying...";
            submitBtn.disabled = true;

            try {
                const response = await API.completePickup(formData);
                window.showToast(response.message || "Pickup verified!", "success");
                setTimeout(() => {
                    window.location.href = '../Driver Dashboard/index.html';
                }, 1500);
            } catch (err) {
                window.showToast(err.message, "error");
            } finally {
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }
}


/**
 * Universal Driver Bottom Navigation Router
 */
function setupDriverBottomNav() {
    const navs = document.querySelectorAll('nav.fixed.bottom-0');
    navs.forEach(nav => {
        const anchors = nav.querySelectorAll('a, button');
        anchors.forEach(a => {
            const iconSpan = a.querySelector('.material-symbols-outlined');
            let iconName = '';
            if (iconSpan) {
                iconName = iconSpan.getAttribute('data-icon') || iconSpan.textContent.trim().toLowerCase();
            }

            if (iconName) {
                a.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (iconName === 'home') {
                        window.location.href = '../Driver Dashboard/index.html';
                    } else if (iconName === 'assignment' || iconName === 'task' || iconName === 'tasks') {
                        window.location.href = '../Assigned Pickups/index.html';
                    } else {
                        window.location.href = '../Driver Dashboard/index.html';
                    }
                });
            }
        });
    });
}

/**
 * Universal Driver Profile Logout
 */
function setupDriverHeader() {
    const profileImg = document.querySelector('header img[alt="User Profile"]');
    if (profileImg) {
        profileImg.style.cursor = 'pointer';
        profileImg.addEventListener('click', () => {
            if (confirm("Logout from Driver account?")) {
                localStorage.removeItem('token');
                localStorage.removeItem('user_role');
                window.location.href = '../Login Screen/index.html';
            }
        });
    }

    document.querySelectorAll('header button').forEach(btn => {
        const notifIcon = btn.querySelector('[data-icon="notifications"], .material-symbols-outlined');
        if (notifIcon && (notifIcon.getAttribute('data-icon') === 'notifications' || notifIcon.textContent.trim() === 'notifications')) {
            btn.addEventListener('click', () => {
                window.showToast("You have no new notifications.", "info");
            });
        }
    });
}
