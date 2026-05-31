/**
 * Admin Logic (Simulated Interactions for Heatmaps & Dashboards)
 */
document.addEventListener('DOMContentLoaded', () => {

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
});
