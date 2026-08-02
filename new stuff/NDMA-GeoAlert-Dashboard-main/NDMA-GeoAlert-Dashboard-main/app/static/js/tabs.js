function switch_tab(tab_name) {
    document.querySelectorAll(".sidebar-tab").forEach((tab) => {
        tab.classList.remove("active");
    });

    document.querySelectorAll(".tab-content").forEach((content) => {
        content.classList.remove("active");
    });

    const tab_button = document.querySelector(`[data-tab="${tab_name}"]`);

    tab_button.classList.add("active");

    document.getElementById(`${tab_name}-tab`).classList.add("active");
}

document.querySelectorAll(".sidebar-tab").forEach((button) => {
    button.addEventListener("click", () => {
        switch_tab(button.dataset.tab);
    });
});
