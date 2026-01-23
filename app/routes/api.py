"""
API Routes Blueprint
====================
General API endpoints for status, exports, and file serving

📁 Copy to: dashboard_flask_refactored/app/routes/api.py
"""

from flask import Blueprint, jsonify, send_from_directory, send_file
from flask_login import login_required
from app.services import RecordingService, StatsService
from app.models import db, PackingRecord
import config
import os

api_bp = Blueprint('api', __name__)

from flask import request
from app.utils import admin_required


@api_bp.route('/api/videos/delete', methods=['POST'])
@login_required
@admin_required
def api_delete_videos():
    """Bulk delete videos (files + db)"""
    data = request.json
    ids_to_delete = data.get('ids', [])
    
    if not ids_to_delete:
        return jsonify({'success': False, 'message': 'No IDs provided'})
        
    deleted_count = 0
    errors = 0
    
    for rec_id in ids_to_delete:
        try:
            record = PackingRecord.query.get(rec_id)
            if not record:
                continue
                
            # 1. Delete Video File
            if record.file_video and os.path.exists(record.file_video):
                try:
                    os.remove(record.file_video)
                except Exception as e:
                    print(f"Failed to delete video file {record.file_video}: {e}")
            
            # 2. Delete JSON Metadata
            if record.file_video:
                json_path = record.file_video.rsplit('.', 1)[0] + '.json'
                if os.path.exists(json_path):
                    try:
                        os.remove(json_path)
                    except Exception as e:
                        print(f"Failed to delete json file {json_path}: {e}")

            # 3. Delete Thumbnail (Calculate path manually or store it)
            # Use simple heuristic based on existing logic in batch generator
            if record.file_video:
                import hashlib
                video_path = record.file_video.replace('\\', '/')
                path_hash = hashlib.md5(video_path.encode()).hexdigest()
                thumb_name = f"thumb_{path_hash}.jpg"
                thumb_path = config.THUMBNAILS_FOLDER / thumb_name
                if thumb_path.exists():
                     try:
                        os.remove(thumb_path)
                     except:
                        pass

            # 4. Delete DB Record
            db.session.delete(record)
            deleted_count += 1
            
        except Exception as e:
            print(f"Error deleting record {rec_id}: {e}")
            errors += 1
            
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database commit failed: {str(e)}'})

    return jsonify({
        'success': True,
        'deleted': deleted_count,
        'errors': errors
    })



@api_bp.route('/api/status')
@login_required
def api_status():
    """Get current recording status"""
    recording_service = RecordingService(db, PackingRecord)
    status = recording_service.get_recording_status()
    return jsonify(status)


@api_bp.route('/api/export/csv')
@login_required
def api_export_csv():
    """Export recordings to CSV"""
    import csv
    import io
    from flask import make_response
    
    # Get all completed recordings
    recordings = PackingRecord.query.filter_by(status='COMPLETED').order_by(
        PackingRecord.waktu_mulai.desc()
    ).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow(['ID', 'Resi', 'Pegawai', 'Platform', 'Waktu Mulai', 'Waktu Selesai', 'Durasi (detik)', 'File Video'])
    
    # Data
    for rec in recordings:
        writer.writerow([
            rec.id,
            rec.resi,
            rec.pegawai,
            rec.platform,
            rec.waktu_mulai.strftime('%Y-%m-%d %H:%M:%S') if rec.waktu_mulai else '',
            rec.waktu_selesai.strftime('%Y-%m-%d %H:%M:%S') if rec.waktu_selesai else '',
            rec.durasi_detik or 0,
            rec.file_video or ''
        ])
    
    # Create response
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=recordings.csv'
    response.headers['Content-Type'] = 'text/csv'
    
    return response


@api_bp.route('/api/export/pdf')
@login_required
def api_export_pdf():
    """Export recordings to PDF"""
    # This would require a PDF library like ReportLab
    # For now, return a placeholder
    return jsonify({
        'success': False,
        'message': 'PDF export not yet implemented'
    })


@api_bp.route('/api/generate-thumbnails-batch', methods=['POST'])
@login_required
def api_generate_thumbnails_batch():
    """Generate thumbnails for all videos"""
    import cv2
    
    recordings = PackingRecord.query.filter_by(status='COMPLETED').all()
    
    generated = 0
    skipped = 0
    errors = 0
    
    for rec in recordings:
        if not rec.file_video or not os.path.exists(rec.file_video):
            errors += 1
            continue
        
        # Generate thumbnail name
        import hashlib
        video_path = rec.file_video.replace('\\', '/')
        path_hash = hashlib.md5(video_path.encode()).hexdigest()
        thumb_name = f"thumb_{path_hash}.jpg"
        thumb_path = config.THUMBNAILS_FOLDER / thumb_name
        
        # Skip if already exists
        if thumb_path.exists():
            skipped += 1
            continue
        
        # Generate thumbnail
        try:
            cap = cv2.VideoCapture(rec.file_video)
            ret, frame = cap.read()
            if ret:
                cv2.imwrite(str(thumb_path), frame)
                generated += 1
            else:
                errors += 1
            cap.release()
        except:
            errors += 1
    
    return jsonify({
        'success': True,
        'generated': generated,
        'skipped': skipped,
        'errors': errors
    })


@api_bp.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Serve recording files"""
    return send_from_directory(config.RECORDINGS_FOLDER, filename)


@api_bp.route('/uploads/thumbnails/<filename>')
def serve_thumbnail(filename):
    """Serve thumbnail files"""
    return send_from_directory(config.THUMBNAILS_FOLDER, filename)


@api_bp.route('/uploads/photos/<filename>')
def serve_photo(filename):
    """Serve photo files"""
    return send_from_directory(config.PHOTOS_FOLDER, filename)


@api_bp.route('/uploads/<filename>')
def serve_upload(filename):
    """Serve uploaded files"""
    return send_from_directory(config.UPLOAD_FOLDER, filename)

