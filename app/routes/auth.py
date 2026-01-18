"""
Authentication Routes
=====================
Blueprint for login, logout, and password management
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler"""
    from app.models import User
    
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Username atau password salah', 'danger')
    
    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout handler"""
    logout_user()
    flash('Anda telah logout', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    from app.models import db
    
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(old_password):
            flash('Password lama salah', 'danger')
        elif new_password != confirm_password:
            flash('Password baru tidak cocok', 'danger')
        elif len(new_password) < 4:
            flash('Password minimal 4 karakter', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password berhasil diubah', 'success')
            return redirect(url_for('main.index'))
    
    return render_template('change_password.html')
