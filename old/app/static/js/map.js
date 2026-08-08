// NHPC Catchment Emergency Warning Terminal — ONLY INDIA Vector GIS Canvas & Location Controller

let map = null;
let catchmentPolygons = {};
let gridLayerGroup = null;
let projectMarkers = {};
let activeRiskFilter = 'ALL';
let currentSelectedCatchment = null;
let modalChart = null;

let currentThresholds = {
    yellow: 15.0,
    orange: 64.5,
    red: 115.6
};

let allCatchmentData = window.INITIAL_CATCHMENTS || [];
let catchmentSummary = window.INITIAL_SUMMARY || {};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    if (window.lucide) {
        lucide.createIcons();
    }

    // Escape key closes open modal dialog popups
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            closeProjectModalForce();
            closeSettingsModalForce();
        }
    });
});

function initMap() {
    // Lock map bounds strictly to India
    const southWest = L.latLng(6.0, 68.0);
    const northEast = L.latLng(37.5, 97.5);
    const indiaBounds = L.latLngBounds(southWest, northEast);

    map = L.map('map', {
        zoomControl: false,
        preferCanvas: true,
        maxBounds: indiaBounds,
        maxBoundsViscosity: 1.0,
        minZoom: 4.5,
        maxZoom: 13
    }).setView([22.9734, 78.6569], 5);

    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // Dedicated Panes for Crisp Rendering Hierarchy
    map.createPane('indiaLandPane');
    map.getPane('indiaLandPane').style.zIndex = 400;

    map.createPane('riversPane');
    map.getPane('riversPane').style.zIndex = 410;

    map.createPane('gridsPane');
    map.getPane('gridsPane').style.zIndex = 420;

    map.createPane('catchmentsPane');
    map.getPane('catchmentsPane').style.zIndex = 430;

    map.createPane('projectsPane');
    map.getPane('projectsPane').style.zIndex = 450;

    // RENDER ONLY INDIA LANDMASS POLYGON (No World Map Tiles / No Foreign Countries!)
    fetch('/static/geojson/india-composite.geojson')
        .then(res => res.json())
        .then(data => {
            const indiaLayer = L.geoJSON(data, {
                pane: 'indiaLandPane',
                interactive: false,
                style: {
                    color: '#ff9933',      // Official Saffron/Orange Boundary Line of India
                    weight: 2.5,
                    opacity: 1,
                    fillColor: '#ffffff',  // Clean White Fill for ONLY India Landmass
                    fillOpacity: 1.0
                }
            }).addTo(map);

            map.fitBounds(indiaLayer.getBounds(), { padding: [10, 10] });
        })
        .catch(err => console.error('Failed to load India landmass:', err));

    // RENDER OFFICIAL RIVERS OF INDIA OVER INDIA
    fetch('/static/geojson/india-rivers-simple.geojson')
        .then(res => res.json())
        .then(data => {
            L.geoJSON(data, {
                pane: 'riversPane',
                interactive: false,
                style: {
                    color: '#2563eb',
                    weight: 1.5,
                    opacity: 0.85
                }
            }).addTo(map);
        })
        .catch(err => console.error('Failed to load rivers overlay:', err));

    // Render Projects, Catchments & 12km Grid Squares inside India
    if (allCatchmentData && allCatchmentData.length > 0) {
        renderCatchmentsOnMap();
    } else {
        fetchCatchmentData();
    }

    // Periodic Refresh (every 30 seconds)
    setInterval(fetchCatchmentData, 30000);
}

function toggleSidebarCollapse() {
    const sidebar = document.getElementById('catchment-nav-sidebar');
    const icon = document.getElementById('sidebar-toggle-icon');
    if (!sidebar) return;

    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');

    if (icon) {
        icon.setAttribute('data-lucide', isCollapsed ? 'chevron-right' : 'chevron-left');
    }
    if (window.lucide) {
        lucide.createIcons();
    }

    setTimeout(() => {
        if (map) map.invalidateSize();
    }, 280);
}

function fetchCatchmentData() {
    fetch('/api/v1/catchments/status')
        .then(res => res.json())
        .then(data => {
            if (data && data.catchments) {
                allCatchmentData = data.catchments;
                catchmentSummary = data.summary;
                updateSummaryTopBar();
                renderCatchmentsOnMap();
            }
        })
        .catch(err => console.warn('Error polling catchment status:', err));
}

function updateSummaryTopBar() {
    if (!catchmentSummary) return;
    document.getElementById('stat-total-catchments').innerText = catchmentSummary.total_catchments || 27;
    document.getElementById('stat-normal-count').innerText = catchmentSummary.normal || 0;
    document.getElementById('stat-watch-count').innerText = catchmentSummary.watch || 0;
    document.getElementById('stat-warning-count').innerText = catchmentSummary.warning || 0;
    document.getElementById('stat-severe-count').innerText = catchmentSummary.severe || 0;
    document.getElementById('stat-projects-affected').innerText = catchmentSummary.projects_affected || 0;
    document.getElementById('stat-districts-affected').innerText = catchmentSummary.districts_affected || 0;
}

function renderCatchmentsOnMap() {
    // Clear existing layers
    Object.keys(catchmentPolygons).forEach(k => map.removeLayer(catchmentPolygons[k]));
    catchmentPolygons = {};

    Object.keys(projectMarkers).forEach(k => map.removeLayer(projectMarkers[k]));
    projectMarkers = {};

    if (gridLayerGroup) {
        map.removeLayer(gridLayerGroup);
    }
    gridLayerGroup = L.layerGroup([], { pane: 'gridsPane' }).addTo(map);

    allCatchmentData.forEach(c => {
        if (!c.coordinates || c.coordinates.length < 3) return;

        const risk = c.risk_level;
        let color = '#3b82f6'; // Normal (Blue)
        let fillOpacity = 0.18;
        let weight = 2.2;

        if (risk === 'Severe') {
            color = '#ef4444'; // Red
            fillOpacity = 0.32;
            weight = 2.8;
        } else if (risk === 'Warning') {
            color = '#f97316'; // Orange
            fillOpacity = 0.28;
            weight = 2.5;
        } else if (risk === 'Watch') {
            color = '#eab308'; // Yellow
            fillOpacity = 0.24;
            weight = 2.3;
        }

        // Render 12km x 12km Grid Squares inside Catchment
        if (c.grid_cells && c.grid_cells.length > 0) {
            c.grid_cells.forEach(g => {
                let gColor = '#3b82f6';
                let gOpacity = 0.18;
                if (g.alert_level === 'RED') {
                    gColor = '#ef4444';
                    gOpacity = 0.48;
                } else if (g.alert_level === 'ORANGE') {
                    gColor = '#f97316';
                    gOpacity = 0.40;
                } else if (g.alert_level === 'YELLOW') {
                    gColor = '#eab308';
                    gOpacity = 0.32;
                }

                const gridPoly = L.polygon(g.coordinates, {
                    pane: 'gridsPane',
                    color: gColor,
                    weight: 1.0,
                    opacity: 0.55,
                    fillColor: gColor,
                    fillOpacity: gOpacity,
                    dashArray: '2, 3'
                });

                gridPoly.bindTooltip(`
                    <div class="catchment-leaflet-tooltip">
                        <span class="tooltip-title" style="color: ${gColor};">[GRID ${g.alert_level}] ${g.grid_id}</span>
                        <span class="tooltip-sub">Project: <strong>${c.catchment_name}</strong></span><br>
                        <span class="tooltip-sub">24h Rain: <strong>${g.weather.rain_24h_mm} mm</strong></span><br>
                        <span class="tooltip-sub">Temp: <strong>${g.weather.temperature_c} °C</strong> | Wind: <strong>${g.weather.wind_speed_kmh} km/h ${g.weather.wind_direction}</strong></span>
                    </div>
                `, { permanent: false, direction: 'top', sticky: true });

                gridPoly.on('click', () => openProjectModal(c.catchment_name));
                gridLayerGroup.addLayer(gridPoly);
            });
        }

        // Catchment Boundary Polygon
        const polygon = L.polygon(c.coordinates, {
            pane: 'catchmentsPane',
            color: color,
            weight: weight,
            opacity: 0.90,
            fillColor: color,
            fillOpacity: fillOpacity,
            lineJoin: 'round',
            lineCap: 'round'
        }).addTo(map);

        polygon.bindTooltip(`
            <div class="catchment-leaflet-tooltip">
                <span class="tooltip-title" style="color: ${color};">[${risk.toUpperCase()}] ${c.catchment_name}</span>
                <span class="tooltip-sub">River System: <strong>${c.river}</strong></span><br>
                <span class="tooltip-sub">12km Grid Count: <strong>${c.grid_summary ? c.grid_summary.total_grids : 0} Grids</strong></span><br>
                <span class="tooltip-sub">Peak 24h Rain: <strong>${c.rainfall_forecast.rain_24h_mm} mm</strong></span>
            </div>
        `, { permanent: false, direction: 'top', sticky: true });

        polygon.on('click', () => openProjectModal(c.catchment_name));
        catchmentPolygons[c.catchment_name] = polygon;

        // Project Location Marker (Teardrop Marker)
        if (c.centroid && c.centroid.lat && c.centroid.lon) {
            const markerColor = color;
            const markerStyle = `
                background-color: ${markerColor};
                width: 1.25rem;
                height: 1.25rem;
                border-radius: 2rem 2rem 0;
                transform: rotate(45deg);
                border: 2px solid #FFFFFF;
                box-shadow: 0 2px 6px rgba(0,0,0,0.35);
            `;

            const projectIcon = L.divIcon({
                className: "project-icon-marker",
                iconSize: [20, 20],
                iconAnchor: [10, 20],
                popupAnchor: [0, -20],
                html: `<div style="${markerStyle}"></div>`
            });

            const marker = L.marker([c.centroid.lat, c.centroid.lon], {
                icon: projectIcon,
                pane: 'projectsPane'
            }).addTo(map);

            marker.bindTooltip(`
                <div class="catchment-leaflet-tooltip">
                    <span class="tooltip-title" style="color: ${color};">${c.catchment_name}</span>
                    <span class="tooltip-sub">River: <strong>${c.river}</strong></span><br>
                    <span class="tooltip-sub">Location: <strong>${c.district}, ${c.state}</strong></span><br>
                    <span class="tooltip-sub">Peak 24h Rain: <strong>${c.rainfall_forecast.rain_24h_mm} mm</strong></span>
                </div>
            `, { permanent: false, direction: 'top' });

            marker.on('click', () => openProjectModal(c.catchment_name));
            projectMarkers[c.catchment_name] = marker;
        }
    });
}

function zoomToProjectOnMap(catchmentName) {
    const poly = catchmentPolygons[catchmentName];
    if (poly) {
        map.fitBounds(poly.getBounds(), { padding: [50, 50], maxZoom: 11, animate: true });
        currentSelectedCatchment = catchmentName;
    }
}

function openProjectModal(catchmentName) {
    const c = allCatchmentData.find(x => x.catchment_name === catchmentName);
    if (!c) return;

    currentSelectedCatchment = catchmentName;
    zoomToProjectOnMap(catchmentName);

    document.getElementById('modal-project-name').innerText = c.catchment_name;
    document.getElementById('modal-catchment-id').innerText = c.catchment_id;
    document.getElementById('modal-river-state').innerText = `${c.river} • ${c.district}, ${c.state}`;

    const badge = document.getElementById('modal-risk-badge');
    badge.innerText = c.risk_level.toUpperCase();
    badge.className = `risk-badge badge-${c.risk_level.toLowerCase()}`;

    // Detailed Weather Parameters with Explicit Units
    document.getElementById('modal-weather-condition').innerText = c.weather.condition;
    document.getElementById('modal-rain-24h').innerText = `${c.rainfall_forecast.rain_24h_mm} mm`;
    document.getElementById('modal-wind-speed').innerText = `${c.weather.wind_speed_kmh} km/h ${c.weather.wind_direction || ''}`;
    document.getElementById('modal-temp-humidity').innerText = `${c.weather.temperature_c} °C / ${c.weather.humidity_percent}%`;
    document.getElementById('modal-pressure').innerText = `${c.weather.pressure_hpa} hPa`;
    document.getElementById('modal-cloud-cover').innerText = `${c.weather.cloud_cover_percent}%`;

    // 12km Grid Breakdown Stats
    if (c.grid_summary) {
        document.getElementById('modal-grid-total').innerText = `${c.grid_summary.total_grids} Grids`;
        document.getElementById('modal-grid-alert-count').innerText = `${c.grid_summary.alert_grids} Grids`;
        const hEl = document.getElementById('modal-highest-grid-alert');
        hEl.innerText = c.grid_summary.highest_grid_alert;
        hEl.style.color = c.grid_summary.highest_grid_alert === 'RED' ? '#ef4444' : (c.grid_summary.highest_grid_alert === 'ORANGE' ? '#f97316' : (c.grid_summary.highest_grid_alert === 'YELLOW' ? '#eab308' : '#3b82f6'));
    }

    // Rain summary intensity
    document.getElementById('modal-max-3h').innerText = `${c.rainfall_forecast.max_3h_rain_mm} mm`;
    document.getElementById('modal-rain-72h').innerText = `${c.rainfall_forecast.rain_72h_mm} mm`;

    // Render IMD Weather & NDMA Sachet Alerts
    const alertsContainer = document.getElementById('modal-alerts-list');
    alertsContainer.innerHTML = '';
    let alertCount = 0;

    if (c.imd_alerts && c.imd_alerts.length > 0) {
        c.imd_alerts.forEach(a => {
            alertCount++;
            const imdColor = (a.alert_level === 'RED' || a.severity === 'Extreme') ? '#ef4444' : ((a.alert_level === 'ORANGE' || a.severity === 'Severe') ? '#f97316' : '#eab308');
            const div = document.createElement('div');
            div.className = 'alert-item imd-alert-card';
            div.style.borderLeft = `4px solid ${imdColor}`;
            div.style.background = (a.alert_level === 'RED') ? '#fef2f2' : ((a.alert_level === 'ORANGE') ? '#fff7ed' : '#fefce8');
            div.innerHTML = `
                <div class="alert-icon" style="color: ${imdColor};"><i data-lucide="cloud-rain"></i></div>
                <div class="alert-body">
                    <strong style="color: ${imdColor};">[IMD ${a.alert_level || 'WARNING'}] ${a.event}</strong>
                    <p style="font-weight: 700; color: #111827; margin: 2px 0;">${a.headline}</p>
                    <p style="font-size: 0.78rem; color: #374151; margin-bottom: 3px;">${a.description}</p>
                    <span class="alert-meta" style="color: #6b7280;">12km Grid NWP Forecast | Peak Rain: <strong>${a.rain_24h_mm} mm</strong></span>
                </div>
            `;
            alertsContainer.appendChild(div);
        });
    }

    if (c.ndma_alerts && c.ndma_alerts.length > 0) {
        c.ndma_alerts.forEach(a => {
            alertCount++;
            const severityColor = (a.severity === 'Severe' || a.severity === 'Extreme') ? '#dc2626' : ((a.severity === 'Warning') ? '#ea580c' : '#d97706');
            const div = document.createElement('div');
            div.className = `alert-item ndma-alert`;
            div.style.borderLeft = `4px solid ${severityColor}`;
            div.innerHTML = `
                <div class="alert-icon" style="color: ${severityColor};"><i data-lucide="alert-triangle"></i></div>
                <div class="alert-body">
                    <strong style="color: ${severityColor};">[NDMA ${a.severity.toUpperCase()}] ${a.event}</strong>
                    <p style="font-weight: 600; color: #111827;">${a.headline}</p>
                    <span class="alert-meta" style="color: #6b7280;">Distance: ${a.distance_km} km | Area: ${a.area_description}</span>
                </div>
            `;
            alertsContainer.appendChild(div);
        });
    }

    if (alertCount === 0) {
        alertsContainer.innerHTML = `<div class="empty-alerts" style="font-size: 0.78rem; color: #6b7280;">No active IMD weather warnings or emergency disaster alerts for this catchment.</div>`;
    }

    // Render 5-Day Rainfall Forecast Chart (Calendar Dates)
    renderModalChart(c.rainfall_forecast.timeline);

    // Show Modal Dialog Backdrop
    const backdrop = document.getElementById('project-modal-backdrop');
    if (backdrop) backdrop.classList.remove('hidden');

    if (window.lucide) {
        lucide.createIcons();
    }
}

function closeProjectModal(event) {
    if (event.target.id === 'project-modal-backdrop') {
        closeProjectModalForce();
    }
}

function closeProjectModalForce() {
    const backdrop = document.getElementById('project-modal-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
}

/* PER-PROJECT RAINFALL ALERT THRESHOLDS & FOOLPROOFING VALIDATION */
let projectThresholdsMap = {};

function initProjectThresholds() {
    allCatchmentData.forEach(c => {
        if (!projectThresholdsMap[c.catchment_name]) {
            projectThresholdsMap[c.catchment_name] = { yellow: 15.0, orange: 64.5, red: 115.6 };
        }
    });
}

function openSettingsModal() {
    initProjectThresholds();
    renderProjectsThresholdInputs();

    const backdrop = document.getElementById('settings-modal-backdrop');
    if (backdrop) backdrop.classList.remove('hidden');

    if (window.lucide) lucide.createIcons();
}

function closeSettingsModal(event) {
    if (event.target.id === 'settings-modal-backdrop') {
        closeSettingsModalForce();
    }
}

function closeSettingsModalForce() {
    const backdrop = document.getElementById('settings-modal-backdrop');
    if (backdrop) backdrop.classList.add('hidden');
}

function renderProjectsThresholdInputs() {
    const container = document.getElementById('projects-threshold-list');
    if (!container) return;

    container.innerHTML = '';

    allCatchmentData.forEach((c, idx) => {
        const t = projectThresholdsMap[c.catchment_name] || { yellow: 15.0, orange: 64.5, red: 115.6 };
        const card = document.createElement('div');
        card.className = 'project-threshold-card';
        card.id = `thresh-card-${idx}`;
        card.innerHTML = `
            <div class="thresh-card-top">
                <span class="risk-badge badge-${c.risk_level.toLowerCase()}">${c.risk_level.toUpperCase()}</span>
                <strong>${c.catchment_name}</strong>
                <span class="thresh-card-river">(${c.river})</span>
            </div>
            <div class="thresh-inputs-row">
                <div class="t-cell watch-border">
                    <label>Yellow (mm):</label>
                    <input type="number" id="thresh-y-${idx}" data-idx="${idx}" data-name="${c.catchment_name}" value="${t.yellow}" min="0" step="0.5" oninput="validateAllProjectThresholds()">
                </div>
                <div class="t-cell warning-border">
                    <label>Orange (mm):</label>
                    <input type="number" id="thresh-o-${idx}" data-idx="${idx}" data-name="${c.catchment_name}" value="${t.orange}" min="0" step="0.5" oninput="validateAllProjectThresholds()">
                </div>
                <div class="t-cell severe-border">
                    <label>Red (mm):</label>
                    <input type="number" id="thresh-r-${idx}" data-idx="${idx}" data-name="${c.catchment_name}" value="${t.red}" min="0" step="0.5" oninput="validateAllProjectThresholds()">
                </div>
            </div>
        `;
        container.appendChild(card);
    });

    validateAllProjectThresholds();
}

function applyGlobalToAllProjects() {
    const gy = parseFloat(document.getElementById('global-yellow').value) || 15.0;
    const go = parseFloat(document.getElementById('global-orange').value) || 64.5;
    const gr = parseFloat(document.getElementById('global-red').value) || 115.6;

    allCatchmentData.forEach((c, idx) => {
        projectThresholdsMap[c.catchment_name] = { yellow: gy, orange: go, red: gr };
        const yEl = document.getElementById(`thresh-y-${idx}`);
        const oEl = document.getElementById(`thresh-o-${idx}`);
        const rEl = document.getElementById(`thresh-r-${idx}`);
        if (yEl) yEl.value = gy;
        if (oEl) oEl.value = go;
        if (rEl) rEl.value = gr;
    });

    validateAllProjectThresholds();
}

/* FOOLPROOFING VALIDATION: 0 <= Yellow < Orange < Red */
function validateAllProjectThresholds() {
    let isValid = true;
    let errorMsg = '';

    allCatchmentData.forEach((c, idx) => {
        const yEl = document.getElementById(`thresh-y-${idx}`);
        const oEl = document.getElementById(`thresh-o-${idx}`);
        const rEl = document.getElementById(`thresh-r-${idx}`);
        const card = document.getElementById(`thresh-card-${idx}`);

        if (!yEl || !oEl || !rEl) return;

        const y = parseFloat(yEl.value);
        const o = parseFloat(oEl.value);
        const r = parseFloat(rEl.value);

        let cardValid = true;

        if (isNaN(y) || y < 0) {
            yEl.classList.add('input-invalid');
            cardValid = false;
            errorMsg = `Project "${c.catchment_name}": Yellow threshold must be a non-negative number.`;
        } else {
            yEl.classList.remove('input-invalid');
        }

        if (isNaN(o) || o <= y) {
            oEl.classList.add('input-invalid');
            cardValid = false;
            if (!errorMsg) errorMsg = `Project "${c.catchment_name}": Orange threshold (${o}mm) must be greater than Yellow threshold (${y}mm).`;
        } else {
            oEl.classList.remove('input-invalid');
        }

        if (isNaN(r) || r <= o) {
            rEl.classList.add('input-invalid');
            cardValid = false;
            if (!errorMsg) errorMsg = `Project "${c.catchment_name}": Red threshold (${r}mm) must be greater than Orange threshold (${o}mm).`;
        } else {
            rEl.classList.remove('input-invalid');
        }

        if (card) {
            if (cardValid) card.classList.remove('card-has-error');
            else card.classList.add('card-has-error');
        }

        if (!cardValid) isValid = false;
    });

    const warningBox = document.getElementById('threshold-validation-error');
    const errorText = document.getElementById('validation-error-text');
    const saveBtn = document.getElementById('save-thresholds-btn');

    if (!isValid) {
        if (warningBox) warningBox.classList.remove('hidden');
        if (errorText) errorText.innerText = `Foolproof Check Failed: ${errorMsg}`;
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.style.opacity = '0.5';
            saveBtn.style.cursor = 'not-allowed';
        }
    } else {
        if (warningBox) warningBox.classList.add('hidden');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.style.opacity = '1.0';
            saveBtn.style.cursor = 'pointer';
        }
    }

    return isValid;
}

function resetAlertThresholdsDefaults() {
    projectThresholdsMap = {};
    initProjectThresholds();
    renderProjectsThresholdInputs();
}

function applyAlertThresholds() {
    if (!validateAllProjectThresholds()) return;

    allCatchmentData.forEach((c, idx) => {
        const yEl = document.getElementById(`thresh-y-${idx}`);
        const oEl = document.getElementById(`thresh-o-${idx}`);
        const rEl = document.getElementById(`thresh-r-${idx}`);
        if (yEl && oEl && rEl) {
            projectThresholdsMap[c.catchment_name] = {
                yellow: parseFloat(yEl.value),
                orange: parseFloat(oEl.value),
                red: parseFloat(rEl.value)
            };
        }
    });

    reevaluateAllProjectAlerts();
    closeSettingsModalForce();
}

function reevaluateAllProjectAlerts() {
    let severeCount = 0;
    let warningCount = 0;
    let watchCount = 0;
    let normalCount = 0;

    allCatchmentData.forEach(c => {
        const t = projectThresholdsMap[c.catchment_name] || { yellow: 15.0, orange: 64.5, red: 115.6 };
        let maxGridAlert = 'GREEN';
        let alertGrids = 0;

        if (c.grid_cells) {
            c.grid_cells.forEach(g => {
                const r24 = g.weather ? g.weather.rain_24h_mm : 0;
                if (r24 >= t.red) {
                    g.alert_level = 'RED';
                    alertGrids++;
                    maxGridAlert = 'RED';
                } else if (r24 >= t.orange) {
                    g.alert_level = 'ORANGE';
                    alertGrids++;
                    if (maxGridAlert !== 'RED') maxGridAlert = 'ORANGE';
                } else if (r24 >= t.yellow) {
                    g.alert_level = 'YELLOW';
                    alertGrids++;
                    if (maxGridAlert !== 'RED' && maxGridAlert !== 'ORANGE') maxGridAlert = 'YELLOW';
                } else {
                    g.alert_level = 'GREEN';
                }
            });
        }

        let catRisk = 'Normal';
        const cRain = c.rainfall_forecast ? c.rainfall_forecast.rain_24h_mm : 0;
        if (maxGridAlert === 'RED' || cRain >= t.red) {
            catRisk = 'Severe';
            severeCount++;
        } else if (maxGridAlert === 'ORANGE' || cRain >= t.orange) {
            catRisk = 'Warning';
            warningCount++;
        } else if (maxGridAlert === 'YELLOW' || cRain >= t.yellow) {
            catRisk = 'Watch';
            watchCount++;
        } else {
            normalCount++;
        }

        c.risk_level = catRisk;
        if (c.grid_summary) {
            c.grid_summary.highest_grid_alert = maxGridAlert;
            c.grid_summary.alert_grids = alertGrids;
        }
    });

    catchmentSummary.severe = severeCount;
    catchmentSummary.warning = warningCount;
    catchmentSummary.watch = watchCount;
    catchmentSummary.normal = normalCount;

    updateSummaryTopBar();
    renderCatchmentsOnMap();
}

function renderModalChart(timeline) {
    const ctx = document.getElementById('modalRainChart').getContext('2d');
    if (modalChart) modalChart.destroy();

    const labels = timeline.map(t => t.date || t.day);
    const rainData = timeline.map(t => t.rain_mm);

    modalChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Rain (mm)',
                data: rainData,
                backgroundColor: 'rgba(31, 41, 55, 0.80)',
                borderColor: '#111827',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { ticks: { color: '#495057', font: { size: 10 } }, grid: { color: '#e9ecef' } },
                y: { ticks: { color: '#495057', font: { size: 10 } }, grid: { color: '#e9ecef' }, beginAtZero: true }
            }
        }
    });
}

function filterCatchmentList() {
    const query = (document.getElementById('catchment-search-input').value || '').toLowerCase();
    
    document.querySelectorAll('.catchment-card').forEach(card => {
        const text = card.innerText.toLowerCase();
        const matchesQuery = text.includes(query);
        const riskClass = card.className.match(/risk-(\w+)/);
        const risk = riskClass ? riskClass[1] : '';
        
        let matchesRisk = true;
        if (activeRiskFilter === 'AFFECTED') {
            matchesRisk = (risk.toLowerCase() !== 'normal');
        } else if (activeRiskFilter !== 'ALL') {
            matchesRisk = (risk.toLowerCase() === activeRiskFilter.toLowerCase());
        }

        card.style.display = (matchesQuery && matchesRisk) ? 'block' : 'none';
    });

    allCatchmentData.forEach(c => {
        const poly = catchmentPolygons[c.catchment_name];
        if (!poly) return;

        const matchesQuery = c.catchment_name.toLowerCase().includes(query) || c.river.toLowerCase().includes(query) || c.district.toLowerCase().includes(query);
        let matchesRisk = true;
        if (activeRiskFilter === 'AFFECTED') {
            matchesRisk = (c.risk_level.toLowerCase() !== 'normal');
        } else if (activeRiskFilter !== 'ALL') {
            matchesRisk = (c.risk_level.toLowerCase() === activeRiskFilter.toLowerCase());
        }

        if (matchesQuery && matchesRisk) {
            poly.addTo(map);
            if (projectMarkers[c.catchment_name]) projectMarkers[c.catchment_name].addTo(map);
        } else {
            map.removeLayer(poly);
            if (projectMarkers[c.catchment_name]) map.removeLayer(projectMarkers[c.catchment_name]);
        }
    });
}

function setRiskFilter(riskLevel) {
    activeRiskFilter = riskLevel;

    document.querySelectorAll('.risk-filter-pills .pill-btn').forEach(btn => {
        if (btn.getAttribute('data-risk') === riskLevel) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    document.querySelectorAll('.catchment-top-bar .catchment-stat-card').forEach(card => {
        card.classList.remove('active');
    });

    if (riskLevel === 'ALL') {
        document.querySelector('.card-total')?.classList.add('active');
    } else if (riskLevel === 'Normal') {
        document.querySelector('.card-normal')?.classList.add('active');
    } else if (riskLevel === 'Watch') {
        document.querySelector('.card-watch')?.classList.add('active');
    } else if (riskLevel === 'Warning') {
        document.querySelector('.card-warning')?.classList.add('active');
    } else if (riskLevel === 'Severe') {
        document.querySelector('.card-severe')?.classList.add('active');
    } else if (riskLevel === 'AFFECTED') {
        document.querySelector('.card-projects')?.classList.add('active');
        document.querySelector('.card-districts')?.classList.add('active');
    }

    filterCatchmentList();
}

function switchSidebarTab(tabName) {
    document.querySelectorAll('.sidebar-tab-switches .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

    document.getElementById(`tab-btn-${tabName}`).classList.add('active');
    document.getElementById(`tab-content-${tabName}`).classList.add('active');
}
