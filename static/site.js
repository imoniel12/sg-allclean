(() => {
    const menu = document.getElementById("mobile-menu");
    const opener = document.querySelector(".menu-button");
    if (menu && opener) {
        opener.addEventListener("click", () => {
            menu.showModal();
            document.body.classList.add("menu-open");
        });
        menu.querySelector("[data-close-menu]")?.addEventListener("click", () => menu.close());
        menu.addEventListener("close", () => document.body.classList.remove("menu-open"));
        menu.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => menu.close()));
        menu.addEventListener("click", (event) => {
            if (event.target !== menu) return;
            const bounds = menu.getBoundingClientRect();
            if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) menu.close();
        });
    }
    document.getElementById("confirmation")?.focus();
})();
