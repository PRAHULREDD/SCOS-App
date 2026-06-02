/**
 * Central API Handler for SCOS Frontend
 */
const BASE_URL = window.location.origin;

class API {
    static getToken() {
        return localStorage.getItem('token');
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

        try {
            const response = await fetch(`${BASE_URL}${endpoint}`, {
                ...options,
                headers
            });

            if (response.status === 401) {
                // Token might be expired, redirect to login
                localStorage.removeItem('token');
                window.location.href = '/app/Login Screen/index.html';
                throw new Error("Session expired. Please login again.");
            }

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || 'An API error occurred');
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
        const formData = new FormData();
        Object.keys(data).forEach(key => formData.append(key, data[key]));
        
        return this.request('/api/auth/register', {
            method: 'POST',
            body: formData
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
        return this.request('/api/admin/dashboard_stats', {
            method: 'GET'
        });
    }

    static async fetchRewards() {
        return this.request('/api/citizen/rewards', {
            method: 'GET'
        });
    }

    static async redeemReward(rewardId) {
        const formData = new FormData();
        formData.append("reward_id", rewardId);
        return this.request('/api/citizen/redeem_reward', {
            method: 'POST',
            body: formData
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
}

window.API = API;
