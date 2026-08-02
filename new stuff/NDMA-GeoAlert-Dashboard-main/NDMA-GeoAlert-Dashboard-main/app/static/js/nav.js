const theme_toggle = document.getElementById("theme-toggle");
const menu_toggle = document.getElementById("menu-toggle");
const menu_dropdown = document.getElementById("menu-dropdown");

function update_theme_icon() {
    const icon = document.getElementById("theme-icon");
    icon.setAttribute("data-lucide", document.body.classList.contains("dark-theme") ? "moon" : "sun");
    lucide.createIcons();
}

const saved_theme = localStorage.getItem("theme");
if (saved_theme === "dark") {
    document.body.classList.add("dark-theme");
}

update_theme_icon();

theme_toggle.addEventListener("click", () => {
    document.body.classList.toggle("dark-theme");
    const is_dark = document.body.classList.contains("dark-theme");
    localStorage.setItem("theme", is_dark ? "dark" : "light");

    update_theme_icon();
});

menu_toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    menu_dropdown.classList.toggle("open");
});

document.addEventListener("click", (event) => {
    if (!menu_dropdown.contains(event.target) && event.target !== menu_toggle) {
        menu_dropdown.classList.remove("open");
    }
});

lucide.createIcons();
