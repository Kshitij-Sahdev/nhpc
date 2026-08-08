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

const open_settings_btn = document.getElementById("open-settings-btn");
const open_settings_btn_nav = document.getElementById("open-settings-btn-nav");
const settings_modal = document.getElementById("settings-modal");
const close_settings_modal = document.getElementById("close-settings-modal");

function openSettings(e) {
    if (e) e.preventDefault();
    if (settings_modal) {
        settings_modal.classList.add("open");
        if (menu_dropdown) menu_dropdown.classList.remove("open");
    }
}

function closeSettings() {
    if (settings_modal) {
        settings_modal.classList.remove("open");
    }
}

if (open_settings_btn) open_settings_btn.addEventListener("click", openSettings);
if (open_settings_btn_nav) open_settings_btn_nav.addEventListener("click", openSettings);
if (close_settings_modal) close_settings_modal.addEventListener("click", closeSettings);

if (settings_modal) {
    settings_modal.addEventListener("click", (e) => {
        if (e.target === settings_modal) closeSettings();
    });
}

lucide.createIcons();
