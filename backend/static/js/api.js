/**
 * Central API Handler for SCOS Frontend
 */
// Centralized backend URL resolved via window.SCOS_CONFIG.
// Precedence: dev override (localStorage) -> Native Capacitor (Render) -> Web (window.location.origin).
// Running from file:// without an override produces a clear error rather than silently hitting Render.
const getActiveBaseUrl = () => {
    if (window.SCOS_CONFIG && typeof window.SCOS_CONFIG.getBackendUrl === 'function') {
        return window.SCOS_CONFIG.getBackendUrl();
    }
    if (window.Capacitor && window.Capacitor.isNativePlatform()) {
        return 'https://scos-app.onrender.com';
    }
    return (window.location.protocol === 'file:') ? null : window.location.origin;
};


class API {
    static getToken() {
        return localStorage.getItem('token');
    }

    static clearAuthSession() {
        localStorage.removeItem('token');
        localStorage.removeItem('user_role');
        localStorage.removeItem('user_id');
    }

    static handleSessionExpired() {
        this.clearAuthSession();
        window.location.href = '../Login Screen/index.html';
        const error = new Error("Session expired. Please login again.");
        error.status = 401;
        throw error;
    }

    static async request(endpoint, options = {}) {
        const headers = {
            ...options.headers
        };

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        // Do not set Content-Type for FormData, the browser sets it automatically with the boundary
        if (!(options.body instanceof FormData) && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        const baseUrl = getActiveBaseUrl();
        if (!baseUrl) {
            throw new Error("SCOS: Backend URL is not configured. Running directly via file:// is not supported. Please serve the application over HTTP or set SCOS_BACKEND_URL.");
        }

        try {
            const response = await fetch(`${baseUrl}${endpoint}`, {
                ...options,
                headers
            });

            if (response.status === 401) {
                this.handleSessionExpired();
            }

            let data = null;
            try {
                data = await response.json();
            } catch (jsonErr) {
                // Non-JSON response or empty body
            }
            
            if (!response.ok) {
                const detail = (data && data.detail) ? data.detail : `An API error occurred (${response.status})`;
                const error = new Error(detail);
                error.status = response.status;
                error.data = data;
                throw error;
            }

            return data;
        } catch (error) {
            console.error('API Request Failed:', error);
            throw error;
        }
    }

    static async loginUser(email, password) {
        // FastAPI OAuth2PasswordRequestForm requires form data
        const formData = new FormData();
        formData.append("username", email);
        formData.append("password", password);
        
        return this.request('/api/auth/login', {
            method: 'POST',
            body: formData
        });
    }

    static async registerUser(data) {
        return this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify(data),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    static async reportWaste(formData) {
        return this.request('/api/citizen/report_issue', {
            method: 'POST',
            body: formData
        });
    }

    static async fetchComplaints() {
        return this.request('/api/citizen/my_reports', {
            method: 'GET'
        });
    }

    static async updateDriverLocation(lat, lng) {
        const formData = new FormData();
        formData.append("lat", lat);
        formData.append("lng", lng);

        return this.request('/api/driver/update_location', {
            method: 'POST',
            body: formData
        });
    }

    static async completePickup(formData) {
        return this.request('/api/driver/complete_pickup', {
            method: 'POST',
            body: formData
        });
    }

    static async fetchDashboardStats() {
        return this.request('/api/admin/overview', {
            method: 'GET'
        });
    }

    static async fetchCitizenDashboard() {
        return this.request('/api/citizen/dashboard', {
            method: 'GET'
        });
    }

    static async fetchDriverDashboard() {
        return this.request('/api/driver/dashboard', {
            method: 'GET'
        });
    }

    static async fetchAssignedTasks() {
        return this.request('/api/driver/assigned_tasks', {
            method: 'GET'
        });
    }

    static async fetchRewards() {
        return this.request('/api/citizen/rewards', {
            method: 'GET'
        });
    }

    static async fetchLeaderboard() {
        return this.request('/api/citizen/leaderboard', {
            method: 'GET'
        });
    }

    static async redeemReward(rewardId) {
        return this.request('/api/citizen/redeem_reward', {
            method: 'POST',
            body: JSON.stringify({ reward_id: rewardId }),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    static async fetchAdminOverview() {
        return this.request('/api/admin/overview', {
            method: 'GET'
        });
    }

    static async fetchAdminHeatmap() {
        return this.request('/api/admin/waste_heatmap', {
            method: 'GET'
        });
    }

    static async fetchIllegalDumping() {
        return this.request('/api/admin/illegal_dumping', {
            method: 'GET'
        });
    }

    static async fetchAdminComplaints() {
        return this.request('/api/admin/complaints', {
            method: 'GET'
        });
    }

    static async fetchDrivers() {
        return this.request('/api/admin/drivers', {
            method: 'GET'
        });
    }

    static async assignTask(complaintId, driverId, wasteType, address) {
        return this.request('/api/admin/assign_task', {
            method: 'POST',
            body: JSON.stringify({
                complaint_id: complaintId,
                driver_id: driverId,
                waste_type: wasteType || 'General',
                address: address || 'Unknown'
            }),
            headers: { 'Content-Type': 'application/json' }
        });
    }

    static async fetchProofPhotoBlob(proofUrl, options = {}) {
        if (!proofUrl) {
            throw new Error("No proof photo URL provided.");
        }
        const token = this.getToken();
        const headers = { ...options.headers };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const baseUrl = getActiveBaseUrl();
        if (!baseUrl) {
            throw new Error("SCOS: Backend URL is not configured. Running directly via file:// is not supported. Please serve the application over HTTP or set SCOS_BACKEND_URL.");
        }
        const endpoint = proofUrl.startsWith('/') ? proofUrl : `/${proofUrl}`;
        const fetchOptions = {
            method: 'GET',
            headers
        };
        if (options.signal) {
            fetchOptions.signal = options.signal;
        }

        const response = await fetch(`${baseUrl}${endpoint}`, fetchOptions);

        if (response.status === 401) {
            this.handleSessionExpired();
        }

        if (!response.ok) {
            let errorMsg = `Failed to load proof photo (${response.status})`;
            try {
                const errData = await response.json();
                if (errData && errData.detail) errorMsg = errData.detail;
            } catch (_) {}
            const err = new Error(errorMsg);
            err.status = response.status;
            throw err;
        }

        const contentType = (response.headers.get('content-type') || '').toLowerCase().split(';')[0].trim();
        const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
        if (!validTypes.includes(contentType)) {
            throw new Error(`Invalid proof image format: ${contentType || 'unknown'}. Expected image/jpeg, image/png, or image/webp.`);
        }

        return await response.blob();
    }

}

window.API = API;
