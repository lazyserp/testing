// api.js — Central API wrapper for the frontend
const BASE_URL = 'http://localhost:8000/api';

class ApiClient {
    constructor() {
        this.token = localStorage.getItem('access_token');
        this.user = JSON.parse(localStorage.getItem('user_profile') || 'null');
    }

    setAuth(token, user) {
        this.token = token;
        this.user = user;
        localStorage.setItem('access_token', token);
        localStorage.setItem('user_profile', JSON.stringify(user));
    }

    clearAuth() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_profile');
    }

    isAuthenticated() {
        return !!this.token;
    }

    async _fetch(endpoint, options = {}) {
        const headers = { ...options.headers };
        
        if (this.token && !options.noAuth) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        if (!(options.body instanceof FormData) && options.body) {
            headers['Content-Type'] = 'application/json';
            options.body = JSON.stringify(options.body);
        }

        const config = { ...options, headers };
        
        try {
            const response = await fetch(`${BASE_URL}${endpoint}`, config);
            const contentType = response.headers.get("content-type");
            let data = null;
            if (contentType && contentType.indexOf("application/json") !== -1) {
                data = await response.json();
            }

            if (!response.ok) {
                if (response.status === 401) {
                    this.clearAuth();
                    window.location.href = 'index.html';
                }
                throw new Error(data?.detail || response.statusText || 'An error occurred');
            }
            
            return data;
        } catch (error) {
            throw error;
        }
    }

    // Auth
    async login(email, password) {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);
        
        const res = await this._fetch('/auth/login', {
            method: 'POST',
            body: formData,
            noAuth: true
        });
        
        this.setAuth(res.access_token, res.employee);
        return res;
    }

    logout() {
        this.clearAuth();
        window.location.href = 'index.html';
    }

    async getProfile() {
        return this._fetch('/auth/me');
    }

    // Schedule & Bookings
    async getWeekSchedule(dateStr = '') {
        const qs = dateStr ? `?d=${dateStr}` : '';
        return this._fetch(`/schedule/week${qs}`);
    }

    async getMyBookings() {
        return this._fetch('/bookings');
    }

    async getAvailableSeats(dateStr) {
        return this._fetch(`/seats/available?d=${dateStr}`);
    }

    async bookFloaterSeat(seatId, dateStr) {
        return this._fetch('/bookings', {
            method: 'POST',
            body: { seat_id: seatId, booking_date: dateStr }
        });
    }

    async releaseFixedSeat(dateStr) {
        return this._fetch('/bookings/release', {
            method: 'POST',
            body: { seat_id: 0, booking_date: dateStr } // seat_id ignored in backend for release
        });
    }

    async cancelBooking(bookingId) {
        return this._fetch(`/bookings/${bookingId}`, { method: 'DELETE' });
    }

    // Leaves
    async markLeave(dateStr, reason = '') {
        return this._fetch('/leaves', {
            method: 'POST',
            body: { leave_date: dateStr, reason }
        });
    }

    // Admin
    async getDailyAllocation(dateStr = '') {
        const qs = dateStr ? `?d=${dateStr}` : '';
        return this._fetch(`/schedule/day${qs}`);
    }

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}

// Global instance
const API = new ApiClient();
