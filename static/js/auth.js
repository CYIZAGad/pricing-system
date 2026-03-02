// Authentication and API utilities

const API_BASE = '/api/v1';

// Store token in localStorage
function setToken(token) {
    localStorage.setItem('token', token);
}

function getToken() {
    return localStorage.getItem('token');
}

function removeToken() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
}

function setUser(user) {
    localStorage.setItem('user', JSON.stringify(user));
}

function getUser() {
    const userStr = localStorage.getItem('user');
    return userStr ? JSON.parse(userStr) : null;
}

// API request helper
async function apiRequest(endpoint, options = {}) {
    const token = getToken();
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Always include credentials for session cookies
    const fetchOptions = {
        ...options,
        headers,
        credentials: 'include'
    };
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, fetchOptions);
        
        let data;
        try {
            data = await response.json();
        } catch (jsonError) {
            // If JSON parsing fails, try to get text
            const text = await response.text();
            console.error('Failed to parse JSON response:', text);
            throw new Error(`Server error: ${response.status} ${response.statusText}`);
        }
        
        // Handle token expiration (401 Unauthorized)
        if (response.status === 401) {
            // Token expired or invalid - log out and redirect to login
            removeToken();
            if (window.location.pathname !== '/') {
                showAlert('Your session has expired. Please log in again.', 'error');
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            }
            throw new Error(data.error || data.message || 'Session expired. Please log in again.');
        }
        
        if (!response.ok) {
            // Extract error message with priority: message > error > status text
            const errorMsg = data.message || data.error || `Request failed: ${response.status} ${response.statusText}`;
            const error = new Error(errorMsg);
            error.status = response.status;
            error.data = data;
            throw error;
        }
        
        return data;
    } catch (error) {
        console.error('API request error:', error);
        // If it's already an Error object with message, just rethrow
        if (error instanceof Error) {
            throw error;
        }
        // Otherwise wrap it
        throw new Error(error.message || 'Request failed');
    }
}

// Login
async function login(email, password) {
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include',  // Include cookies for session
        body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.error || 'Login failed');
    }
    
    setToken(data.token);
    setUser(data.user);
    
    return data;
}

// Logout
async function logout() {
    try {
        // Call backend to destroy session
        await apiRequest('/auth/logout', {
            method: 'POST'
        });
    } catch (error) {
        // Continue with logout even if API call fails
        console.error('Logout API error:', error);
    }
    
    // Clear all authentication data
    removeToken();
    
    // Clear session storage
    sessionStorage.clear();
    
    // Clear any cached data
    if ('caches' in window) {
        caches.keys().then(names => {
            names.forEach(name => caches.delete(name));
        });
    }
    
    // Force redirect to landing page with cache bypass
    window.location.replace('/');
}

// Check authentication and verify session with backend
async function checkAuth() {
    const token = getToken();
    const user = getUser();
    
    if (!token || !user) {
        removeToken();
        window.location.replace('/');
        return false;
    }
    
    // Verify session is still valid by making an API call
    try {
        // Use session verification endpoint (uses cookies, not token)
        const response = await fetch(`${API_BASE}/auth/verify`, {
            method: 'GET',
            credentials: 'include'  // Include cookies for session
        });
        
        if (!response.ok) {
            // Session is invalid or expired
            removeToken();
            window.location.replace('/');
            return false;
        }
        
        return true;
    } catch (error) {
        // Network error or session invalid
        removeToken();
        window.location.replace('/');
        return false;
    }
}

// Show alert
function showAlert(message, type = 'error') {
    const container = document.getElementById('alert-container');
    if (!container) {
        // Fallback: use console and alert if container doesn't exist
        console.error('Alert container not found. Message:', message);
        alert(message);
        return;
    }
    
    // Remove any existing alerts first
    const existingAlerts = container.querySelectorAll('.alert');
    existingAlerts.forEach(alert => alert.remove());
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.style.cssText = 'padding: 15px 20px; margin-bottom: 10px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); animation: slideIn 0.3s ease-out;';
    
    if (type === 'success') {
        alert.style.background = '#10b981';
        alert.style.color = 'white';
    } else if (type === 'error') {
        alert.style.background = '#ef4444';
        alert.style.color = 'white';
    } else {
        alert.style.background = '#3b82f6';
        alert.style.color = 'white';
    }
    
    alert.textContent = message;
    container.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => alert.remove(), 300);
        }
    }, 5000);
}

// Login form handler
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const submitBtn = loginForm.querySelector('button[type="submit"]');
            
            submitBtn.disabled = true;
            submitBtn.textContent = 'Logging in...';
            
            try {
                const data = await login(email, password);
                
                // Redirect based on role (only admin and depot)
                const role = data.user.role;
                if (role === 'admin') {
                    window.location.href = '/admin.html';
                } else if (role === 'depot') {
                    window.location.href = '/depot.html';
                } else {
                    showAlert('Unknown user role. Please contact administrator.', 'error');
                }
            } catch (error) {
                showAlert(error.message || 'Login failed', 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Login';
            }
        });
    }
});
