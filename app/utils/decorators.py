"""
Decorators
==========
Custom decorators for route protection and access control
"""

from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user


def admin_required(f):
    """
    Decorator to require admin role
    
    Usage:
        @app.route('/admin')
        @login_required
        @admin_required
        def admin_page():
            return render_template('admin.html')
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            # flash('Akses ditolak. Hanya admin yang dapat mengakses halaman ini.', 'danger')
            return redirect(url_for('main.index')) 
        return f(*args, **kwargs)
    return decorated_function
