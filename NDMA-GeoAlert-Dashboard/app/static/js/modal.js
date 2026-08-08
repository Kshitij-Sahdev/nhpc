const alerts_by_id = {};

state_dashboard.forEach((state) => {
    state.alerts.forEach((alert) => {
        alerts_by_id[alert.alert_id] = alert;
    });
});

function renderAlertModal(alert, project_id) {
    const modal_body = document.getElementById("modal-body");

    const districts = (alert.district_names || [])
        .map((district) => `<span class="district-tag">${district}</span>`)
        .join("");

    const projects = (alert.affected_projects || [])
        .map(
            (project) =>
                `<button
                        class="project-tag"
                        data-project-id="${project.project_id}"
                    >
                        ${project.project_name}
                    </button>`
        )
        .join("");

    const linked_sites = (alert.affected_projects || []).filter((site) => site.project_id === project_id);
    const affected_sites = linked_sites
        .map((site) => `<span class="district-tag">${site.project_name}</span>`)
        .join("");

    modal_body.innerHTML = `
        <div class="alert-card modal-alert-card">
            <div class="alert-summary">
                <div class="alert-summary-left">
                    <div
                        class="severity-indicator severity-${(alert.severity || "unknown").toLowerCase()}"
                    ></div>

                    <div class="alert-summary-text">
                        <div class="alert-title-row">
                            <h3 class="alert-event">
                                ${alert.event ?? ""}
                            </h3>

                            <span class="alert-identifier">
                                ${alert.alert_identifier ?? ""}
                            </span>
                        </div>
                    </div>
                </div>

                ${
                    alert.expires
                        ? `
                        <div class="alert-summary-right">
                            <div class="alert-expiry">
                                <label>Valid Until</label>

                                <span>
                                    ${alert.expires}
                                </span>
                            </div>
                        </div>
                        `
                        : ""
                }
            </div>

            <div class="alert-details modal-alert-details">
                <div class="alert-headline-box">
                    ${alert.headline_en ?? ""}
                </div>

                <div class="detail-section">
                    <div class="detail-section-title">
                        Alert Classification
                    </div>

                    <div class="alert-detail-grid">

                        <div class="detail-item">
                            <label>Severity</label>
                            <span>${alert.severity ?? "-"}</span>
                        </div>

                        <div class="detail-item">
                            <label>Urgency</label>
                            <span>${alert.urgency ?? "-"}</span>
                        </div>

                        <div class="detail-item">
                            <label>Certainty</label>
                            <span>${alert.certainty ?? "-"}</span>
                        </div>
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-section-title">
                        Timeline
                    </div>

                    <div class="alert-detail-grid">
                        ${
                            alert.effective
                                ? `
                                <div class="detail-item">
                                    <label>Effective</label>
                                    <span>${alert.effective}</span>
                                </div>
                                `
                                : ""
                        }

                        ${
                            alert.onset
                                ? `
                                <div class="detail-item">
                                    <label>Onset</label>
                                    <span>${alert.onset}</span>
                                </div>
                                `
                                : ""
                        }

                        ${
                            alert.expires
                                ? `
                                <div class="detail-item">
                                    <label>Expires</label>
                                    <span>${alert.expires}</span>
                                </div>
                                `
                                : ""
                        }

                    </div>
                </div>

                ${
                    districts
                        ? `
                        <div class="detail-section">
                            <div class="detail-section-title">
                                Affected Districts
                            </div>

                            <div class="district-tags">
                                ${districts}
                            </div>
                        </div>
                        `
                        : ""
                }

                ${
                    affected_sites
                        ? `
                        <div class="detail-section">
                            <div class="detail-section-title">
                                Affected Linked Sites
                            </div>

                            <div class="district-tags">
                                ${affected_sites}
                            </div>
                        </div>
                        `
                        : ""
                }

                ${
                    projects
                        ? `
                        <div class="detail-section">
                            <div class="detail-section-title">
                                All Affected Projects
                            </div>

                            <div class="project-tags">
                                ${projects}
                            </div>
                        </div>
                        `
                        : ""
                }
            </div>
        </div>
    `;
}

document.querySelectorAll(".project-alert-item").forEach((button) => {
    button.addEventListener("click", async () => {
        const alert_id = Number(button.dataset.alertId);
        const project_id = Number(button.dataset.projectId);
        const alert = alerts_by_id[alert_id];
        if (!alert) {
            console.error(`Alert ${alert_id} not found`);
            return;
        }
        renderAlertModal(alert, project_id);
        document.getElementById("alert-modal").classList.add("open");
    });
});

document.getElementById("close-modal").addEventListener("click", () => {
    document.getElementById("alert-modal").classList.remove("open");
});

document.getElementById("alert-modal").addEventListener("click", (event) => {
    if (event.target.id === "alert-modal") {
        event.target.classList.remove("open");
    }
});

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        document.getElementById("alert-modal").classList.remove("open");
        const gm = document.getElementById("grid-modal");
        if (gm) gm.classList.remove("open");
    }
});

// IMD 12km Grid Modal Popup Handler
const grid_modal = document.getElementById("grid-modal");
const close_grid_modal = document.getElementById("close-grid-modal");

document.addEventListener("click", async (e) => {
    const btn = e.target.closest(".open-grid-modal-btn");
    if (!btn) return;

    e.preventDefault();
    const cname = btn.getAttribute("data-catchment-name");
    
    try {
        const res = await fetch("/api/ai-summary");
        const data = await res.json();
        const projects = data.projects || [];
        const project = projects.find(p => p.project_name.toLowerCase().includes(cname.toLowerCase()) || cname.toLowerCase().includes(p.project_name.toLowerCase())) || {};
        const csummary = project.catchment_grid_summary || {};
        const grid_warnings = csummary.grid_warnings || [];

        document.getElementById("grid-modal-title").innerText = `${cname} — 12km Grid Forecast Data`;
        document.getElementById("grid-modal-subtitle").innerText = `IMD Status: ${csummary.catchment_status || 'GREEN'} • Max 3h Rain: ${csummary.max_predicted_rain_3h_mm || 0}mm • Max 24h Rain: ${csummary.max_predicted_rain_24h_mm || 0}mm`;

        const body = document.getElementById("grid-modal-body");

        if (!grid_warnings || grid_warnings.length === 0) {
            body.innerHTML = `<div style="padding: 1rem; text-align: center; color: var(--text-secondary); background: var(--bg-secondary); border-radius: 8px;">No active grid warnings for this catchment. All 12km grid points normal (GREEN).</div>`;
        } else {
            body.innerHTML = grid_warnings.map(g => `
                <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.6rem 0.8rem; border-radius: 6px; background: var(--bg-secondary); border: 1px solid var(--border);">
                    <div>
                        <strong style="color: var(--text-primary); font-size: 0.88rem;">📍 Grid Point (${g.latitude}, ${g.longitude})</strong>
                        <div style="color: var(--text-secondary); font-size: 0.78rem; margin-top: 2px;">${g.condition || 'Precipitation Warning'}</div>
                    </div>
                    <div style="text-align: right;">
                        <span style="font-weight: 700; font-size: 0.9rem; color: ${g.alert_level === 'RED' ? '#d20f39' : (g.alert_level === 'YELLOW' ? '#df8e1d' : '#40a02b')};">
                            ${g.rain_3h_mm} mm / 3h
                        </span>
                        <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">24h: ${g.rain_24h_mm}mm • Gust: ${g.gust_m_s}m/s</div>
                    </div>
                </div>
            `).join("");
        }

        if (grid_modal) grid_modal.classList.add("open");
    } catch (err) {
        console.error("Failed to load grid forecast modal data:", err);
    }
});

if (close_grid_modal) {
    close_grid_modal.addEventListener("click", () => {
        if (grid_modal) grid_modal.classList.remove("open");
    });
}

if (grid_modal) {
    grid_modal.addEventListener("click", (e) => {
        if (e.target === grid_modal) grid_modal.classList.remove("open");
    });
}
