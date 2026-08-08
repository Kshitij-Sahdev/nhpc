function locate_project(project_name) {
    if (!window.map || !project_name) return;

    const pname = project_name.trim();

    // Helper to normalize names for reliable comparison
    const norm = (str) => {
        if (!str) return "";
        return str
            .toLowerCase()
            .replace(/[^a-z0-9]/g, "")
            .replace("hep", "")
            .replace("powerstation", "")
            .replace("multipurposeproject", "")
            .replace("hydroelectricproject", "")
            .replace("catchment", "")
            .replace("area", "")
            .replace("corrected", "")
            .trim();
    };

    const search_norm = norm(pname);

    // 1. Check direct project markers
    if (window.project_markers) {
        for (const name in window.project_markers) {
            const n_name = norm(name);
            if (n_name === search_norm || n_name.includes(search_norm) || search_norm.includes(n_name)) {
                const marker = window.project_markers[name];
                if (marker && marker.getLatLng) {
                    window.map.flyTo(marker.getLatLng(), 11, { animate: true, duration: 1 });
                    marker.openPopup();
                    return;
                }
            }
        }
    }

    // 2. Check catchment polygon layers
    if (window.catchment_layers) {
        for (const name in window.catchment_layers) {
            const n_name = norm(name);
            if (n_name === search_norm || n_name.includes(search_norm) || search_norm.includes(n_name)) {
                const layer = window.catchment_layers[name];
                if (layer && layer.getBounds) {
                    const bounds = layer.getBounds();
                    window.map.flyToBounds(bounds, { maxZoom: 11, animate: true, duration: 1 });
                    layer.openPopup();
                    return;
                }
            }
        }
    }

    // 3. Fallback: Search in project_sites array directly
    if (typeof project_sites !== "undefined" && Array.isArray(project_sites)) {
        const site = project_sites.find((s) => {
            const n_s = norm(s.project_name);
            return n_s.includes(search_norm) || search_norm.includes(n_s);
        });
        if (site && site.lat && site.lng) {
            window.map.flyTo([site.lat, site.lng], 11, { animate: true, duration: 1 });
        }
    }
}

// Global click event for all .project-locate-button map pin buttons
document.addEventListener("click", (event) => {
    const btn = event.target.closest(".project-locate-button");
    if (btn) {
        event.preventDefault();
        event.stopPropagation();
        const pname = btn.getAttribute("data-project-name");
        if (pname) {
            locate_project(pname);
        }
        return;
    }

    if (event.target.classList.contains("project-tag")) {
        const project_id = event.target.dataset.projectId;
        if (typeof switch_tab === "function") switch_tab("projects");
        document
            .querySelector(`.project-card[data-project-id="${project_id}"]`)
            ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }
});
