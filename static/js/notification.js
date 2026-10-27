async function tandaiDibaca(event) {
    event.preventDefault();

    const form = event.currentTarget;
    const tombol = form.querySelector("button");
    const kartu = form.closest(".notif-card");
    const status = kartu.querySelector(".notif-card-status");
    const jumlah = document.getElementById("notif-unread-count");
    const pesan = document.getElementById("notif-feedback");

    if (tombol.disabled) {
        return;
    }

    tombol.disabled = true;
    pesan.textContent = "Menyimpan...";

    try {
        // Mengirim form ke View Django.
        const response = await fetch(form.action, {
            method: "POST",
            headers: {
                "Accept": "application/json"
            },
            body: new FormData(form)
        });

        const hasil = await response.json();

        if (!response.ok || !hasil.success) {
            pesan.textContent = hasil.message || "Gagal menyimpan status.";
            tombol.disabled = false;
            return;
        }

        // Memperbarui tampilan setelah database berhasil diubah.
        kartu.classList.remove("notif-card-unread");

        status.textContent = "Sudah dibaca";
        status.classList.add("notif-card-status-read");

        tombol.textContent = "Sudah dibaca";
        jumlah.textContent = hasil.unread_count + " belum dibaca";

        pesan.textContent = "Notifikasi berhasil ditandai sudah dibaca.";
    } catch {
        pesan.textContent = "Terjadi kesalahan. Silakan coba lagi.";
        tombol.disabled = false;
    }
}

const daftarForm = document.querySelectorAll(".notif-read-form");

for (const form of daftarForm) {
    form.addEventListener("submit", tandaiDibaca);
}