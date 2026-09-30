(() => {
    document.querySelectorAll("[data-quote-form]").forEach((form) => {
        const phone = form.elements.phone;
        const email = form.elements.email;
        const photos = form.elements.photos;
        const validateContact = () => phone.setCustomValidity(phone.value.trim() || email.value.trim() ? "" : "Please provide a phone number or email address.");
        phone.addEventListener("input", validateContact);
        email.addEventListener("input", validateContact);
        validateContact();
        photos.addEventListener("change", () => {
            const invalid = photos.files.length > 3 || [...photos.files].some((file) => file.size > 5 * 1024 * 1024);
            photos.setCustomValidity(invalid ? "Choose at most three photos, 5 MB each." : "");
        });
    });
    document.getElementById("form-errors")?.focus();
})();
