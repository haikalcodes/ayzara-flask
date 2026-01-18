/**
 * UI Module
 * =========
 * Handles UI interactions like sidebar, datetime, modals
 */

/**
 * Initialize sidebar toggle
 */
export function initSidebar() {
    const toggleBtn = document.getElementById('toggleSidebar');
    const sidebar = document.getElementById('sidebar');

    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('show');
        });

        // Close on click outside (mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 992) {
                if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }
}

/**
 * Update datetime display
 */
export function updateDateTime() {
    const el = document.getElementById('datetime');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleString('id-ID', {
            weekday: 'short',
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

/**
 * Play video in modal
 */
export function playVideo(videoPath, resi, duration) {
    const modal = new bootstrap.Modal(document.getElementById('videoModal'));
    const video = document.getElementById('modalVideo');
    const title = document.getElementById('modalVideoTitle');

    if (video) {
        video.src = videoPath;
        video.load();
    }

    if (title) {
        title.textContent = `${resi} (${duration}s)`;
    }

    modal.show();

    // Pause on close
    document.getElementById('videoModal').addEventListener('hidden.bs.modal', () => {
        if (video) {
            video.pause();
            video.src = '';
        }
    }, { once: true });
}

/**
 * Export to CSV
 */
export function exportCSV() {
    window.location.href = '/api/export/csv';
}

/**
 * Export to PDF
 */
export function exportPDF() {
    window.location.href = '/api/export/pdf';
}

/**
 * Share to social media
 */
export function shareToSocial(platform, videoUrl, resi) {
    const text = `📦 Video Packing - ${resi}`;
    const url = encodeURIComponent(window.location.origin + videoUrl);

    let shareUrl;

    switch (platform) {
        case 'facebook':
            shareUrl = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
            break;
        case 'twitter':
            shareUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${url}`;
            break;
        case 'whatsapp':
            shareUrl = `https://wa.me/?text=${encodeURIComponent(text + ' ' + window.location.origin + videoUrl)}`;
            break;
        case 'telegram':
            shareUrl = `https://t.me/share/url?url=${url}&text=${encodeURIComponent(text)}`;
            break;
        default:
            // Copy to clipboard
            navigator.clipboard.writeText(window.location.origin + videoUrl);
            alert('Link copied to clipboard!');
            return;
    }

    window.open(shareUrl, '_blank', 'width=600,height=400');
}

// Make functions globally available for inline onclick handlers
window.playVideo = playVideo;
window.exportCSV = exportCSV;
window.exportPDF = exportPDF;
window.shareToSocial = shareToSocial;
