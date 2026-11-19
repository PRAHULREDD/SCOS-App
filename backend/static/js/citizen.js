/**
 * Citizen Logic (Reporting, Dashboard, History, Rewards, Leaderboard)
 */

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function targetedLogout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('user_id');
    localStorage.removeItem('eco_points');
    window.location.href = '../Login Screen/index.html';
}

document.addEventListener('DOMContentLoaded', () => {
    
    // ---- Auto-Redirect if not authenticated ----
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('user_role');
    if (!token || role !== 'CITIZEN') {
        targetedLogout();
        return;
    }

    // ---- Universal Citizen Navigation ----
    const navAnchors = document.querySelectorAll('nav a, nav button');
    navAnchors.forEach(anchor => {
        const iconSpan = anchor.querySelector('.material-symbols-outlined');
        let iconName = '';
        if (iconSpan) {
            iconName = iconSpan.getAttribute('data-icon') || iconSpan.textContent.trim().toLowerCase();
        }

        if (iconName) {
            anchor.addEventListener('click', (e) => {
                e.preventDefault();
                if (iconName === 'home') {
                    window.location.href = '../Citizen Dashboard/index.html';
                } else if (iconName === 'add_circle' || iconName === 'report' || iconName === 'history') {
                    window.location.href = '../Report Waste/index.html';
                } else if (iconName === 'assignment') {
                    window.location.href = '../Complaint History/index.html';
                } else if (iconName === 'stars' || iconName === 'redeem' || iconName === 'rewards') {
                    window.location.href = '../Rewards/index.html';
                }
            });
        }
    });

    // ---- Back to Dashboard Navigation ----
    const backBtn = document.querySelector('header button, header a');
    if (backBtn) {
        const backIcon = backBtn.querySelector('.material-symbols-outlined');
        if (backIcon && (backIcon.textContent.trim() === 'arrow_back' || backIcon.textContent.trim() === 'chevron_left')) {
            backBtn.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = '../Citizen Dashboard/index.html';
            });
        }
    }

    // ---- Profile Logout Trigger ----
    const profilePics = document.querySelectorAll('header img, header .rounded-full');
    profilePics.forEach(pic => {
        pic.style.cursor = 'pointer';
        pic.addEventListener('click', () => {
            if (confirm("Do you want to log out?")) {
                targetedLogout();
            }
        });
    });

    // ---- EcoPoints Display Update ----
    const updatePointsUI = () => {
        const pointsDisplay = document.getElementById('eco-points-display');
        if (pointsDisplay) {
            pointsDisplay.innerText = Number(localStorage.getItem('eco_points') || "0").toLocaleString();
        }
    };
    updatePointsUI();

    // ---- Dashboard "Redeem Rewards" FAB & Buttons ----
    const redeemBtn = document.querySelector('button[class*="bg-on-primary-container"]');
    if (redeemBtn) {
        redeemBtn.addEventListener('click', () => {
            window.location.href = '../Rewards/index.html';
        });
    }

    const fabReport = document.querySelector('button.fixed.bottom-24.right-6');
    if (fabReport) {
        fabReport.addEventListener('click', () => {
            window.location.href = '../Report Waste/index.html';
        });
    }

    // ---- Header Notification Triggers ----
    document.querySelectorAll('header button, #btn-notifications, header [data-icon="notifications"]').forEach(btn => {
        const notifIcon = btn.querySelector ? btn.querySelector('[data-icon="notifications"], .material-symbols-outlined') : null;
        const isNotif = btn.id === 'btn-notifications' ||
            btn.getAttribute('data-icon') === 'notifications' ||
            (notifIcon && (notifIcon.getAttribute('data-icon') === 'notifications' || notifIcon.textContent.trim() === 'notifications'));
        if (isNotif) {
            btn.addEventListener('click', async () => {
                try {
                    const response = await API.fetchComplaints().catch(() => ({ reports: [] }));
                    const reports = response.reports || [];
                    const pending = reports.filter(r => r.status === 'PENDING').length;
                    const resolved = reports.filter(r => r.status === 'RESOLVED').length;
                    if (pending > 0) {
                        window.showToast(`You have ${pending} waste report(s) under review.`, "info");
                    } else if (resolved > 0) {
                        window.showToast(`All ${resolved} of your reports have been resolved!`, "success");
                    } else {
                        window.showToast("You have no active notifications.", "info");
                    }
                } catch (err) {
                    window.showToast("Notification services are active.", "info");
                }
            });
        }
    });

    // Rewards action buttons
    const viewAllRewardsBtn = document.querySelector('button.text-primary.font-label-lg');
    if (viewAllRewardsBtn) {
        viewAllRewardsBtn.addEventListener('click', () => {
            const list = document.getElementById('rewards-list');
            if (list) list.scrollIntoView({ behavior: 'smooth' });
        });
    }

    const refreshLeaderboardBtn = document.getElementById('btn-refresh-leaderboard');
    if (refreshLeaderboardBtn) {
        refreshLeaderboardBtn.addEventListener('click', () => {
            loadLeaderboard();
            window.showToast("Leaderboard refreshed from live database.", "info");
        });
    }

    // ---- Dynamic Complaints List Renderer ----
    const loadComplaints = async () => {
        const complaintsList = document.getElementById('complaints-list');
        if (complaintsList) {
            try {
                const response = await API.fetchComplaints();
                const complaints = response.reports || [];
                
                // If on dashboard, show only top 2
                const isDashboard = decodeURIComponent(window.location.pathname).includes('Citizen Dashboard');
                const displayList = isDashboard ? complaints.slice(0, 2) : complaints;

                if (displayList.length === 0) {
                    complaintsList.innerHTML = `
                        <div class="py-8 flex flex-col items-center justify-center text-center bg-white border border-outline-variant/20 rounded-xl p-6">
                            <span class="material-symbols-outlined text-outline text-4xl mb-2">delete_outline</span>
                            <p class="text-on-surface-variant font-medium">No waste reports submitted yet.</p>
                        </div>
                    `;
                    return;
                }

                complaintsList.innerHTML = displayList.map(c => {
                    let statusColor = "bg-primary/10 text-primary";
                    let statusIcon = "sync";
                    if (c.status === "RESOLVED") {
                        statusColor = "bg-emerald-100 text-emerald-800";
                        statusIcon = "check_circle";
                    } else if (c.status === "PENDING") {
                        statusColor = "bg-amber-100 text-amber-800";
                        statusIcon = "pending";
                    } else if (c.status === "IN_PROGRESS") {
                        statusColor = "bg-blue-100 text-blue-800";
                        statusIcon = "local_shipping";
                    }
                    
                    const descHtml = c.description ? `
                        <p class="font-body-sm text-xs text-on-surface-variant text-left mt-1 line-clamp-2">${escapeHtml(c.description)}</p>
                    ` : '';

                    const hasProof = c.status === "RESOLVED" && Boolean(c.proof_photo_url);
                    const safeProofUrl = hasProof ? escapeHtml(c.proof_photo_url) : '';
                    const safeWasteType = escapeHtml(c.waste_type || "General");
                    const safeArea = escapeHtml(c.area || "Area");

                    const proofActionHtml = hasProof ? `
                        <div class="mt-2">
                            <button type="button"
                                    data-action="view-citizen-proof"
                                    data-proof-url="${safeProofUrl}"
                                    data-complaint-id="${c.id}"
                                    data-waste-type="${safeWasteType}"
                                    data-area="${safeArea}"
                                    class="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-300 rounded-full text-xs font-semibold transition-all active:scale-95 shadow-sm">
                                <span class="material-symbols-outlined text-[15px]">photo_camera</span>
                                <span>View Collection Proof</span>
                            </button>
                        </div>
                    ` : '';

                    return `
                        <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-md flex items-center justify-between group hover:shadow-md transition-all">
                            <div class="flex items-center gap-md">
                                <div class="w-12 h-12 bg-surface-container rounded-lg flex items-center justify-center">
                                    <span class="material-symbols-outlined text-secondary" data-icon="delete_outline">delete_outline</span>
                                </div>
                                <div class="max-w-[200px] sm:max-w-md">
                                    <h4 class="font-title-md text-on-surface text-left font-semibold">${safeWasteType} Waste - ${safeArea}</h4>
                                    ${descHtml}
                                    <p class="font-body-md text-xs text-on-surface-variant text-left mt-0.5">${c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Recent'}</p>
                                    ${proofActionHtml}
                                </div>
                            </div>
                            <div class="flex items-center gap-md">
                                <span class="${statusColor} px-3 py-1 rounded-full font-label-sm text-xs font-semibold">${escapeHtml(c.status)}</span>
                                <span class="material-symbols-outlined text-outline-variant group-hover:text-primary transition-colors" data-icon="chevron_right">chevron_right</span>
                            </div>
                        </div>
                    `;
                }).join('');

            } catch (err) {
                console.error("Failed to load complaints", err);
                complaintsList.innerHTML = `<p class="text-error p-4">Error loading reports: ${escapeHtml(err.message)}</p>`;
            }
        }
    };
    
    if (decodeURIComponent(window.location.pathname).includes('Citizen Dashboard') || decodeURIComponent(window.location.pathname).includes('Complaint History')) {
        loadComplaints();
    }

    // ---- Dynamic Dashboard Stats Renderer (Factual Metrics, No Fake City-Average) ----
    const loadCitizenDashboard = async () => {
        const scoreDisplay = document.getElementById('cleanliness-score-display');
        const messageDisplay = document.getElementById('cleanliness-message');
        
        if (scoreDisplay && messageDisplay) {
            try {
                const data = await API.fetchCitizenDashboard();
                
                // Update Cleanliness Score
                scoreDisplay.innerText = Math.round(data.cleanliness_score || 0);

                // Factual resolution metric replacing fake city-average comparison
                if (data.total_reports > 0) {
                    messageDisplay.innerText = `${data.resolved_reports} of ${data.total_reports} reported issues resolved. Keep up the clean work!`;
                } else {
                    messageDisplay.innerText = "No issues reported yet. Report waste in your locality to earn EcoPoints!";
                }
                
                // Update EcoPoints dynamically from backend
                localStorage.setItem('eco_points', data.eco_points);
                updatePointsUI();
            } catch (err) {
                console.error("Failed to load citizen dashboard", err);
                scoreDisplay.innerText = "--";
                messageDisplay.innerText = "Unable to load neighborhood statistics.";
            }
        }
    };
    
    if (decodeURIComponent(window.location.pathname).includes('Citizen Dashboard')) {
        loadCitizenDashboard();
    }

    // ---- Community Leaderboard Loader ----
    const loadLeaderboard = async () => {
        const listEl = document.getElementById('leaderboard-list');
        if (!listEl) return;

        try {
            const data = await API.fetchLeaderboard();
            const items = data.leaderboard || [];

            if (items.length === 0) {
                listEl.innerHTML = `
                    <div class="p-6 text-center text-sm text-on-surface-variant bg-slate-50 rounded-2xl">
                        <span class="material-symbols-outlined text-3xl text-outline mb-1">leaderboard</span>
                        <p class="font-medium">No community rankings yet.</p>
                        <p class="text-xs text-on-surface-variant mt-1">Be the first citizen to report waste and earn EcoPoints!</p>
                    </div>
                `;
                return;
            }

            listEl.innerHTML = items.map(u => {
                const isMe = u.is_current_user;
                const cardStyle = isMe
                    ? 'bg-emerald-50 border-emerald-300 ring-1 ring-emerald-500/20'
                    : 'bg-white border-slate-100 hover:bg-slate-50';

                let rankBadge = `<span class="font-bold text-slate-500">${u.rank}</span>`;
                let trophyIcon = '';
                if (u.rank === 1) {
                    rankBadge = `<span class="font-bold text-amber-700">1</span>`;
                    trophyIcon = `<span class="material-symbols-outlined text-yellow-500 text-lg" style="font-variation-settings: 'FILL' 1;">emoji_events</span>`;
                } else if (u.rank === 2) {
                    rankBadge = `<span class="font-bold text-slate-600">2</span>`;
                    trophyIcon = `<span class="material-symbols-outlined text-slate-400 text-lg" style="font-variation-settings: 'FILL' 1;">military_tech</span>`;
                } else if (u.rank === 3) {
                    rankBadge = `<span class="font-bold text-amber-900">3</span>`;
                    trophyIcon = `<span class="material-symbols-outlined text-amber-700 text-lg" style="font-variation-settings: 'FILL' 1;">military_tech</span>`;
                }

                return `
                    <div class="flex items-center justify-between p-3 rounded-2xl border transition-all ${cardStyle}">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-sm">
                                ${rankBadge}
                            </div>
                            <div>
                                <p class="font-title-md font-bold text-on-surface text-left">
                                    ${escapeHtml(u.name)} ${isMe ? '<span class="text-xs font-semibold text-primary ml-1">(You)</span>' : ''}
                                </p>
                                <p class="font-label-sm text-xs text-on-surface-variant text-left">${Number(u.eco_points).toLocaleString()} pts</p>
                            </div>
                        </div>
                        ${trophyIcon}
                    </div>
                `;
            }).join('');

            // If user is outside the top 20, render user ranking footer
            if (data.user_rank && data.user_rank > items.length) {
                listEl.innerHTML += `
                    <div class="mt-4 pt-4 border-t border-slate-100">
                        <div class="flex items-center justify-between p-3 rounded-2xl bg-emerald-50 border border-emerald-200">
                            <div class="flex items-center gap-3">
                                <div class="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center font-bold text-xs text-emerald-800">
                                    ${data.user_rank}
                                </div>
                                <div>
                                    <p class="font-title-md font-bold text-on-surface text-left">${escapeHtml(data.user_name)} <span class="text-xs text-primary font-semibold">(You)</span></p>
                                    <p class="font-label-sm text-xs text-on-surface-variant text-left">${Number(data.user_points).toLocaleString()} pts</p>
                                </div>
                            </div>
                            <span class="text-xs font-semibold text-emerald-700">Rank #${data.user_rank}</span>
                        </div>
                    </div>
                `;
            }

        } catch (err) {
            console.error("Failed to load community leaderboard:", err);
            listEl.innerHTML = `<p class="text-error text-sm p-4 text-center">Unable to load community leaderboard.</p>`;
        }
    };

    const loadRewardsMetrics = async () => {
        try {
            const data = await API.fetchCitizenDashboard();
            const filedEl = document.getElementById('rewards-reports-filed');
            const resolvedEl = document.getElementById('rewards-reports-resolved');
            if (filedEl) filedEl.textContent = data.total_reports ?? 0;
            if (resolvedEl) resolvedEl.textContent = data.resolved_reports ?? 0;
            const pointsEl = document.getElementById('eco-points-display');
            if (pointsEl) pointsEl.textContent = Number(data.eco_points || 0).toLocaleString();
        } catch (err) {
            console.warn("Failed to load rewards metrics:", err);
        }
    };

    if (decodeURIComponent(window.location.pathname).includes('Rewards')) {
        loadLeaderboard();
        loadRewardsMetrics();
    }

    // ---- Report Waste Form Submit & Geolocation Handling ----
    const reportForm = document.getElementById('report-waste-form');
    if (reportForm) {
        let currentLocation = null;
        const coordsEl = document.getElementById('current-location-coords');
        const areaEl = document.getElementById('current-location-area');
        const refineBtn = document.getElementById('btn-refine-gps');

        const updateCoordsUI = (lat, lng) => {
            if (coordsEl) {
                coordsEl.textContent = `${lat.toFixed(4)}° N, ${lng.toFixed(4)}° E`;
                coordsEl.classList.remove('text-error');
                coordsEl.classList.add('text-outline');
            }
            if (areaEl && areaEl.textContent === 'Detecting location...') {
                areaEl.textContent = "Coordinates recorded via device GPS";
            }
        };

        const setGPSUnavailable = (message) => {
            currentLocation = null;
            if (coordsEl) {
                coordsEl.textContent = message;
                coordsEl.classList.remove('text-outline');
                coordsEl.classList.add('text-error');
            }
            if (areaEl && areaEl.textContent === 'Detecting location...') {
                areaEl.textContent = "Manual locality required";
            }
        };

        const acquireLocation = () => {
            if (!navigator.geolocation) {
                setGPSUnavailable("Geolocation is not supported by your browser.");
                return;
            }

            if (coordsEl) coordsEl.textContent = "Acquiring GPS signal...";
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    const lat = pos.coords.latitude;
                    const lng = pos.coords.longitude;
                    if (typeof lat === 'number' && typeof lng === 'number' && !isNaN(lat) && !isNaN(lng) && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
                        currentLocation = { lat, lng };
                        updateCoordsUI(lat, lng);
                        if (refineBtn) refineBtn.textContent = 'Refine';
                    } else {
                        setGPSUnavailable("Invalid GPS coordinates received.");
                    }
                },
                (err) => {
                    console.warn("Geolocation warning:", err);
                    let msg = "GPS unavailable.";
                    switch (err.code) {
                        case 1: // PERMISSION_DENIED
                            msg = "Location permission denied. Enter area manually.";
                            break;
                        case 2: // POSITION_UNAVAILABLE
                            msg = "Location unavailable. Enter area manually.";
                            break;
                        case 3: // TIMEOUT
                            msg = "Location request timed out. Enter area manually.";
                            break;
                        default:
                            msg = "Unable to acquire GPS. Enter area manually.";
                    }
                    setGPSUnavailable(msg);
                    if (refineBtn) refineBtn.textContent = 'Retry GPS';
                },
                { enableHighAccuracy: true, timeout: 8000, maximumAge: 30000 }
            );
        };

        // Initialize geolocation on load
        acquireLocation();

        // Refine GPS button listener
        if (refineBtn) {
            refineBtn.addEventListener('click', () => {
                refineBtn.textContent = 'Updating...';
                acquireLocation();
            });
        }

        reportForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = reportForm.querySelector('button[type="submit"]');

            const zone = document.getElementById('zone')?.value || "Zone A";
            const area = (document.getElementById('area')?.value || "").trim();
            const description = (document.getElementById('description')?.value || "").trim();

            if (!area) {
                window.showToast("Please enter an area or locality.", "error");
                document.getElementById('area')?.focus();
                return;
            }

            // Get selected waste type from radio buttons
            const wasteTypeRadio = reportForm.querySelector('input[name="waste_type"]:checked');
            const wasteType = wasteTypeRadio 
                ? wasteTypeRadio.closest('label')?.querySelector('span.text-label-sm')?.textContent?.trim() || "General"
                : "General";

            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Submitting Report...";
            submitBtn.disabled = true;

            try {
                // Submit real GPS or null — NEVER submit fabricated/Bengaluru coordinates
                const payload = {
                    zone: zone,
                    area: area,
                    description: description || null,
                    lat: currentLocation ? currentLocation.lat : null,
                    lng: currentLocation ? currentLocation.lng : null,
                    waste_type: wasteType,
                    severity_level: "MEDIUM"
                };

                const response = await API.request('/api/citizen/report_issue', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                    headers: { 'Content-Type': 'application/json' }
                });

                // Update local points from actual backend response
                if (response.points !== undefined) {
                    localStorage.setItem('eco_points', response.points);
                    updatePointsUI();
                }
                
                window.showToast(`Waste reported successfully! EcoPoints balance: ${response.points}`, "success");

                setTimeout(() => {
                    window.location.href = '../Citizen Dashboard/index.html';
                }, 1500);
            } catch (err) {
                window.showToast(err.message || "Failed to submit report.", "error");
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // ---- Dynamic Rewards List Loader & Redemption ----
    const loadRewards = async () => {
        const rewardsList = document.getElementById('rewards-list');
        if (rewardsList) {
            try {
                const data = await API.fetchRewards();
                const availableRewards = data.available_rewards || data.rewards || [];

                if (availableRewards.length === 0) {
                    rewardsList.innerHTML = '<p class="text-on-surface-variant p-4">No rewards currently available.</p>';
                    return;
                }

                rewardsList.innerHTML = availableRewards.map(r => `
                    <div class="bg-white border border-slate-100 rounded-3xl p-4 flex gap-4 hover:shadow-md transition-shadow">
                        <div class="w-24 h-24 rounded-2xl overflow-hidden flex-shrink-0 bg-emerald-50 flex items-center justify-center">
                            <span class="material-symbols-outlined text-emerald-600 text-4xl">redeem</span>
                        </div>
                        <div class="flex flex-col justify-between py-1 flex-grow">
                            <div>
                                <p class="font-label-sm text-primary uppercase font-bold text-left text-xs">${escapeHtml(r.category || 'Reward')}</p>
                                <h3 class="font-title-md font-bold leading-tight text-left text-base text-on-surface">${escapeHtml(r.title)}</h3>
                                <p class="font-body-md text-on-surface-variant mt-1 text-left text-xs">${escapeHtml(r.provider)}</p>
                            </div>
                            <div class="flex items-center justify-between mt-2">
                                <div class="flex items-center gap-1 text-emerald-700 font-bold">
                                    <span class="material-symbols-outlined text-sm" style="font-variation-settings: 'FILL' 1;">stars</span>
                                    <span class="text-sm">${Number(r.points_cost).toLocaleString()} pts</span>
                                </div>
                                <button onclick="redeemReward(${r.id}, ${r.points_cost}, '${escapeHtml(r.title).replace(/'/g, "\\'")}')" class="px-4 py-1.5 bg-primary text-white text-xs font-bold rounded-full hover:opacity-90 active:scale-95 transition-transform cursor-pointer">
                                    Redeem
                                </button>
                            </div>
                        </div>
                    </div>
                `).join('');
            } catch (err) {
                console.error("Failed to load rewards:", err);
                rewardsList.innerHTML = `<p class="text-error p-4">Failed to load rewards from server: ${escapeHtml(err.message)}</p>`;
            }
        }
    };
    loadRewards();

    // Redeem handler exposed to window so onclick works
    window.redeemReward = async (rewardId, cost, title) => {
        const currentPoints = Number(localStorage.getItem('eco_points') || "0");
        if (currentPoints < cost) {
            window.showToast(`Insufficient points! You need ${cost} points.`, "error");
            return;
        }

        try {
            const response = await API.redeemReward(rewardId);
            localStorage.setItem('eco_points', response.remaining_points);
            updatePointsUI();
            window.showToast(`Successfully redeemed: ${title}! Remaining points: ${response.remaining_points}`, "success");
            loadRewards();
            loadLeaderboard();
        } catch (err) {
            window.showToast(err.message || "Failed to redeem reward.", "error");
        }
    };
});

// ---- Collection Proof Photo Viewer Functions ----
let _citizenProofObjectUrl = null;
let _citizenAbortController = null;
let _citizenRequestGen = 0;

function ensureCitizenProofModal() {
    let modal = document.getElementById('citizen-proof-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'citizen-proof-modal';
        modal.className = 'fixed inset-0 bg-black/60 z-[100] flex items-center justify-center p-4 hidden backdrop-blur-sm';
        modal.innerHTML = `
          <div class="bg-white dark:bg-slate-900 rounded-3xl w-full max-w-lg p-6 space-y-4 shadow-2xl border border-slate-100 dark:border-slate-800">
            <div class="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
              <div class="flex items-center gap-2">
                <span class="material-symbols-outlined text-primary text-2xl">photo_library</span>
                <h3 class="font-title-md font-bold text-on-surface">Collection Proof Photo</h3>
              </div>
              <button id="citizen-proof-modal-close" class="p-1.5 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
                <span class="material-symbols-outlined text-2xl">close</span>
              </button>
            </div>
            <div id="citizen-proof-info" class="text-xs text-on-surface-variant font-medium"></div>
            <div class="relative w-full aspect-video bg-slate-100 dark:bg-slate-800 rounded-2xl overflow-hidden flex items-center justify-center border border-outline-variant/30">
              <div id="citizen-proof-loading" class="flex flex-col items-center justify-center text-slate-400 gap-2">
                <span class="material-symbols-outlined text-3xl animate-spin">sync</span>
                <span class="text-xs font-medium">Retrieving collection proof photo...</span>
              </div>
              <div id="citizen-proof-error" class="hidden flex flex-col items-center justify-center text-error p-4 text-center gap-2">
                <span class="material-symbols-outlined text-3xl">broken_image</span>
                <span id="citizen-proof-error-msg" class="text-xs font-medium">Unable to load proof photo.</span>
              </div>
              <img id="citizen-proof-img" class="w-full h-full object-contain hidden" alt="Collection Proof Photo">
            </div>
            <div class="flex justify-end pt-2">
              <button id="citizen-proof-modal-dismiss" class="px-5 py-2.5 bg-primary text-on-primary text-sm font-medium rounded-full active:scale-95 transition-transform">
                Done
              </button>
            </div>
          </div>
        `;
        document.body.appendChild(modal);
    }

    const closeBtn = document.getElementById('citizen-proof-modal-close');
    const dismissBtn = document.getElementById('citizen-proof-modal-dismiss');
    if (closeBtn && !closeBtn._bound) {
        closeBtn._bound = true;
        closeBtn.addEventListener('click', closeCitizenProofModal);
    }
    if (dismissBtn && !dismissBtn._bound) {
        dismissBtn._bound = true;
        dismissBtn.addEventListener('click', closeCitizenProofModal);
    }
    if (!modal._boundBackdrop) {
        modal._boundBackdrop = true;
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeCitizenProofModal();
        });
    }
    return modal;
}

function closeCitizenProofModal() {
    _citizenRequestGen++;
    if (_citizenAbortController) {
        _citizenAbortController.abort();
        _citizenAbortController = null;
    }
    const modal = document.getElementById('citizen-proof-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    if (_citizenProofObjectUrl) {
        URL.revokeObjectURL(_citizenProofObjectUrl);
        _citizenProofObjectUrl = null;
    }
    const imgEl = document.getElementById('citizen-proof-img');
    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.removeAttribute('src');
        imgEl.classList.add('hidden');
    }
}

async function viewCitizenProofPhoto(proofUrl, complaintId, wasteType, area) {
    if (!proofUrl) {
        if (typeof window.showToast === 'function') {
            window.showToast('No proof photo is available for this report.', 'info');
        }
        return;
    }

    const currentGen = ++_citizenRequestGen;
    if (_citizenAbortController) {
        _citizenAbortController.abort();
        _citizenAbortController = null;
    }
    if (_citizenProofObjectUrl) {
        URL.revokeObjectURL(_citizenProofObjectUrl);
        _citizenProofObjectUrl = null;
    }

    const modal = ensureCitizenProofModal();
    const infoEl = document.getElementById('citizen-proof-info');
    const loadingEl = document.getElementById('citizen-proof-loading');
    const errorEl = document.getElementById('citizen-proof-error');
    const errorMsgEl = document.getElementById('citizen-proof-error-msg');
    const imgEl = document.getElementById('citizen-proof-img');

    if (imgEl) {
        imgEl.onload = null;
        imgEl.onerror = null;
        imgEl.removeAttribute('src');
        imgEl.classList.add('hidden');
    }

    const taskId = proofUrl.split('/').filter(Boolean).pop();
    if (infoEl) {
        infoEl.textContent = `Report #${complaintId} (Task #${taskId}) · ${wasteType || 'General'} Waste in ${area || 'Municipal Area'}`;
    }

    loadingEl?.classList.remove('hidden');
    errorEl?.classList.add('hidden');
    modal.classList.remove('hidden');

    _citizenAbortController = new AbortController();

    try {
        const blob = await API.fetchProofPhotoBlob(proofUrl, { signal: _citizenAbortController.signal });
        if (currentGen !== _citizenRequestGen) {
            return;
        }
        _citizenProofObjectUrl = URL.createObjectURL(blob);
        if (imgEl) {
            imgEl.onload = () => {
                if (currentGen !== _citizenRequestGen) return;
                loadingEl?.classList.add('hidden');
                imgEl.classList.remove('hidden');
            };
            imgEl.onerror = () => {
                if (currentGen !== _citizenRequestGen) return;
                loadingEl?.classList.add('hidden');
                errorEl?.classList.remove('hidden');
                if (errorMsgEl) errorMsgEl.textContent = 'Failed to render retrieved image.';
            };
            imgEl.src = _citizenProofObjectUrl;
        }
    } catch (err) {
        if (currentGen !== _citizenRequestGen || err.name === 'AbortError') {
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

// Delegated click handler for citizen proof buttons
if (!window._citizenProofDelegationBound) {
    window._citizenProofDelegationBound = true;
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('button[data-action="view-citizen-proof"]');
        if (btn) {
            e.stopPropagation();
            const { proofUrl, complaintId, wasteType, area } = btn.dataset;
            viewCitizenProofPhoto(proofUrl, complaintId, wasteType, area);
        }
    });
}

window.viewCitizenProofPhoto = viewCitizenProofPhoto;
window.closeCitizenProofModal = closeCitizenProofModal;
window.addEventListener('beforeunload', () => {
    _citizenRequestGen++;
    if (_citizenAbortController) {
        _citizenAbortController.abort();
        _citizenAbortController = null;
    }
    if (_citizenProofObjectUrl) {
        URL.revokeObjectURL(_citizenProofObjectUrl);
        _citizenProofObjectUrl = null;
    }
});
