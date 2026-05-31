/**
 * Citizen Logic (Reporting, Dashboard, History, Rewards)
 */
document.addEventListener('DOMContentLoaded', () => {
    
    // ---- Auto-Redirect if not authenticated ----
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('user_role');
    if (!token || role !== 'CITIZEN') {
        localStorage.clear();
        window.location.href = '../Login Screen/index.html';
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
                } else if (iconName === 'map' || iconName === 'explore') {
                    window.location.href = '../Waste Heatmap/index.html';
                } else if (iconName === 'assignment') {
                    window.location.href = '../Complaint History/index.html';
                } else if (iconName === 'history') {
                    window.location.href = '../Report Waste/index.html';
                } else if (iconName === 'leaderboard') {
                    window.location.href = '../Cleanliness Heatmap/index.html';
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
                localStorage.clear();
                window.location.href = '../Login Screen/index.html';
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

    const notifBtn = document.getElementById('btn-notifications');
    if (notifBtn) {
        notifBtn.addEventListener('click', () => {
            window.showToast("You have no new notifications.", "info");
        });
    }

    // ---- Dynamic Complaints List Renderer ----
    const loadComplaints = async () => {
        const complaintsList = document.getElementById('complaints-list');
        if (complaintsList) {
            try {
                const complaints = await API.fetchComplaints();
                
                // If on dashboard, show only top 2
                const isDashboard = window.location.pathname.includes('Citizen Dashboard');
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
                        statusColor = "bg-slate-100 text-slate-500";
                        statusIcon = "check_circle";
                    } else if (c.status === "PENDING") {
                        statusColor = "bg-error/10 text-error";
                        statusIcon = "pending";
                    }
                    
                    return `
                        <div class="bg-surface-container-lowest border border-outline-variant/20 rounded-xl p-md flex items-center justify-between group hover:shadow-md transition-all">
                            <div class="flex items-center gap-md">
                                <div class="w-12 h-12 bg-surface-container rounded-lg flex items-center justify-center">
                                    <span class="material-symbols-outlined text-secondary" data-icon="delete_outline">delete_outline</span>
                                </div>
                                <div>
                                    <h4 class="font-title-md text-on-surface text-left">${c.waste_type || "General"} Waste - ${c.area || "Area"}</h4>
                                    <p class="font-body-md text-body-md text-on-surface-variant text-left">${new Date(c.created_at).toLocaleDateString()}</p>
                                </div>
                            </div>
                            <div class="flex items-center gap-md">
                                <span class="${statusColor} px-3 py-1 rounded-full font-label-sm text-label-sm">${c.status}</span>
                                <span class="material-symbols-outlined text-outline-variant group-hover:text-primary transition-colors" data-icon="chevron_right">chevron_right</span>
                            </div>
                        </div>
                    `;
                }).join('');

            } catch (err) {
                console.error("Failed to load complaints", err);
                complaintsList.innerHTML = `<p class="text-error p-4">Error loading reports: ${err.message}</p>`;
            }
        }
    };
    
    if (window.location.pathname.includes('Citizen Dashboard') || window.location.pathname.includes('Complaint History')) {
        loadComplaints();
    }

    // ---- Report Waste Form Submit ----
    const reportForm = document.getElementById('report-waste-form');
    if (reportForm) {
        let currentLocation = null;

        // Geolocation callback
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    currentLocation = { lat: pos.coords.latitude, lng: pos.coords.longitude };
                },
                (err) => {
                    console.warn("Geolocation warning:", err);
                    currentLocation = { lat: 12.9716, lng: 77.5946 }; // Default fallback coordinates
                }
            );
        } else {
            currentLocation = { lat: 12.9716, lng: 77.5946 }; // Default fallback coordinates
        }

        reportForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = reportForm.querySelector('button[type="submit"]');
            const imageInput = document.getElementById('waste-image');
            
            if (!imageInput.files[0]) {
                window.showToast("Please capture or select an image", "error");
                return;
            }

            if (!currentLocation) {
                currentLocation = { lat: 12.9716, lng: 77.5946 }; // Ensure fallback
            }

            const zone = document.getElementById('zone')?.value || "Zone A";
            const area = document.getElementById('area')?.value || "Downtown";

            const formData = new FormData();
            formData.append('file', imageInput.files[0]);
            formData.append('lat', currentLocation.lat);
            formData.append('lng', currentLocation.lng);
            formData.append('zone', zone);
            formData.append('area', area);

            const originalText = submitBtn.innerText;
            submitBtn.innerText = "Submitting Report...";
            submitBtn.disabled = true;

            try {
                const response = await API.reportWaste(formData);
                window.showToast("Waste reported successfully!", "success");
                
                // Update local points
                localStorage.setItem('eco_points', response.points);
                
                setTimeout(() => {
                    window.location.href = '../Citizen Dashboard/index.html';
                }, 1500);
            } catch (err) {
                window.showToast(err.message, "error");
                submitBtn.innerText = originalText;
                submitBtn.disabled = false;
            }
        });
    }

    // ---- Rewards List Loader & Mock Redemption ----
    const loadRewards = () => {
        const rewardsList = document.getElementById('rewards-list');
        if (rewardsList) {
            const availableRewards = [
                { id: 1, title: "Free Oat Latte", provider: "The Green Bean", cost: 450, category: "Local Shop" },
                { id: 2, title: "Botanic Garden Pass", provider: "City Parks Dept", cost: 800, category: "Public Service" },
                { id: 3, title: "15% Off Organic Box", provider: "Farm-to-Door", cost: 300, category: "Discount" },
                { id: 4, title: "Weekly Transit Pass", provider: "Metro Transit", cost: 1500, category: "Transport" }
            ];

            rewardsList.innerHTML = availableRewards.map(r => `
                <div class="bg-white border border-slate-100 rounded-3xl p-4 flex gap-4 hover:shadow-md transition-shadow">
                    <div class="w-24 h-24 rounded-2xl overflow-hidden flex-shrink-0 bg-emerald-50 flex items-center justify-center">
                        <span class="material-symbols-outlined text-emerald-600 text-4xl">redeem</span>
                    </div>
                    <div class="flex flex-col justify-between py-1 flex-grow">
                        <div>
                            <p class="font-label-sm text-primary uppercase font-bold text-left">${r.category}</p>
                            <h3 class="font-title-md font-bold leading-tight text-left">${r.title}</h3>
                            <p class="font-body-md text-on-surface-variant mt-1 text-left">${r.provider}</p>
                        </div>
                        <div class="flex items-center justify-between mt-2">
                            <div class="flex items-center gap-1 text-emerald-700 font-bold">
                                <span class="material-symbols-outlined text-sm" style="font-variation-settings: 'FILL' 1;">stars</span>
                                <span class="text-sm">${r.cost} pts</span>
                            </div>
                            <button onclick="redeemReward(${r.id}, ${r.cost}, '${r.title}')" class="px-4 py-1.5 bg-primary text-white text-xs font-bold rounded-full hover:opacity-90 active:scale-95 transition-transform">
                                Redeem
                            </button>
                        </div>
                    </div>
                </div>
            `).join('');
        }
    };
    loadRewards();

    // Redeem handler exposed to window so onclick works
    window.redeemReward = (rewardId, cost, title) => {
        const currentPoints = Number(localStorage.getItem('eco_points') || "0");
        if (currentPoints < cost) {
            window.showToast(`Insufficient points! You need ${cost} points.`, "error");
            return;
        }

        const newPoints = currentPoints - cost;
        localStorage.setItem('eco_points', newPoints);
        updatePointsUI();
        window.showToast(`Successfully redeemed: ${title}!`, "success");
    };
});
