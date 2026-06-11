/**
 * Driver Logic (Dashboard, Tasks, GPS Tracking & Pickup Verification)
 */
document.addEventListener('DOMContentLoaded', () => {

    const isDriverPage = window.location.pathname.includes('Driver Dashboard') ||
        window.location.pathname.includes('Pickup Verification') ||
        window.location.pathname.includes('Assigned Pickups') ||
        window.location.pathname.includes('Navigation Screen');

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
        
        // ---- Real-time WebSocket Push Notifications ----
        const userId = localStorage.getItem('user_id');
        if (userId) {
            const protocol = window.location.protocol === 'https:' || window.location.href.includes('onrender') ? 'wss:' : 'ws:';
            const wsBaseUrl = (window.Capacitor && window.Capacitor.isNativePlatform()) || window.location.origin.includes('localhost') || window.location.protocol === 'file:' 
                ? 'scos-app.onrender.com' 
                : window.location.host;
            
            const wsUrl = `${protocol}//${wsBaseUrl}/api/ws/driver/${userId}`;
            const ws = new WebSocket(wsUrl);
            
            ws.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'NEW_TASK') {
                    // Trigger capacitor push notification if native
                    if (window.Capacitor && window.Capacitor.isNativePlatform()) {
                        try {
                            const { LocalNotifications } = window.Capacitor.Plugins;
                            const { Haptics, ImpactStyle } = window.Capacitor.Plugins;
                            
                            await Haptics.impact({ style: ImpactStyle.Heavy });
                            
                            await LocalNotifications.schedule({
                                notifications: [
                                    {
                                        title: "New Pickup Assigned! 🚨",
                                        body: data.message,
                                        id: new Date().getTime(),
                                        schedule: { at: new Date(Date.now() + 100) },
                                        sound: null, // Default
                                        attachments: null,
                                        actionTypeId: "",
                                        extra: null
                                    }
                                ]
                            });
                        } catch (e) {
                            console.error("Capacitor Native Alert Failed", e);
                        }
                    } else {
                        // Standard web fallback
                        window.showToast("🚨 New Pickup Assigned: " + data.message, "error");
                    }
                    
                    // Reload dashboard or assigned tasks if on those screens
                    if (window.location.pathname.includes('Driver Dashboard')) loadDriverDashboard();
                    if (window.location.pathname.includes('Assigned Pickups')) loadAssignedTasks();
                }
            };
            ws.onopen = () => console.log("Live WebSocket connection established");
            ws.onerror = (e) => console.log("WebSocket error", e);
        }
    }

    // Route logic based on current page
    if (window.location.pathname.includes('Driver Dashboard')) {
        loadDriverDashboard();
    } else if (window.location.pathname.includes('Assigned Pickups')) {
        loadAssignedTasks();
    } else if (window.location.pathname.includes('Navigation Screen')) {
        setupNavigationScreen();
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
                                <button onclick="window.showToast('Incident acknowledged', 'success')" class="px-4 py-2 font-label-lg text-error hover:bg-error/10 rounded-lg transition-colors active:scale-95">Acknowledge</button>
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

        const tasks = await API.fetchAssignedTasks();
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
                        <button class="flex-1 md:flex-none border border-outline px-md py-sm rounded-full font-label-lg text-label-lg text-primary hover:bg-surface-container transition-colors" onclick="window.showToast('Viewing details for task ${task.id}', 'info')">
                            Details
                        </button>
                        <button class="flex-1 md:flex-none bg-primary text-on-primary px-lg py-sm rounded-full font-label-lg text-label-lg flex items-center justify-center gap-sm active:scale-95 transition-transform" onclick="window.location.href='../Navigation Screen/index.html?id=${task.complaint_id}'">
                            <span class="material-symbols-outlined">navigation</span>
                            Start Route
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
 * Binds arrived button to navigate to pickup verification screen
 */
function setupNavigationScreen() {
    const urlParams = new URLSearchParams(window.location.search);
    const complaintId = urlParams.get('id');

    const arrivedBtn = document.getElementById('btn-arrived');
    if (arrivedBtn && complaintId) {
        arrivedBtn.addEventListener('click', () => {
            window.location.href = `../Pickup Verification/index.html?id=${complaintId}`;
        });
    } else if (arrivedBtn) {
        // Fallback for mock demo without specific ID
        arrivedBtn.addEventListener('click', () => {
            window.location.href = `../Pickup Verification/index.html?id=1`;
        });
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

    const pickupForm = document.getElementById('pickup-verification-form');
    if (pickupForm) {
        pickupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = pickupForm.querySelector('button[type="submit"]');

            const imageInput = document.getElementById('proof-image');
            const targetComplaintId = document.getElementById('complaint-id')?.value || 1;

            if (!imageInput.files[0]) {
                window.showToast("Please select a proof photo", "error");
                return;
            }

            const formData = new FormData();
            formData.append('proof_photo', imageInput.files[0]);
            formData.append('complaint_id', targetComplaintId);

            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Verifying...";
            submitBtn.disabled = true;

            try {
                const response = await API.completePickup(formData);
                window.showToast(response.message || "Pickup verified!", "success");

                if (response.fraud_check && response.fraud_check.is_fraud) {
                    window.showToast("Warning: Potential fraud detected.", "error");
                } else {
                    setTimeout(() => {
                        window.location.href = '../Driver Dashboard/index.html';
                    }, 1500);
                }
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
                    } else if (iconName === 'assignment') {
                        window.location.href = '../Assigned Pickups/index.html';
                    } else if (iconName === 'map' || iconName === 'explore') {
                        window.location.href = '../Navigation Screen/index.html';
                    } else {
                        // Placeholder for unlinked stats/reports
                        window.showToast('Feature coming soon!', 'info');
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
}
