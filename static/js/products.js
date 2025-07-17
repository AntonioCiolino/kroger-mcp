// Product search and display functions
const searchProducts = async () => {
    const term = document.getElementById('searchTerm').value;
    const limit = document.getElementById('searchLimit').value;

    if (!term) {
        showToast('Please enter a search term', 'error');
        return;
    }

    showLoading('productResults');

    try {
        const response = await fetch('/api/products/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ term, limit: parseInt(limit) })
        });

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to search products');
        }

        displayProductResults(result.data);
    } catch (error) {
        showResults('productResults', 'Error: ' + error.message, true);
    }
};

const displayProductResults = (data) => {
    const resultsEl = document.getElementById('productResults');

    if (!data.success || !data.products || data.products.length === 0) {
        resultsEl.innerHTML = `
            <div class="results">
                <p>No products found matching "${data.search_term}"</p>
            </div>
        `;
        resultsEl.style.display = 'block';
        return;
    }

    let html = `
        <h3>Found ${data.products.length} products matching "${data.search_term}"</h3>
        <div class="products-grid">
    `;

    data.products.forEach(product => {
        const imageUrl = product.images && product.images.length > 0
            ? product.images.find(img => img.perspective === 'front')?.url || product.images[0].url
            : null;

        const pricing = product.pricing || {};
        const regularPrice = pricing.regular_price;
        const salePrice = pricing.sale_price;
        const onSale = salePrice && regularPrice && salePrice < regularPrice;

        // Check for price tracking info
        const priceTracking = product.price_tracking || {};
        const priceDropBadge = priceTracking.price_dropped ?
            `<div class="price-drop-badge">📉 Price Drop!</div>` : '';
        const lowestPriceBadge = priceTracking.is_lowest_ever ?
            `<div class="lowest-price-badge">🎯 Lowest Ever!</div>` : '';

        html += `
            <div class="product-card">
                ${onSale ? '<div class="sale-badge">SALE</div>' : ''}
                <div class="product-image" onclick="showProductDetails('${product.productId}')" style="cursor: pointer;" title="Click to view product details">
                    ${imageUrl ? `<img src="${imageUrl}" alt="${product.description}">` : '📦'}
                </div>
                <div class="product-info">
                    <div class="product-brand">${product.brand || 'Brand'}</div>
                    <div class="product-title">${product.description || 'Product'}</div>
                    <div class="product-price ${onSale ? 'on-sale' : ''}">
                        ${onSale ? `$${salePrice.toFixed(2)} <span style="text-decoration: line-through; font-size: 12px; color: #999;">$${regularPrice.toFixed(2)}</span>` :
                regularPrice ? `$${regularPrice.toFixed(2)}` : 'Price not available'}
                    </div>
                    <button class="quick-add-btn" onclick="quickAddToCart('${product.productId}')">Add to Cart</button>
                </div>
            </div>
        `;
    });

    html += '</div>';
    resultsEl.innerHTML = html;
    resultsEl.style.display = 'block';
};

const showProductDetails = async (productId) => {
    const modal = document.getElementById('productDetailsModal');
    modal.style.display = 'flex';

    const content = document.getElementById('productDetailsContent');
    content.innerHTML = `
        <div style="display: flex; flex-direction: column; align-items: center; padding: 40px 20px;">
            <div class="spinner" style="width: 40px; height: 40px; margin-bottom: 15px;"></div>
            <p style="color: #666;">Loading product details...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/products/details?product_id=${productId}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch product details: ${response.status}`);
        }

        const result = await response.json();

        if (!result.success) {
            throw new Error(result.error || 'Failed to load product details');
        }

        // Log the product details for debugging
        console.log('Product details response:', result);

        displayProductDetails(result.data);
    } catch (error) {
        content.innerHTML = `
            <div class="results error">
                <p>Error loading product details: ${error.message}</p>
                <button onclick="closeProductDetails()" class="btn-primary" style="margin-top: 15px;">Close</button>
            </div>
        `;
        console.error('Error loading product details:', error);
    }
};

const closeProductDetails = () => {
    document.getElementById('productDetailsModal').style.display = 'none';
};

const displayProductDetails = (product) => {
    // Log the product object to debug
    console.log('Product details:', product);

    const content = document.getElementById('productDetailsContent');

    const imageUrl = product.images && product.images.length > 0
        ? product.images.find(img => img.perspective === 'front')?.url || product.images[0].url
        : null;

    const pricing = product.pricing || {};
    const regularPrice = pricing.regular_price;
    const salePrice = pricing.sale_price;
    const onSale = salePrice && regularPrice && salePrice < regularPrice;

    const priceDisplay = salePrice ? `$${salePrice.toFixed(2)}` :
        regularPrice ? `$${regularPrice.toFixed(2)}` : 'Price not available';
    const priceClass = onSale ? 'product-details-price on-sale' : 'product-details-price';

    // Make sure we're using the correct product ID field
    const productId = product.product_id || product.productId;

    let html = `
        <div class="product-details-header">
            <div class="product-details-image">
                ${imageUrl ? `<img src="${imageUrl}" alt="${product.description}">` : '📦'}
            </div>
            <div class="product-details-info">
                <div class="product-details-brand">${product.brand || 'Brand'}</div>
                <h2 class="product-details-title">${product.description || 'Product'}</h2>
                <div class="${priceClass}">
                    ${priceDisplay}
                    ${onSale ? `<span style="text-decoration: line-through; font-size: 16px; color: #999; margin-left: 10px;">$${regularPrice.toFixed(2)}</span>` : ''}
                </div>
                
                <div class="product-details-actions">
                    <div class="quantity-selector">
                        <button class="quantity-btn" onclick="updateQuantity(-1)">-</button>
                        <input type="number" id="detailsQuantity" class="quantity-input" value="1" min="1" max="99">
                        <button class="quantity-btn" onclick="updateQuantity(1)">+</button>
                    </div>
                    <div class="modality-selector">
                        <select id="detailsModality" class="modality-select">
                            <option value="PICKUP">🚗 Pickup</option>
                            <option value="DELIVERY">🚚 Delivery</option>
                        </select>
                    </div>
                    <button class="add-to-cart-btn" onclick="addToCartFromDetails('${productId}')">Add to Cart</button>
                </div>
            </div>
        </div>
    `;

    // Add product details sections
    html += `
        <div class="product-details-section">
            <h3>Product Information</h3>
            <div class="product-details-grid">
                <div class="product-detail-item">
                    <strong>UPC:</strong> ${product.upc || 'N/A'}
                </div>
                <div class="product-detail-item">
                    <strong>Size:</strong> ${product.item_details?.size || 'N/A'}
                </div>
                <div class="product-detail-item">
                    <strong>Country of Origin:</strong> ${product.country_origin || 'N/A'}
                </div>
            </div>
        </div>
    `;

    // Add image gallery if multiple images (moved above store location)
    if (product.images && product.images.length > 1) {
        html += `
            <div class="product-details-section">
                <h3>Product Images</h3>
                <div class="image-gallery">
                    ${product.images.map((img, index) => `
                        <div class="gallery-image ${index === 0 ? 'active' : ''}" 
                             data-image-url="${img.url}" 
                             data-product-name="${escapeHtml(product.description || 'Product')}"
                             data-all-images="${escapeHtml(JSON.stringify(product.images))}"
                             onclick="openImageModalSafe(this)">
                            <img src="${img.url}" alt="${img.perspective || 'Product image'}">
                            <div class="gallery-overlay">
                                <span class="zoom-icon">🔍</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <p class="gallery-hint">👆 Click any thumbnail to view full-size images with zoom and navigation</p>
            </div>
        `;
    }

    // Add aisle locations if available (moved below images)
    if (product.aisle_locations && product.aisle_locations.length > 0) {
        html += `
            <div class="product-details-section">
                <h3>Store Location</h3>
                ${product.aisle_locations.map(aisle => `
                    <div class="aisle-location">
                        <strong>Aisle:</strong> ${aisle.number || 'N/A'} ${aisle.side ? `(${aisle.side} side)` : ''}
                        ${aisle.description ? `<br><strong>Section:</strong> ${aisle.description}` : ''}
                        ${aisle.shelf_number ? `<br><strong>Shelf:</strong> ${aisle.shelf_number}` : ''}
                    </div>
                `).join('')}
            </div>
        `;
    }

    content.innerHTML = html;
};

const updateQuantity = (change) => {
    const input = document.getElementById('detailsQuantity');
    let value = parseInt(input.value) + change;
    value = Math.max(1, Math.min(99, value));
    input.value = value;
};

const switchMainImage = (element, url) => {
    // Remove active class from all gallery images
    document.querySelectorAll('.gallery-image').forEach(img => img.classList.remove('active'));

    // Add active class to clicked image
    element.classList.add('active');

    // Update main image
    const mainImage = document.querySelector('.product-details-image img');
    if (mainImage) {
        mainImage.src = url;
    }
};

const addToCartFromDetails = async (productId) => {
    const quantity = parseInt(document.getElementById('detailsQuantity').value);
    const modality = document.getElementById('detailsModality').value;
    const button = document.querySelector('.add-to-cart-btn');
    
    // Store original button content
    const originalContent = button.innerHTML;
    
    try {
        // Show authentication warning if needed
        const authResult = await checkAuthStatus();
        if (!authResult || !authResult.data || !authResult.data.authenticated) {
            showToast('⚠️ Please authenticate first to add items to cart', 'error');
            toggleAuth(); // Show auth section
            return;
        }

        // Show loading state
        button.disabled = true;
        button.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
                <div class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></div>
                Adding...
            </div>
        `;

        const response = await fetch('/api/cart/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                product_id: productId,
                quantity: quantity,
                modality: modality
            })
        });
        const result = await response.json();

        if (result.success) {
            // Show success state briefly
            button.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; gap: 8px;">
                    ✅ Added to Cart!
                </div>
            `;
            
            const modalityText = modality === 'PICKUP' ? 'Pickup' : 'Delivery';
            showToast(`✅ Added ${quantity} item(s) to cart for ${modalityText}!`, 'success');
            await updateCartView();
            
            // Close modal after brief delay
            setTimeout(() => {
                closeProductDetails();
            }, 1000);
        } else {
            showToast('❌ Error: ' + result.error, 'error');
            // Restore original button state
            button.disabled = false;
            button.innerHTML = originalContent;
        }
    } catch (error) {
        showToast('❌ Error: ' + error.message, 'error');
        // Restore original button state
        button.disabled = false;
        button.innerHTML = originalContent;
    }
};

// Add event listener for Enter key on search input when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    const searchInput = document.getElementById('searchTerm');
    if (searchInput) {
        searchInput.addEventListener('keypress', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                searchProducts();
            }
        });
    }
});

// Price tracking functions
const togglePriceAlerts = async () => {
    const alertsSection = document.getElementById('priceAlerts');

    if (alertsSection.style.display === 'none') {
        // Show alerts and load data
        alertsSection.style.display = 'block';
        await loadPriceAlerts();
    } else {
        // Hide alerts
        alertsSection.style.display = 'none';
    }
};

const loadPriceAlerts = async () => {
    const content = document.getElementById('priceAlertsContent');
    content.innerHTML = 'Loading price alerts...';

    try {
        const response = await fetch('/api/price-tracking/alerts?threshold=5');
        const result = await response.json();

        if (result.success && result.data.alerts.length > 0) {
            let html = '';
            result.data.alerts.forEach(alert => {
                html += `
                    <div class="price-alert-item">
                        <div class="price-alert-info">
                            <div class="price-alert-product">${alert.product_name}</div>
                            <div class="price-alert-change">
                                Was $${alert.previous_price.toFixed(2)} → Now $${alert.current_price.toFixed(2)}
                                (Save $${alert.drop_amount.toFixed(2)})
                            </div>
                        </div>
                        <div class="price-alert-badge">
                            ${alert.drop_percentage.toFixed(1)}% OFF
                        </div>
                    </div>
                `;
            });
            content.innerHTML = html;
        } else {
            content.innerHTML = '<p>No significant price drops found. Keep searching for products to build your price history!</p>';
        }
    } catch (error) {
        content.innerHTML = '<p>Error loading price alerts. Please try again.</p>';
        console.error('Error loading price alerts:', error);
    }
};

// Make functions globally available
window.togglePriceAlerts = togglePriceAlerts;

// Utility function to escape HTML and problematic characters
const escapeHtml = (text) => {
    if (!text) return '';
    
    // Create a temporary div to safely escape HTML
    const div = document.createElement('div');
    div.textContent = text;
    let escaped = div.innerHTML;
    
    // Additional escaping for problematic characters that could break JavaScript
    escaped = escaped
        .replace(/'/g, '&#39;')     // Single quotes
        .replace(/"/g, '&quot;')    // Double quotes  
        .replace(/`/g, '&#96;')     // Backticks
        .replace(/\\/g, '&#92;')    // Backslashes
        .replace(/\r?\n/g, ' ')     // Line breaks
        .replace(/\r/g, ' ')        // Carriage returns
        .replace(/\t/g, ' ');       // Tabs
    
    return escaped;
};

// Safe image modal opener that uses data attributes
const openImageModalSafe = (element) => {
    const imageUrl = element.dataset.imageUrl;
    const productName = element.dataset.productName;
    const allImagesJson = element.dataset.allImages;
    
    let allImages;
    try {
        allImages = JSON.parse(allImagesJson);
    } catch (e) {
        console.error('Error parsing images data:', e);
        allImages = [{ url: imageUrl, perspective: 'main' }];
    }
    
    openImageModal(imageUrl, productName, allImages);
};

// Image modal functions
const openImageModal = (imageUrl, productName, allImages) => {
    // Create or get the image modal
    let imageModal = document.getElementById('imageModal');
    if (!imageModal) {
        // Create the modal if it doesn't exist
        imageModal = document.createElement('div');
        imageModal.id = 'imageModal';
        imageModal.className = 'image-modal';
        document.body.appendChild(imageModal);
    }

    // Parse the images array if it's a string
    let images = [];
    try {
        images = typeof allImages === 'string' ? JSON.parse(allImages.replace(/&quot;/g, '"')) : allImages;
    } catch (e) {
        images = [{ url: imageUrl, perspective: 'main' }];
    }

    // Find current image index
    const currentIndex = images.findIndex(img => img.url === imageUrl);

    imageModal.innerHTML = `
        <div class="image-modal-overlay" onclick="closeImageModal()">
            <div class="image-modal-content" onclick="event.stopPropagation()">
                <div class="image-modal-header">
                    <h3>${productName}</h3>
                    <button class="image-modal-close" onclick="closeImageModal()">✕</button>
                </div>
                <div class="image-modal-body">
                    <div class="image-modal-main">
                        <img id="modalMainImage" src="${imageUrl}" alt="${productName}">
                    </div>
                    ${images.length > 1 ? `
                        <div class="image-modal-nav">
                            <button class="nav-btn prev" onclick="navigateImage(-1)" ${currentIndex <= 0 ? 'disabled' : ''}>‹</button>
                            <span class="image-counter">${currentIndex + 1} of ${images.length}</span>
                            <button class="nav-btn next" onclick="navigateImage(1)" ${currentIndex >= images.length - 1 ? 'disabled' : ''}>›</button>
                        </div>
                        <div class="image-modal-thumbnails">
                            ${images.map((img, index) => `
                                <div class="modal-thumbnail ${index === currentIndex ? 'active' : ''}" 
                                     onclick="switchModalImage(${index})">
                                    <img src="${img.url}" alt="${img.perspective || 'Product image'}">
                                </div>
                            `).join('')}
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;

    // Store images data for navigation
    imageModal.dataset.images = JSON.stringify(images);
    imageModal.dataset.currentIndex = currentIndex.toString();

    // Show the modal
    imageModal.style.display = 'flex';
    document.body.style.overflow = 'hidden'; // Prevent background scrolling
};

const closeImageModal = () => {
    const imageModal = document.getElementById('imageModal');
    if (imageModal) {
        imageModal.style.display = 'none';
        document.body.style.overflow = ''; // Restore scrolling
    }
};

const navigateImage = (direction) => {
    const imageModal = document.getElementById('imageModal');
    if (!imageModal) return;

    const images = JSON.parse(imageModal.dataset.images);
    let currentIndex = parseInt(imageModal.dataset.currentIndex);

    currentIndex += direction;
    if (currentIndex < 0) currentIndex = 0;
    if (currentIndex >= images.length) currentIndex = images.length - 1;

    switchModalImage(currentIndex);
};

const switchModalImage = (index) => {
    const imageModal = document.getElementById('imageModal');
    if (!imageModal) return;

    const images = JSON.parse(imageModal.dataset.images);
    const image = images[index];

    // Update main image
    const mainImage = document.getElementById('modalMainImage');
    if (mainImage) {
        mainImage.src = image.url;
    }

    // Update thumbnails
    document.querySelectorAll('.modal-thumbnail').forEach((thumb, i) => {
        thumb.classList.toggle('active', i === index);
    });

    // Update navigation
    const prevBtn = document.querySelector('.nav-btn.prev');
    const nextBtn = document.querySelector('.nav-btn.next');
    const counter = document.querySelector('.image-counter');

    if (prevBtn) prevBtn.disabled = index <= 0;
    if (nextBtn) nextBtn.disabled = index >= images.length - 1;
    if (counter) counter.textContent = `${index + 1} of ${images.length}`;

    // Update stored index
    imageModal.dataset.currentIndex = index.toString();
};

// Make functions globally available
window.openImageModal = openImageModal;
window.closeImageModal = closeImageModal;
window.navigateImage = navigateImage;
window.switchModalImage = switchModalImage;
window.openImageModalSafe = openImageModalSafe;
window.escapeHtml = escapeHtml;