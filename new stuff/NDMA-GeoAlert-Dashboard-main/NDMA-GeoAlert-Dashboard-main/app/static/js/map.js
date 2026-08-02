const map = L.map("map").setView([22.9734, 78.6569], 5);
const polygon_layers = {};
let active_layers = [];

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors"
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

const labelled_rivers = new Set();
fetch("/static/geojson/india-rivers-labels.geojson")
    .then((response) => response.json())
    .then((data) => {
        L.geoJSON(data, {
            interactive: false,

            style: {
                opacity: 0,
                weight: 0
            },

            onEachFeature(feature, layer) {
                const river_name = feature.properties.rivname;

                if (!river_name || labelled_rivers.has(river_name)) {
                    return;
                }

                labelled_rivers.add(river_name);

                layer.setText(river_name, {
                    repeat: false,
                    center: true,
                    offset: -3,

                    attributes: {
                        fill: "#2b6cb0",
                        "font-size": "10px",
                        "font-style": "italic",
                        "font-family": "Inter, sans-serif",
                        "font-weight": "600"
                    }
                });
            }
        }).addTo(map);
    })
    .catch((error) => {
        console.error("Failed to load river labels:", error);
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

const project_markers = {};

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
    map.setView([22.5937, 78.9629], 5);
}
const reset_map_button = document.getElementById("reset-map-button");
reset_map_button.addEventListener("click", reset_map_view);
