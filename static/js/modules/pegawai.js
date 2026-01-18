/**
 * Pegawai Module
 * ==============
 * Handles team/pegawai management operations
 */

/**
 * Show add pegawai modal
 */
export function showAddPegawaiModal() {
    const modal = new bootstrap.Modal(document.getElementById('pegawaiModal'));
    document.getElementById('pegawaiForm').reset();
    document.getElementById('pegawaiModalTitle').textContent = 'Tambah Pegawai';
    document.getElementById('pegawaiId').value = '';
    modal.show();
}

/**
 * Edit pegawai
 */
export function editPegawai(id) {
    fetch(`/api/pegawai/${id}`)
        .then(res => res.json())
        .then(data => {
            document.getElementById('pegawaiId').value = data.id;
            document.getElementById('pegawaiNama').value = data.nama || '';
            document.getElementById('pegawaiJabatan').value = data.jabatan || '';
            document.getElementById('pegawaiTelepon').value = data.telepon || '';
            document.getElementById('pegawaiEmail').value = data.email || '';
            document.getElementById('pegawaiAlamat').value = data.alamat || '';
            document.getElementById('pegawaiModalTitle').textContent = 'Edit Pegawai';

            const modal = new bootstrap.Modal(document.getElementById('pegawaiModal'));
            modal.show();
        });
}

/**
 * Save pegawai (create or update)
 */
export async function savePegawai(event) {
    event.preventDefault();

    const form = document.getElementById('pegawaiForm');
    const formData = new FormData(form);
    const id = document.getElementById('pegawaiId').value;

    const url = id ? `/api/pegawai/${id}` : '/api/pegawai';
    const method = id ? 'PUT' : 'POST';

    try {
        const response = await fetch(url, {
            method: method,
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            // Close modal first
            const modalEl = document.getElementById('pegawaiModal');
            const modalInstance = bootstrap.Modal.getInstance(modalEl);
            if (modalInstance) modalInstance.hide();

            // Show feedback
            await Swal.fire({
                icon: 'success',
                title: 'Berhasil!',
                text: id ? 'Data pegawai berhasil diperbarui' : 'Pegawai baru berhasil ditambahkan',
                timer: 1500,
                showConfirmButton: false
            });

            location.reload();
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Gagal',
                text: data.error || 'Gagal menyimpan data pegawai'
            });
        }
    } catch (error) {
        console.error('Save failed:', error);
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: 'Terjadi kesalahan sistem: ' + error.message
        });
    }
}

/**
 * Delete pegawai
 */
/**
 * Toggle pegawai status
 */
export async function togglePegawaiStatus(id, nama, isActive) {
    const action = isActive ? 'nonaktifkan' : 'aktifkan';

    const confirmResult = await Swal.fire({
        title: `Konfirmasi`,
        text: `Apakah Anda yakin ingin meng-${action} pegawai "${nama}"?`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonColor: isActive ? '#dc3545' : '#28a745',
        confirmButtonText: `Ya, ${action}`,
        cancelButtonText: 'Batal'
    });

    if (!confirmResult.isConfirmed) return;

    try {
        const response = await fetch(`/api/pegawai/${id}/status`, {
            method: 'PUT'
        });
        const data = await response.json();

        if (data.success) {
            await Swal.fire({
                icon: 'success',
                title: 'Berhasil',
                text: `Status pegawai berhasil diubah menjadi ${data.is_active ? 'Aktif' : 'Nonaktif'}`,
                timer: 1500,
                showConfirmButton: false
            });
            location.reload();
        } else {
            throw new Error(data.error || 'Gagal mengubah status');
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Gagal',
            text: error.message
        });
    }
}

/**
 * Delete pegawai
 */
export async function deletePegawai(id, nama) {
    const confirmResult = await Swal.fire({
        title: 'HAPUS PERMANEN?',
        text: `Pegawai "${nama}" akan dihapus permanen dari database beserta foto profilnya. Data rekaman yang terkait TIDAK akan ikut terhapus. Tindakan ini tidak dapat dibatalkan!`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Ya, Hapus Permanen!',
        cancelButtonText: 'Batal'
    });

    if (!confirmResult.isConfirmed) return;

    try {
        const response = await fetch(`/api/pegawai/${id}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            await Swal.fire({
                icon: 'success',
                title: 'Terhapus!',
                text: 'Data pegawai dan foto profil telah dihapus permanen.',
                timer: 2000,
                showConfirmButton: false
            });
            location.reload();
        } else {
            throw new Error(data.error || 'Gagal menghapus pegawai');
        }
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Error',
            text: error.message
        });
    }
}

// Make functions globally available
window.showAddPegawaiModal = showAddPegawaiModal;
window.editPegawai = editPegawai;
window.savePegawai = savePegawai;
window.deletePegawai = deletePegawai;
window.togglePegawaiStatus = togglePegawaiStatus;
