document.addEventListener("DOMContentLoaded", function () {
    const hamburgerBtn = document.getElementById("hamburgerBtn");
    const sideMenu = document.getElementById("sideMenu");

    if (!hamburgerBtn || !sideMenu) return;

    hamburgerBtn.addEventListener("click", function () {
        sideMenu.classList.toggle("open");
    });

    // Optional: close menu when clicking outside
    document.addEventListener("click", function (event) {
        if (
            sideMenu.classList.contains("open") &&
            !sideMenu.contains(event.target) &&
            !hamburgerBtn.contains(event.target)
        ) {
            sideMenu.classList.remove("open");
        }
    });
});
