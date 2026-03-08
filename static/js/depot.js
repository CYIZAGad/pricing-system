// Depot dashboard functionality

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
        
        // Load page-specific data
        if (pageName === 'products') {
            loadProducts();
        } else if (pageName === 'download-prices') {
            // Reset download prices form
            const downloadForm = document.getElementById('download-prices-form');
            const resultsContainer = document.getElementById('download-results-container');
            const processingContainer = document.getElementById('download-processing');
            
            if (downloadForm) downloadForm.reset();
            if (resultsContainer) resultsContainer.style.display = 'none';
            if (processingContainer) processingContainer.style.display = 'none';
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
    if (!user || user.role !== 'depot') {
        console.log('User role check failed, redirecting...');
        // Redirect non-depot users to login
        removeToken();
        window.location.replace('/');
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
    const user = getUser();
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            setupDashboard(user);
        });
    } else {
        setupDashboard(user);
    }
}

function setupDashboard(user) {
    console.log('setupDashboard called');
    
    // Display user info in sidebar
    if (user) {
        const userNameEl = document.getElementById('user-name');
        const userRoleEl = document.getElementById('user-role');
        
        if (userNameEl) {
            userNameEl.textContent = user.full_name || user.email;
        }
        if (userRoleEl) {
            userRoleEl.textContent = 'Depot';
        }
    }
    
    // Verify page elements exist
    const uploadPage = document.getElementById('upload-page');
    const productsPage = document.getElementById('products-page');
    const downloadPage = document.getElementById('download-prices-page');
    
    console.log('Page elements:', {
        upload: !!uploadPage,
        products: !!productsPage,
        download: !!downloadPage
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
    
    // Show Get Prices page by default after login
    showPage('download-prices');
    
    // Ensure the correct nav item is marked active
    document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
    const getPricesNav = document.querySelector('.nav-item[data-page="download-prices"]');
    if (getPricesNav) {
        getPricesNav.classList.add('active');
    }
}


// Upload form handler
function setupUploadForm() {
    const uploadForm = document.getElementById('upload-form');
    if (!uploadForm) return;
    
    uploadForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('price-file');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select a file', 'error');
        return;
    }
    
    // Show immediate feedback
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.textContent;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ Uploading...';
    
    // Show loading message immediately
    showAlert('📤 Uploading file, please wait...', 'info');
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const token = getToken();
        const response = await fetch('/api/v1/depot/upload', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            // Prefer message over error for more specific details
            const errorMsg = data.message || data.error || 'Upload failed';
            // Include errors array if available for debugging
            if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
                throw new Error(`${errorMsg}. First errors: ${data.errors.slice(0, 3).join('; ')}`);
            }
            throw new Error(errorMsg);
        }
        
        // Success message with details
        const successMsg = `✅ Upload successful! ${data.statistics.valid_items} items processed. All medicines have been added to your catalog.`;
        
        showAlert(successMsg, 'success');
        fileInput.value = '';
        
        // Refresh products page if it's currently visible
        if (document.getElementById('products-page') && !document.getElementById('products-page').classList.contains('hidden')) {
            loadProducts();
        }
    } catch (error) {
        showAlert(`❌ Upload failed: ${error.message || 'Unknown error'}`, 'error');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalText;
    }
    });
}

// Initialize upload form when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupUploadForm);
} else {
    setupUploadForm();
}

// Download Prices - Store matched medicines
let matchedMedicines = [];

// Load products
// Format price with RWF currency
function formatPriceRWF(price) {
    return new Intl.NumberFormat('en-RW', {
        style: 'currency',
        currency: 'RWF',
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    }).format(price);
}

// Pagination state
let currentPage = 1;
const itemsPerPage = 100;

async function loadProducts(search = '', page = 1) {
    const container = document.getElementById('products-list');
    container.innerHTML = '<div class="spinner"></div><p>Loading products...</p>';
    
    currentPage = page;
    
    try {
        const url = `/depot/medicines?page=${page}&limit=${itemsPerPage}${search ? `&search=${encodeURIComponent(search)}` : ''}`;
        const data = await apiRequest(url);
        
        if (data.medicines.length === 0) {
            container.innerHTML = `
                <div class="alert alert-info">
                    <p>No products found. Upload a price list first to add products.</p>
                    <button class="btn btn-primary" onclick="showPage('upload'); document.querySelector('.nav-item[data-page=\\'upload\\']').click();">
                        Upload Price List
                    </button>
                </div>
            `;
            return;
        }
        
        // Build pagination controls
        const totalPages = data.pagination.pages || Math.ceil(data.pagination.total / itemsPerPage);
        const paginationHTML = buildPaginationControls(page, totalPages, search);
        
        const table = `
            <div class="table-container">
                <div style="margin-bottom: 15px; padding: 12px; background: #e0f2fe; border-radius: 8px; border-left: 4px solid var(--primary-color);">
                    <strong>📦 Total Products:</strong> ${data.pagination.total} medicines from all your uploaded price lists
                </div>
                <table class="table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Medicine Name</th>
                            <th>Price</th>
                            <th>Expiry Date</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.medicines.map((med, index) => {
                            const expiryDate = med.expiry_date ? new Date(med.expiry_date).toLocaleDateString() : 'N/A';
                            return `
                            <tr>
                                <td>${(page - 1) * itemsPerPage + index + 1}</td>
                                <td><strong>${escapeHtml(med.medicine_name)}</strong></td>
                                <td><strong style="color: #10b981; font-size: 16px;">${formatPriceRWF(med.unit_price)}</strong></td>
                                <td>${expiryDate}</td>
                                <td>
                                    <div style="display: flex; gap: 5px;">
                                        <button class="btn btn-secondary" onclick="editMedicine('${med.id}')" style="padding: 6px 12px; font-size: 12px;">✏️ Edit</button>
                                        <button class="btn btn-danger" onclick="deleteMedicine('${med.id}', '${escapeHtml(med.medicine_name).replace(/'/g, "\\'")}')" style="padding: 6px 12px; font-size: 12px;">🗑️ Delete</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                        }).join('')}
                    </tbody>
                </table>
                <div style="margin-top: 15px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                    <div style="color: var(--text-secondary);">
                        Showing ${(page - 1) * itemsPerPage + 1} to ${Math.min(page * itemsPerPage, data.pagination.total)} of ${data.pagination.total} products
                    </div>
                    ${paginationHTML}
                </div>
            </div>
        `;
        
        container.innerHTML = table;
    } catch (error) {
        // Don't show error if it's a token expiration (will be handled by apiRequest)
        if (error.message && error.message.includes('Session expired')) {
            // apiRequest will handle redirect, just clear the container
            container.innerHTML = '<p>Redirecting to login...</p>';
        } else {
            container.innerHTML = `<div class="alert alert-error">${error.message || 'Failed to load products'}</div>`;
        }
    }
}

function buildPaginationControls(currentPage, totalPages, search = '') {
    if (totalPages <= 1) {
        return '';
    }
    
    const maxVisiblePages = 7;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    let paginationHTML = '<div style="display: flex; gap: 5px; align-items: center; flex-wrap: wrap;">';
    
    // Previous button
    if (currentPage > 1) {
        paginationHTML += `<button class="btn btn-secondary" onclick="loadProducts('${search.replace(/'/g, "\\'")}', ${currentPage - 1})" style="padding: 6px 12px;">‹ Previous</button>`;
    } else {
        paginationHTML += `<button class="btn btn-secondary" disabled style="padding: 6px 12px; opacity: 0.5;">‹ Previous</button>`;
    }
    
    // First page
    if (startPage > 1) {
        paginationHTML += `<button class="btn btn-secondary" onclick="loadProducts('${search.replace(/'/g, "\\'")}', 1)" style="padding: 6px 12px;">1</button>`;
        if (startPage > 2) {
            paginationHTML += `<span style="padding: 6px;">...</span>`;
        }
    }
    
    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        if (i === currentPage) {
            paginationHTML += `<button class="btn btn-primary" disabled style="padding: 6px 12px; font-weight: bold;">${i}</button>`;
        } else {
            paginationHTML += `<button class="btn btn-secondary" onclick="loadProducts('${search.replace(/'/g, "\\'")}', ${i})" style="padding: 6px 12px;">${i}</button>`;
        }
    }
    
    // Last page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            paginationHTML += `<span style="padding: 6px;">...</span>`;
        }
        paginationHTML += `<button class="btn btn-secondary" onclick="loadProducts('${search.replace(/'/g, "\\'")}', ${totalPages})" style="padding: 6px 12px;">${totalPages}</button>`;
    }
    
    // Next button
    if (currentPage < totalPages) {
        paginationHTML += `<button class="btn btn-secondary" onclick="loadProducts('${search.replace(/'/g, "\\'")}', ${currentPage + 1})" style="padding: 6px 12px;">Next ›</button>`;
    } else {
        paginationHTML += `<button class="btn btn-secondary" disabled style="padding: 6px 12px; opacity: 0.5;">Next ›</button>`;
    }
    
    paginationHTML += '</div>';
    return paginationHTML;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Search products
function searchProducts() {
    const search = document.getElementById('product-search').value.trim();
    loadProducts(search, 1); // Reset to page 1 when searching
}

// Enter key search
document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('product-search');
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchProducts();
            }
        });
    }
});

// Download Prices Form Handler
function setupDownloadForm() {
    const downloadForm = document.getElementById('download-prices-form');
    if (downloadForm) {
        downloadForm.addEventListener('submit', handleDownloadPrices);
    }
}

// Initialize download form when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupDownloadForm);
} else {
    setupDownloadForm();
}

// Handle Download Prices
async function handleDownloadPrices(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('names-file');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('Please select a file', 'error');
        return;
    }
    
    // Show processing state
    document.getElementById('download-processing').style.display = 'block';
    document.getElementById('download-results-container').style.display = 'none';
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        const token = getToken();
        const response = await fetch('/api/v1/depot/download-prices', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to process file');
        }
        
        // Store matched medicines
        matchedMedicines = data.matched_medicines || [];
        
        // Hide processing, show results
        document.getElementById('download-processing').style.display = 'none';
        
        if (matchedMedicines.length === 0) {
            showAlert('No medicines matched. Please check the medicine names in your file.', 'error');
            return;
        }
        
        // Display results
        displayDownloadResults(matchedMedicines, data.statistics, data.not_found);
        document.getElementById('download-results-container').style.display = 'block';
        
    } catch (error) {
        document.getElementById('download-processing').style.display = 'none';
        showAlert(`Failed to process file: ${error.message || 'Unknown error'}`, 'error');
    }
}

// Display Download Results
function displayDownloadResults(medicines, statistics, notFound) {
    const tbody = document.getElementById('download-results-tbody');
    tbody.innerHTML = '';
    
    medicines.forEach((med, index) => {
        const row = document.createElement('tr');
        const expiryDate = med.expiry_date ? new Date(med.expiry_date).toLocaleDateString() : 'N/A';
        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${escapeHtml(med.scanned_name || med.medicine_name || '')}</td>
            <td><strong>${escapeHtml(med.medicine_name)}</strong></td>
            <td><strong style="color: #10b981;">${med.unit_price.toFixed(2)}</strong></td>
            <td>${expiryDate}</td>
        `;
        tbody.appendChild(row);
    });
    
    // Update summary
    const summary = `Requested: ${statistics.total_requested} | Matched: ${statistics.matched} | Not Found: ${statistics.not_found}`;
    document.getElementById('download-summary').textContent = summary;
    
    // Show not found warning if any
    if (notFound && notFound.length > 0) {
        const warning = document.createElement('div');
        warning.style.cssText = 'margin-top: 15px; padding: 12px; background: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px;';
        warning.innerHTML = `
            <strong>⚠️ Not Found (${notFound.length}):</strong>
            <p style="margin: 5px 0; font-size: 14px;">${notFound.slice(0, 10).join(', ')}${notFound.length > 10 ? '...' : ''}</p>
        `;
        document.getElementById('download-results-container').querySelector('.card').appendChild(warning);
    }
}

// Download Prices as CSV
function downloadPricesCSV() {
    if (matchedMedicines.length === 0) {
        showAlert('No data to download', 'error');
        return;
    }
    
    // Get depot name for filename
    const tenant = JSON.parse(localStorage.getItem('tenant') || '{}');
    const depotName = (tenant.business_name || 'medicine').replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_');
    
    // Create CSV content
    let csv = 'Medicine Name,Unit Price,Expiry Date\n';
    matchedMedicines.forEach(med => {
        const expiryDate = med.expiry_date || 'N/A';
        csv += `"${med.medicine_name}",${med.unit_price.toFixed(2)},${expiryDate}\n`;
    });
    
    // Create download link
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${depotName}_prices_${new Date().toISOString().split('T')[0]}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('CSV file downloaded successfully', 'success');
}

// Download Prices as Excel
async function downloadPricesExcel() {
    if (matchedMedicines.length === 0) {
        showAlert('No data to download', 'error');
        return;
    }
    
    try {
        // Send request to backend to generate Excel file
        const token = getToken();
        const response = await fetch('/api/v1/depot/download-prices-excel', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                medicines: matchedMedicines,
                depot_name: (JSON.parse(localStorage.getItem('tenant') || '{}')).business_name || ''
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to generate Excel file');
        }
        
        // Get the Excel file as blob
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        // Use filename from server response
        const disposition = response.headers.get('Content-Disposition');
        let filename = `medicine_prices_${new Date().toISOString().split('T')[0]}.xlsx`;
        if (disposition) {
            const match = disposition.match(/filename[^;=\n]*=(['"]?)([^'"\n;]*)/); 
            if (match && match[2]) filename = match[2];
        }
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        showAlert('Excel file downloaded successfully', 'success');
    } catch (error) {
        showAlert(`Failed to download Excel: ${error.message}`, 'error');
    }
}

// Escape HTML helper
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Edit medicine
async function editMedicine(medicineId) {
    try {
        const data = await apiRequest('/depot/medicines?page=1&limit=1000');
        const medicine = data.medicines.find(m => m.id === medicineId);
        
        if (!medicine) {
            showAlert('Medicine not found', 'error');
            return;
        }
        
        // Show edit modal
        const editModal = document.getElementById('edit-medicine-modal') || createEditMedicineModal();
        document.getElementById('edit-medicine-id').value = medicine.id;
        document.getElementById('edit-medicine-name').value = medicine.medicine_name || '';
        document.getElementById('edit-medicine-price').value = medicine.unit_price || '';
        
        editModal.style.display = 'block';
    } catch (error) {
        showAlert(error.message || 'Failed to load medicine data', 'error');
    }
}

// Create edit medicine modal
function createEditMedicineModal() {
    const modal = document.createElement('div');
    modal.id = 'edit-medicine-modal';
    modal.style.cssText = 'display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 10000;';
    modal.innerHTML = `
        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 30px; border-radius: 12px; max-width: 600px; width: 90%; max-height: 90vh; overflow-y: auto;">
            <h2 style="margin-top: 0;">Edit Medicine</h2>
            <form id="edit-medicine-form">
                <input type="hidden" id="edit-medicine-id">
                <div class="form-group">
                    <label class="form-label">Medicine Name *</label>
                    <input type="text" id="edit-medicine-name" class="form-input" required>
                </div>
                <div class="form-group">
                    <label class="form-label">Price (RWF) *</label>
                    <input type="number" id="edit-medicine-price" class="form-input" step="0.01" min="0" required>
                    <small style="color: var(--text-secondary); margin-top: 5px; display: block;">
                        Enter price in Rwandan Francs (RWF)
                    </small>
                </div>
                <div style="display: flex; gap: 10px; margin-top: 20px;">
                    <button type="submit" class="btn btn-primary">Update Medicine</button>
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('edit-medicine-modal').style.display='none'">Cancel</button>
                </div>
            </form>
        </div>
    `;
    document.body.appendChild(modal);
    
    // Handle form submission
    document.getElementById('edit-medicine-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const formData = {
            medicine_name: document.getElementById('edit-medicine-name').value.trim(),
            unit_price: parseFloat(document.getElementById('edit-medicine-price').value)
        };
        
        try {
            const medicineId = document.getElementById('edit-medicine-id').value;
            await apiRequest(`/depot/medicine/${medicineId}`, {
                method: 'PUT',
                body: JSON.stringify(formData)
            });
            
            showAlert('Medicine updated successfully', 'success');
            modal.style.display = 'none';
            loadProducts();
        } catch (error) {
            showAlert(error.message || 'Failed to update medicine', 'error');
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

// Delete medicine
async function deleteMedicine(medicineId, medicineName) {
    if (!confirm(`Are you sure you want to delete "${medicineName}"? This action cannot be undone.`)) {
        return;
    }
    
    try {
        await apiRequest(`/depot/medicine/${medicineId}`, {
            method: 'DELETE'
        });
        
        showAlert('Medicine deleted successfully', 'success');
        loadProducts();
    } catch (error) {
        showAlert(error.message || 'Failed to delete medicine', 'error');
    }
}

// OCR Upload Functions
let ocrPreviewData = [];

// Manual upload data
let manualUploadData = [];

// Switch upload tab
function switchUploadTab(tab) {
    const fileSection = document.getElementById('file-upload-section');
    const manualSection = document.getElementById('manual-upload-section');
    const fileTab = document.querySelector('.upload-tab-btn[data-tab="file"]');
    const manualTab = document.querySelector('.upload-tab-btn[data-tab="manual"]');
    
    // Hide all sections
    fileSection.style.display = 'none';
    if (manualSection) manualSection.style.display = 'none';
    
    // Reset all tabs
    [fileTab, manualTab].forEach(t => {
        if (t) {
            t.classList.remove('active');
            t.style.borderBottom = 'none';
            t.style.color = 'var(--text-secondary)';
            t.style.fontWeight = 'normal';
        }
    });
    
    // Show selected section and activate tab
    if (tab === 'file') {
        fileSection.style.display = 'block';
        fileTab.classList.add('active');
        fileTab.style.borderBottom = '2px solid var(--primary-color)';
        fileTab.style.color = 'var(--primary-color)';
        fileTab.style.fontWeight = '600';
    } else if (tab === 'manual') {
        if (manualSection) {
            manualSection.style.display = 'block';
            // Initialize with one empty row if empty
            if (manualUploadData.length === 0) {
                addManualRow();
            }
        }
        if (manualTab) {
            manualTab.classList.add('active');
            manualTab.style.borderBottom = '2px solid var(--primary-color)';
            manualTab.style.color = 'var(--primary-color)';
            manualTab.style.fontWeight = '600';
        }
    }
}

// Setup OCR upload form
function setupOCRUploadForm() {
    const ocrForm = document.getElementById('ocr-upload-form');
    if (!ocrForm) return;
    
    ocrForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('ocr-file');
        const file = fileInput.files[0];
        
        if (!file) {
            showAlert('Please select an image or PDF file', 'error');
            return;
        }
        
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Scanning...';
        
        // Show progress bar
        showOCRProgress(0, 'Starting scan...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        // Start progress polling
        let progressInterval = null;
        let progressComplete = false;
        
        const pollProgress = async () => {
            try {
                const progressResponse = await fetch('/api/v1/depot/upload-ocr-progress', {
                    method: 'GET',
                    credentials: 'include'
                });
                const progressData = await progressResponse.json();
                
                if (progressData.percentage !== undefined) {
                    showOCRProgress(progressData.percentage, progressData.message || 'Processing...');
                    
                    if (progressData.percentage >= 100) {
                        progressComplete = true;
                        if (progressInterval) {
                            clearInterval(progressInterval);
                        }
                    }
                }
            } catch (err) {
                // Ignore progress polling errors
            }
        };
        
        // Poll every 500ms
        progressInterval = setInterval(pollProgress, 500);
        
        try {
            const response = await fetch('/api/v1/depot/upload-ocr', {
                method: 'POST',
                body: formData,
                credentials: 'include'  // Include session cookies
            });
            
            // Stop polling
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'OCR scan failed');
            }
            
            // Show 100% progress
            showOCRProgress(100, 'Complete!');
            
            // Store preview data
            ocrPreviewData = data.structured_data || [];
            
            // If no structured data, try to create from text
            if (ocrPreviewData.length === 0 && data.text) {
                const lines = data.text.split('\n');
                ocrPreviewData = lines.filter(line => line.trim().length > 2).map(line => ({
                    medicine_name: line.trim(),
                    unit_price: null
                }));
            }
            
            // Hide progress bar after a moment
            setTimeout(() => {
                hideOCRProgress();
            }, 1000);
            
            // Display preview table
            displayOCRPreview(ocrPreviewData);
            document.getElementById('ocr-preview-section').style.display = 'block';
            
            showAlert(`✅ Successfully scanned ${data.pages} page(s). Please review and edit the data.`, 'success');
            
        } catch (error) {
            // Stop polling on error
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            hideOCRProgress();
            showAlert(`❌ OCR scan failed: ${error.message || 'Unknown error'}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Display OCR preview table
function displayOCRPreview(data) {
    const tbody = document.getElementById('ocr-preview-tbody');
    tbody.innerHTML = '';
    
    data.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="text" class="form-input" value="${escapeHtml(item.medicine_name || '')}" 
                       onchange="updateOCRRow(${index}, 'medicine_name', this.value)" 
                       style="width: 100%; padding: 8px;">
            </td>
            <td>
                <input type="number" class="form-input" value="${item.unit_price || ''}" 
                       step="0.01" min="0"
                       onchange="updateOCRRow(${index}, 'unit_price', this.value)" 
                       style="width: 100%; padding: 8px;">
            </td>
            <td>
                <button class="btn btn-danger" onclick="removeOCRRow(${index})" style="padding: 6px 12px; font-size: 12px;">
                    🗑️ Remove
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
    
    // Store data
    ocrPreviewData = data;
}

// Update OCR row
function updateOCRRow(index, field, value) {
    if (ocrPreviewData[index]) {
        if (field === 'unit_price') {
            ocrPreviewData[index][field] = value ? parseFloat(value) : null;
        } else {
            ocrPreviewData[index][field] = value;
        }
    }
}

// Remove OCR row
function removeOCRRow(index) {
    ocrPreviewData.splice(index, 1);
    displayOCRPreview(ocrPreviewData);
}

// Add new OCR row
function addOCRRow() {
    ocrPreviewData.push({
        medicine_name: '',
        unit_price: null
    });
    displayOCRPreview(ocrPreviewData);
}

// Clear OCR preview
function clearOCRPreview() {
    ocrPreviewData = [];
    document.getElementById('ocr-preview-section').style.display = 'none';
    document.getElementById('ocr-upload-form').reset();
}

// Confirm OCR upload
async function confirmOCRUpload() {
    // Validate data
    const validRecords = ocrPreviewData.filter(item => {
        const name = item.medicine_name && item.medicine_name.trim();
        const price = item.unit_price !== null && item.unit_price !== undefined;
        return name && price && item.unit_price > 0;
    });
    
    if (validRecords.length === 0) {
        showAlert('Please add at least one valid medicine with name and price', 'error');
        return;
    }
    
    try {
        showAlert('📤 Uploading medicines...', 'info');
        
        const response = await fetch('/api/v1/depot/upload-ocr-confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                records: validRecords
            }),
            credentials: 'include'  // Include session cookies
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Upload failed');
        }
        
        showAlert(`✅ Successfully uploaded ${data.statistics.valid_items} medicines!`, 'success');
        
        // Clear preview
        clearOCRPreview();
        
        // Refresh products if on products page
        if (document.getElementById('products-page') && !document.getElementById('products-page').classList.contains('hidden')) {
            loadProducts();
        }
        
    } catch (error) {
        showAlert(`❌ Upload failed: ${error.message || 'Unknown error'}`, 'error');
    }
}

// Switch download tab
function switchDownloadTab(tab) {
    const fileSection = document.getElementById('download-file-section');
    const ocrSection = document.getElementById('download-ocr-section');
    const manualSection = document.getElementById('download-manual-section');
    const fileTab = document.querySelector('.download-tab-btn[data-tab="file"]');
    const ocrTab = document.querySelector('.download-tab-btn[data-tab="ocr"]');
    const manualTab = document.querySelector('.download-tab-btn[data-tab="manual"]');
    
    // Hide all sections
    fileSection.style.display = 'none';
    ocrSection.style.display = 'none';
    if (manualSection) manualSection.style.display = 'none';
    
    // Reset all tabs
    [fileTab, ocrTab, manualTab].forEach(t => {
        if (t) {
            t.classList.remove('active');
            t.style.borderBottom = 'none';
            t.style.color = 'var(--text-secondary)';
            t.style.fontWeight = 'normal';
        }
    });
    
    // Show selected section and activate tab
    if (tab === 'file') {
        fileSection.style.display = 'block';
        fileTab.classList.add('active');
        fileTab.style.borderBottom = '2px solid var(--primary-color)';
        fileTab.style.color = 'var(--primary-color)';
        fileTab.style.fontWeight = '600';
    } else if (tab === 'ocr') {
        ocrSection.style.display = 'block';
        ocrTab.classList.add('active');
        ocrTab.style.borderBottom = '2px solid var(--primary-color)';
        ocrTab.style.color = 'var(--primary-color)';
        ocrTab.style.fontWeight = '600';
    } else if (tab === 'manual') {
        if (manualSection) manualSection.style.display = 'block';
        if (manualTab) {
            manualTab.classList.add('active');
            manualTab.style.borderBottom = '2px solid var(--primary-color)';
            manualTab.style.color = 'var(--primary-color)';
            manualTab.style.fontWeight = '600';
        }
    }
}

// Setup download prices OCR form
function setupDownloadPricesOCRForm() {
    const ocrForm = document.getElementById('download-prices-ocr-form');
    if (!ocrForm) return;
    
    ocrForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const fileInput = document.getElementById('download-ocr-file');
        const file = fileInput.files[0];
        
        if (!file) {
            showAlert('Please select an image or PDF file', 'error');
            return;
        }
        
        const submitBtn = e.target.querySelector('button[type="submit"]');
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Scanning...';
        
        // Show processing state
        document.getElementById('download-processing').style.display = 'block';
        document.getElementById('download-results-container').style.display = 'none';
        
        // Show progress bar (use the same progress container)
        showOCRProgress(0, 'Starting scan...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        // Start progress polling
        let progressInterval = null;
        
        const pollProgress = async () => {
            try {
                const progressResponse = await fetch('/api/v1/depot/download-prices-ocr-progress', {
                    method: 'GET',
                    credentials: 'include'
                });
                const progressData = await progressResponse.json();
                
                if (progressData.percentage !== undefined) {
                    showOCRProgress(progressData.percentage, progressData.message || 'Processing...');
                    
                    if (progressData.percentage >= 100) {
                        if (progressInterval) {
                            clearInterval(progressInterval);
                        }
                    }
                }
            } catch (err) {
                // Ignore progress polling errors
            }
        };
        
        // Poll every 500ms
        progressInterval = setInterval(pollProgress, 500);
        
        try {
            const response = await fetch('/api/v1/depot/download-prices-ocr', {
                method: 'POST',
                body: formData,
                credentials: 'include'  // Include session cookies
            });
            
            // Stop polling
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            
            const data = await response.json();
            
            if (!response.ok) {
                // Extract detailed error message
                const errorMsg = data.message || data.error || 'OCR scan failed';
                const errorType = data.error_type || '';
                console.error('Download prices OCR failed:', {
                    status: response.status,
                    error: errorMsg,
                    error_type: errorType,
                    full_response: data
                });
                throw new Error(errorMsg);
            }
            
            // Show 100% progress
            showOCRProgress(100, 'Complete!');
            
            // Store matched medicines
            matchedMedicines = data.matched_medicines || [];
            
            // Hide processing, show results
            document.getElementById('download-processing').style.display = 'none';
            
            // Hide progress bar after a moment
            setTimeout(() => {
                hideOCRProgress();
            }, 1000);
            
            if (matchedMedicines.length === 0) {
                showAlert('No medicines matched. Please check the medicine names in your document.', 'error');
                return;
            }
            
            // Display results
            displayDownloadResults(matchedMedicines, {
                total_requested: data.total_requested,
                matched: data.total_matched,
                not_found: data.total_not_found
            }, data.not_found);
            document.getElementById('download-results-container').style.display = 'block';
            
            showAlert(`✅ Found ${data.total_matched} matched medicines out of ${data.total_requested} requested`, 'success');
            
        } catch (error) {
            // Stop polling on error
            if (progressInterval) {
                clearInterval(progressInterval);
            }
            hideOCRProgress();
            document.getElementById('download-processing').style.display = 'none';
            
            // Show detailed error message
            const errorMsg = error.message || 'Unknown error';
            console.error('Download prices OCR error:', error);
            showAlert(`❌ OCR scan failed: ${errorMsg}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    });
}

// Show OCR progress bar (works for both upload and download sections)
function showOCRProgress(percentage, message) {
    let progressContainer = document.getElementById('ocr-progress-container');
    if (!progressContainer) {
        // Try to find the active OCR section (upload or download)
        let ocrSection = document.getElementById('ocr-upload-section');
        if (!ocrSection || ocrSection.style.display === 'none') {
            ocrSection = document.getElementById('download-ocr-section');
        }
        if (!ocrSection) return; // No OCR section found
        
        progressContainer = document.createElement('div');
        progressContainer.id = 'ocr-progress-container';
        progressContainer.style.cssText = 'margin-top: 20px; padding: 20px; background: #f0f9ff; border-radius: 8px; border-left: 4px solid #3b82f6;';
        progressContainer.innerHTML = `
            <div style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 5px;">
                    <span style="font-weight: 600; color: #1e40af;" id="ocr-progress-message">${message}</span>
                    <span style="font-weight: 600; color: #3b82f6;" id="ocr-progress-percentage">${percentage}%</span>
                </div>
                <div style="width: 100%; height: 24px; background: #e0e7ff; border-radius: 12px; overflow: hidden;">
                    <div id="ocr-progress-bar" style="height: 100%; background: linear-gradient(90deg, #3b82f6, #2563eb); width: ${percentage}%; transition: width 0.3s ease; border-radius: 12px;"></div>
                </div>
            </div>
        `;
        ocrSection.appendChild(progressContainer);
    } else {
        // Update existing progress
        progressContainer.style.display = 'block';
        document.getElementById('ocr-progress-message').textContent = message;
        document.getElementById('ocr-progress-percentage').textContent = percentage + '%';
        document.getElementById('ocr-progress-bar').style.width = percentage + '%';
    }
}

// Hide OCR progress bar
function hideOCRProgress() {
    const progressContainer = document.getElementById('ocr-progress-container');
    if (progressContainer) {
        progressContainer.style.display = 'none';
    }
}

// Manual Entry Upload Functions
function addManualRow() {
    manualUploadData.push({
        medicine_name: '',
        unit_price: null,
        expiry_date: ''
    });
    renderManualUploadTable();
}

function removeManualRow(index) {
    manualUploadData.splice(index, 1);
    renderManualUploadTable();
}

function updateManualRow(index, field, value) {
    if (manualUploadData[index]) {
        if (field === 'unit_price') {
            manualUploadData[index][field] = value ? parseFloat(value) : null;
        } else {
            manualUploadData[index][field] = value;
        }
    }
}

function renderManualUploadTable() {
    const tbody = document.getElementById('manual-upload-tbody');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    manualUploadData.forEach((item, index) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>
                <input type="text" class="form-input" value="${escapeHtml(item.medicine_name || '')}" 
                       onchange="updateManualRow(${index}, 'medicine_name', this.value)" 
                       style="width: 100%; padding: 8px;" placeholder="Enter medicine name" required>
            </td>
            <td>
                <input type="number" class="form-input" value="${item.unit_price || ''}" 
                       step="0.01" min="0"
                       onchange="updateManualRow(${index}, 'unit_price', this.value)" 
                       style="width: 100%; padding: 8px;" placeholder="0.00" required>
            </td>
            <td>
                <input type="date" class="form-input" value="${item.expiry_date || ''}" 
                       onchange="updateManualRow(${index}, 'expiry_date', this.value)" 
                       style="width: 100%; padding: 8px;" required>
            </td>
            <td>
                <button class="btn btn-danger" onclick="removeManualRow(${index})" style="padding: 6px 12px; font-size: 12px;">
                    🗑️ Remove
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

async function submitManualUpload() {
    // Validate data (require name, price, and expiry_date)
    const validRecords = manualUploadData.filter(item => {
        const name = item.medicine_name && item.medicine_name.trim();
        const price = item.unit_price !== null && item.unit_price !== undefined;
        const expiry = item.expiry_date && item.expiry_date.trim();
        return name && price && item.unit_price > 0 && expiry;
    });
    
    if (validRecords.length === 0) {
        showAlert('Please add at least one valid medicine with name, price, and expiry date', 'error');
        return;
    }
    
    try {
        showAlert('📤 Uploading medicines...', 'info');
        
        const token = getToken();
        const response = await fetch('/api/v1/depot/upload-manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                records: validRecords
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            const errorMsg = data.message || data.error || 'Upload failed';
            console.error('Upload error:', data);
            throw new Error(errorMsg);
        }
        
        showAlert(`✅ Successfully uploaded ${data.statistics.valid_items} medicines!`, 'success');
        
        // Clear table
        manualUploadData = [];
        renderManualUploadTable();
        
        // Refresh products if on products page
        if (document.getElementById('products-page') && !document.getElementById('products-page').classList.contains('hidden')) {
            loadProducts();
        }
        
    } catch (error) {
        console.error('Manual upload error:', error);
        const errorMsg = error.message || 'Unknown error';
        showAlert(`❌ Upload failed: ${errorMsg}`, 'error');
    }
}

// Manual Entry Download Prices Functions
async function getManualPrices() {
    const textarea = document.getElementById('manual-medicine-names');
    if (!textarea) return;
    
    const input = textarea.value.trim();
    if (!input) {
        showAlert('Please enter at least one medicine name', 'error');
        return;
    }
    
    // Parse medicine names (split by newline or comma)
    const medicineNames = input
        .split(/[\n,]+/)
        .map(name => name.trim())
        .filter(name => name.length > 0);
    
    if (medicineNames.length === 0) {
        showAlert('Please enter at least one valid medicine name', 'error');
        return;
    }
    
    // Show processing state
    document.getElementById('download-processing').style.display = 'block';
    document.getElementById('download-results-container').style.display = 'none';
    
    try {
        const token = getToken();
        const response = await fetch('/api/v1/depot/download-prices-manual', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                medicine_names: medicineNames
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to get prices');
        }
        
        // Store matched medicines
        matchedMedicines = data.matched_medicines || [];
        
        // Hide processing, show results
        document.getElementById('download-processing').style.display = 'none';
        
        // Clear the text area after processing (whether successful or not)
        if (textarea) {
            textarea.value = '';
        }
        
        if (matchedMedicines.length === 0) {
            showAlert('No medicines matched. Please check the medicine names.', 'error');
            return;
        }
        
        // Display results
        displayDownloadResults(matchedMedicines, {
            total_requested: data.total_requested,
            matched: data.total_matched,
            not_found: data.total_not_found
        }, data.not_found);
        document.getElementById('download-results-container').style.display = 'block';
        
        showAlert(`✅ Found ${data.total_matched} matched medicines out of ${data.total_requested} requested`, 'success');
        
    } catch (error) {
        document.getElementById('download-processing').style.display = 'none';
        // Clear text area even on error
        if (textarea) {
            textarea.value = '';
        }
        showAlert(`Failed to get prices: ${error.message || 'Unknown error'}`, 'error');
    }
}

// Download Prices as PDF
async function downloadPricesPDF() {
    if (matchedMedicines.length === 0) {
        showAlert('No data to download', 'error');
        return;
    }
    
    try {
        const token = getToken();
        const response = await fetch('/api/v1/depot/download-prices-pdf', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                medicines: matchedMedicines,
                depot_name: (JSON.parse(localStorage.getItem('tenant') || '{}')).business_name || ''
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to generate PDF file');
        }
        
        // Get the PDF file as blob
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        // Use filename from server response
        const disposition = response.headers.get('Content-Disposition');
        let filename = `medicine_prices_${new Date().toISOString().split('T')[0]}.pdf`;
        if (disposition) {
            const match = disposition.match(/filename[^;=\n]*=(['"]?)([^'"\n;]*)/); 
            if (match && match[2]) filename = match[2];
        }
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
        
        showAlert('PDF file downloaded successfully', 'success');
    } catch (error) {
        showAlert(`Failed to download PDF: ${error.message}`, 'error');
    }
}

// Initialize OCR forms when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        setupOCRUploadForm();
        setupDownloadPricesOCRForm();
    });
} else {
    setupOCRUploadForm();
    setupDownloadPricesOCRForm();
}
