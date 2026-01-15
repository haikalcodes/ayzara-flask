/**
 * Video Player Module
 * Hanldes opening the video modal, setting sources, and managing metadata display.
 * Shared between videos.html (Gallery) and recording.html (Recording Page).
 */

// Export function if using modules, but for simple script inclusion we attach to window
window.openVideoModal = function (data) {
    console.log('Opening video modal with data:', data);

    // 1. Set Basic Info (Title & Subtitle)
    const titleEl = document.getElementById('modalVideoTitle');
    const subtitleEl = document.getElementById('modalVideoSubtitle');

    if (titleEl) titleEl.innerHTML = `<i class="bi bi-box-seam me-2"></i> ${data.resi || '-'}`;
    if (subtitleEl) subtitleEl.textContent = `${data.platform || '-'} • ${data.pegawai || '-'}`;

    // 2. Update Metadata Fields
    const metaResi = document.getElementById('metaResi');
    const metaPegawai = document.getElementById('metaPegawai');
    const metaPlatform = document.getElementById('metaPlatform');
    const metaTime = document.getElementById('metaTime');

    if (metaResi) metaResi.textContent = data.resi || '-';
    if (metaPegawai) metaPegawai.textContent = data.pegawai || '-';
    if (metaPlatform) metaPlatform.textContent = data.platform || '-';
    if (metaTime) metaTime.textContent = data.time || '-';

    // 3. Video Source & Overlay Logic
    const video = document.getElementById('modalVideo');
    const overlay = document.getElementById('videoMissingOverlay');
    const btnDownload = document.getElementById('btnDownloadVideo');

    if (!video) {
        console.error("Video player element 'modalVideo' not found!");
        return;
    }

    // Determine if file exists. 
    // Handle both boolean true/false and string "true"/"false" if passed from attributes
    let fileExists = data.file_exists;
    if (typeof fileExists === 'string') {
        fileExists = (fileExists === 'true');
    }
    // Default to true if undefined but url is present (fallback for legacy/simple calls), 
    // UNLESS it's explicitly explicitly marked as missing.
    // However, for consistency, we should check what the server sends.
    // If undefined, we assume true if there is a URL, BUT robust mode relies on explicit flag.
    if (fileExists === undefined && data.url) {
        fileExists = true;
    }

    if (fileExists && data.url) {
        // --- FILE EXISTS ---
        video.style.display = 'block';
        if (overlay) overlay.classList.add('d-none');

        video.src = data.url;
        video.load();

        // Apply autoplay if desired
        video.play().catch(e => console.log('Autoplay blocked/failed:', e));

        // Enable Download Button
        if (btnDownload) {
            btnDownload.classList.remove('disabled', 'btn-secondary');
            btnDownload.classList.add('btn-primary');
            btnDownload.href = data.url;
            btnDownload.download = data.url.split('/').pop();
            btnDownload.innerHTML = '<i class="bi bi-download me-2"></i>Unduh Video';
        }
    } else {
        // --- FILE MISSING ---
        video.style.display = 'none';

        // Show overlay if it exists, otherwise we just hide video (maybe show alert?)
        if (overlay) {
            overlay.classList.remove('d-none');
        } else {
            // If no overlay element exists in DOM (e.g. recording page might miss it), creates issue.
            // We should ensure recording.html has the overlay or we handle it gracefully.
            console.warn("Video file missing and no overlay element found.");
            // Optional: Insert simple message
        }

        video.src = "";

        // Disable Download Button
        if (btnDownload) {
            btnDownload.classList.add('disabled', 'btn-secondary');
            btnDownload.classList.remove('btn-primary');
            btnDownload.removeAttribute('href');
            btnDownload.removeAttribute('download');
            btnDownload.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>File Video Hilang';
        }
    }

    // 4. Load JSON Metadata
    const jsonPre = document.getElementById('metaJson');
    if (jsonPre) {
        jsonPre.textContent = 'Loading metadata...';
        jsonPre.className = 'bg-dark text-light p-3 rounded small text-break border border-secondary';

        if (data.json && data.json !== '#') {
            fetch(data.json)
                .then(res => {
                    if (!res.ok) throw new Error('Metadata JSON not found');
                    return res.json();
                })
                .then(jsonData => {
                    jsonPre.textContent = JSON.stringify(jsonData, null, 2);
                })
                .catch(err => {
                    jsonPre.textContent = "Metadata JSON tidak dapat dimuat: " + err.message;
                });
        } else {
            jsonPre.textContent = "URL Metadata tidak tersedia.";
        }
    }

    // 5. Show Modal
    const modalEl = document.getElementById('videoModal');
    if (modalEl) {
        const modal = new bootstrap.Modal(modalEl);
        modal.show();

        // Stop video on close
        modalEl.addEventListener('hidden.bs.modal', function handler() {
            video.pause();
            video.src = '';
            modalEl.removeEventListener('hidden.bs.modal', handler);
        });
    }
};
