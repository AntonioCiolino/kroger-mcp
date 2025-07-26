// Global modality preference functions
const getGlobalModality = () => {
    // Check localStorage for user's preferred modality, default to DELIVERY
    return localStorage.getItem('globalModality') || 'DELIVERY';
};

const setGlobalModality = (modality) => {
    localStorage.setItem('globalModality', modality);
    showToast(`✅ Default modality set to ${modality === 'PICKUP' ? 'Pickup' : 'Delivery'}`, 'success');
};

// Toggle cart panel visibility
const toggleCart = () => {
    console.log('toggleCart called!'); // Debug log
    const cartPanel = document.getElementById('cartPanel');
    console.log('cartPanel element:', cartPanel); // Debug log
    
    if (!cartPanel) {
        console.error('Cart panel element not found!');
        showToast('❌ Cart panel not found', 'error');
        return;
    }
    
    if (cartPanel.style.display === 'none' || !cartPanel.classList.contains('show')) {
        console.log('Opening cart panel'); // Debug log
        cartPanel.style.display = 'block';
        setTimeout(() => cartPanel.classList.add('show'), 10);

        const cartResults = document.getElementById('cartResults');
        if (cartResults) {
            cartResults.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; padding: 40px 20px;">
                    <div class="spinner" style="width: 40px; height: 40px; margin-bottom: 15px;"></div>
                    <p style="color: #666;">Loading your cart...</p>
                </div>
            `;
        }

        viewCart();
    } else {
        console.log('Closing cart panel'); // Debug log
        cartPanel.classList.remove('show');
        setTimeout(() => cartPanel.style.display = 'none', 300);
    }
};

// Make toggleCart available globally for onclick handlers
window.toggleCart = toggleCart;

// Fetch cart from Kroger API and sync with local cart
const fetchActualKrogerCart = async () => {
    try {
        showToast('🔄 Fetching your Kroger cart...', 'info');
        
        const response = await fetch('/api/cart/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fetch: true })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast(`✅ ${result.message}`, 'success');
            await updateCartView();
            await viewCart(); // Refresh the cart display
        } else {
            showToast(`❌ ${result.error || 'Failed to fetch Kroger cart'}`, 'error');
        }
    } catch (error) {
        console.error('Error fetching Kroger cart:', error);
        showToast('❌ Error fetching Kroger cart', 'error');
    }
};

// Cart functions
const updateCartView = async () => {
    // Use the consolidated cart count update function
    await updateCartCount();
};

const quickAddToCart = async (productId) => {
    // Find the add to cart button for this product to show loading state
    const addButton = document.querySelector(`[onclick="quickAddToCart('${productId}')"]`);
    const originalText = addButton ? addButton.textContent : '';
    
    try {
        // Check authentication status first
        const authStatus = await checkAuthStatusForCart();
        if (!authStatus) {
            showToast('⚠️ Please authenticate first to add items to cart', 'error');
            toggleAuth(); // Show auth section
            return;
        }

        // Show loading state with spinner
        if (addButton) {
            addButton.disabled = true;
            addButton.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 6px;">
                    <div class="spinner" style="width: 12px; height: 12px; border-width: 2px;"></div>
                    Adding...
                </div>
            `;
        }

        await retryWithBackoff(async () => {
            const response = await fetch('/api/cart/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: productId,
                    quantity: 1,
                    modality: getGlobalModality() // Use global modality preference
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || 'Add to cart failed');
            }
            
            return result;
        });

        // Show success state briefly
        if (addButton) {
            addButton.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 6px;">
                    ✅ Added!
                </div>
            `;
        }
        
        showToast('✅ Added to cart', 'success');
        await updateCartView();

        // If cart panel is open, refresh it
        const cartPanel = document.getElementById('cartPanel');
        if (cartPanel.classList.contains('show')) {
            await viewCart();
        }
        
        // Restore button after brief delay
        setTimeout(() => {
            if (addButton) {
                addButton.disabled = false;
                addButton.innerHTML = originalText;
            }
        }, 1500);
        
    } catch (error) {
        console.error('Error adding to cart:', error);
        showToast(`❌ Failed to add to cart: ${error.message}`, 'error');
        
        // Restore button state immediately on error
        if (addButton) {
            addButton.disabled = false;
            addButton.innerHTML = originalText;
        }
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

// Duplicate toggleCart function removed - using the one with debug logging above

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
            <div class="cart-actions" style="display: flex; justify-content: space-between; align-items: center; margin-top: 15px;">
                <div class="sync-status" style="font-size: 12px; color: #666;">
                    ✅ Always synced with your Kroger cart
                </div>
                <button data-action="clear-cart" class="btn-clear-cart">
                    🗑️
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
            ? item.images.find(img => img.perspective === 'front')?.url || item.images[0].url
            : null;

        const pricing = item.pricing || {};
        const regularPrice = pricing.regular_price || 0;
        const salePrice = pricing.sale_price;
        const displayPrice = salePrice || regularPrice;
        const onSale = pricing.on_sale;

        html += `
            <div class="cart-item">
                <div class="cart-item-image clickable" onclick="showProductDetails('${item.product_id}')" title="Click to view product details">
                    ${imageUrl ? `<img src="${imageUrl}" alt="${item.description || 'Product'}">` : '<div class="no-image">📦</div>'}
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
    const cartItem = document.querySelector(`[data-product-id="${productId}"]`).closest('.cart-item');
    
    if (!cartItem) {
        console.error('Cart item not found for removal');
        return;
    }
    
    // Show loading state on the specific item
    showItemLoading(productId, true);
    
    try {
        await retryWithBackoff(async () => {
            const response = await fetch('/api/cart/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: productId
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || 'Remove failed');
            }
            
            return result;
        });

        // Animate item removal
        cartItem.style.transition = 'all 0.3s ease';
        cartItem.style.transform = 'translateX(-100%)';
        cartItem.style.opacity = '0';
        cartItem.style.height = cartItem.offsetHeight + 'px';
        
        // After animation, collapse height and remove
        setTimeout(() => {
            cartItem.style.height = '0';
            cartItem.style.padding = '0';
            cartItem.style.margin = '0';
            cartItem.style.overflow = 'hidden';
            
            // Remove from DOM after collapse animation
            setTimeout(() => {
                cartItem.remove();
                
                // Update cart count and check if cart is empty
                updateCartCount();
                checkEmptyCart();
            }, 300);
        }, 300);

        showToast('✅ Item removed', 'success');
        
        // Only update the cart view counter, not the full cart
        await updateCartView();
        
    } catch (error) {
        console.error('Error removing item:', error);
        showToast(`❌ Failed to remove item: ${error.message}`, 'error');
        showItemLoading(productId, false);
    }
};

// Show clear cart confirmation modal
const clearCart = () => {
    const modal = document.getElementById('clearCartModal');
    modal.classList.add('show');
};

// Close clear cart modal
const closeClearCartModal = () => {
    const modal = document.getElementById('clearCartModal');
    modal.classList.remove('show');
};

// Confirm and execute cart clearing
const confirmClearCart = async () => {
    closeClearCartModal();
    
    // Show loading state for the clear button
    const clearButton = document.querySelector('[data-action="clear-cart"]');
    if (clearButton) {
        clearButton.disabled = true;
        clearButton.innerHTML = '⏳';
    }

    try {
        await retryWithBackoff(async () => {
            const response = await fetch('/api/cart/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || 'Clear failed');
            }
            
            return result;
        });

        showToast('✅ Cart cleared', 'success');
        await viewCart();
        await updateCartView();
        
    } catch (error) {
        console.error('Error clearing cart:', error);
        showToast(`❌ Failed to clear cart: ${error.message}`, 'error');
    } finally {
        // Restore the clear button
        if (clearButton) {
            clearButton.disabled = false;
            clearButton.innerHTML = '🗑️';
        }
    }
};

// Confirm and execute local cart clearing only
const confirmClearLocalCart = async () => {
    closeClearCartModal();
    
    // Show loading state for the clear button
    const clearButton = document.querySelector('[data-action="clear-cart"]');
    if (clearButton) {
        clearButton.disabled = true;
        clearButton.innerHTML = '⏳';
    }

    try {
        await retryWithBackoff(async () => {
            const response = await fetch('/api/cart/clear-local', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const result = await response.json();
            if (!result.success) {
                throw new Error(result.error || 'Local clear failed');
            }
            
            return result;
        });

        showToast('✅ Local cart tracking cleared', 'success');
        await viewCart();
        await updateCartView();
        
    } catch (error) {
        console.error('Error clearing local cart:', error);
        showToast(`❌ Failed to clear local cart: ${error.message}`, 'error');
    } finally {
        // Restore the clear button
        if (clearButton) {
            clearButton.disabled = false;
            clearButton.innerHTML = '🗑️';
        }
    }
};

// Make functions globally available
window.closeClearCartModal = closeClearCartModal;
window.confirmClearCart = confirmClearCart;
window.confirmClearLocalCart = confirmClearLocalCart;

// Helper functions
const checkAuthStatusForCart = async () => {
    try {
        // Use the cached auth status check from utils.js to reduce API calls
        const result = await checkAuthStatus();
        return result && result.data && (result.data.authenticated || result.data.token_valid);
    } catch (error) {
        console.error('Error checking auth status:', error);
        return false;
    }
};

// Update cart count in header - consolidated function
const updateCartCount = async () => {
    try {
        const response = await fetch('/api/cart/view');
        const result = await response.json();
        if (result.success) {
            const cartItems = result.data.cart_items || [];
            const totalQuantity = cartItems.reduce((sum, item) => sum + (item.quantity || 1), 0);
            const countElement = document.getElementById('cartItemCount');
            if (countElement) {
                countElement.textContent = totalQuantity;
                console.log(`Cart count updated: ${totalQuantity}`);
            }
        }
    } catch (error) {
        console.error('Error updating cart count:', error);
        // Set to 0 on error to avoid showing stale data
        const countElement = document.getElementById('cartItemCount');
        if (countElement) {
            countElement.textContent = '0';
        }
    }
};

// Check if cart is empty and update display
const checkEmptyCart = () => {
    const cartItems = document.querySelectorAll('.cart-item');
    const cartResults = document.getElementById('cartResults');
    
    if (cartItems.length === 0) {
        // Show empty cart message
        const cartHeader = cartResults.querySelector('.cart-header');
        const emptyCartHtml = `
            <div class="empty-cart">
                <h3>Your cart is empty</h3>
                <p>Search for products to add to your cart</p>
            </div>
        `;
        
        if (cartHeader) {
            cartHeader.insertAdjacentHTML('afterend', emptyCartHtml);
        } else {
            cartResults.innerHTML = emptyCartHtml;
        }
        
        // Remove price summary if it exists
        const priceSummary = cartResults.querySelector('.price-summary');
        if (priceSummary) {
            priceSummary.remove();
        }
    }
};

// Duplicate fetchActualKrogerCart function removed - using the one above with fetch: true

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
            debouncedQuantityUpdate(productId, quantity);
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

// Debouncing for quantity updates
let quantityUpdateTimeouts = {};

// Retry logic with exponential backoff
const retryWithBackoff = async (fn, maxRetries = 3, baseDelay = 1000) => {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await fn();
        } catch (error) {
            if (attempt === maxRetries) {
                throw error;
            }
            
            const delay = baseDelay * Math.pow(2, attempt - 1);
            console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }
};

// Show loading state for specific cart item
const showItemLoading = (productId, isLoading) => {
    const cartItems = document.querySelectorAll('.cart-item');
    cartItems.forEach(item => {
        const decreaseBtn = item.querySelector('[data-action="decrease-qty"]');
        if (decreaseBtn && decreaseBtn.getAttribute('data-product-id') === productId) {
            const buttons = item.querySelectorAll('[data-action*="qty"], [data-action="remove-item"]');
            buttons.forEach(btn => {
                btn.disabled = isLoading;
                btn.style.opacity = isLoading ? '0.5' : '1';
            });
            
            if (isLoading) {
                const loadingIndicator = document.createElement('div');
                loadingIndicator.className = 'item-loading';
                loadingIndicator.innerHTML = '⏳';
                loadingIndicator.style.cssText = 'position: absolute; top: 5px; right: 5px; font-size: 12px;';
                item.style.position = 'relative';
                item.appendChild(loadingIndicator);
            } else {
                const loadingIndicator = item.querySelector('.item-loading');
                if (loadingIndicator) {
                    loadingIndicator.remove();
                }
            }
        }
    });
};

const debouncedQuantityUpdate = (productId, newQuantity) => {
    // Clear any existing timeout for this product
    if (quantityUpdateTimeouts[productId]) {
        clearTimeout(quantityUpdateTimeouts[productId]);
    }
    
    // Update UI immediately for responsiveness
    updateQuantityDisplay(productId, newQuantity);
    
    // Set a new timeout to send the API update after 500ms of no more clicks
    quantityUpdateTimeouts[productId] = setTimeout(async () => {
        showItemLoading(productId, true);
        
        try {
            await retryWithBackoff(async () => {
                const response = await fetch('/api/cart/update-quantity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: productId,
                        quantity: newQuantity
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                
                const result = await response.json();
                if (!result.success) {
                    throw new Error(result.error || 'Update failed');
                }
                
                return result;
            });
            
            showToast('✅ Quantity updated', 'success');
            
        } catch (error) {
            console.error('Error updating quantity:', error);
            showToast(`❌ Failed to update quantity: ${error.message}`, 'error');
            // Refresh cart to show correct state
            await viewCart();
        } finally {
            showItemLoading(productId, false);
            // Clean up the timeout reference
            delete quantityUpdateTimeouts[productId];
        }
    }, 500);
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
    
    // Initialize cart count on page load
    updateCartCount();
});