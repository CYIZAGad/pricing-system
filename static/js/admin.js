// Admin dashboard functionality

// Utility: escape HTML to prevent XSS
function escapeHtml(text) {
    if (text == null) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// Make showPage globally accessible
window.showPage = function(pageName) {
    try {
        console.log('showPage called with:', pageName);
        
        // Hide all pages
        document.querySelectorAll('.page').forEach(page => page.classList.add('hidden'));
        
        // Show target page
        const targetPage = document.getElementById(`${pageName}-page`);
        if (!targetPage) {
            console.error(`Page element not found: ${pageName}-page`);
            return;
        }
        
        targetPage.classList.remove('hidden');
        console.log('Page shown:', pageName);
        
        // Load page data
        if (pageName === 'manage-depot') {
            loadDepotUsers();
        } else if (pageName === 'admin-profile') {
            loadAdminProfile();
        }
    } catch (error) {
        console.error('Error in showPage:', error);
        showAlert('Failed to load page. Please refresh and try again.', 'error');
    }
};

// Authentication check on page load
(async function() {
    console.log('Starting authentication check...');
    const isAuthenticated = await checkAuth();
    if (!isAuthenticated) {
        console.log('Authentication failed, redirecting...');
        return; // Will redirect to login
    }
    
    const user = getUser();
    if (!user || user.role !== 'admin') {
        console.log('User role check failed, redirecting...');
        // Redirect non-admin users based on their role
        if (user && user.role === 'depot') {
            window.location.replace('/depot.html');
        } else {
            removeToken();
            window.location.replace('/');
        }
        return;
    }
    
    console.log('Authentication successful, initializing dashboard...');
    // Initialize dashboard after authentication
    initializeDashboard();
})();

// Detect back/forward button navigation
window.addEventListener('pageshow', async function(event) {
    // If page was loaded from cache (back button), verify authentication
    if (event.persisted) {
        const isAuthenticated = await checkAuth();
        if (!isAuthenticated) {
            return; // Will redirect to login
        }
    }
});

// Prevent page caching
window.addEventListener('beforeunload', function() {
    // Clear sensitive data if needed
});

function initializeDashboard() {
    // All dashboard initialization code goes here
    
    // Wait for DOM to be ready, then setup
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setupDashboard();
        });
    } else {
        setupDashboard();
    }
}

// Setup forms and navigation (called from initializeDashboard after auth)
function setupDashboard() {
    console.log('setupDashboard called');
    
    // Verify page elements exist
    const manageDepotPage = document.getElementById('manage-depot-page');
    const adminProfilePage = document.getElementById('admin-profile-page');
    
    console.log('Page elements:', {
        manageDepot: !!manageDepotPage,
        adminProfile: !!adminProfilePage
    });
    
    // Navigation
    const navItems = document.querySelectorAll('.nav-item[data-page]');
    console.log('Setting up navigation for', navItems.length, 'items');
    
    if (navItems.length === 0) {
        console.error('No navigation items found!');
        return;
    }
    
    navItems.forEach(item => {
        const page = item.getAttribute('data-page');
        console.log('Adding listener for page:', page);
        
        item.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('Navigation clicked:', page);
            
            const pageName = item.getAttribute('data-page');
            if (!pageName) {
                console.error('No data-page attribute found');
                return;
            }
            
            // Update active state
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');
            
            // Show page
            showPage(pageName);
        });
    });
    
    // Setup forms
    setupCreateTenantForm();
    setupAdminProfileForm();
    setupAdminPasswordForm();
    
    // Show manage-depot page by default
    showPage('manage-depot');
}

// Load depot users only
async function loadDepotUsers() {
    const container = document.getElementById('depot-users-list');
    container.innerHTML = '<div class="spinner"></div><p>Loading depot users...</p>';
    
    try {
        // Get all users and filter for depot role
        const data = await apiRequest('/admin/users');
        const depotUsers = data.users.filter(u => u.role === 'depot');
        
        if (depotUsers.length === 0) {
            container.innerHTML = '<p>No depot users found. Create a new depot above.</p>';
            return;
        }
        
        const table = `
            <div style="margin-bottom: 15px; padding: 12px; background: #e0f2fe; border-radius: 8px; border-left: 4px solid var(--primary-color);">
                <strong>📊 Total Depot Users:</strong> ${depotUsers.length} depot(s) registered in the system
            </div>
            <div class="table-container" style="overflow-x: auto;">
                <table class="table" style="min-width: 1200px;">
                    <thead>
                        <tr>
                            <th>Business Name</th>
                            <th>Registration Number</th>
                            <th>Contact Person</th>
                            <th>Email</th>
                            <th>Phone</th>
                            <th>Address</th>
                            <th>Status</th>
                            <th>Created</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${depotUsers.map(user => {
                            const tenant = user.tenant || {};
                            return `
                            <tr>
                                <td><strong>${escapeHtml(tenant.business_name) || '-'}</strong></td>
                                <td>${escapeHtml(tenant.registration_number) || '-'}</td>
                                <td>${escapeHtml(tenant.contact_person || user.full_name) || '-'}</td>
                                <td>${escapeHtml(user.email || tenant.email) || '-'}</td>
                                <td>${escapeHtml(user.phone || tenant.phone) || '-'}</td>
                                <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(tenant.address)}">${escapeHtml(tenant.address) || '-'}</td>
                                <td><span class="badge ${user.is_active ? 'active' : 'inactive'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
                                <td>${user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</td>
                                <td>
                                    <div style="display: flex; gap: 5px;">
                                        <button class="btn btn-secondary" onclick="editDepotUser('${escapeHtml(user.id)}')" style="padding: 6px 12px; font-size: 12px;">✏️ Edit</button>
                                        <button class="btn btn-danger" onclick="deleteDepotUser('${escapeHtml(user.id)}', '${escapeHtml(user.email)}')" style="padding: 6px 12px; font-size: 12px;">🗑️ Delete</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
        `;
        
        container.innerHTML = table;
    } catch (error) {
        console.error('Error loading depot users:', error);
        container.innerHTML = `<div class="alert alert-error">${error.message || 'Failed to load depot users'}</div>`;
    }
}

// Create tenant form handler
function setupCreateTenantForm() {
    const form = document.getElementById('create-tenant-form');
    if (!form) {
        console.error('Create tenant form not found');
        return;
    }
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            business_name: document.getElementById('business-name').value.trim(),
            registration_number: document.getElementById('registration-number').value.trim(),
            contact_person: document.getElementById('contact-person').value.trim(),
            email: document.getElementById('tenant-email').value.trim(),
            phone: document.getElementById('tenant-phone').value.trim(),
            address: document.getElementById('tenant-address').value.trim(),
            password: document.getElementById('manager-password').value,
            password_confirm: document.getElementById('manager-password-confirm').value
        };
        
        // Validate required fields
        if (!formData.business_name || !formData.email) {
            showAlert('Business name and email are required', 'error');
            return;
        }
        
        // Validate password
        if (!formData.password || formData.password.length < 6) {
            showAlert('Password is required and must be at least 6 characters', 'error');
            return;
        }
        
        // Validate password confirmation
        if (formData.password !== formData.password_confirm) {
            showAlert('Passwords do not match', 'error');
            return;
        }
        
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';
        
        try {
            console.log('Creating depot:', formData);
            const data = await apiRequest('/admin/tenant', {
                method: 'POST',
                body: JSON.stringify(formData)
            });
            
            console.log('Depot created successfully:', data);
            showAlert('Depot and user account created successfully! The depot user can now login with the email and password you set.', 'success');
            e.target.reset();
            
            // Refresh depot users after a short delay
            setTimeout(() => {
                loadDepotUsers();
            }, 1000);
        } catch (error) {
            console.error('Error creating depot:', error);
            // Extract detailed error message with better handling
            let errorMessage = 'Failed to create depot.';
            
            if (error.message) {
                errorMessage = error.message;
            } else if (error.error) {
                errorMessage = error.error;
            } else if (error.data) {
                // Try to get message from error.data
                errorMessage = error.data.message || error.data.error || errorMessage;
            }
            
            // Log full error for debugging
            console.error('Full error details:', {
                message: error.message,
                status: error.status,
                data: error.data,
                error: error
            });
            
            // Show the error message
            showAlert(errorMessage, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Edit depot user
async function editDepotUser(userId) {
    try {
        const data = await apiRequest('/admin/users');
        const user = data.users.find(u => u.id === userId && u.role === 'depot');
        
        if (!user) {
            showAlert('Depot user not found', 'error');
            return;
        }
        
        // Show edit modal
        const editModal = document.getElementById('edit-depot-user-modal') || createEditDepotUserModal();
        document.getElementById('edit-depot-user-id').value = user.id;
        document.getElementById('edit-depot-user-email').value = user.email || '';
        document.getElementById('edit-depot-user-full-name').value = user.full_name || '';
        document.getElementById('edit-depot-user-phone').value = user.phone || '';
        document.getElementById('edit-depot-user-is-active').checked = user.is_active || false;
        
        editModal.style.display = 'block';
    } catch (error) {
        showAlert(error.message || 'Failed to load depot user data', 'error');
    }
}

// Create edit depot user modal
function createEditDepotUserModal() {
    const modal = document.createElement('div');
    modal.id = 'edit-depot-user-modal';
    modal.style.cssText = 'display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000;';
    modal.innerHTML = `
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%; max-height: 90vh; overflow-y: auto;">
            <h2 style="margin-top: 0;">Edit Depot User</h2>
            <form id="edit-depot-user-form">
                <input type="hidden" id="edit-depot-user-id">
                <div class="form-group">
                    <label class="form-label">Email *</label>
                    <input type="email" id="edit-depot-user-email" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Full Name *</label>
                    <input type="text" id="edit-depot-user-full-name" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Phone</label>
                    <input type="tel" id="edit-depot-user-phone" class="form-input">
                </div>
                <div class="form-group">
                    <label style="display: flex; align-items: center; gap: 10px;">
                        <input type="checkbox" id="edit-depot-user-is-active">
                        Active
                    </label>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="submit" class="btn btn-primary">Update User</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('edit-depot-user-modal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Handle form submission
    document.getElementById('edit-depot-user-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            email: document.getElementById('edit-depot-user-email').value.trim(),
            full_name: document.getElementById('edit-depot-user-full-name').value.trim(),
            phone: document.getElementById('edit-depot-user-phone').value.trim(),
            is_active: document.getElementById('edit-depot-user-is-active').checked
        };
        
        try {
            const userId = document.getElementById('edit-depot-user-id').value;
            await apiRequest(`/admin/user/${userId}`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            
            showAlert('Depot user updated successfully', 'success');
            modal.style.display = 'none';
            loadDepotUsers();
        } catch (error) {
            showAlert(error.message || 'Failed to update depot user', 'error');
        }
    });
    
    // Close on background click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.style.display = 'none';
        }
    });
    
    return modal;
}

// Delete depot user
async function deleteDepotUser(userId, userEmail) {
    if (!confirm(`Are you sure you want to delete depot user "${userEmail}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        await apiRequest(`/admin/user/${userId}`, {
            method: 'DELETE'
        });
        
        showAlert('Depot user deleted successfully', 'success');
        loadDepotUsers();
    } catch (error) {
        showAlert(error.message || 'Failed to delete depot user', 'error');
    }
}

// Load admin profile
async function loadAdminProfile() {
    try {
        const data = await apiRequest('/admin/profile');
        const adminUser = data.user;
        
        // Populate profile form
        document.getElementById('profile-email').value = adminUser.email || '';
        document.getElementById('profile-full-name').value = adminUser.full_name || '';
        document.getElementById('profile-phone').value = adminUser.phone || '';
        document.getElementById('profile-created-at').textContent = adminUser.created_at 
            ? new Date(adminUser.created_at).toLocaleString() 
            : '-';
        document.getElementById('profile-last-login').textContent = adminUser.last_login 
            ? new Date(adminUser.last_login).toLocaleString() 
            : 'Never';
    } catch (error) {
        console.error('Error loading admin profile:', error);
        showAlert(error.message || 'Failed to load profile', 'error');
    }
}

// Setup admin profile form
function setupAdminProfileForm() {
    const form = document.getElementById('admin-profile-form');
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            email: document.getElementById('profile-email').value.trim(),
            full_name: document.getElementById('profile-full-name').value.trim(),
            phone: document.getElementById('profile-phone').value.trim()
        };
        
        if (!formData.email || !formData.full_name) {
            showAlert('Email and full name are required', 'error');
            return;
        }
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Updating...';
        
        try {
            await apiRequest('/admin/profile', {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            
            showAlert('Profile updated successfully', 'success');
            // Reload profile to get updated info
            loadAdminProfile();
        } catch (error) {
            console.error('Error updating profile:', error);
            showAlert(error.message || 'Failed to update profile', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Setup admin password form
function setupAdminPasswordForm() {
    const form = document.getElementById('admin-password-form');
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            current_password: document.getElementById('current-password').value,
            new_password: document.getElementById('new-password').value,
            confirm_password: document.getElementById('confirm-password').value
        };
        
        if (!formData.current_password || !formData.new_password || !formData.confirm_password) {
            showAlert('All password fields are required', 'error');
            return;
        }
        
        if (formData.new_password.length < 6) {
            showAlert('New password must be at least 6 characters', 'error');
            return;
        }
        
        if (formData.new_password !== formData.confirm_password) {
            showAlert('New passwords do not match', 'error');
            return;
        }
        
        const submitBtn = form.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = 'Changing...';
        
        try {
            await apiRequest('/admin/profile/password', {
                method: 'PUT',
                body: JSON.stringify({
                    current_password: formData.current_password,
                    new_password: formData.new_password,
                    confirm_password: formData.confirm_password
                })
            });
            
            showAlert('Password changed successfully', 'success');
            form.reset();
        } catch (error) {
            console.error('Error changing password:', error);
            showAlert(error.message || 'Failed to change password', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Setup forms (called from initializeDashboard)
function setupDashboard() {
    setupCreateTenantForm();
    setupAdminProfileForm();
    setupAdminPasswordForm();
    showPage('manage-depot');
}
