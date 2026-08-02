document.querySelectorAll(".project-locate-button").forEach((button) => {
    button.addEventListener("click", () => {
        const project_name = button.dataset.projectName;
        const marker = project_markers[project_name];

        if (!marker) {
            return;
        }

        map.flyTo(marker.getLatLng(), 10, {
            animate: true,
            duration: 1
        });

        marker.openPopup();
    });
});

document.addEventListener("click", (event) => {
    if (!event.target.classList.contains("project-tag")) {
        return;
    }

    const project_id = event.target.dataset.projectId;

    switch_tab("projects");

    document
        .querySelector(`.project-card[data-project-id="${project_id}"]`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
});
