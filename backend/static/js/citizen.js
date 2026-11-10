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

    // ---- Header Notification Triggers (Clearly Labelled as Demo Notification) ----
    document.querySelectorAll('header button, #btn-notifications').forEach(btn => {
        const notifIcon = btn.querySelector('[data-icon="notifications"], .material-symbols-outlined');
        if (btn.id === 'btn-notifications' || (notifIcon && (notifIcon.getAttribute('data-icon') === 'notifications' || notifIcon.textContent.trim() === 'notifications'))) {
            btn.addEventListener('click', async () => {
                try {
                    const response = await API.fetchComplaints().catch(() => ({ reports: [] }));
                    const reports = response.reports || [];
                    const pending = reports.filter(r => r.status === 'PENDING').length;
                    const resolved = reports.filter(r => r.status === 'RESOLVED').length;
                    if (pending > 0) {
                        window.showToast(`[Demo Notification] You have ${pending} waste report(s) under review.`, "info");
                    } else if (resolved > 0) {
                        window.showToast(`[Demo Notification] All ${resolved} of your reports have been resolved!`, "success");
                    } else {
                        window.showToast("[Demo Notification] You have no active notifications.", "info");
                    }
                } catch (err) {
                    window.showToast("[Demo Notification] Notification services are active.", "info");
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

                    return `
                        <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-md flex items-center justify-between group hover:shadow-md transition-all">
                            <div class="flex items-center gap-md">
                                <div class="w-12 h-12 bg-surface-container rounded-lg flex items-center justify-center">
                                    <span class="material-symbols-outlined text-secondary" data-icon="delete_outline">delete_outline</span>
                                </div>
                                <div class="max-w-[200px] sm:max-w-md">
                                    <h4 class="font-title-md text-on-surface text-left font-semibold">${escapeHtml(c.waste_type || "General")} Waste - ${escapeHtml(c.area || "Area")}</h4>
                                    ${descHtml}
                                    <p class="font-body-md text-xs text-on-surface-variant text-left mt-0.5">${c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Recent'}</p>
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

    if (decodeURIComponent(window.location.pathname).includes('Rewards')) {
        loadLeaderboard();
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
