const project_search = document.getElementById("project-search");
const search_results = document.getElementById("project-search-results");
const warning_project_set = new Set(warning_projects);

project_search.addEventListener("input", () => {
    const query = project_search.value.trim().toLowerCase();

    search_results.innerHTML = "";

    if (!query) {
        return;
    }

    const matches = project_sites.filter((project) => project.project_name.toLowerCase().includes(query));

    if (matches.length === 0) {
        search_results.innerHTML = `
                <div class="search-result no-warning">
                    No matching projects found.
                </div>
            `;

        return;
    }

    matches.forEach((project) => {
        const has_warnings = warning_project_set.has(project.project_id);

        const result = document.createElement("div");

        result.className = "search-result";

        if (has_warnings) {
            result.dataset.projectId = project.project_id;

            result.textContent = project.project_name;
        } else {
            result.classList.add("no-warning");

            result.textContent = `${project.project_name} has no present warnings`;
        }

        search_results.appendChild(result);
    });
});

search_results.addEventListener("click", (event) => {
    const result = event.target.closest("[data-project-id]");

    if (!result) {
        return;
    }

    const project_id = result.dataset.projectId;

    const card = document.querySelector(`.project-card[data-project-id="${project_id}"]`);
    
    if (!card) {
        return;
    }

    card.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });

    card.classList.add("alert-card-active");

    project_search.value = "";
    search_results.innerHTML = "";

    setTimeout(() => {
        card.classList.remove("alert-card-active");
    }, 3000);
});
