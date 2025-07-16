// Location functions
const showLocationPopup = () => {
    document.getElementById('locationPopup').style.display = 'flex';
};

const closeLocationPopup = () => {
    document.getElementById('locationPopup').style.display = 'none';
};

const searchLocations = async () => {
    const zipCode = document.getElementById('zipCode').value;
    
    if (!zipCode) {
        showToast('Please enter a zip code', 'error');
        return;
    }
    
    showLoading('locationResults');
    
    try {
        const response = await fetch('/api/locations/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ zip_code: zipCode })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Failed to search locations');
        }
        
        displayLocationResults(result.data);
    } catch (error) {
        showResults('locationResults', 'Error: ' + error.message, true);
    }
};

const displayLocationResults = (data) => {
    const resultsEl = document.getElementById('locationResults');
    
    if (!data.success || !data.locations || data.locations.length === 0) {
        resultsEl.innerHTML = `
            <div class="results">
                <p>No locations found for this zip code</p>
            </div>
        `;
        resultsEl.style.display = 'block';
        return;
    }
    
    let html = `<h3>Found ${data.locations.length} locations</h3>`;
    
    data.locations.forEach(location => {
        html += `
            <div class="location-card">
                <h4>${location.name}</h4>
                <p>${location.address}</p>
                <p><strong>Phone:</strong> ${location.phone || 'N/A'}</p>
                <p><strong>Chain:</strong> ${location.chain || 'Kroger'}</p>
                <button onclick="setPreferredLocation('${location.locationId}')" class="btn-success" style="margin-top: 10px;">Set as Preferred</button>
            </div>
        `;
    });
    
    resultsEl.innerHTML = html;
    resultsEl.style.display = 'block';
};

const setPreferredLocation = async (locationId) => {
    try {
        const response = await fetch('/api/locations/set-preferred', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ location_id: locationId })
        });
        
        const result = await response.json();
        
        if (!result.success) {
            throw new Error(result.error || 'Failed to set preferred location');
        }
        
        showToast('✅ Preferred location set!', 'success');
        closeLocationPopup();
        
        // Update the location name in the header
        const locationName = result.data.location_name || `Store #${locationId}`;
        document.getElementById('preferredLocationName').textContent = locationName;
    } catch (error) {
        showToast('❌ Error: ' + error.message, 'error');
    }
};

const checkPreferredLocation = async () => {
    try {
        const response = await fetch('/api/locations/get-preferred');
        const result = await response.json();
        
        if (result.success && result.data.location_id) {
            const locationName = result.data.location_name || `Store #${result.data.location_id}`;
            document.getElementById('preferredLocationName').textContent = locationName;
        } else {
            document.getElementById('preferredLocationName').textContent = 'Set Location';
        }
    } catch (error) {
        console.error('Error checking preferred location:', error);
    }
};