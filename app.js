// NHPC Weather Warning System - Frontend Controller

// State variables
let currentSelectedPlant = null;
let currentChart = null;
let currentTab = 'temp-tab'; // temp-tab or rain-tab
let map = null;
let mapMarkers = {};
let mapPolygons = {};

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
    BLUE: '#3b82f6',
    PURPLE: '#8b5cf6',
    GRID: 'rgba(255, 255, 255, 0.05)',
    TEXT: '#9ca3af'
};

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Lucide Icons
    lucide.createIcons();
    
    // Check if data is loaded
    if (!window.FORECAST_DATA) {
        console.error("Forecast data (forecast_data.js) is missing or failed to load.");
        alert("Error: Weather forecast data could not be found. Please ensure update_forecasts.py was run.");
        return;
    }
    
    // Initialize Dashboard UI with initial data
    updateDashboardUI(window.FORECAST_DATA);
    
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
    document.getElementById('station-count').innerText = data.plants.length;
    
    // Sort plants: Red first, then Yellow, then Green, then alphabetically by name
    const sortedPlants = [...data.plants].sort((a, b) => {
        const priority = { 'RED': 1, 'YELLOW': 2, 'GREEN': 3, 'UNKNOWN': 4 };
        const statusDiff = priority[a.alert_level] - priority[b.alert_level];
        if (statusDiff !== 0) return statusDiff;
        return a.name.localeCompare(b.name);
    });
    
    // Initialize map if it hasn't been initialized yet
    if (!map) {
        initMap(data.plants);
    } else {
        // Update markers if map already exists
        data.plants.forEach(plant => {
            if (mapMarkers[plant.id]) {
                // Update popup info in case of new forecast readings
                let popupText = `
                    <div class="leaflet-popup-title">${plant.name}</div>
                    <div class="leaflet-popup-desc">
                        <strong>Status:</strong> ${plant.alert_level}<br>
                        <strong>24h Rain:</strong> ${plant.summary.rain_24h || 0.0} mm<br>
                        <strong>Max Wind:</strong> ${plant.summary.max_wind || 0.0} m/s
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
    
    // Set initial selection if none is selected
    if (!currentSelectedPlant) {
        const initialSelection = sortedPlants.find(p => p.alert_level === 'RED') || 
                                  sortedPlants.find(p => p.alert_level === 'YELLOW') || 
                                  sortedPlants[0];
        if (initialSelection) {
            selectPlant(initialSelection.id);
        }
    }
}

// Dynamic polling to check for data updates without page refresh
function startAutoPolling() {
    setInterval(() => {
        console.log("Checking for background forecast updates...");
        
        // Remove old script tag to prevent piling
        const oldScript = document.querySelector('script[src^="forecast_data.js"]');
        if (oldScript) {
            oldScript.remove();
        }
        
        // Append a new script tag with cache buster
        const newScript = document.createElement('script');
        newScript.src = `forecast_data.js?t=${new Date().getTime()}`;
        newScript.onload = () => {
            const data = window.FORECAST_DATA;
            if (data) {
                // Check if data timestamp has actually changed
                const currentTimestamp = document.getElementById('update-timestamp').innerText;
                if (data.generated_at !== currentTimestamp) {
                    console.log("New forecast data detected! Re-rendering dashboard...");
                    updateDashboardUI(data);
                    
                    // Update active selected plant parameters
                    if (currentSelectedPlant) {
                        const updatedSelected = data.plants.find(p => p.id === currentSelectedPlant.id);
                        if (updatedSelected) {
                            selectPlant(updatedSelected.id, false); // select without panning map again
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
    // Center map roughly over northern India where most NHPC hydro stations are located
    map = L.map('map', {
        zoomControl: false
    }).setView([29.0, 79.0], 5);
    
    // Add custom zoom control position
    L.control.zoom({ position: 'topright' }).addTo(map);
    
    // Dark mode maps: CartoDB Dark Matter
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);
    
    // Create markers for each plant
    plants.forEach(plant => {
        const lat = plant.lat;
        const lon = plant.lon;
        const status = plant.alert_level;
        
        // Custom HTML marker using L.divIcon for pulsing effect
        const pulseHtml = `
            <div class="custom-marker">
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
        
        const marker = L.marker([lat, lon], { icon: customIcon }).addTo(map);
        
        // Construct popup text
        let popupText = `
            <div class="leaflet-popup-title">${plant.name}</div>
            <div class="leaflet-popup-desc">
                <strong>Status:</strong> ${status}<br>
                <strong>24h Rain:</strong> ${plant.summary.rain_24h || 0.0} mm<br>
                <strong>Max Wind:</strong> ${plant.summary.max_wind || 0.0} m/s
            </div>
        `;
        
        marker.bindPopup(popupText, { offset: [0, -5] });
        
        // Hover effects
        marker.on('mouseover', function(e) {
            this.openPopup();
            highlightCatchmentBoundaries(plant, false);
        });
        marker.on('mouseout', function(e) {
            if (currentSelectedPlant && currentSelectedPlant.id !== plant.id) {
                removePolygon(plant.id);
            }
        });
        
        // Click action
        marker.on('click', () => {
            selectPlant(plant.id);
        });
        
        mapMarkers[plant.id] = marker;
    });
}

// Highlight Catchment Boundaries on Map
function highlightCatchmentBoundaries(plant, isSelected = false) {
    if (mapPolygons[plant.id]) {
        if (isSelected) {
            mapPolygons[plant.id].forEach(p => {
                p.setStyle({ weight: 3, fillOpacity: 0.25 });
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
            weight: isSelected ? 3 : 1.5,
            fillColor: color,
            fillOpacity: isSelected ? 0.25 : 0.08,
            dashArray: isSelected ? '' : '3, 5'
        }).addTo(map);
        
        poly.on('click', () => selectPlant(plant.id));
        polygons.push(poly);
    });
    
    mapPolygons[plant.id] = polygons;
}

// Remove boundary polygon from map
function removePolygon(plantId) {
    if (mapPolygons[plantId]) {
        mapPolygons[plantId].forEach(p => map.removeLayer(p));
        delete mapPolygons[plantId];
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
        
        // Active class recovery
        if (currentSelectedPlant && currentSelectedPlant.id === plant.id) {
            li.classList.add('active');
        }
        
        li.innerHTML = `
            <div class="station-main">
                <span class="station-name">${plant.name}</span>
                <span class="station-meta">Lat: ${plant.lat.toFixed(2)}, Lon: ${plant.lon.toFixed(2)}</span>
            </div>
            <span class="status-badge ${plant.alert_level.toLowerCase()}">${plant.alert_level}</span>
        `;
        
        li.addEventListener('click', () => selectPlant(plant.id));
        listContainer.appendChild(li);
    });
}

// Search Filter Input Setup
function setupSearch(plants) {
    const searchInput = document.getElementById('station-search');
    
    // Detach old listeners
    const newSearchInput = searchInput.cloneNode(true);
    searchInput.parentNode.replaceChild(newSearchInput, searchInput);
    
    newSearchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        const items = document.querySelectorAll('.station-item');
        
        items.forEach(item => {
            const name = item.getAttribute('data-name');
            if (name.includes(query)) {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
    });
}

// Select Plant Action
function selectPlant(plantId, panMap = true) {
    const data = window.FORECAST_DATA;
    const plant = data.plants.find(p => p.id === plantId);
    if (!plant) return;
    
    currentSelectedPlant = plant;
    
    // 1. Update list selection UI
    document.querySelectorAll('.station-item').forEach(item => {
        item.classList.remove('active');
    });
    const selectedItem = document.getElementById(`station-item-${plantId}`);
    if (selectedItem) {
        selectedItem.classList.add('active');
    }
    
    // 2. Clear other map polygons and highlight selected one
    clearInactivePolygons();
    highlightCatchmentBoundaries(plant, true);
    
    // 3. Pan map if requested
    if (panMap && map) {
        map.setView([plant.lat, plant.lon], 7, { animate: true, duration: 0.8 });
        if (mapMarkers[plantId]) {
            mapMarkers[plantId].openPopup();
        }
    }
    
    // 4. Update Details Dashboard Content
    document.getElementById('no-selection').classList.add('hidden');
    document.getElementById('active-dashboard').classList.remove('hidden');
    
    document.getElementById('selected-plant-name').innerText = plant.name;
    document.getElementById('selected-lat').innerText = plant.lat.toFixed(4);
    document.getElementById('selected-lon').innerText = plant.lon.toFixed(4);
    
    // Metrics updates
    document.getElementById('val-rain-24h').innerText = `${plant.summary.rain_24h || 0.0} mm`;
    document.getElementById('val-rain-72h').innerText = `${plant.summary.rain_72h || 0.0} mm`;
    document.getElementById('val-temp-range').innerText = `${plant.summary.min_temp || 0}° - ${plant.summary.max_temp || 0}°C`;
    document.getElementById('val-wind-gust').innerText = `${plant.summary.max_gust || 0.0} m/s`;
    
    // Update Warnings and Alarm sound triggers
    updateDashboardWarningUI(plant);
    
    // Redraw charts
    drawForecastChart();
    
    // Re-trigger Lucide Icons inside dynamic content
    lucide.createIcons();
}

// Update Warning Banner, flasher style, and audio siren
function updateDashboardWarningUI(plant) {
    const detailsContainer = document.getElementById('dashboard-details');
    const statusBanner = document.getElementById('status-banner');
    const statusText = document.getElementById('status-text');
    const statusIcon = document.getElementById('status-icon');
    
    // Reset flashing alert classes
    detailsContainer.classList.remove('flashing-red', 'flashing-yellow');
    
    // Status banner update
    statusBanner.className = 'alert-status-banner ' + plant.alert_level.toLowerCase();
    statusText.innerText = plant.alert_level === 'GREEN' ? 'SAFE STATUS' : (plant.alert_level === 'YELLOW' ? 'YELLOW WATCH' : 'RED WARNING ALERT');
    statusIcon.setAttribute('data-lucide', plant.alert_level === 'GREEN' ? 'check-circle' : 'alert-triangle');
    
    // Warning Callout Box (heavy rainfall details)
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
        
        // Add flashing effect
        if (plant.alert_level === 'RED') {
            detailsContainer.classList.add('flashing-red');
        } else if (plant.alert_level === 'YELLOW') {
            detailsContainer.classList.add('flashing-yellow');
        }
        
        // Fire Audio Alarm!
        startSirenSound();
    } else {
        callout.classList.add('hidden');
        // Stop Audio Alarm!
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
    if (sirenOscillator) return; // Already running
    
    sirenOscillator = audioCtx.createOscillator();
    sirenGain = audioCtx.createGain();
    
    sirenOscillator.type = 'sawtooth';
    sirenOscillator.frequency.setValueAtTime(440, audioCtx.currentTime); // Standard pitch
    
    sirenGain.gain.setValueAtTime(0.08, audioCtx.currentTime); // Low moderate volume
    
    sirenOscillator.connect(sirenGain);
    sirenGain.connect(audioCtx.destination);
    
    sirenOscillator.start();
    
    // Oscillate pitch between 350Hz and 650Hz every 0.4 seconds to create a wailing siren
    let highPitch = true;
    sirenInterval = setInterval(() => {
        if (!audioCtx || !sirenOscillator) return;
        const targetFreq = highPitch ? 650 : 350;
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
        text.innerText = 'Siren Muted';
        icon.setAttribute('data-lucide', 'volume-x');
        stopSirenSound();
    } else {
        // Safari and Chrome require user gestures to resume Audio Context
        if (audioCtx && audioCtx.state === 'suspended') {
            audioCtx.resume();
        }
        
        btn.classList.remove('muted');
        text.innerText = 'Siren Enabled';
        icon.setAttribute('data-lucide', 'volume-2');
        
        // Trigger sound if active plant is currently on RED/YELLOW alert
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
                    font: { family: 'Outfit', size: 10 },
                    maxTicksLimit: 12
                }
            },
            y: {
                grid: { color: COLORS.GRID },
                ticks: {
                    color: COLORS.TEXT,
                    font: { family: 'Outfit', size: 11 }
                }
            }
        },
        plugins: {
            legend: {
                labels: {
                    color: '#f3f4f6',
                    font: { family: 'Outfit', size: 12, weight: '500' }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(13, 19, 33, 0.95)',
                titleFont: { family: 'Outfit', size: 12, weight: 'bold' },
                bodyFont: { family: 'Outfit', size: 12 },
                borderColor: COLORS.GRID,
                borderWidth: 1,
                padding: 10
            }
        }
    };
    
    if (currentTab === 'temp-tab') {
        datasets = [
            {
                label: 'Temperature (°C)',
                data: forecast.temp,
                borderColor: COLORS.YELLOW,
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.3,
                yAxisID: 'y'
            },
            {
                label: 'Relative Humidity (%)',
                data: forecast.rh,
                borderColor: COLORS.BLUE,
                backgroundColor: 'rgba(59, 130, 246, 0.05)',
                borderWidth: 2,
                fill: false,
                tension: 0.3,
                yAxisID: 'y1'
            }
        ];
        
        options.scales.y1 = {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
                color: COLORS.TEXT,
                font: { family: 'Outfit', size: 11 }
            },
            min: 0,
            max: 100
        };
    } else {
        datasets = [
            {
                label: '3h Rainfall (mm)',
                data: forecast.rain,
                borderColor: COLORS.BLUE,
                backgroundColor: 'rgba(59, 130, 246, 0.45)',
                borderWidth: 1.5,
                type: 'bar',
                yAxisID: 'y'
            },
            {
                label: 'Wind Speed (m/s)',
                data: forecast.wind_speed,
                borderColor: COLORS.GREEN,
                borderWidth: 2,
                fill: false,
                tension: 0.3,
                yAxisID: 'y1'
            },
            {
                label: 'Wind Gust (m/s)',
                data: forecast.wind_gust,
                borderColor: COLORS.RED,
                borderWidth: 1.5,
                borderDash: [4, 4],
                fill: false,
                tension: 0.3,
                yAxisID: 'y1'
            }
        ];
        
        options.scales.y1 = {
            position: 'right',
            grid: { drawOnChartArea: false },
            ticks: {
                color: COLORS.TEXT,
                font: { family: 'Outfit', size: 11 }
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
