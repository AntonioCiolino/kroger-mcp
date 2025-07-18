// Utility functions
const showLoading = (id) => {
    const el = document.getElementById(id);
    el.style.display = 'block';
    el.innerHTML = '<p>Loading...</p>';
};

const showResults = (id, data, isError = false) => {
    const el = document.getElementById(id);
    el.style.display = 'block';
    el.className = isError ? 'results error' : 'results success';
    el.innerHTML = typeof data === 'object' ? '<pre>' + JSON.stringify(data, null, 2) + '</pre>' : '<p>' + data + '</p>';
};

const showToast = (message, type = 'info') => {
    const existingToast = document.querySelector('.toast');
    if (existingToast) existingToast.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
        background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#0066cc'};
        color: white; padding: 12px 24px; border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2); z-index: 10000;
        font-weight: 500; opacity: 0; transition: opacity 0.3s;
    `;

    document.body.appendChild(toast);
    setTimeout(() => toast.style.opacity = '1', 10);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
};

// Page loading spinner
const showPageLoader = () => {
    const loader = document.getElementById('pageLoader');
    loader.style.display = 'flex';
};

const hidePageLoader = () => {
    const loader = document.getElementById('pageLoader');
    if (loader) {
        loader.style.opacity = '0';
        setTimeout(() => {
            loader.style.display = 'none';
        }, 300);
    }
};

// Make hidePageLoader globally available
window.hidePageLoader = hidePageLoader;

// Show different sections
const showSection = (sectionId) => {
    // Hide all sections
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });
    
    // Show the selected section
    document.getElementById(sectionId + 'Section').style.display = 'block';
    
    // Update active button
    document.querySelectorAll('.toolbar-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Find the button for this section and make it active
    const activeButton = Array.from(document.querySelectorAll('.toolbar-btn')).find(
        btn => btn.getAttribute('onclick').includes(sectionId)
    );
    
    if (activeButton) {
        activeButton.classList.add('active');
    }
};

// Auth modal functions
const toggleAuth = () => {
    const modal = document.getElementById('authModal');
    modal.classList.add('show');
    checkAuthStatus(true); // Force refresh status when opening auth modal
};

const closeAuthModal = () => {
    const modal = document.getElementById('authModal');
    modal.classList.remove('show');
};

// Make auth functions globally available
window.toggleAuth = toggleAuth;
window.closeAuthModal = closeAuthModal;

// Authentication functions
const authenticateWithKroger = async () => {
    const authButton = document.getElementById('authButton');
    const authResults = document.getElementById('authResults');
    
    try {
        authButton.disabled = true;
        authButton.textContent = '⏳ Starting authentication...';
        authResults.style.display = 'none';
        
        const response = await fetch('/api/auth/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success && result.data.authorization_url) {
            // Open auth URL in new tab
            window.open(result.data.authorization_url, '_blank');
            
            authResults.innerHTML = `
                <div class="results success">
                    <p><strong>✅ Authentication started!</strong></p>
                    <p>A new tab has opened for Kroger authentication.</p>
                    <p>After completing authentication, click "Refresh Status" to update your connection status.</p>
                </div>
            `;
            authResults.style.display = 'block';
            
            showToast('✅ Authentication window opened', 'success');
        } else {
            throw new Error(result.error || 'Failed to start authentication');
        }
    } catch (error) {
        authResults.innerHTML = `
            <div class="results error">
                <p><strong>❌ Authentication failed</strong></p>
                <p>${error.message}</p>
            </div>
        `;
        authResults.style.display = 'block';
        showToast('❌ Authentication failed', 'error');
    } finally {
        authButton.disabled = false;
        authButton.textContent = '🔗 Authenticate with Kroger';
    }
};

// Cache auth status to reduce API calls
let authStatusCache = null;
let authStatusCacheTime = 0;
const AUTH_CACHE_DURATION = 30000; // 30 seconds

// Helper function to update auth UI elements
const updateAuthStatusUI = (result, statusIndicator, statusText, headerLoginStatus, loginText, loginIcon) => {
    if (result.success && result.data.authenticated) {
        // Update modal status
        statusIndicator.className = 'status-indicator status-connected';
        statusText.textContent = `✅ Connected (${result.data.scopes?.join(', ') || 'authenticated'})`;
        
        // Update header status
        if (headerLoginStatus && loginText && loginIcon) {
            headerLoginStatus.className = 'login-status authenticated';
            loginIcon.textContent = '👋';
            // Try to show user name if available, otherwise show "Logged In"
            const userName = result.data.user_name || result.data.name || 'Logged In';
            loginText.textContent = userName;
        }
    } else {
        // Update modal status
        statusIndicator.className = 'status-indicator status-disconnected';
        statusText.textContent = '❌ Not authenticated';
        
        // Update header status
        if (headerLoginStatus && loginText && loginIcon) {
            headerLoginStatus.className = 'login-status';
            loginIcon.textContent = '👤';
            loginText.textContent = 'Login';
        }
    }
};

const checkAuthStatus = async (forceRefresh = false) => {
    const authStatus = document.getElementById('authStatus');
    const statusIndicator = authStatus.querySelector('.status-indicator');
    const statusText = authStatus.querySelector('span:last-child');
    
    // Also update header login status
    const headerLoginStatus = document.getElementById('headerLoginStatus');
    const loginText = headerLoginStatus?.querySelector('.login-text');
    const loginIcon = headerLoginStatus?.querySelector('.login-icon');
    
    // Use cached result if available and not expired (unless forced refresh)
    const now = Date.now();
    if (!forceRefresh && authStatusCache && (now - authStatusCacheTime) < AUTH_CACHE_DURATION) {
        updateAuthStatusUI(authStatusCache, statusIndicator, statusText, headerLoginStatus, loginText, loginIcon);
        return authStatusCache;
    }
    
    try {
        const response = await fetch('/api/auth/status');
        const result = await response.json();
        
        // Cache the result
        authStatusCache = result;
        authStatusCacheTime = now;
        
        // Update UI using the helper function
        updateAuthStatusUI(result, statusIndicator, statusText, headerLoginStatus, loginText, loginIcon);
        
        if (result.success && result.data.authenticated) {
            showToast('✅ Authentication verified', 'success');
            
            // Auto-dismiss the auth modal if it's open and authentication is successful
            const authModal = document.getElementById('authModal');
            if (authModal && authModal.classList.contains('show')) {
                setTimeout(() => {
                    closeAuthModal();
                }, 1500); // Wait 1.5 seconds to let user see the success message
            }
        }
        
        return result;
    } catch (error) {
        // Update modal status
        statusIndicator.className = 'status-indicator status-warning';
        statusText.textContent = '⚠️ Status check failed';
        
        // Update header status
        if (headerLoginStatus && loginText && loginIcon) {
            headerLoginStatus.className = 'login-status error';
            loginIcon.textContent = '⚠️';
            loginText.textContent = 'Error';
        }
        
        console.error('Auth status check failed:', error);
    }
};

const logoutFromKroger = async () => {
    if (!confirm('Are you sure you want to logout from Kroger?')) {
        return;
    }
    
    const logoutButton = document.getElementById('logoutButton');
    
    try {
        logoutButton.disabled = true;
        logoutButton.textContent = '⏳ Logging out...';
        
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('✅ Logged out successfully', 'success');
            await checkAuthStatus(true); // Force refresh status after logout
        } else {
            throw new Error(result.error || 'Logout failed');
        }
    } catch (error) {
        showToast('❌ Logout failed', 'error');
        console.error('Logout error:', error);
    } finally {
        logoutButton.disabled = false;
        logoutButton.textContent = '🚪 Logout';
    }
};

// Make auth functions globally available
window.authenticateWithKroger = authenticateWithKroger;
window.checkAuthStatus = checkAuthStatus;
window.logoutFromKroger = logoutFromKroger;