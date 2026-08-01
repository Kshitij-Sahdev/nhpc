// NHPC Weather Warning System - Frontend Controller

// XSS Prevention: escape user-controlled strings before innerHTML insertion
function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    const s = String(str);
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
}

// State variables
let currentSelectedPlant = null;
let currentChart = null;
let currentTab = 'temp-tab'; // temp-tab or rain-tab
let map = null;
let mapMarkers = {};
let mapPolygons = {};
let mapCircles = {};
let customLocations = [];
let debounceTimer = null;

// Siren Audio State variables
let audioCtx = null;
let sirenOscillator = null;
let sirenGain = null;
let isSirenMuted = true;
let sirenInterval = null;

// Color variables matching CSS
const COLORS = {
    RED: '#ef4444',
    YELLOW: '#f59e0b',
    GREEN: '#10b981',
    BLUE: '#38bdf8',
    PURPLE: '#c084fc',
    GRID: 'rgba(255, 255, 255, 0.05)',
    TEXT: '#94a3b8'
};

// Load custom locations from LocalStorage
customLocations = JSON.parse(localStorage.getItem('nhpc_custom_locations') || '[]');

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons safely
    if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
        lucide.createIcons();
    }
    
    // Check if data is loaded
    if (!window.FORECAST_DATA) {
        console.error("Forecast data (forecast_data.js) is missing or failed to load.");
        alert("Error: Weather forecast data could not be found. Please ensure update_forecasts.py was run.");
        return;
    }
    
    // Initialize Dashboard UI with initial data
    updateDashboardUI(window.FORECAST_DATA);
    
    // Render custom locations after map and official stations are loaded
    renderCustomLocationsOnInit();
    
    // Set up clear custom locations button
    const clearCustomBtn = document.getElementById('clear-custom-btn');
    if (clearCustomBtn) {
        clearCustomBtn.addEventListener('click', clearAllCustomLocations);
    }
    
    // Start dynamic polling for weather data updates every 30 seconds
    startAutoPolling();
});

// Update the entire dashboard UI from data
function updateDashboardUI(data) {
    // Render statistics & updates
    document.getElementById('update-timestamp').innerText = data.generated_at || 'N/A';
    document.getElementById('stat-red').querySelector('.stat-num').innerText = data.statistics.red;
    document.getElementById('stat-yellow').querySelector('.stat-num').innerText = data.statistics.yellow;
    document.getElementById('stat-green').querySelector('.stat-num').innerText = data.statistics.green;
    
    // Sort plants alphabetically by name
    const sortedPlants = [...data.plants].sort((a, b) => {
        return a.name.localeCompare(b.name);
    });
    
    // Initialize map if it hasn't been initialized yet
    if (!map) {
        initMap(data.plants);
    } else {
        // Update markers if map already exists
        data.plants.forEach(plant => {
            if (mapMarkers[plant.id]) {
                let affectedRegionsHtml = '';
                if (plant.affected_regions && plant.affected_regions.length > 0) {
                    affectedRegionsHtml = '<br><strong>Affected Regions:</strong><br>' + 
                        plant.affected_regions.map(r => `[${r.lat}, ${r.lon}] (${r.level})`).join('<br>');
                }
                let popupText = `
                    <div class="leaflet-popup-title">${escapeHtml(plant.name)}</div>
                    <div class="leaflet-popup-desc">
                        <strong>Status:</strong> ${escapeHtml(plant.alert_level)}<br>
                        <strong>24h Rain:</strong> ${plant.summary.rain_24h || 0.0} mm<br>
                        <strong>Max Wind:</strong> ${plant.summary.max_wind || 0.0} m/s${affectedRegionsHtml}
                    </div>
                `;
                mapMarkers[plant.id].setPopupContent(popupText);
            }
        });
    }
    
    // Populate Sidebar Station List
    populateStationList(sortedPlants);
    
    // Setup Search
    setupSearch(sortedPlants);
    
    // Auto-select first active alert if no selection has been made yet
    if (!currentSelectedPlant) {
        const initialSelection = sortedPlants.find(p => p.alert_level === 'RED') || 
                                  sortedPlants.find(p => p.alert_level === 'YELLOW');
        if (initialSelection) {
            selectPlant(initialSelection.id);
        }
    }
}

// Dynamic polling to check for data updates without page refresh
function startAutoPolling() {
    setInterval(() => {
        const oldScript = document.querySelector('script[src^="forecast_data.js"]');
        if (oldScript) {
            oldScript.remove();
        }
        
        const newScript = document.createElement('script');
        newScript.src = `forecast_data.js?t=${new Date().getTime()}`;
        newScript.onload = () => {
            const data = window.FORECAST_DATA;
            if (data) {
                const currentTimestamp = document.getElementById('update-timestamp').innerText;
                if (data.generated_at !== currentTimestamp) {
                    console.log("New forecast data detected! Re-rendering dashboard...");
                    updateDashboardUI(data);
                    
                    if (currentSelectedPlant) {
                        const isCustom = currentSelectedPlant.id.toString().startsWith('custom-');
                        if (isCustom) {
                            fetchCustomLocationForecast(currentSelectedPlant.lat, currentSelectedPlant.lon, currentSelectedPlant.name);
                        } else {
                            const updatedSelected = data.plants.find(p => p.id === currentSelectedPlant.id);
                            if (updatedSelected) {
                                selectPlant(updatedSelected.id, false); // select without panning map
                            }
                        }
                    }
                }
            }
        };
        document.body.appendChild(newScript);
    }, 30000); // check every 30 seconds
}

// Map Initialization
function initMap(plants) {
    // Center map roughly over northern India
    map = L.map('map', {
        zoomControl: false,
        attributionControl: true
    }).setView([29.0, 80.0], 5);
    
    L.control.zoom({ position: 'bottomleft' }).addTo(map);
    
    // Dark mode maps: CartoDB Dark Matter
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
    
    // Create markers for each plant
    plants.forEach(plant => {
        addMapMarker(plant, false);
    });
}

// Add Map Marker helper (supports official & custom locations)
function addMapMarker(plant, isCustom = false) {
    const lat = plant.lat;
    const lon = plant.lon;
    const status = plant.alert_level;
    
    const pulseHtml = `
        <div class="custom-marker ${isCustom ? 'custom-location-marker' : ''}">
            <div class="marker-pulse ${status.toLowerCase()}"></div>
            <div class="marker-dot ${status.toLowerCase()}"></div>
        </div>
    `;
    
    const customIcon = L.divIcon({
        html: pulseHtml,
        className: 'div-marker-icon',
        iconSize: [24, 24],
        iconAnchor: [12, 12]
    });
    
    // Remove if already exists
    if (mapMarkers[plant.id]) {
        map.removeLayer(mapMarkers[plant.id]);
    }
    
    const marker = L.marker([lat, lon], { icon: customIcon }).addTo(map);
    
    let affectedRegionsHtml = '';
    if (plant.affected_regions && plant.affected_regions.length > 0) {
        affectedRegionsHtml = '<br><strong>Affected Regions:</strong><br>' + 
            plant.affected_regions.map(r => `[${r.lat}, ${r.lon}] (${r.level})`).join('<br>');
    }

    let popupText = `
        <div class="leaflet-popup-title">${escapeHtml(plant.name)} ${isCustom ? '<span style="color: var(--color-blue); font-size: 0.65rem; font-weight: normal; margin-left: 4px;">(Searched)</span>' : ''}</div>
        <div class="leaflet-popup-desc">
            <strong>Status:</strong> ${escapeHtml(status)}<br>
            <strong>24h Rain:</strong> ${plant.summary.rain_24h || 0.0} mm<br>
            <strong>Max Wind:</strong> ${plant.summary.max_wind || 0.0} m/s${affectedRegionsHtml}
        </div>
    `;
    
    marker.bindPopup(popupText, { offset: [0, -5] });
    
    // Hover effects
    marker.on('mouseover', function(e) {
        this.openPopup();
        if (!isCustom) {
            highlightCatchmentBoundaries(plant, false);
        } else {
            drawCustomCircle(plant, false);
        }
    });
    marker.on('mouseout', function(e) {
        if (currentSelectedPlant && currentSelectedPlant.id !== plant.id) {
            if (!isCustom) {
                removePolygon(plant.id);
            } else {
                removeCustomCircle(plant.id);
            }
        }
    });
    
    // Click action
    marker.on('click', () => {
        selectPlant(plant.id);
    });
    
    mapMarkers[plant.id] = marker;

    // Draw polygon immediately so catchment area is permanently colored by alert level
    if (!isCustom) {
        highlightCatchmentBoundaries(plant, false);
    }
}

// Highlight circular area for searched custom coordinates
function drawCustomCircle(plant, isSelected = false) {
    if (mapCircles[plant.id]) {
        if (isSelected) {
            mapCircles[plant.id].setStyle({ weight: 2.5, fillOpacity: 0.15 });
        }
        return;
    }
    
    const status = plant.alert_level;
    const color = status === 'RED' ? COLORS.RED : (status === 'YELLOW' ? COLORS.YELLOW : COLORS.GREEN);
    
    // Draw 5km radius circle around pin
    const circle = L.circle([plant.lat, plant.lon], {
        radius: 5000,
        color: color,
        weight: isSelected ? 2.5 : 1.2,
        fillColor: color,
        fillOpacity: isSelected ? 0.15 : 0.05,
        dashArray: isSelected ? '' : '3, 5'
    }).addTo(map);
    
    circle.on('click', () => selectPlant(plant.id));
    mapCircles[plant.id] = circle;
}

function removeCustomCircle(plantId) {
    if (mapCircles[plantId]) {
        map.removeLayer(mapCircles[plantId]);
        delete mapCircles[plantId];
    }
}

function clearInactiveCircles() {
    Object.keys(mapCircles).forEach(id => {
        if (!currentSelectedPlant || currentSelectedPlant.id.toString() !== id.toString()) {
            removeCustomCircle(id);
        }
    });
}

function renderCustomLocationsOnInit() {
    populateCustomStationList();
    if (map) {
        customLocations.forEach(loc => {
            addMapMarker(loc, true);
        });
    }
}

// Highlight Catchment Boundaries on Map
function highlightCatchmentBoundaries(plant, isSelected = false) {
    if (mapPolygons[plant.id]) {
        if (isSelected) {
            mapPolygons[plant.id].forEach(p => {
                p.setStyle({ weight: 3.5, fillOpacity: 0.25 });
            });
        }
        return;
    }
    
    if (!plant.boundaries || plant.boundaries.length === 0) return;
    
    const status = plant.alert_level;
    const color = status === 'RED' ? COLORS.RED : (status === 'YELLOW' ? COLORS.YELLOW : COLORS.GREEN);
    
    const polygons = [];
    plant.boundaries.forEach(coords => {
        const poly = L.polygon(coords, {
            color: color,
            weight: isSelected ? 3.5 : 1.5,
            fillColor: color,
            fillOpacity: isSelected ? 0.25 : 0.08,
            dashArray: isSelected ? '' : '3, 5'
        }).addTo(map);
        
        poly.on('click', () => selectPlant(plant.id));
        polygons.push(poly);
    });
    
    mapPolygons[plant.id] = polygons;
}

// Remove boundary polygon from map (Now resets style instead of removing)
function removePolygon(plantId) {
    if (mapPolygons[plantId]) {
        mapPolygons[plantId].forEach(p => p.setStyle({ weight: 1.5, fillOpacity: 0.08 }));
    }
}

// Clear all active boundary layers that are not the selected plant
function clearInactivePolygons() {
    Object.keys(mapPolygons).forEach(id => {
        if (!currentSelectedPlant || currentSelectedPlant.id.toString() !== id.toString()) {
            removePolygon(id);
        }
    });
}

// Populate Station List in Sidebar
function populateStationList(plants) {
    const listContainer = document.getElementById('station-list');
    listContainer.innerHTML = '';
    
    plants.forEach(plant => {
        const li = document.createElement('li');
        li.className = 'station-item';
        li.id = `station-item-${plant.id}`;
        li.setAttribute('data-name', plant.name.toLowerCase());
        
        if (currentSelectedPlant && currentSelectedPlant.id === plant.id) {
            li.classList.add('active');
        }
        
        let regionsMeta = `Lat: ${plant.lat.toFixed(2)}, Lon: ${plant.lon.toFixed(2)}`;
        if (plant.affected_regions && plant.affected_regions.length > 0) {
            regionsMeta = `<div style="color: var(--color-red); font-size: 0.75rem;">Affected: ${plant.affected_regions.map(r => r.lat + ',' + r.lon).join(' | ')}</div>`;
        }

        li.innerHTML = `
            <div class="station-main">
                <span class="station-name">${escapeHtml(plant.name)}</span>
                <span class="station-meta">${regionsMeta}</span>
            </div>
            <span class="status-badge ${escapeHtml(plant.alert_level.toLowerCase())}">${escapeHtml(plant.alert_level)}</span>
        `;
        
        li.addEventListener('click', () => selectPlant(plant.id));
        listContainer.appendChild(li);
    });
}

// Search Filter Input Setup with Coordinate Parsing and Geocoding APIs
function setupSearch(plants) {
    const searchInput = document.getElementById('station-search');
    const clearSearchBtn = document.getElementById('clear-search-btn');
    const suggestionsBox = document.getElementById('search-suggestions');
    
    // Clear search button behavior
    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        clearSearchBtn.classList.add('hidden');
        suggestionsBox.classList.add('hidden');
        
        // Reset official filtering
        const items = document.querySelectorAll('#official-stations-group .station-item');
        items.forEach(item => item.classList.remove('hidden'));
        
        // Reset custom filtering
        const customItems = document.querySelectorAll('#custom-stations-group .station-item');
        customItems.forEach(item => item.classList.remove('hidden'));
    });
    
    // Hide suggestions when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-container')) {
            suggestionsBox.classList.add('hidden');
        }
    });
    
    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim().length >= 2) {
            suggestionsBox.classList.remove('hidden');
        }
    });

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.trim();
        
        if (query.length > 0) {
            clearSearchBtn.classList.remove('hidden');
        } else {
            clearSearchBtn.classList.add('hidden');
            suggestionsBox.classList.add('hidden');
        }
        
        // Local filtering
        const lowerQuery = query.toLowerCase();
        const items = document.querySelectorAll('#official-stations-group .station-item');
        items.forEach(item => {
            const name = item.getAttribute('data-name');
            if (name.includes(lowerQuery)) {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
        
        const customItems = document.querySelectorAll('#custom-stations-group .station-item');
        customItems.forEach(item => {
            const name = item.getAttribute('data-name');
            if (name.includes(lowerQuery)) {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
        
        clearTimeout(debounceTimer);
        
        if (query.length < 2) {
            suggestionsBox.innerHTML = '';
            suggestionsBox.classList.add('hidden');
            return;
        }
        
        // Debounce external queries
        debounceTimer = setTimeout(() => {
            handleSearchSuggestions(query);
        }, 400);
    });
}

function handleSearchSuggestions(query) {
    const suggestionsBox = document.getElementById('search-suggestions');
    suggestionsBox.innerHTML = '';
    suggestionsBox.classList.remove('hidden');
    
    // Check if coordinates
    const coordRegex = /^\s*(-?\d+(?:\.\d+)?)\s*[\s,]\s*(-?\d+(?:\.\d+)?)\s*$/;
    const match = query.match(coordRegex);
    
    if (match) {
        const lat = parseFloat(match[1]);
        const lon = parseFloat(match[2]);
        
        if (lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180) {
            const item = document.createElement('div');
            item.className = 'suggestion-item';
            item.innerHTML = `
                <i data-lucide="map-pin"></i>
                <div class="suggestion-details">
                    <span class="suggestion-name">Go to Coordinates</span>
                    <span class="suggestion-sub">Lat: ${lat.toFixed(4)}, Lon: ${lon.toFixed(4)}</span>
                </div>
            `;
            item.addEventListener('click', () => {
                suggestionsBox.classList.add('hidden');
                document.getElementById('station-search').value = '';
                document.getElementById('clear-search-btn').classList.add('hidden');
                fetchCustomLocationForecast(lat, lon, `Coordinates (${lat.toFixed(4)}, ${lon.toFixed(4)})`);
            });
            suggestionsBox.appendChild(item);
            lucide.createIcons();
            return;
        }
    }
    
    // Show loading
    const loadingItem = document.createElement('div');
    loadingItem.className = 'suggestion-item loading';
    loadingItem.innerHTML = `<i data-lucide="loader-2"></i><span>Searching online...</span>`;
    suggestionsBox.appendChild(loadingItem);
    lucide.createIcons();
    
    // Query Open-Meteo Geocoding API
    const geocodeUrl = `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(query)}&count=5&language=en&format=json`;
    
    fetch(geocodeUrl)
        .then(res => res.json())
        .then(data => {
            suggestionsBox.innerHTML = '';
            
            if (!data.results || data.results.length === 0) {
                const noResult = document.createElement('div');
                noResult.className = 'suggestion-item loading';
                noResult.innerHTML = `<span>No locations found</span>`;
                suggestionsBox.appendChild(noResult);
                return;
            }
            
            data.results.forEach(loc => {
                const item = document.createElement('div');
                item.className = 'suggestion-item';
                
                const locName = loc.name;
                const locSub = [loc.admin1, loc.country].filter(Boolean).join(', ');
                
                item.innerHTML = `
                    <i data-lucide="search"></i>
                    <div class="suggestion-details">
                        <span class="suggestion-name">${locName}</span>
                        <span class="suggestion-sub">${locSub} (${loc.latitude.toFixed(3)}°, ${loc.longitude.toFixed(3)}°)</span>
                    </div>
                `;
                
                item.addEventListener('click', () => {
                    suggestionsBox.classList.add('hidden');
                    document.getElementById('station-search').value = '';
                    document.getElementById('clear-search-btn').classList.add('hidden');
                    const displayName = `${locName}, ${loc.country || ''}`.trim().replace(/,\s*$/, '');
                    fetchCustomLocationForecast(loc.latitude, loc.longitude, displayName);
                });
                
                suggestionsBox.appendChild(item);
            });
            lucide.createIcons();
        })
        .catch(err => {
            console.error("Geocoding fetch error:", err);
            suggestionsBox.innerHTML = '';
            const errorItem = document.createElement('div');
            errorItem.className = 'suggestion-item loading';
            errorItem.innerHTML = `<span>Error searching locations</span>`;
            suggestionsBox.appendChild(errorItem);
            lucide.createIcons();
        });
}

function fetchCustomLocationForecast(lat, lon, name) {
    const statusBanner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    if (statusBanner) {
        statusText.innerText = 'LOADING IMD FORECAST...';
        statusBanner.className = 'alert-status-banner green animate-pulse';
    }
    
    const apiUrl = `/api/forecast?lat=${lat}&lon=${lon}&name=${encodeURIComponent(name)}`;
    
    fetch(apiUrl)
        .then(res => {
            if (!res.ok) {
                throw new Error(`Server returned status ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            const existingIdx = customLocations.findIndex(l => l.id === data.id);
            if (existingIdx !== -1) {
                customLocations[existingIdx] = data;
            } else {
                customLocations.unshift(data);
            }
            
            localStorage.setItem('nhpc_custom_locations', JSON.stringify(customLocations));
            
            addMapMarker(data, true);
            populateCustomStationList();
            selectPlant(data.id);
        })
        .catch(err => {
            console.error("Error fetching forecast:", err);
            alert(`Unable to load forecast data from IMD API: ${err.message}\n\nPlease check server logs and ensure internet connection.`);
            if (statusBanner && currentSelectedPlant) {
                updateDashboardWarningUI(currentSelectedPlant);
            }
        });
}

function populateCustomStationList() {
    const listContainer = document.getElementById('custom-station-list');
    const groupContainer = document.getElementById('custom-stations-group');
    
    listContainer.innerHTML = '';
    
    if (customLocations.length === 0) {
        groupContainer.classList.add('hidden');
        return;
    }
    
    groupContainer.classList.remove('hidden');
    
    customLocations.forEach(plant => {
        const li = document.createElement('li');
        li.className = 'station-item';
        li.id = `station-item-${plant.id}`;
        li.setAttribute('data-name', plant.name.toLowerCase());
        
        if (currentSelectedPlant && currentSelectedPlant.id === plant.id) {
            li.classList.add('active');
        }
        
        li.innerHTML = `
            <div class="station-main">
                <span class="station-name">${escapeHtml(plant.name)}</span>
                <span class="station-meta">Lat: ${plant.lat.toFixed(2)}, Lon: ${plant.lon.toFixed(2)}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
                <span class="status-badge ${escapeHtml(plant.alert_level.toLowerCase())}">${escapeHtml(plant.alert_level)}</span>
                <button class="station-delete-btn" title="Delete Location">
                    <i data-lucide="trash-2"></i>
                </button>
            </div>
        `;
        
        li.addEventListener('click', (e) => {
            if (e.target.closest('.station-delete-btn')) {
                e.stopPropagation();
                deleteCustomLocation(plant.id);
                return;
            }
            selectPlant(plant.id);
        });
        
        listContainer.appendChild(li);
    });
    
    lucide.createIcons();
}

function deleteCustomLocation(plantId) {
    customLocations = customLocations.filter(loc => loc.id !== plantId);
    localStorage.setItem('nhpc_custom_locations', JSON.stringify(customLocations));
    
    if (mapMarkers[plantId]) {
        map.removeLayer(mapMarkers[plantId]);
        delete mapMarkers[plantId];
    }
    removeCustomCircle(plantId);
    
    if (currentSelectedPlant && currentSelectedPlant.id === plantId) {
        closeDashboard();
    }
    
    populateCustomStationList();
}

function clearAllCustomLocations() {
    if (confirm("Are you sure you want to clear all searched locations?")) {
        customLocations.forEach(plant => {
            if (mapMarkers[plant.id]) {
                map.removeLayer(mapMarkers[plant.id]);
                delete mapMarkers[plant.id];
            }
            removeCustomCircle(plant.id);
        });
        
        customLocations = [];
        localStorage.removeItem('nhpc_custom_locations');
        
        if (currentSelectedPlant && currentSelectedPlant.id.toString().startsWith('custom-')) {
            closeDashboard();
        }
        
        populateCustomStationList();
    }
}

// Select Plant Action (modified for custom plants and circles support)
function selectPlant(plantId, panMap = true) {
    const data = window.FORECAST_DATA;
    const plant = data.plants.find(p => p.id === plantId) || customLocations.find(p => p.id === plantId);
    if (!plant) return;
    
    currentSelectedPlant = plant;
    const isCustom = plant.id.toString().startsWith('custom-');
    
    // 1. Update list selection UI
    document.querySelectorAll('.station-item').forEach(item => {
        item.classList.remove('active');
    });
    const selectedItem = document.getElementById(`station-item-${plantId}`);
    if (selectedItem) {
        selectedItem.classList.add('active');
        selectedItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    // 2. Clear other map shapes and highlight selected one
    clearInactivePolygons();
    clearInactiveCircles();
    if (!isCustom) {
        highlightCatchmentBoundaries(plant, true);
    } else {
        drawCustomCircle(plant, true);
    }
    
    // 3. Pan map left-offset to shift marker out from under the details slide sheet
    if (panMap && map) {
        map.setView([plant.lat, plant.lon], 7, { animate: true });
        
        const isCollapsed = document.getElementById('sidebar').classList.contains('collapsed');
        const offsetPx = isCollapsed ? -220 : -140;
        
        map.once('moveend', () => {
            map.panBy([offsetPx, 0], { animate: true, duration: 0.6 });
        });
        
        if (mapMarkers[plantId]) {
            mapMarkers[plantId].openPopup();
        }
    }
    
    // 4. Slide-in Dashboard Sheet
    const dashboard = document.getElementById('dashboard-details');
    dashboard.classList.add('active');
    
    // 5. Update content
    document.getElementById('selected-plant-name').innerText = plant.name;
    document.getElementById('selected-lat').innerText = plant.lat.toFixed(4);
    document.getElementById('selected-lon').innerText = plant.lon.toFixed(4);
    
    document.getElementById('val-rain-24h').innerText = `${plant.summary.rain_24h || 0.0} mm`;
    document.getElementById('val-rain-72h').innerText = `${plant.summary.rain_72h || 0.0} mm`;
    document.getElementById('val-temp-range').innerText = `${plant.summary.min_temp || 0}°-${plant.summary.max_temp || 0}°C`;
    document.getElementById('val-wind-gust').innerText = `${plant.summary.max_gust || 0.0} m/s`;
    
    updateDashboardWarningUI(plant);
    drawForecastChart();
    
    lucide.createIcons();
}

// Close/Dismiss details panel
function closeDashboard() {
    const dashboard = document.getElementById('dashboard-details');
    dashboard.classList.remove('active');
    
    // Deselect active list item
    document.querySelectorAll('.station-item').forEach(item => {
        item.classList.remove('active');
    });
    
    // Clear boundaries and silence alarms
    if (currentSelectedPlant) {
        const isCustom = currentSelectedPlant.id.toString().startsWith('custom-');
        if (!isCustom) {
            removePolygon(currentSelectedPlant.id);
        } else {
            removeCustomCircle(currentSelectedPlant.id);
        }
    }
    currentSelectedPlant = null;
    stopSirenSound();
    
    // Re-center map generally
    if (map) {
        map.setView([29.0, 80.0], 5, { animate: true });
    }
}

// Toggle Sidebar slide
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const toggleIcon = document.getElementById('sidebar-toggle-icon');
    const openBtn = document.getElementById('open-sidebar-btn');
    
    sidebar.classList.toggle('collapsed');
    
    if (sidebar.classList.contains('collapsed')) {
        openBtn.classList.remove('hidden');
    } else {
        openBtn.classList.add('hidden');
    }
    
    // Pan map to compensate for new visible area space
    if (map && currentSelectedPlant) {
        const offsetPx = sidebar.classList.contains('collapsed') ? -80 : 80;
        map.panBy([offsetPx, 0], { animate: true, duration: 0.5 });
    }
}

// Update Warning states
function updateDashboardWarningUI(plant) {
    const detailsContainer = document.getElementById('dashboard-details');
    const statusBanner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    const statusIcon = document.getElementById('status-icon');
    
    detailsContainer.classList.remove('flashing-red', 'flashing-yellow');
    
    statusBanner.className = 'alert-status-banner ' + plant.alert_level.toLowerCase();
    statusText.innerText = plant.alert_level === 'GREEN' ? 'SAFE STATUS' : (plant.alert_level === 'YELLOW' ? 'WATCH ACTIVE' : 'CRITICAL ALERT');
    statusIcon.setAttribute('data-lucide', plant.alert_level === 'GREEN' ? 'check-circle' : 'alert-triangle');
    
    const callout = document.getElementById('warning-callout');
    const warningList = document.getElementById('warning-reasons-list');
    warningList.innerHTML = '';
    
    if (plant.alert_level !== 'GREEN' && plant.reasons && plant.reasons.length > 0) {
        callout.className = 'warning-callout ' + (plant.alert_level === 'RED' ? 'red-callout' : 'yellow-callout');
        callout.classList.remove('hidden');
        plant.reasons.forEach(reason => {
            const li = document.createElement('li');
            li.innerText = reason;
            warningList.appendChild(li);
        });
        
        if (plant.alert_level === 'RED') {
            detailsContainer.classList.add('flashing-red');
        } else if (plant.alert_level === 'YELLOW') {
            detailsContainer.classList.add('flashing-yellow');
        }
        
        startSirenSound();
    } else {
        callout.classList.add('hidden');
        stopSirenSound();
    }
}

// --- WEB AUDIO API SIREN SYNTHESIS ---
function initAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

function startSirenSound() {
    if (isSirenMuted) return;
    initAudio();
    if (sirenOscillator) return;
    
    sirenOscillator = audioCtx.createOscillator();
    sirenGain = audioCtx.createGain();
    
    sirenOscillator.type = 'sawtooth';
    sirenOscillator.frequency.setValueAtTime(440, audioCtx.currentTime);
    
    sirenGain.gain.setValueAtTime(0.06, audioCtx.currentTime); // Subtle volume
    
    sirenOscillator.connect(sirenGain);
    sirenGain.connect(audioCtx.destination);
    
    sirenOscillator.start();
    
    let highPitch = true;
    sirenInterval = setInterval(() => {
        if (!audioCtx || !sirenOscillator) return;
        const targetFreq = highPitch ? 600 : 380;
        sirenOscillator.frequency.exponentialRampToValueAtTime(targetFreq, audioCtx.currentTime + 0.35);
        highPitch = !highPitch;
    }, 400);
}

function stopSirenSound() {
    if (sirenInterval) {
        clearInterval(sirenInterval);
        sirenInterval = null;
    }
    if (sirenOscillator) {
        try {
            sirenOscillator.stop();
            sirenOscillator.disconnect();
        } catch (e) {}
        sirenOscillator = null;
    }
    if (sirenGain) {
        try {
            sirenGain.disconnect();
        } catch (e) {}
        sirenGain = null;
    }
}

function toggleSirenMute() {
    isSirenMuted = !isSirenMuted;
    
    const btn = document.getElementById('siren-toggle');
    const text = document.getElementById('siren-text');
    const icon = document.getElementById('siren-icon');
    
    if (isSirenMuted) {
        btn.classList.add('muted');
        text.innerText = 'Mute';
        icon.setAttribute('data-lucide', 'volume-x');
        stopSirenSound();
    } else {
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        
        btn.classList.remove('muted');
        text.innerText = 'Siren';
        icon.setAttribute('data-lucide', 'volume-2');
        
        if (currentSelectedPlant && (currentSelectedPlant.alert_level === 'RED' || currentSelectedPlant.alert_level === 'YELLOW')) {
            startSirenSound();
        }
    }
    lucide.createIcons();
}

// Chart tab toggle
function switchTab(tabId) {
    if (currentTab === tabId) return;
    
    document.getElementById('tab-temp').classList.remove('active');
    document.getElementById('tab-rain').classList.remove('active');
    
    if (tabId === 'temp-tab') {
        document.getElementById('tab-temp').classList.add('active');
    } else {
        document.getElementById('tab-rain').classList.add('active');
    }
    
    currentTab = tabId;
    drawForecastChart();
}

// Draw weather forecast chart using Chart.js
function drawForecastChart() {
    if (!currentSelectedPlant || !currentSelectedPlant.forecast) return;
    
    const forecast = currentSelectedPlant.forecast;
    const ctx = document.getElementById('forecastChart').getContext('2d');
    
    if (currentChart) {
        currentChart.destroy();
    }
    
    const formattedLabels = forecast.times.map(t => {
        const dateObj = new Date(t);
        const day = dateObj.getDate();
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const month = months[dateObj.getMonth()];
        const hrs = String(dateObj.getHours()).padStart(2, '0');
        const mins = String(dateObj.getMinutes()).padStart(2, '0');
        return `${day} ${month} ${hrs}:${mins}`;
    });
    
    let datasets = [];
    let options = {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
            mode: 'index',
            intersect: false
        },
        scales: {
            x: {
                grid: { color: COLORS.GRID },
                ticks: {
                    color: COLORS.TEXT,
                    font: { family: 'Outfit', size: 9 },
                    maxTicksLimit: 12
                }
            },
            y: {
                grid: { color: COLORS.GRID },
                ticks: {
                    color: COLORS.TEXT,
                    font: { family: 'Outfit', size: 10 }
                }
            }
        },
        plugins: {
            legend: {
                labels: {
                    color: '#f8fafc',
                    font: { family: 'Outfit', size: 11, weight: '500' },
                    boxWidth: 10,
                    padding: 8
                }
            },
            tooltip: {
                backgroundColor: 'rgba(10, 15, 26, 0.95)',
                titleFont: { family: 'Outfit', size: 11, weight: 'bold' },
                bodyFont: { family: 'Outfit', size: 11 },
                borderColor: COLORS.GRID,
                borderWidth: 1,
                padding: 8
            }
        }
    };
    
    if (currentTab === 'temp-tab') {
        datasets = [
            {
                label: 'Temperature (°C)',
                data: forecast.temp,
                borderColor: COLORS.YELLOW,
                backgroundColor: 'rgba(245, 158, 11, 0.05)',
                borderWidth: 2.5,
                fill: true,
                tension: 0.35,
                yAxisID: 'y'
            },
            {
                label: 'Humidity (%)',
                data: forecast.rh,
                borderColor: COLORS.BLUE,
                backgroundColor: 'rgba(56, 189, 248, 0.02)',
                borderWidth: 2,
                fill: false,
                tension: 0.35,
                yAxisID: 'y1'
            }
        ];
        
        options.scales.y1 = {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
                color: COLORS.TEXT,
                font: { family: 'Outfit', size: 10 }
            },
            min: 0,
            max: 100
        };
    } else {
        datasets = [
            {
                label: 'Precipitation (mm)',
                data: forecast.rain,
                borderColor: COLORS.BLUE,
                backgroundColor: 'rgba(56, 189, 248, 0.4)',
                borderWidth: 1,
                type: 'bar',
                yAxisID: 'y'
            },
            {
                label: 'Wind Speed (m/s)',
                data: forecast.wind_speed,
                borderColor: COLORS.GREEN,
                borderWidth: 2,
                fill: false,
                tension: 0.35,
                yAxisID: 'y1'
            },
            {
                label: 'Wind Gust (m/s)',
                data: forecast.wind_gust,
                borderColor: COLORS.RED,
                borderWidth: 1.5,
                borderDash: [3, 3],
                fill: false,
                tension: 0.35,
                yAxisID: 'y1'
            }
        ];
        
        options.scales.y1 = {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
                color: COLORS.TEXT,
                font: { family: 'Outfit', size: 10 }
            }
        };
    }
    
    currentChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: formattedLabels,
            datasets: datasets
        },
        options: options
    });
}
