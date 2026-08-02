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
    if (e.key === "Escape") document.getElementById("alert-modal").classList.remove("open");
});
