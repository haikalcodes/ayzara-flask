"""
Pegawai API Routes Blueprint
=============================
API endpoints for team/employee management

📁 Copy to: dashboard_flask_refactored/app/routes/pegawai.py
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.utils import admin_required
from app.models import db, Pegawai
from werkzeug.utils import secure_filename
import config
import os
import uuid

pegawai_bp = Blueprint('pegawai', __name__)


@pegawai_bp.route('/api/pegawai')
@login_required
def api_pegawai_list():
    """Get list of all pegawai"""
    pegawai_list = Pegawai.query.order_by(Pegawai.nama).all()
    return jsonify({
        'success': True,
        'pegawai': [p.to_dict() for p in pegawai_list]
    })


@pegawai_bp.route('/api/pegawai/<int:pegawai_id>')
@login_required
def api_pegawai_get(pegawai_id):
    """Get single pegawai by ID"""
    pegawai = Pegawai.query.get_or_404(pegawai_id)
    return jsonify(pegawai.to_dict())


@pegawai_bp.route('/api/pegawai', methods=['POST'])
@login_required
@admin_required
def api_pegawai_create():
    """Create new pegawai"""
    try:
        # Get form data
        nama = request.form.get('nama')
        jabatan = request.form.get('jabatan', '')
        telepon = request.form.get('telepon', '')
        email = request.form.get('email', '')
        alamat = request.form.get('alamat', '')
        
        if not nama:
            return jsonify({'success': False, 'error': 'Nama harus diisi'}), 400
        
        # Handle photo upload
        photo_path = None
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                # Use random filename (UUID)
                ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
                filename = f"{uuid.uuid4().hex}{ext}"
                
                photo_path = os.path.join('photos', filename)
                file.save(config.PHOTOS_FOLDER / filename)
        
        # Create pegawai
        pegawai = Pegawai(
            nama=nama,
            jabatan=jabatan,
            telepon=telepon,
            email=email,
            alamat=alamat,
            photo=photo_path
        )
        
        db.session.add(pegawai)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'pegawai': pegawai.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@pegawai_bp.route('/api/pegawai/<int:pegawai_id>', methods=['PUT'])
@login_required
@admin_required
def api_pegawai_update(pegawai_id):
    """Update existing pegawai"""
    try:
        pegawai = Pegawai.query.get_or_404(pegawai_id)
        
        # Update fields
        if 'nama' in request.form:
            pegawai.nama = request.form.get('nama')
        if 'jabatan' in request.form:
            pegawai.jabatan = request.form.get('jabatan')
        if 'telepon' in request.form:
            pegawai.telepon = request.form.get('telepon')
        if 'email' in request.form:
            pegawai.email = request.form.get('email')
        if 'alamat' in request.form:
            pegawai.alamat = request.form.get('alamat')
        
        # Handle photo upload
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename:
                # Use random filename (UUID)
                ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
                filename = f"{uuid.uuid4().hex}{ext}"
                
                # Delete old photo if exists
                if pegawai.photo:
                    try:
                        old_filename = os.path.basename(pegawai.photo)
                        old_file_path = config.PHOTOS_FOLDER / old_filename
                        if old_file_path.exists():
                            old_file_path.unlink() # Delete file
                            print(f"[Pegawai] Old photo deleted: {old_filename}")
                    except Exception as e:
                        print(f"[Pegawai] Failed to delete old photo: {e}")
                
                photo_path = os.path.join('photos', filename)
                file.save(config.PHOTOS_FOLDER / filename)
                
                # Update photo path
                pegawai.photo = photo_path
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'pegawai': pegawai.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@pegawai_bp.route('/api/pegawai/<int:pegawai_id>/status', methods=['PUT'])
@login_required
@admin_required
def api_pegawai_toggle_status(pegawai_id):
    """Toggle pegawai active status"""
    try:
        pegawai = Pegawai.query.get_or_404(pegawai_id)
        
        # Toggle status
        pegawai.is_active = not pegawai.is_active
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'is_active': pegawai.is_active,
            'message': 'Status pegawai berhasil diubah'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@pegawai_bp.route('/api/pegawai/<int:pegawai_id>', methods=['DELETE'])
@login_required
@admin_required
def api_pegawai_delete(pegawai_id):
    """Delete pegawai PERMANENTLY"""
    try:
        pegawai = Pegawai.query.get_or_404(pegawai_id)
        
        # Delete photo file if exists
        if pegawai.photo:
            try:
                filename = os.path.basename(pegawai.photo)
                file_path = config.PHOTOS_FOLDER / filename
                if file_path.exists():
                    file_path.unlink()
                    print(f"[Pegawai] Photo deleted: {filename}")
            except Exception as e:
                print(f"[Pegawai] Failed to delete photo: {e}")

        # Hard delete from DB
        db.session.delete(pegawai)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
