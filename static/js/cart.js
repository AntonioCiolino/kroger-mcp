// Global modality preference functions
const getGlobalModality = () => {
    // Check localStorage for user's preferred modality, default to DELIVERY
    return localStorage.getItem('globalModality') || 'DELIVERY';
};

const setGlobalModality = (modality) => {
    localStorage.setItem('globalModality', modality);
    showToast(`✅ Default modality set to ${modality === 'PICKUP' ? 'Pickup' : 'Delivery'}`, 'success');
};

// Cart functions
const updateCartView = async () => {
    try {
        // Always fetch ALL cart items for the header count
        const response = await fetch('/api/cart/view');
        const result = await response.json();
        if (result.success) {
            const cartItems = result.data.cart_items;
            const totalQuantity = cartItems.reduce((sum, item) => sum + (item.quantity || 1), 0);
            document.getElementById('cartItemCount').textContent = totalQuantity;
        }
    } catch (error) {
        console.error('Error updating cart view:', error);
    }
};

const quickAddToCart = async (productId) => {
    try {
        // Check authentication status first
        const authStatus = await checkAuthStatusForCart();
        if (!authStatus) {
            showToast('⚠️ Please authenticate first to add items to cart', 'error');
            toggleAuth(); // Show auth section
            return;
        }

        const response = await fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                quantity: 1,
                modality: getGlobalModality() // Use global modality preference
            })
        });
        const result = await response.json();

        if (result.success) {
            showToast('✅ Added to cart', 'success');
            await updateCartView();

            // If cart panel is open, refresh it
            const cartPanel = document.getElementById('cartPanel');
            if (cartPanel.classList.contains('show')) {
                await viewCart();
            }
        } else {
            showToast('❌ ' + (result.error || 'Failed to add to cart'), 'error');
        }
    } catch (error) {
        showToast('❌ Error adding to cart', 'error');
    }
};

const addToCart = async () => {
    const productId = document.getElementById('productId').value;
    const quantity = parseInt(document.getElementById('quantity').value);

    if (!productId) {
        showToast('Please enter a product ID', 'error');
        return;
    }

    try {
        const response = await fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                quantity: quantity,
                modality: 'PICKUP' // Default to PICKUP for manual add
            })
        });
        const result = await response.json();

        if (result.success) {
            showToast('✅ Added to cart', 'success');
            document.getElementById('productId').value = '';
            document.getElementById('quantity').value = '1';
            await updateCartView();

            // If cart panel is open, refresh it
            const cartPanel = document.getElementById('cartPanel');
            if (cartPanel.classList.contains('show')) {
                await viewCart();
            }
        } else {
            showToast('❌ ' + (result.error || 'Failed to add to cart'), 'error');
        }
    } catch (error) {
        showToast('❌ Error adding to cart', 'error');
    }
};

// Make toggleCart available globally for onclick handlers
window.toggleCart = () => {
    const cartPanel = document.getElementById('cartPanel');
    if (cartPanel.style.display === 'none' || !cartPanel.classList.contains('show')) {
        cartPanel.style.display = 'block';
        setTimeout(() => cartPanel.classList.add('show'), 10);

        const cartResults = document.getElementById('cartResults');
        cartResults.innerHTML = `
            <div style="display: flex; flex-direction: column; align-items: center; padding: 40px 20px;">
                <div class="spinner" style="width: 40px; height: 40px; margin-bottom: 15px;"></div>
                <p style="color: #666;">Loading your cart...</p>
            </div>
        `;

        viewCart();
    } else {
        cartPanel.classList.remove('show');
        setTimeout(() => cartPanel.style.display = 'none', 300);
    }
};

const toggleCart = window.toggleCart;

const viewCart = async () => {
    showLoading('cartResults');
    try {
        // Always fetch ALL cart items, then filter on the frontend
        const response = await fetch('/api/cart/view');
        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load cart');
        }

        renderCart(result.data);
    } catch (error) {
        document.getElementById('cartResults').innerHTML = `
            <div class="results error">
                <p>Error loading cart: ${error.message}</p>
            </div>
        `;
    }
};

const filterCartByModality = (filterValue) => {
    // Save the filter preference
    localStorage.setItem('cartModalityFilter', filterValue);
    
    // Debug: Log the filter change
    console.log('Filter changed to:', filterValue);
    
    // Re-render the cart with the new filter
    viewCart();
};

// Helper function to reset cart filter (for debugging)
const resetCartFilter = () => {
    localStorage.removeItem('cartModalityFilter');
    console.log('Cart filter reset to show all items');
    viewCart();
};



const renderCart = (data) => {
    const allCartItems = data.cart_items || [];
    const cartResults = document.getElementById('cartResults');
    
    // Get current filter setting (default to show all items)
    // Force reset to ALL if there's a mismatch
    let currentFilter = localStorage.getItem('cartModalityFilter') || 'ALL';
    
    // Auto-reset filter if no items match the current filter
    if (currentFilter !== 'ALL') {
        const hasMatchingItems = allCartItems.some(item => {
            if (currentFilter === 'PICKUP') {
                return (item.modality || 'PICKUP') === 'PICKUP';
            } else if (currentFilter === 'DELIVERY') {
                return (item.modality || 'PICKUP') === 'DELIVERY';
            }
            return true;
        });
        
        if (!hasMatchingItems && allCartItems.length > 0) {
            console.log(`No items match filter "${currentFilter}", resetting to ALL`);
            currentFilter = 'ALL';
            localStorage.setItem('cartModalityFilter', 'ALL');
        }
    }
    
    // Debug: Log cart items and their modalities
    console.log('All cart items:', allCartItems);
    console.log('Current filter:', currentFilter);
    allCartItems.forEach((item, index) => {
        console.log(`Item ${index}:`, item.description, 'Modality:', item.modality || 'PICKUP');
    });
    
    // Filter cart items based on the selected filter
    let cartItems = allCartItems;
    if (currentFilter === 'PICKUP') {
        cartItems = allCartItems.filter(item => (item.modality || 'PICKUP') === 'PICKUP');
    } else if (currentFilter === 'DELIVERY') {
        cartItems = allCartItems.filter(item => (item.modality || 'PICKUP') === 'DELIVERY');
    }
    
    console.log('Filtered cart items:', cartItems);

    // Add cart actions and modality filter at the top
    const cartActionsHtml = `
        <div class="cart-header">
            <div class="cart-modality-selector">
                <label for="cartModalityFilter" style="font-weight: bold; margin-right: 10px;">Show Items:</label>
                <select id="cartModalityFilter" class="modality-select" style="padding: 8px; border-radius: 4px; border: 1px solid #ddd;" onchange="filterCartByModality(this.value)">
                    <option value="ALL" ${currentFilter === 'ALL' ? 'selected' : ''}>🛒 All Items (${allCartItems.length})</option>
                    <option value="PICKUP" ${currentFilter === 'PICKUP' ? 'selected' : ''}>🚗 Pickup Only (${allCartItems.filter(item => (item.modality || 'PICKUP') === 'PICKUP').length})</option>
                    <option value="DELIVERY" ${currentFilter === 'DELIVERY' ? 'selected' : ''}>🚚 Delivery Only (${allCartItems.filter(item => (item.modality || 'PICKUP') === 'DELIVERY').length})</option>
                </select>
            </div>
            <div class="cart-actions" style="flex-wrap: wrap; gap: 10px; margin-top: 15px;">
                <button data-action="fetch-cart" class="btn-primary">
                    🔄 Fetch My Kroger Cart
                </button>
                <button data-action="add-samples" class="btn-secondary">
                    ➕ Add Sample Items
                </button>
                <button data-action="manual-entry" class="btn-secondary">
                    📝 Manual Entry
                </button>
                <button data-action="clear-cart" class="btn-danger">
                    🗑️ Clear Cart
                </button>
            </div>
        </div>
    `;

    if (cartItems.length === 0) {
        const emptyMessage = currentFilter === 'ALL' ? 
            'Your cart is empty' : 
            `No ${currentFilter.toLowerCase()} items in your cart`;
        const emptySubMessage = currentFilter === 'ALL' ? 
            'Search for products to add to your cart' : 
            `Switch to "All Items" to see items from other fulfillment methods`;
            
        cartResults.innerHTML = `
            ${cartActionsHtml}
            <div class="empty-cart">
                <h3>${emptyMessage}</h3>
                <p>${emptySubMessage}</p>
            </div>
        `;
        return;
    }

    if (allCartItems.length === 0) {
        cartResults.innerHTML = `
            ${cartActionsHtml}
            <div class="empty-cart">
                <h3>Your cart is empty</h3>
                <p>Search for products to add to your cart</p>
            </div>
        `;
        return;
    }

    // Calculate totals
    let subtotal = 0;
    let savings = 0;

    cartItems.forEach(item => {
        const pricing = item.pricing || {};
        const regularPrice = pricing.regular_price || 0;
        const salePrice = pricing.sale_price || regularPrice;
        const quantity = item.quantity || 1;

        subtotal += salePrice * quantity;

        if (pricing.on_sale) {
            savings += (regularPrice - salePrice) * quantity;
        }
    });

    // Price summary
    let html = `
        ${cartActionsHtml}
        <div class="price-summary">
            <div class="price-summary-header">
                <h3>Order Summary</h3>
            </div>
            <div class="price-content">
                <div class="price-row">
                    <span>Subtotal (${cartItems.length} items)</span>
                    <span class="price-value">$${subtotal.toFixed(2)}</span>
                </div>
    `;

    if (savings > 0) {
        html += `
            <div class="price-row savings">
                <span>Savings</span>
                <span class="price-value">-$${savings.toFixed(2)}</span>
            </div>
        `;
    }

    html += `
                <div class="price-row total">
                    <span>Estimated Total</span>
                    <span class="price-value total">$${(subtotal - savings).toFixed(2)}</span>
                </div>
            </div>
            <div class="checkout-note">
                Complete your order on Kroger.com or the Kroger app
            </div>
        </div>
    `;

    // Cart item list
    html += '<div class="cart-items">';

    cartItems.forEach(item => {
        const imageUrl = item.images && item.images.length > 0
            ? item.images[0].url
            : null;

        const pricing = item.pricing || {};
        const regularPrice = pricing.regular_price || 0;
        const salePrice = pricing.sale_price;
        const displayPrice = salePrice || regularPrice;
        const onSale = pricing.on_sale;

        html += `
            <div class="cart-item">
                <div class="cart-item-image">
                    ${imageUrl ? `<img src="${imageUrl}" alt="${item.description || 'Product'}">` : '<div class="no-image">No Image</div>'}
                </div>
                <div class="cart-item-details">
                    <div class="cart-item-header">
                        <h4>${item.description || 'Unknown Product'}</h4>
                        <div class="fulfillment-icon clickable" 
                             title="Click to switch between Pickup and Delivery" 
                             onclick="toggleItemModality('${item.product_id}', '${item.modality || 'PICKUP'}')">
                            ${(item.modality || 'PICKUP') === 'PICKUP' ? '🚗' : '🚚'}
                        </div>
                    </div>
                    <div style="font-size: 12px; color: #666;">${item.size || ''}</div>
                    <div style="margin-top: 4px; font-weight: bold; color: ${onSale ? '#e74c3c' : '#0066cc'}">
                        $${displayPrice ? displayPrice.toFixed(2) : '0.00'}
                        ${onSale ? `<span style="text-decoration: line-through; color: #666; margin-left: 5px;">$${regularPrice.toFixed(2)}</span>` : ''}
                    </div>
                    <div class="cart-item-controls">
                        <button class="qty-btn" data-action="decrease-qty" data-product-id="${item.product_id}" data-quantity="${Math.max(1, (item.quantity || 1) - 1)}">-</button>
                        <div class="qty-display">${item.quantity || 1}</div>
                        <button class="qty-btn" data-action="increase-qty" data-product-id="${item.product_id}" data-quantity="${(item.quantity || 1) + 1}">+</button>
                        <button class="remove-btn" data-action="remove-item" data-product-id="${item.product_id}">Remove</button>
                    </div>
                </div>
            </div>
        `;
    });

    html += '</div>';

    cartResults.innerHTML = html;
};

const updateCartItemQuantity = async (productId, newQuantity) => {
    try {
        // Optimistically update the UI first
        updateQuantityDisplay(productId, newQuantity);
        
        const response = await fetch('/api/cart/update-quantity', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                quantity: newQuantity
            })
        });

        const result = await response.json();

        if (result.success) {
            // Only update the cart count in header, not the whole cart
            await updateCartView();
            // Recalculate and update totals
            await updateCartTotals();
        } else {
            // Revert the optimistic update on error
            await viewCart();
            showToast('❌ ' + (result.error || 'Failed to update quantity'), 'error');
        }
    } catch (error) {
        // Revert the optimistic update on error
        await viewCart();
        showToast('❌ Error updating quantity', 'error');
    }
};

const updateCartItemModality = async (productId, newModality) => {
    try {
        const response = await fetch('/api/cart/update-modality', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                modality: newModality
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast(`✅ Updated to ${newModality === 'PICKUP' ? 'Pickup' : 'Delivery'}`, 'success');
            await viewCart();
            await updateCartView();
        } else {
            showToast('❌ ' + (result.error || 'Failed to update modality'), 'error');
        }
    } catch (error) {
        showToast('❌ Error updating modality', 'error');
    }
};

const toggleItemModality = async (productId, currentModality) => {
    // Toggle between PICKUP and DELIVERY
    const newModality = currentModality === 'PICKUP' ? 'DELIVERY' : 'PICKUP';
    
    // Optimistically update the icon immediately for better UX
    const iconElement = document.querySelector(`[onclick*="${productId}"]`);
    if (iconElement) {
        iconElement.innerHTML = newModality === 'PICKUP' ? '🚗' : '🚚';
        iconElement.title = `Click to switch to ${newModality === 'PICKUP' ? 'Delivery' : 'Pickup'}`;
        iconElement.setAttribute('onclick', `toggleItemModality('${productId}', '${newModality}')`);
    }
    
    // Update the backend
    await updateCartItemModality(productId, newModality);
};

const removeFromCart = async (productId) => {
    try {
        const response = await fetch('/api/cart/remove', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId
            })
        });

        const result = await response.json();

        if (result.success) {
            showToast('✅ Item removed', 'success');
            await viewCart();
            await updateCartView();
        } else {
            showToast('❌ ' + (result.error || 'Failed to remove item'), 'error');
        }
    } catch (error) {
        showToast('❌ Error removing item', 'error');
    }
};

const clearCart = async () => {
    if (!confirm('Are you sure you want to clear your cart?')) {
        return;
    }

    try {
        const response = await fetch('/api/cart/clear', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        const result = await response.json();

        if (result.success) {
            showToast('✅ Cart cleared', 'success');
            await viewCart();
            await updateCartView();
        } else {
            showToast('❌ ' + (result.error || 'Failed to clear cart'), 'error');
        }
    } catch (error) {
        showToast('❌ Error clearing cart', 'error');
    }
};

// Helper functions
const checkAuthStatusForCart = async () => {
    try {
        const response = await fetch('/api/auth/status');
        const result = await response.json();
        return result.data && (result.data.authenticated || result.data.token_valid);
    } catch (error) {
        console.error('Error checking auth status:', error);
        return false;
    }
};

// Function to fetch actual Kroger cart
const fetchActualKrogerCart = async () => {
    try {
        showToast('Fetching your Kroger cart...', 'info');

        const response = await fetch('/api/cart/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ use_sample: false })
        });

        const result = await response.json();

        if (result.success) {
            showToast('✅ ' + (result.message || 'Cart fetched successfully'), 'success');
            await updateCartView();
            await viewCart();
        } else {
            showToast('❌ ' + (result.error || 'Failed to fetch cart'), 'error');
            console.error('Error details:', result);
        }
    } catch (error) {
        console.error('Error fetching cart:', error);
        showToast('❌ Error fetching your Kroger cart', 'error');
    }
};

// Function to add sample items to cart (for demo purposes)
const addSampleItems = async () => {
    try {
        showToast('Adding sample items to cart...', 'info');

        const response = await fetch('/api/cart/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ use_sample: true })
        });

        const result = await response.json();

        if (result.success) {
            showToast('✅ ' + (result.message || 'Sample items added'), 'success');
            await updateCartView();
            await viewCart();
        } else {
            showToast('❌ ' + (result.error || 'Failed to add sample items'), 'error');
        }
    } catch (error) {
        console.error('Error adding sample items:', error);
        showToast('❌ Error adding sample items', 'error');
    }
};

// Show manual cart entry modal
const showManualCartEntry = () => {
    // Create modal if it doesn't exist
    let modal = document.getElementById('manualCartEntryModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'manualCartEntryModal';
        modal.className = 'popup-overlay';
        modal.style.display = 'none';

        modal.innerHTML = `
            <div class="popup-content">
                <div class="popup-header">
                    <h3>📝 Manual Cart Entry</h3>
                    <button onclick="closeManualCartEntry()" class="popup-close">✕</button>
                </div>
                <div class="popup-body">
                    <p>Enter your cart items below. Each line should be in the format:</p>
                    <p><code>product_id,quantity</code></p>
                    <p>Example: <code>0001111042248,2</code></p>
                    
                    <div class="form-group">
                        <textarea id="manualCartItems" rows="10" style="width: 100%; padding: 10px; font-family: monospace;" 
                            placeholder="0001111042248,2
0001111091188,1
0001111050624,1"></textarea>
                    </div>
                    
                    <div class="form-actions">
                        <button onclick="submitManualCartItems()" class="btn-primary">Import Items</button>
                        <button onclick="closeManualCartEntry()" class="btn-secondary">Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    }

    modal.style.display = 'flex';
};

// Close manual cart entry modal
const closeManualCartEntry = () => {
    const modal = document.getElementById('manualCartEntryModal');
    if (modal) {
        modal.style.display = 'none';
    }
};

// Submit manual cart items
const submitManualCartItems = async () => {
    try {
        const textarea = document.getElementById('manualCartItems');
        const text = textarea.value.trim();

        if (!text) {
            showToast('Please enter cart items', 'error');
            return;
        }

        const lines = text.split('\n');
        const items = [];

        for (const line of lines) {
            if (!line.trim()) continue;

            const parts = line.split(',');
            if (parts.length < 2) {
                showToast(`Invalid format: ${line}`, 'error');
                continue;
            }

            const productId = parts[0].trim();
            const quantity = parseInt(parts[1].trim()) || 1;

            items.push({
                product_id: productId,
                quantity: quantity
            });
        }

        if (items.length === 0) {
            showToast('No valid items found', 'error');
            return;
        }

        showToast(`Importing ${items.length} items...`, 'info');

        const response = await fetch('/api/cart/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items })
        });

        const result = await response.json();

        if (result.success) {
            showToast('✅ Items imported successfully', 'success');
            closeManualCartEntry();
            await updateCartView();
            await viewCart();
        } else {
            showToast('❌ ' + (result.error || 'Failed to import items'), 'error');
        }
    } catch (error) {
        console.error('Error importing items:', error);
        showToast('❌ Error importing items', 'error');
    }
};

// Removed updateCartModality function - dropdown is now filter-only

// Event delegation for cart interactions to prevent page refreshes
document.addEventListener('click', function(event) {
    const target = event.target;
    const action = target.getAttribute('data-action');
    
    if (!action) return;
    
    event.preventDefault();
    event.stopPropagation();
    
    switch (action) {
        case 'fetch-cart':
            fetchActualKrogerCart();
            break;
        case 'add-samples':
            addSampleItems();
            break;
        case 'manual-entry':
            showManualCartEntry();
            break;
        case 'clear-cart':
            clearCart();
            break;
        case 'close-cart':
            toggleCart();
            break;
        case 'decrease-qty':
        case 'increase-qty':
            const productId = target.getAttribute('data-product-id');
            const quantity = parseInt(target.getAttribute('data-quantity'));
            updateCartItemQuantity(productId, quantity);
            break;
        case 'remove-item':
            const removeProductId = target.getAttribute('data-product-id');
            removeFromCart(removeProductId);
            break;
    }
});

// Removed cart modality change event listeners - dropdown is now filter-only

// Removed old fulfillment method sync functions - no longer needed with filter-only approach

// Helper function to update quantity display without full refresh
const updateQuantityDisplay = (productId, newQuantity) => {
    const cartItems = document.querySelectorAll('.cart-item');
    cartItems.forEach(item => {
        const decreaseBtn = item.querySelector('[data-action="decrease-qty"]');
        const increaseBtn = item.querySelector('[data-action="increase-qty"]');
        
        if (decreaseBtn && decreaseBtn.getAttribute('data-product-id') === productId) {
            // Update the quantity display
            const qtyDisplay = item.querySelector('.qty-display');
            if (qtyDisplay) {
                qtyDisplay.textContent = newQuantity;
            }
            
            // Update button data attributes for next clicks
            decreaseBtn.setAttribute('data-quantity', Math.max(1, newQuantity - 1));
            increaseBtn.setAttribute('data-quantity', newQuantity + 1);
            
            return;
        }
    });
};

// Helper function to update cart totals without full refresh
const updateCartTotals = async () => {
    try {
        // Fetch all cart items (no modality filtering needed)
        const response = await fetch(`/api/cart/view`);
        const result = await response.json();
        
        if (result.success) {
            const cartItems = result.data.cart_items || [];
            
            // Calculate totals
            let subtotal = 0;
            let savings = 0;
            
            cartItems.forEach(item => {
                const pricing = item.pricing || {};
                const regularPrice = pricing.regular_price || 0;
                const salePrice = pricing.sale_price || regularPrice;
                const quantity = item.quantity || 1;
                
                subtotal += salePrice * quantity;
                
                if (pricing.on_sale) {
                    savings += (regularPrice - salePrice) * quantity;
                }
            });
            
            // Update the price summary elements
            const subtotalElement = document.querySelector('.price-row:first-child .price-value');
            const totalElement = document.querySelector('.price-row.total .price-value');
            const savingsElement = document.querySelector('.price-row.savings .price-value');
            const itemCountElement = document.querySelector('.price-row:first-child span:first-child');
            
            if (subtotalElement) {
                subtotalElement.textContent = `$${subtotal.toFixed(2)}`;
            }
            if (totalElement) {
                totalElement.textContent = `$${(subtotal - savings).toFixed(2)}`;
            }
            if (savingsElement && savings > 0) {
                savingsElement.textContent = `-$${savings.toFixed(2)}`;
            }
            if (itemCountElement) {
                itemCountElement.textContent = `Subtotal (${cartItems.length} items)`;
            }
        }
    } catch (error) {
        console.error('Error updating cart totals:', error);
    }
};

// Initialize global modality selector on page load
document.addEventListener('DOMContentLoaded', function() {
    const globalFulfillmentSelect = document.getElementById('globalFulfillmentMethod');
    if (globalFulfillmentSelect) {
        // Set initial value from localStorage
        globalFulfillmentSelect.value = getGlobalModality();
        
        // Add event listener for changes
        globalFulfillmentSelect.addEventListener('change', function() {
            setGlobalModality(this.value);
        });
    }
});