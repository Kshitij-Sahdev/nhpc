// NHPC Catchment Emergency Warning Terminal — Professional GIS & Merged Sidebar Controller

let map = null;
let catchmentPolygons = {};
let projectMarkers = {};
let ndmaLayerGroup = null;
let riverLayerGroup = null;
let activeRiskFilter = 'ALL';
let currentSelectedCatchment = null;
let catchmentChart = null;

let allCatchmentData = window.INITIAL_CATCHMENTS || [];
let catchmentSummary = window.INITIAL_SUMMARY || {};

document.addEventListener('DOMContentLoaded', () => {
    initMap();
    if (window.lucide) {
        lucide.createIcons();
    }
});

function initMap() {
    map = L.map('map', {
        zoomControl: false,
        preferCanvas: true
    }).setView([28.5, 83.5], 5);

    L.control.zoom({ position: 'bottomleft' }).addTo(map);

    // Flat Light Monochrome Base Map Tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap &copy; CARTO',
        subdomains: 'abcd',
        maxZoom: 19
    }).addTo(map);


    // Layer Panes for Hierarchy
    map.createPane('riversPane');
    map.getPane('riversPane').style.zIndex = 410;

    map.createPane('catchmentsPane');
    map.getPane('catchmentsPane').style.zIndex = 430;

    map.createPane('warningsPane');
    map.getPane('warningsPane').style.zIndex = 440;

    map.createPane('projectsPane');
    map.getPane('projectsPane').style.zIndex = 450;

    // Load & Render Clean Solid Blue River Channel Vectors (Pane 410)
    fetch('/api/v1/rivers')
        .then(r => r.json())
        .then(data => {
            if (data && data.features) {
                riverLayerGroup = L.geoJSON(data, {
                    pane: 'riversPane',
                    style: {
                        color: '#38bdf8', // Clean Solid Blue
                        weight: 2.5,
                        opacity: 0.85,
                        lineJoin: 'round',
                        lineCap: 'round'
                    },
                    onEachFeature: (feature, layer) => {
                        if (feature.properties && feature.properties.name) {
                            layer.bindTooltip(
                                `<div style="font-family: Inter, sans-serif; font-size: 0.8rem; padding: 2px;">
                                    <strong style="color: #38bdf8;">${feature.properties.name}</strong><br>
                                    <span style="font-size: 0.7rem; color: #8b949e;">${feature.properties.type || 'River Channel'}</span>
                                 </div>`, 
                                { permanent: false, direction: 'top', sticky: true }
                            );
                        }
                    }
                }).addTo(map);
            }
        })
        .catch(e => console.warn('River vector load error:', e));

    // Load Catchments & Dam Sites
    if (allCatchmentData && allCatchmentData.length > 0) {
        renderCatchmentsOnMap();
    } else {
        fetchCatchmentData();
    }

    // Live Telemetry Polling (every 30 seconds)
    setInterval(fetchCatchmentData, 30000);
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
    // Clear existing polygon layers & dam markers
    Object.keys(catchmentPolygons).forEach(k => map.removeLayer(catchmentPolygons[k]));
    catchmentPolygons = {};

    Object.keys(projectMarkers).forEach(k => map.removeLayer(projectMarkers[k]));
    projectMarkers = {};

    allCatchmentData.forEach(c => {
        if (!c.coordinates || c.coordinates.length < 3) return;

        const risk = c.risk_level;
        let color = '#3b82f6'; // Normal (Blue)
        let fillOpacity = 0.22;
        let weight = 1.8;

        if (risk === 'Severe') {
            color = '#ef4444'; // Red
            fillOpacity = 0.40;
            weight = 2.5;
        } else if (risk === 'Warning') {
            color = '#f97316'; // Orange
            fillOpacity = 0.35;
            weight = 2.2;
        } else if (risk === 'Watch') {
            color = '#eab308'; // Yellow
            fillOpacity = 0.28;
            weight = 2.0;
        }

        // Polygon Layer
        const polygon = L.polygon(c.coordinates, {
            pane: 'catchmentsPane',
            color: color,
            weight: weight,
            opacity: 0.85,
            fillColor: color,
            fillOpacity: fillOpacity,
            lineJoin: 'round',
            lineCap: 'round'
        }).addTo(map);

        // Polygon Tooltip
        polygon.bindTooltip(`
            <div class="catchment-leaflet-tooltip">
                <span class="tooltip-title" style="color: ${color};">[${risk.toUpperCase()}] ${c.catchment_name}</span>
                <span class="tooltip-sub">River: ${c.river}</span><br>
                <span class="tooltip-sub">24h Rain: ${c.rainfall_forecast.rain_24h_mm} mm</span><br>
                <span class="tooltip-sub">Reservoir Level: ${c.river_and_reservoir.reservoir_level_m} m (${c.river_and_reservoir.storage_capacity_percent}%)</span>
            </div>
        `, { permanent: false, direction: 'top', sticky: true });

        // Hover effect
        polygon.on('mouseover', function() {
            this.setStyle({ weight: weight + 1.2, fillOpacity: fillOpacity + 0.12 });
        });

        polygon.on('mouseout', function() {
            if (currentSelectedCatchment !== c.catchment_name) {
                this.setStyle({ weight: weight, fillOpacity: fillOpacity });
            }
        });

        polygon.on('click', () => {
            selectCatchment(c.catchment_name, true);
        });

        catchmentPolygons[c.catchment_name] = polygon;

        // Render Dam & Hydro Power Station Marker at exact site coordinates
        if (c.centroid && c.centroid.lat && c.centroid.lon) {
            const project = c.projects_inside && c.projects_inside.length > 0 ? c.projects_inside[0] : { capacity_mw: 0 };
            const capacityMW = project.capacity_mw || 0;
            const isDam = capacityMW > 0;
            const riskClass = risk.toLowerCase();

            const pinHtml = `
                <div class="dam-marker-pin ${riskClass}">
                    <span class="dam-title-text">${c.catchment_name.replace(' HEP', '').replace(' Power Station', '')}</span>
                    ${isDam ? `<span class="dam-mw-badge">${capacityMW} MW</span>` : ''}
                </div>
            `;

            const damIcon = L.divIcon({
                html: pinHtml,
                className: 'custom-dam-marker-icon',
                iconSize: [110, 22],
                iconAnchor: [55, 11]
            });

            const marker = L.marker([c.centroid.lat, c.centroid.lon], {
                icon: damIcon,
                pane: 'projectsPane'
            }).addTo(map);

            marker.bindTooltip(`
                <div class="catchment-leaflet-tooltip">
                    <span class="tooltip-title" style="color: ${color};">${c.catchment_name}</span>
                    <span class="tooltip-sub">River: <strong>${c.river}</strong></span><br>
                    ${isDam ? `<span class="tooltip-sub">Capacity: <strong>${capacityMW} MW</strong></span><br>` : ''}
                    <span class="tooltip-sub">FRL: <strong>${c.river_and_reservoir.frl_m} m</strong> | Reservoir: <strong>${c.river_and_reservoir.reservoir_level_m} m</strong></span><br>
                    <span class="tooltip-sub">Inflow: <strong>${c.river_and_reservoir.inflow_cumecs} m³/s</strong> | Status: <strong>${c.river_and_reservoir.dam_status}</strong></span>
                </div>
            `, { permanent: false, direction: 'top' });

            marker.on('click', () => selectCatchment(c.catchment_name, true));
            projectMarkers[c.catchment_name] = marker;
        }
    });
}

function selectCatchment(catchmentName, panTo = true) {
    const c = allCatchmentData.find(x => x.catchment_name === catchmentName);
    if (!c) return;

    currentSelectedCatchment = catchmentName;

    // Highlight selected polygon
    Object.keys(catchmentPolygons).forEach(name => {
        const poly = catchmentPolygons[name];
        const isTarget = (name === catchmentName);
        if (isTarget) {
            poly.setStyle({ weight: 3.5, opacity: 1.0, fillOpacity: 0.5 });
            poly.bringToFront();
        } else {
            const risk = (allCatchmentData.find(x => x.catchment_name === name) || {}).risk_level || 'Normal';
            const defaultColor = risk === 'Severe' ? '#ef4444' : (risk === 'Warning' ? '#f97316' : (risk === 'Watch' ? '#eab308' : '#3b82f6'));
            poly.setStyle({ color: defaultColor, weight: 1.8, opacity: 0.85, fillOpacity: 0.22 });
        }
    });

    // Zoom map to bounds
    if (panTo && catchmentPolygons[catchmentName]) {
        map.fitBounds(catchmentPolygons[catchmentName].getBounds(), { padding: [40, 40], maxZoom: 11, animate: true });
    }

    // Populate & Open Merged Catchment Detail View inside Left Sidebar
    populateSidePanel(c);
}

function populateSidePanel(c) {
    // Switch Left Sidebar from List View to Detail View
    document.getElementById('sidebar-view-list').classList.add('hidden');
    document.getElementById('sidebar-view-detail').classList.remove('hidden');

    document.getElementById('panel-catchment-name').innerText = c.catchment_name;
    document.getElementById('panel-catchment-id').innerText = c.catchment_id;
    document.getElementById('panel-river-state').innerText = `${c.river} • ${c.district}, ${c.state}`;

    const badge = document.getElementById('panel-risk-badge');
    badge.innerText = c.risk_level.toUpperCase();
    badge.className = `risk-badge badge-${c.risk_level.toLowerCase()}`;

    // Weather Telemetry
    document.getElementById('panel-weather-condition').innerText = c.weather.condition;
    document.getElementById('panel-rain-24h').innerText = `${c.rainfall_forecast.rain_24h_mm} mm`;
    document.getElementById('panel-wind-speed').innerText = `${c.weather.wind_speed_kmh} km/h`;
    document.getElementById('panel-temp-humidity').innerText = `${c.weather.temperature_c}°C / ${c.weather.humidity_percent}%`;

    // Rain summary
    document.getElementById('panel-max-3h').innerText = `${c.rainfall_forecast.max_3h_rain_mm} mm`;
    document.getElementById('panel-rain-72h').innerText = `${c.rainfall_forecast.rain_72h_mm} mm`;

    // River & Reservoir
    document.getElementById('panel-frl').innerText = `${c.river_and_reservoir.frl_m} m`;
    document.getElementById('panel-res-level').innerText = `${c.river_and_reservoir.reservoir_level_m} m (${c.river_and_reservoir.storage_capacity_percent}%)`;
    document.getElementById('panel-danger-mark').innerText = `${c.river_and_reservoir.danger_mark_m} m`;
    document.getElementById('panel-inflow').innerText = `${c.river_and_reservoir.inflow_cumecs} m³/s`;
    document.getElementById('panel-outflow').innerText = `${c.river_and_reservoir.outflow_cumecs} m³/s`;
    document.getElementById('panel-river-trend').innerText = c.river_and_reservoir.river_trend;
    
    const damStatusEl = document.getElementById('panel-dam-status');
    damStatusEl.querySelector('span').innerText = c.river_and_reservoir.dam_status;

    // Render NDMA Disaster Alerts
    const alertsContainer = document.getElementById('panel-ndma-alerts-list');
    alertsContainer.innerHTML = '';
    if (c.ndma_alerts && c.ndma_alerts.length > 0) {
        c.ndma_alerts.forEach(a => {
            const severityColor = (a.severity === 'Severe' || a.severity === 'Extreme') ? '#dc2626' : ((a.severity === 'Warning') ? '#ea580c' : '#d97706');
            const div = document.createElement('div');
            div.className = `alert-item ndma-alert`;
            div.style.borderLeft = `4px solid ${severityColor}`;
            div.innerHTML = `
                <div class="alert-icon" style="color: ${severityColor};"><i data-lucide="alert-triangle"></i></div>
                <div class="alert-body">
                    <strong style="color: ${severityColor};">[${a.severity.toUpperCase()}] ${a.event}</strong>
                    <p style="font-weight: 600; color: #111827;">${a.headline}</p>
                    <span class="alert-meta" style="color: #6b7280;">Distance: ${a.distance_km} km | Area: ${a.area_description}</span>
                </div>
            `;
            alertsContainer.appendChild(div);
        });
    } else {
        alertsContainer.innerHTML = `<div class="empty-alerts" style="font-size: 0.78rem; color: #6b7280;">No active emergency disaster alerts for this catchment.</div>`;
    }

    // Projects Inside
    const projectsList = document.getElementById('panel-projects-list');
    projectsList.innerHTML = '';
    c.projects_inside.forEach(p => {
        const li = document.createElement('li');
        li.className = 'project-item';
        li.innerHTML = `
            <strong>${p.name}</strong>
            <span>Type: ${p.type} | Installed Capacity: ${p.capacity_mw} MW</span><br>
            <span style="color: #6b7280;">Status: ${p.status}</span>
        `;
        projectsList.appendChild(li);
    });


    // Districts
    const districtsContainer = document.getElementById('panel-districts-tags');
    districtsContainer.innerHTML = '';
    (c.affected_districts || []).forEach(d => {
        const span = document.createElement('span');
        span.className = 'district-tag';
        span.innerText = d;
        districtsContainer.appendChild(span);
    });

    document.getElementById('panel-last-updated').innerText = c.last_updated;

    // Render 5-Day Rainfall Timeline Chart
    renderCatchmentChart(c.rainfall_forecast.timeline);

    if (window.lucide) {
        lucide.createIcons();
    }
}

function closeSidePanel() {
    // Switch Left Sidebar from Detail View back to List View
    document.getElementById('sidebar-view-detail').classList.add('hidden');
    document.getElementById('sidebar-view-list').classList.remove('hidden');

    if (currentSelectedCatchment && catchmentPolygons[currentSelectedCatchment]) {
        const risk = (allCatchmentData.find(x => x.catchment_name === currentSelectedCatchment) || {}).risk_level || 'Normal';
        const defaultColor = risk === 'Severe' ? '#ef4444' : (risk === 'Warning' ? '#f97316' : (risk === 'Watch' ? '#eab308' : '#3b82f6'));
        catchmentPolygons[currentSelectedCatchment].setStyle({ color: defaultColor, weight: 1.8, fillOpacity: 0.22 });
    }
    currentSelectedCatchment = null;
}

function renderCatchmentChart(timeline) {
    const ctx = document.getElementById('catchmentRainChart').getContext('2d');
    if (catchmentChart) catchmentChart.destroy();

    const labels = timeline.map(t => t.day);
    const rainData = timeline.map(t => t.rain_mm);

    catchmentChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Predicted Rain (mm)',
                data: rainData,
                backgroundColor: 'rgba(31, 41, 55, 0.75)',
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
    
    // Filter list
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

    // Filter map polygons & markers
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

    // Update risk filter pills state
    document.querySelectorAll('.risk-filter-pills .pill-btn').forEach(btn => {
        if (btn.getAttribute('data-risk') === riskLevel) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Update top stat cards state
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

    // Make sure we are in list view when filtering
    closeSidePanel();

    filterCatchmentList();
}

function switchSidebarTab(tabName) {
    document.querySelectorAll('.sidebar-tab-switches .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

    document.getElementById(`tab-btn-${tabName}`).classList.add('active');
    document.getElementById(`tab-content-${tabName}`).classList.add('active');
}
