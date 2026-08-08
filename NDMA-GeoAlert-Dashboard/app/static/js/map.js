const southWest = L.latLng(6.0, 68.0);
const northEast = L.latLng(37.5, 97.5);
const indiaBounds = L.latLngBounds(southWest, northEast);

const map = L.map("map", {
    maxBounds: indiaBounds,
    maxBoundsViscosity: 1.0,
    minZoom: 5
}).fitBounds(indiaBounds);

const polygon_layers = {};
let active_layers = [];

L.tileLayer("https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png", {
    attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a> contributors &copy; <a href=\"https://carto.com/attributions\">CARTO</a>",
    subdomains: "abcd",
    maxZoom: 19
}).addTo(map);

fetch("/static/geojson/india-composite.geojson")
    .then((response) => response.json())
    .then((data) => {
        L.geoJSON(data, {
            interactive: false,
            style: {
                color: "#ff9933",
                weight: 3,
                opacity: 1,
                fillOpacity: 0
            }
        }).addTo(map);
    })
    .catch((error) => {
        console.error("Failed to load India boundary overlay:", error);
    });

fetch("/static/geojson/india-rivers-simple.geojson")
    .then((response) => response.json())
    .then((data) => {
        L.geoJSON(data, {
            interactive: false,

            style: {
                color: "#4A90E2",
                weight: 1.5,
                opacity: 0.75
            }
        }).addTo(map);
    })
    .catch((error) => {
        console.error("Failed to load river overlay:", error);
    });

window.map = map;
window.catchment_layers = {};
window.project_markers = {};

// Load Catchments & style dynamically based on IMD 12km Catchment Alert Status
Promise.all([
    fetch("/static/geojson/catchment-nhpc.geojson").then((res) => res.json()),
    fetch("/api/ai-summary").then((res) => res.json()).catch(() => null)
])
    .then(([geojson_data, ai_summary_data]) => {
        const CANONICAL_MAP = {
            "bairasiul power station": "Baira",
            "bairasiul": "Baira",
            "siul": "Baira",
            "surangani g&d": "Baira",
            "bhaledh": "Baira",
            "baloo g&d": "Baira",
            "churi g&d": "Baira",
            "tanakpur power station": "Tanakpur",
            "tanakpurcorrected": "Tanakpur",
            "tanakpur": "Tanakpur",
            "chamera-i": "Chamera-I",
            "chamera i": "Chamera-I",
            "chamera ii": "Chamera-II",
            "chamera-ii": "Chamera-II",
            "chamera iii": "Chamera-III",
            "chamera-iii": "Chamera-III",
            "uri power station": "Uri-I",
            "uri_i": "Uri-I",
            "uri-i": "Uri-I",
            "uri-ii power station": "Uri-II",
            "uri_ii": "Uri-II",
            "uri-ii": "Uri-II",
            "tld-iv power station": "TLD-IV",
            "tld4": "TLD-IV",
            "tld-iii power station": "TLD-III",
            "teesta v power station": "Teesta-V",
            "nimmo bazgo power station": "Nimoo Bazgo",
            "nbpdam": "Nimoo Bazgo",
            "subansiri lower he project": "Subansiri Lower",
            "sublowdam": "Subansiri Lower",
            "dibang multipurpose project": "Dibang",
            "dibang catchment area": "Dibang",
            "salal ramban": "Salal",
            "salal": "Salal",
            "kishanganga power station": "Kishanganga",
            "kishanganga": "Kishanganga",
            "chutak power station": "Chutak",
            "chutakps": "Chutak"
        };

        const getCanonical = (str) => {
            if (!str) return "";
            const clean = str.trim().toLowerCase();
            if (CANONICAL_MAP[clean]) return CANONICAL_MAP[clean];
            for (const k in CANONICAL_MAP) {
                if (clean.includes(k) || k.includes(clean)) return CANONICAL_MAP[k];
            }
            return str.replace(" HEP", "").replace(" Power Station", "").replace(" POWER STATION", "").trim();
        };

        const catchment_map = {};
        if (ai_summary_data && ai_summary_data.projects) {
            ai_summary_data.projects.forEach((proj) => {
                const csummary = proj.catchment_grid_summary || {};
                const cname = getCanonical(proj.project_name || "");
                catchment_map[cname] = csummary;
                if (csummary.catchment_name) {
                    catchment_map[getCanonical(csummary.catchment_name)] = csummary;
                }
            });
        }

        L.geoJSON(geojson_data, {
            style(feature) {
                const raw_name = feature.properties ? feature.properties.Name : "";
                const cname = getCanonical(raw_name);

                const info = catchment_map[cname] || {};
                const status = info.catchment_status || "GREEN";

                let border_color = "#10b981";
                let fill_color = "#10b981";
                let opacity = 0.2;

                if (status === "RED") {
                    border_color = "#d20f39";
                    fill_color = "#d20f39";
                    opacity = 0.45;
                } else if (status === "YELLOW") {
                    border_color = "#df8e1d";
                    fill_color = "#df8e1d";
                    opacity = 0.35;
                }

                return {
                    color: border_color,
                    weight: status === "GREEN" ? 2 : 3,
                    opacity: 0.9,
                    fillColor: fill_color,
                    fillOpacity: opacity
                };
            },
            onEachFeature(feature, layer) {
                const raw_name = feature.properties ? feature.properties.Name : "";
                const cname = getCanonical(raw_name);

                if (cname) {
                    window.catchment_layers[cname] = layer;
                    window.catchment_layers[raw_name] = layer;
                }

                const info = catchment_map[cname] || {};
                const status = info.catchment_status || "GREEN";
                const max_rain_3h = info.max_predicted_rain_3h_mm !== undefined ? info.max_predicted_rain_3h_mm : "0.0";
                const max_rain_24h = info.max_predicted_rain_24h_mm !== undefined ? info.max_predicted_rain_24h_mm : "0.0";
                const max_gust = info.max_predicted_gust_m_s !== undefined ? info.max_predicted_gust_m_s : "0.0";

                let badge_bg = "#10b981";
                if (status === "RED") badge_bg = "#d20f39";
                else if (status === "YELLOW") badge_bg = "#df8e1d";

                const popup_html = `
                    <div style="font-family: sans-serif; padding: 4px;">
                        <h4 style="margin: 0 0 6px 0; color: #1e293b;">${cname} Catchment</h4>
                        <div style="margin-bottom: 6px;">
                            <span style="background: ${badge_bg}; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 11px;">
                                IMD Status: ${status}
                            </span>
                        </div>
                        <div style="font-size: 12px; color: #334155; line-height: 1.4;">
                            <b>Max 3h Rain:</b> ${max_rain_3h} mm<br>
                            <b>Max 24h Rain:</b> ${max_rain_24h} mm<br>
                            <b>Max Wind Gust:</b> ${max_gust} m/s
                        </div>
                    </div>
                `;

                layer.bindPopup(popup_html);
                layer.bindTooltip(`${cname} (${status})`, { permanent: false, direction: "center" });
            }
        }).addTo(map);

        try {
            catchment_layer_group.bringToFront();
        } catch (e) {}
        window.catchment_layer_group = catchment_layer_group;
    })
    .catch((error) => {
        console.error("Failed to load Catchment GeoJSON or IMD summary:", error);
    });

const parse_polygon = (polygon_string) => {
    return polygon_string
        .trim()
        .split(" ")
        .map((coordinate_pair) => {
            const [lat, lng] = coordinate_pair.split(",").map(Number);
            return [lat, lng];
        });
};

polygon_data.forEach((alert) => {
    if (!alert.polygons) {
        return;
    }

    polygon_layers[alert.alert_id] = [];

    const severity_colors = {
        Extreme: getComputedStyle(document.documentElement).getPropertyValue("--severity-extreme"),
        Severe: getComputedStyle(document.documentElement).getPropertyValue("--severity-severe"),
        Moderate: getComputedStyle(document.documentElement).getPropertyValue("--severity-moderate"),
        Minor: getComputedStyle(document.documentElement).getPropertyValue("--severity-minor")
    };

    let polygon_color = "";
    if (alert.severity === "Extreme") polygon_color = severity_colors["Extreme"];
    else if (alert.severity === "Severe") polygon_color = severity_colors["Severe"];
    else if (alert.severity === "Moderate") polygon_color = severity_colors["Moderate"];
    else if (alert.severity === "Minor") polygon_color = severity_colors["Minor"];
    else polygon_color = "#3388ff";

    alert.polygons.forEach((polygon) => {
        try {
            // Render on map
            const coordinates = parse_polygon(polygon);
            const polygon_layer = L.polygon(coordinates, {
                weight: 2,
                color: polygon_color,
                opacity: 0.8,
                fillOpacity: 0.2
            }).addTo(map);

            // Open associated card
            polygon_layer.on("click", () => {
                const alert_card = document.getElementById(`alert-card-${alert.alert_id}`);

                if (!alert_card) {
                    return;
                }

                document.querySelectorAll(".alert-card").forEach((card) => {
                    if (card !== alert_card) {
                        card.open = false;
                    }
                });

                alert_card.open = true;

                alert_card.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                alert_card.classList.add("alert-card-active");

                setTimeout(() => {
                    alert_card.classList.remove("alert-card-active");
                }, 1500);
            });

            polygon_layers[alert.alert_id].push(polygon_layer);
        } catch (error) {
            console.error("Polygon parse failed:", error);
        }
    });
});

document.querySelectorAll(".alert-card").forEach((card) => {
    card.addEventListener("click", () => {
        const alert_id = card.dataset.alertId;
        const layers = polygon_layers[alert_id];

        if (!layers) {
            return;
        }

        active_layers.forEach((layer) => {
            layer.setStyle({ weight: 2, fillOpacity: 0.2 });
        });
        active_layers = [];

        const combined_bounds = L.latLngBounds();
        layers.forEach((layer) => {
            layer.setStyle({ weight: 4, fillOpacity: 0.4 });
            active_layers.push(layer);
            combined_bounds.extend(layer.getBounds());
        });
        map.fitBounds(combined_bounds);
    });
});

document.querySelectorAll(".alert-card").forEach((card) => {
    card.addEventListener("toggle", () => {
        if (!card.open) {
            return;
        }

        document.querySelectorAll(".alert-card").forEach((otherCard) => {
            if (otherCard !== card) {
                otherCard.open = false;
            }
        });
    });
});

window.project_markers = window.project_markers || {};
const project_markers = window.project_markers;

project_sites.forEach((site) => {
    const marker_color = "#583470";
    const marker_style = `
        background-color: ${marker_color};
        width: 1.5rem;
        height: 1.5rem;
        border-radius: 3rem 4rem 0;
        transform: rotate(45deg);
        border: 1px solid #FFFFFF;
    `;
    const project_icon = L.divIcon({
        className: "project-icon",
        iconSize: [24, 24],
        iconAnchor: [12, 24],
        popupAnchor: [0, -24],
        html: `<div style="${marker_style}"><div/>`
    });
    const marker = L.marker([site.lat, site.lng], { icon: project_icon }).addTo(map);
    marker.bindPopup(
        `
        <b>Project Site</b>
        <br>
        ${site.project_name}
        <br>
        ID:
        ${site.project_id}
        `
    );

    project_markers[site.project_name] = marker;
});

gnd_sites.forEach((site) => {
    const marker_color = "#347058";
    const marker_style = `
        background-color: ${marker_color};
        width: 1rem;
        height: 1rem;
        border-radius: 3rem 4rem 0;
        transform: rotate(45deg);
        border: 1px solid #FFFFFF;
    `;
    const gnd_icon = L.divIcon({
        className: "gnd-icon",
        iconSize: [16, 16],
        iconAnchor: [8, 16],
        popupAnchor: [0, -16],
        html: `<div style="${marker_style}"></div>`
    });
    const marker = L.marker([site.lat, site.lng], { icon: gnd_icon }).addTo(map);
    marker.bindPopup(
        `
            <b>GND Site</b>
            <br>
            ${site.site_name}
            <br>
            Project ID:
            ${site.project_id}
            `
    );
});

const sidebar = document.getElementById("sidebar");
const toggle_button = document.getElementById("sidebar-toggle");

function is_mobile() {
    return window.innerWidth <= 768;
}

if (is_mobile()) {
    sidebar.classList.remove("sidebar-open");
}

let animation_frame;
function update_map_size() {
    map.invalidateSize({ pan: true });

    animation_frame = requestAnimationFrame(update_map_size);
}

toggle_button.addEventListener("click", () => {
    if (is_mobile()) {
        sidebar.classList.toggle("sidebar-open");
    } else {
        sidebar.classList.toggle("sidebar-hidden");
    }

    reset_map_button.classList.toggle("map-controls-hidden");
});

sidebar.addEventListener("transitionstart", update_map_size);

sidebar.addEventListener("transitionend", () => {
    cancelAnimationFrame(animation_frame);
    map.invalidateSize({ pan: true });
});

function reset_map_view() {
    map.fitBounds(indiaBounds);
}
const reset_map_button = document.getElementById("reset-map-button");
reset_map_button.addEventListener("click", reset_map_view);
