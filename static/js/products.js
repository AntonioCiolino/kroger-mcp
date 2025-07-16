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

        html += `
            <div class="product-card">
                ${onSale ? '<div class="sale-badge">SALE</div>' : ''}
                <div class="product-image">
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
                    <button class="quick-add-btn" style="margin-top: 5px; background: #6c757d;" onclick="showProductDetails('${product.productId}')">View Details</button>
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

    // Add aisle locations if available
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

    // Add image gallery if multiple images
    if (product.images && product.images.length > 1) {
        html += `
            <div class="product-details-section">
                <h3>Product Images</h3>
                <div class="image-gallery">
                    ${product.images.map((img, index) => `
                        <div class="gallery-image ${index === 0 ? 'active' : ''}" onclick="switchMainImage(this, '${img.url}')">
                            <img src="${img.url}" alt="${img.perspective || 'Product image'}">
                        </div>
                    `).join('')}
                </div>
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
    
    try {
        // Show authentication warning if needed
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
                quantity: quantity,
                modality: modality
            })
        });
        const result = await response.json();

        if (result.success) {
            const modalityText = modality === 'PICKUP' ? 'Pickup' : 'Delivery';
            showToast(`✅ Added ${quantity} item(s) to cart for ${modalityText}!`, 'success');
            await updateCartView();
            closeProductDetails();
        } else {
            showToast('❌ Error: ' + result.error, 'error');
        }
    } catch (error) {
        showToast('❌ Error: ' + error.message, 'error');
    }
};

// Add event listener for Enter key on search input when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('searchTerm');
    if (searchInput) {
        searchInput.addEventListener('keypress', function(event) {
            if (event.key === 'Enter') {
                event.preventDefault();
                searchProducts();
            }
        });
    }
});