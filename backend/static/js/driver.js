/**
 * Driver Logic (Dashboard, Tasks, GPS Tracking & Pickup Verification)
 */

/**
 * Phase 5: Singleton WebSocket Connection Controller for Driver
 * Handles automatic reconnect with exponential backoff & jitter,
 * connection stability reset, lifecycle pause/resume,
 * authoritative REST probe auth recovery, BFCache restoration,
 * task reconciliation on connect, and idempotent cleanup.
 */
const DriverSocketController = {
    ws: null,
    retryTimer: null,
    stabilityTimer: null,
    retryCount: 0,
    isConnecting: false,
    isExplicitClose: false,
    isAuthForbidden: false,
    activeAuthProbePromise: null,
    activeReconnectPromise: null,

    getWsUrl() {
        const userId = localStorage.getItem('user_id');
        const wsToken = (typeof API !== 'undefined' && typeof API.getToken === 'function')
            ? API.getToken()
            : localStorage.getItem('token');

        if (!userId || !wsToken) {
            return null;
        }

        if (window.SCOS_CONFIG && typeof window.SCOS_CONFIG.getWsUrl === 'function') {
            return window.SCOS_CONFIG.getWsUrl(`/api/ws/driver/${userId}?token=${encodeURIComponent(wsToken)}`);
        }

        const protocol = (window.location.protocol === 'https:' || window.location.href.includes('onrender')) ? 'wss:' : 'ws:';
        const isNative = (window.Capacitor && window.Capacitor.isNativePlatform()) || window.location.protocol === 'file:';
        const wsBaseUrl = isNative ? 'scos-app.onrender.com' : window.location.host;
        return `${protocol}//${wsBaseUrl}/api/ws/driver/${userId}?token=${encodeURIComponent(wsToken)}`;
    },

    connect() {
        if (this.isExplicitClose || this.isAuthForbidden) {
            return;
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        if (this.retryTimer) {
            clearTimeout(this.retryTimer);
            this.retryTimer = null;
        }

        const wsUrl = this.getWsUrl();
        if (!wsUrl) {
            console.warn("[DriverSocket] Missing credentials or backend URL; connection skipped.");
            return;
        }

        this.isConnecting = true;
        try {
            const socket = new WebSocket(wsUrl);
            this.ws = socket;

            socket.onopen = () => {
                if (this.ws !== socket) return;

                console.log("[DriverSocket] Live WebSocket connection established");
                this.isConnecting = false;

                // Stability timer: only reset retryCount if the connection remains open for 5 seconds
                if (this.stabilityTimer) {
                    clearTimeout(this.stabilityTimer);
                    this.stabilityTimer = null;
                }
                this.stabilityTimer = setTimeout(() => {
                    if (this.ws === socket && socket.readyState === WebSocket.OPEN) {
                        console.log("[DriverSocket] Connection stable for 5s; resetting retry counter.");
                        this.retryCount = 0;
                    }
                    this.stabilityTimer = null;
                }, 5000);

                // Reconnect reconciliation: reload assigned tasks & dashboard without duplicating entries or notifications
                this.reconcileTasks();
            };

            socket.onmessage = async (event) => {
                if (this.ws !== socket) return;
                try {
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
                                console.error("[DriverSocket] Capacitor Native Alert Failed", e);
                            }
                        } else {
                            if (typeof window.showToast === 'function') {
                                window.showToast("🚨 New Pickup Assigned: " + data.message, "error");
                            }
                        }

                        this.reconcileTasks();
                    }
                } catch (e) {
                    console.error("[DriverSocket] Error parsing WebSocket message:", e);
                }
            };

            socket.onerror = (e) => {
                console.log("[DriverSocket] WebSocket error observed", e);
            };

            socket.onclose = async (event) => {
                if (this.ws !== socket) return;

                console.log(`[DriverSocket] WebSocket closed (code: ${event.code}, wasClean: ${event.wasClean})`);
                this.ws = null;
                this.isConnecting = false;

                if (this.stabilityTimer) {
                    clearTimeout(this.stabilityTimer);
                    this.stabilityTimer = null;
                }

                if (this.isExplicitClose || this.isAuthForbidden) {
                    return;
                }

                // Following abnormal closure (e.g. 1006): do not infer auth failure from close code.
                // Schedule backoff reconnect, checking auth authoritatively via REST probe.
                this.scheduleReconnect();
            };
        } catch (err) {
            console.error("[DriverSocket] Failed to create WebSocket instance:", err);
            this.ws = null;
            this.isConnecting = false;
            if (this.stabilityTimer) {
                clearTimeout(this.stabilityTimer);
                this.stabilityTimer = null;
            }
            this.scheduleReconnect();
        }
    },

    reconcileTasks() {
        try {
            const path = decodeURIComponent(window.location.pathname);
            if (path.includes('Driver Dashboard') && typeof loadDriverDashboard === 'function') {
                loadDriverDashboard();
            }
            if (path.includes('Assigned Pickups') && typeof loadAssignedTasks === 'function') {
                loadAssignedTasks();
            }
        } catch (err) {
            console.error("[DriverSocket] Error reconciling tasks:", err);
        }
    },

    scheduleReconnect() {
        if (this.isExplicitClose || this.isAuthForbidden) {
            return;
        }

        if (this.retryTimer) {
            clearTimeout(this.retryTimer);
            this.retryTimer = null;
        }

        // Pause retry while document is hidden / backgrounded
        if (document.hidden) {
            console.log("[DriverSocket] Document hidden; pausing reconnect timer.");
            return;
        }

        // Exponential backoff with jitter, strictly capped at 30,000 ms:
        // Math.min(1000 * Math.pow(1.5, retryCount) + Math.random() * 500, 30000)
        const delay = Math.min(1000 * Math.pow(1.5, this.retryCount) + Math.random() * 500, 30000);
        this.retryCount++;

        console.log(`[DriverSocket] Scheduling reconnect attempt #${this.retryCount} in ${Math.round(delay)}ms`);

        this.retryTimer = setTimeout(async () => {
            this.retryTimer = null;
            await this.reconnectWithAuthCheck();
        }, delay);
    },

    async reconnectWithAuthCheck() {
        if (this.isExplicitClose || this.isAuthForbidden) {
            return;
        }

        if (document.hidden) {
            return;
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            return;
        }

        // Single-flight reconnect lock: coalesce concurrent reconnect requests
        if (this.activeReconnectPromise) {
            return this.activeReconnectPromise;
        }

        // Cancel any pending timer since we are initiating immediate reconnect check
        if (this.retryTimer) {
            clearTimeout(this.retryTimer);
            this.retryTimer = null;
        }

        let currentReconnectPromise = null;
        currentReconnectPromise = (async () => {
            try {
                // Authoritative authentication recovery check using GET /api/driver/dashboard:
                const probeStatus = await this.probeAuth();

                // If this reconnect attempt was cancelled or superseded while probe was in-flight, abort immediately
                if (this.activeReconnectPromise !== currentReconnectPromise) {
                    return;
                }

                // If explicit close occurred while probe was in-flight, abort immediately
                if (this.isExplicitClose) {
                    return;
                }

                if (probeStatus === 'EXPIRED') {
                    this.isExplicitClose = true;
                    return;
                }

                if (probeStatus === 'FORBIDDEN') {
                    this.isAuthForbidden = true;
                    if (typeof window.showToast === 'function') {
                        window.showToast("Driver authorization required. Live connection disabled.", "error");
                    }
                    return;
                }

                // Check document.hidden AFTER probe resolves and immediately before connecting:
                // If page was backgrounded while probe was in flight, defer until foreground event.
                if (document.hidden) {
                    console.log("[DriverSocket] Document became hidden during auth probe; deferring reconnect until foreground.");
                    return;
                }

                if (this.isExplicitClose || this.isAuthForbidden) {
                    return;
                }

                // Double check if another socket connected while probe was in-flight
                if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
                    return;
                }

                // Either probe succeeded (valid auth) or was transient network failure: proceed to connect
                this.connect();
            } finally {
                // Identity-checked cleanup: only clear if activeReconnectPromise still points to this exact promise
                if (this.activeReconnectPromise === currentReconnectPromise) {
                    this.activeReconnectPromise = null;
                }
            }
        })();

        this.activeReconnectPromise = currentReconnectPromise;
        return currentReconnectPromise;
    },

    async probeAuth() {
        // Single-flight authentication probe: coalesce concurrent callers
        if (this.activeAuthProbePromise) {
            return this.activeAuthProbePromise;
        }

        let currentProbePromise = null;
        currentProbePromise = (async () => {
            try {
                if (typeof API !== 'undefined' && typeof API.fetchDriverDashboard === 'function') {
                    await API.fetchDriverDashboard();
                    return 'SUCCESS';
                }
                return 'SUCCESS';
            } catch (err) {
                // Classify HTTP status reliably:
                // 1. HTTP 401 / Session Expired
                if (err && (err.status === 401 || (err.message && err.message.includes("Session expired")))) {
                    return 'EXPIRED';
                }
                // 2. HTTP 403 / Authorization Failure
                if (err && (err.status === 403 || (err.message && (err.message.includes("authorization required") || err.message.includes("Forbidden"))))) {
                    return 'FORBIDDEN';
                }
                // 3. Transient Network Failure or other non-auth error
                return 'NETWORK_FAILURE';
            } finally {
                // Identity-checked cleanup: only clear if activeAuthProbePromise still points to this exact promise
                if (this.activeAuthProbePromise === currentProbePromise) {
                    this.activeAuthProbePromise = null;
                }
            }
        })();

        this.activeAuthProbePromise = currentProbePromise;
        return currentProbePromise;
    },

    disconnect(isExplicit = false) {
        if (isExplicit) {
            this.isExplicitClose = true;
        }
        if (this.retryTimer) {
            clearTimeout(this.retryTimer);
            this.retryTimer = null;
        }
        if (this.stabilityTimer) {
            clearTimeout(this.stabilityTimer);
            this.stabilityTimer = null;
        }
        if (this.ws) {
            try {
                const socket = this.ws;
                this.ws = null;
                socket.onopen = null;
                socket.onmessage = null;
                socket.onerror = null;
                socket.onclose = null;
                socket.close(1000, isExplicit ? "Driver session logged out" : "Page teardown");
            } catch (e) {
                // Ignore socket closing error on teardown
            }
        }
        this.isConnecting = false;
        this.activeAuthProbePromise = null;
        this.activeReconnectPromise = null;
    }
};

window.DriverSocketController = DriverSocketController;

// ---- Application Lifecycle Handlers ----
// Visibility change: pause retries when backgrounded; reconnect when returning to foreground
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (DriverSocketController.retryTimer) {
            clearTimeout(DriverSocketController.retryTimer);
            DriverSocketController.retryTimer = null;
        }
    } else {
        if (!DriverSocketController.isExplicitClose && !DriverSocketController.isAuthForbidden) {
            if (!DriverSocketController.ws || DriverSocketController.ws.readyState === WebSocket.CLOSED || DriverSocketController.ws.readyState === WebSocket.CLOSING) {
                DriverSocketController.reconnectWithAuthCheck();
            }
        }
    }
});

// BFCache restoration handling: pageshow with event.persisted
window.addEventListener('pageshow', (event) => {
    if (event.persisted) {
        console.log("[DriverSocket] Page restored from BFCache; checking connection status.");
        if (!DriverSocketController.isExplicitClose && !DriverSocketController.isAuthForbidden) {
            if (!DriverSocketController.ws || DriverSocketController.ws.readyState === WebSocket.CLOSED || DriverSocketController.ws.readyState === WebSocket.CLOSING) {
                DriverSocketController.reconnectWithAuthCheck();
            }
        }
    }
});

// Clean up socket and pending timers on page hide & before unload without permanent explicit closure
const handlePageTeardown = () => {
    DriverSocketController.disconnect(false);
};
window.addEventListener('pagehide', handlePageTeardown);
window.addEventListener('beforeunload', handlePageTeardown);

document.addEventListener('DOMContentLoaded', () => {

    // ---- Auth guard: redirect non-drivers to login ----
    const _token = localStorage.getItem('token');
    const _role  = localStorage.getItem('user_role');
    if (!_token || _role !== 'DRIVER') {
        localStorage.clear();
        window.location.href = '../Login Screen/index.html';
        return;
    }

    const isDriverPage = decodeURIComponent(window.location.pathname).includes('Driver Dashboard') ||
        decodeURIComponent(window.location.pathname).includes('Pickup Verification') ||
        decodeURIComponent(window.location.pathname).includes('Assigned Pickups');

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
        
        // ---- Phase 5: Real-time WebSocket Push Notifications with Resilience ----
        DriverSocketController.connect();
    }

    // Route logic based on current page
    if (decodeURIComponent(window.location.pathname).includes('Driver Dashboard')) {
        loadDriverDashboard();
    } else if (decodeURIComponent(window.location.pathname).includes('Assigned Pickups')) {
        loadAssignedTasks();
    } else if (decodeURIComponent(window.location.pathname).includes('Pickup Verification')) {
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

        // Update genuine operational task metrics
        const pendingEl = document.getElementById('driver-pending-tasks');
        if (pendingEl) pendingEl.textContent = Math.max(0, (stats.total_tasks || 0) - (stats.completed_today || 0));

        const completedEl = document.getElementById('driver-completed-today');
        if (completedEl) completedEl.textContent = stats.completed_today || 0;

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

        const nextPickupEl = document.getElementById('next-pickup-header');
        const routeInfoEl = document.getElementById('route-vehicle-info');
        if (tasks.length === 0) {
            if (nextPickupEl) nextPickupEl.textContent = 'All Pickups Complete';
            if (routeInfoEl) routeInfoEl.textContent = 'No pending pickups assigned';
            tasksList.innerHTML = '<p class="text-center text-outline p-md font-body-md">No tasks assigned currently. Have a great day!</p>';
            return;
        } else {
            if (nextPickupEl) nextPickupEl.textContent = `Next Pickup: ${tasks[0].distance_km} km`;
            if (routeInfoEl) routeInfoEl.textContent = `${tasks.length} active assignment(s) on route`;
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
                                <span class="material-symbols-outlined text-[18px]">schedule</span>
                                <span class="font-body-md text-body-md">Status: ${task.status || 'ASSIGNED'}</span>
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
    const titleEl = document.getElementById('pickup-bin-title');
    if (complaintId) {
        if (complaintInput) complaintInput.value = complaintId;
        if (titleEl) titleEl.textContent = `Complaint #${complaintId}`;
    } else {
        if (complaintInput) complaintInput.value = '';
        if (titleEl) titleEl.textContent = 'No Active Task Selected';
    }

    const pickupForm = document.getElementById('pickup-verification-form');
    if (pickupForm) {
        pickupForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = pickupForm.querySelector('button[type="submit"]');

            const imageInput = document.getElementById('proof-image');
            const inputVal = document.getElementById('complaint-id')?.value?.trim();
            const targetComplaintId = inputVal || (complaintId ? complaintId.trim() : null);

            if (!targetComplaintId) {
                window.showToast("No complaint selected for verification. Please select an active task from Assigned Pickups.", "error");
                return;
            }

            const formData = new FormData();
            // Include proof photo if selected (validated and persisted on backend)
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
                if (window.DriverSocketController && typeof window.DriverSocketController.disconnect === 'function') {
                    window.DriverSocketController.disconnect(true);
                }
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
