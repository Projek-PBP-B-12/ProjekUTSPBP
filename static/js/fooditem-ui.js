(function () {
    "use strict";
    const modal = document.getElementById("food-detail-modal");
    const statusButton = document.getElementById("modal-mark-consume-button");
    const storeButton = document.getElementById("modal-store-button");
    const deleteLink = document.getElementById("modal-delete-url");
    const shareLink = document.getElementById("modal-share-url");
    const modalError = document.getElementById("modal-food-error");
    const inventoryError = document.getElementById("inventory-error");
    let selectedFood = null;
    const states = {CONSUMED: "Sudah habis", EXPIRED: "Sudah kedaluwarsa", EXPIRES_TODAY: "Kedaluwarsa hari ini", FRESH: "Belum kedaluwarsa"};
    const filterToggle = document.querySelector(".inventory-filter-toggle");
    const filters = document.getElementById("inventory-filters");
    filters.hidden = filters.dataset.active !== "true";
    filterToggle.hidden = false;
    filterToggle.setAttribute("aria-expanded", String(!filters.hidden));
    filterToggle.addEventListener("click", function () {
        filters.hidden = !filters.hidden;
        filterToggle.setAttribute("aria-expanded", String(!filters.hidden));
        if (!filters.hidden) document.getElementById("food-search").focus();
    });

    async function mutateFood(url) {
        const token = document.querySelector('input[name="csrfmiddlewaretoken"]');
        const response = await fetch(url, {
            method: "POST", credentials: "same-origin",
            headers: {"X-CSRFToken": token ? token.value : "", "Accept": "application/json"},
        });
        const result = await response.json().catch(function () { return {}; });
        if (!response.ok) throw new Error(result.message || "Perubahan gagal disimpan. Coba lagi atau muat ulang halaman.");
    }

    async function refreshInventory() {
        const response = await fetch(window.location.href, {credentials: "same-origin", headers: {"Accept": "text/html"}});
        if (!response.ok || response.redirected) throw new Error("Data berubah, tetapi daftar belum dapat dimuat ulang. Segarkan halaman.");
        const updated = new DOMParser().parseFromString(await response.text(), "text/html");
        const table = updated.querySelector(".inventory-table-scroll");
        const count = updated.getElementById("food-amount");
        if (!table || !count) throw new Error("Daftar belum dapat dimuat ulang. Segarkan halaman.");
        document.querySelector(".inventory-table-scroll").replaceWith(table);
        document.getElementById("food-amount").textContent = count.textContent;
    }

    document.addEventListener("click", async function (event) {
        const button = event.target.closest(".detail-link");
        if (button) {
            const data = button.dataset;
            selectedFood = data;
            modalError.hidden = true;
            statusButton.disabled = false;
            storeButton.disabled = false;
            storeButton.hidden = data.statusCode !== "OFFERED";
            statusButton.textContent = data.statusCode === "CONSUMED" ? "Simpan kembali" : "Tandai habis";
            document.getElementById("modal-food-name").textContent = data.name;
            document.getElementById("modal-food-category").textContent = data.category;
            document.getElementById("modal-purchase-date").textContent = data.purchaseDate;
            document.getElementById("modal-expiration-date").textContent = data.expirationDate;
            document.getElementById("modal-status").textContent = data.status;
            document.getElementById("modal-expiration-state").textContent = states[data.expirationState] || data.expirationState;
            document.getElementById("modal-change-url").href = data.changeUrl;
            deleteLink.href = data.deletePageUrl;
            deleteLink.dataset.deleteUrl = data.deleteUrl;
            deleteLink.dataset.foodName = data.name;
            shareLink.hidden = !data.shareUrl;
            shareLink.textContent = data.shareLabel;
            if (data.shareUrl) shareLink.href = data.shareUrl;
            else shareLink.removeAttribute("href");
            const image = document.getElementById("modal-image-url");
            document.getElementById("modal-image-row").hidden = !data.imageUrl;
            if (data.imageUrl) {
                image.src = data.imageUrl;
                image.alt = data.name;
            } else {
                image.removeAttribute("src");
                image.alt = "";
            }
            modal.showModal();
            return;
        }
        const removeLink = event.target.closest(".inventory-delete");
        if (!removeLink) return;
        event.preventDefault();
        if (statusButton.disabled) return;
        if (removeLink.dataset.busy === "true" || !window.confirm("Hapus " + removeLink.dataset.foodName + " beserta penawarannya? Tindakan ini tidak dapat dibatalkan.")) return;
        removeLink.dataset.busy = "true";
        const errorMessage = modal.open ? modalError : inventoryError;
        errorMessage.hidden = true;
        try {
            await mutateFood(removeLink.dataset.deleteUrl);
            if (modal.open) modal.close();
            await refreshInventory();
        } catch (error) {
            const message = modal.open ? modalError : inventoryError;
            message.textContent = error.message;
            message.hidden = false;
        } finally {
            delete removeLink.dataset.busy;
        }
    });
    async function changeModalStatus(url) {
        if (!selectedFood || statusButton.disabled || deleteLink.dataset.busy === "true") return;
        statusButton.disabled = true;
        storeButton.disabled = true;
        modalError.hidden = true;
        try {
            await mutateFood(url);
            modal.close();
            await refreshInventory();
        } catch (error) {
            const message = modal.open ? modalError : inventoryError;
            message.textContent = error.message;
            message.hidden = false;
        } finally {
            statusButton.disabled = false;
            storeButton.disabled = false;
        }
    }
    statusButton.addEventListener("click", function () {
        if (selectedFood) changeModalStatus(selectedFood.statusCode === "CONSUMED" ? selectedFood.storedUrl : selectedFood.consumedUrl);
    });
    storeButton.addEventListener("click", function () {
        if (selectedFood) changeModalStatus(selectedFood.storedUrl);
    });
    modal.querySelectorAll("[data-close-food-modal]").forEach(function (button) {
        button.addEventListener("click", function () { modal.close(); });
    });
    modal.addEventListener("click", function (event) { if (event.target === modal) modal.close(); });
})();
