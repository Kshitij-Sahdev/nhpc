function switch_tab(tab_name) {
    document.querySelectorAll(".sidebar-tab").forEach((tab) => {
        tab.classList.remove("active");
    });

    document.querySelectorAll(".tab-content").forEach((content) => {
        content.classList.remove("active");
    });

    const tab_button = document.querySelector(`[data-tab="${tab_name}"]`);
    if (tab_button) {
        tab_button.classList.add("active");
    }

    const tab_content = document.getElementById(`${tab_name}-tab`);
    if (tab_content) {
        tab_content.classList.add("active");
    }

    setTimeout(() => {
        if (window.map) {
            window.map.invalidateSize();
        }
    }, 150);
}

document.querySelectorAll(".sidebar-tab").forEach((button) => {
    button.addEventListener("click", () => {
        switch_tab(button.dataset.tab);
    });
});
