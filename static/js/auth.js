// Authentication functions
const updateAuthStatus = (isAuthenticated) => {
    const statusEl = document.getElementById('authStatus');
    const indicator = statusEl.querySelector('.status-indicator');
    const text = statusEl.querySelector('span:last-child');
    const button = document.getElementById('authButton');

    if (isAuthenticated) {
        indicator.className = 'status-indicator status-connected';
        text.textContent = 'Authenticated ✓';
        button.textContent = '✓ Already Authenticated';
        button.disabled = true;
        button.className = 'btn-secondary';
    } else {
        indicator.className = 'status-indicator status-disconnected';
        text.textContent = 'Not authenticated';
        button.textContent = '🔗 Authenticate with Kroger';
        button.disabled = false;
        button.className = 'btn-success';
    }
};

const checkAuthStatus = async () => {
    try {
        const response = await fetch('/api/auth/status');
        const result = await response.json();
        updateAuthStatus(result.data.authenticated || result.data.token_valid);
        showResults('authResults', result.success ? result.data : result, !result.success);
    } catch (error) {
        updateAuthStatus(false);
        showResults('authResults', 'Error: ' + error.message, true);
    }
};

const authenticateWithKroger = async () => {
    const button = document.getElementById('authButton');
    const originalText = button.textContent;

    try {
        button.textContent = 'Starting authentication...';
        button.disabled = true;

        // Show debug info
        showResults('authResults', {
            message: 'Starting authentication process...',
            status: 'Contacting Kroger API...'
        });

        const response = await fetch('/api/auth/start', { method: 'POST' });
        const result = await response.json();
        
        // Log the result for debugging
        console.log('Auth start response:', result);

        if (result.success && result.data.authorization_url) {
            button.textContent = 'Opening Kroger login...';
            
            // Show the authorization URL for debugging
            showResults('authResults', {
                message: 'Authentication window opening! Please log in to your Kroger account.',
                status: 'Waiting for authentication to complete...',
                auth_url: result.data.authorization_url
            });
            
            // Open the authorization URL in a new window
            const authWindow = window.open(result.data.authorization_url, '_blank', 'width=600,height=700');
            
            if (!authWindow) {
                throw new Error('Popup blocked! Please allow popups for this site and try again.');
            }

            button.textContent = 'Waiting for login...';
            pollForAuthCompletion();
        } else {
            throw new Error(result.error || 'Failed to start authentication');
        }
    } catch (error) {
        button.textContent = originalText;
        button.disabled = false;
        showResults('authResults', 'Error: ' + error.message, true);
    }
};

const pollForAuthCompletion = async () => {
    let attempts = 0;
    const maxAttempts = 60;

    const checkAuth = async () => {
        attempts++;
        try {
            const response = await fetch('/api/auth/check');
            const result = await response.json();

            if (result.authenticated) {
                updateAuthStatus(true);
                showResults('authResults', {
                    message: '🎉 Authentication successful!',
                    status: 'You can now use cart operations and other authenticated features.'
                });
                return;
            }

            if (attempts < maxAttempts) {
                setTimeout(checkAuth, 2000);
            } else {
                const button = document.getElementById('authButton');
                button.textContent = '🔗 Authenticate with Kroger';
                button.disabled = false;
                button.className = 'btn-success';
                showResults('authResults', 'Authentication timed out. Please try again.', true);
            }
        } catch (error) {
            if (attempts < maxAttempts) setTimeout(checkAuth, 2000);
        }
    };

    setTimeout(checkAuth, 2000);
};

const logoutFromKroger = async () => {
    const button = document.getElementById('logoutButton');
    const originalText = button.textContent;

    try {
        button.textContent = 'Logging out...';
        button.disabled = true;

        const response = await fetch('/api/auth/logout', { method: 'POST' });
        const result = await response.json();

        if (result.success) {
            updateAuthStatus(false);
            showResults('authResults', {
                message: '🚪 Logout successful!',
                status: 'You have been logged out. You can now re-authenticate with fresh permissions.'
            });
        } else {
            throw new Error(result.error || 'Failed to logout');
        }
    } catch (error) {
        showResults('authResults', 'Error: ' + error.message, true);
    } finally {
        button.textContent = originalText;
        button.disabled = false;
    }
};

const toggleAuth = () => {
    showSection('auth');
    checkAuthStatus();
};