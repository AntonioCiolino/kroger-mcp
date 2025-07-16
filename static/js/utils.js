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
    loader.style.opacity = '0';
    setTimeout(() => {
        loader.style.display = 'none';
    }, 300);
};

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