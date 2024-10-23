from flask import render_template, redirect, url_for, flash, request, session
from app import app, db
from models import User
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
import secrets
import time

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        
        # Check session timeout (30 minutes)
        if 'last_activity' in session:
            if time.time() - session['last_activity'] > 1800:  # 30 minutes
                session.clear()
                flash('Session expired. Please login again.', 'warning')
                return redirect(url_for('login'))
        
        session['last_activity'] = time.time()
        return f(*args, **kwargs)
    return decorated_function

@app.before_request
def before_request():
    # Generate CSRF token if it doesn't exist
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)

def validate_csrf_token():
    token = session.get('csrf_token')
    return token and token == request.form.get('csrf_token')

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid form submission.', 'danger')
            return redirect(url_for('register'))

        try:
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if not username or not password or not confirm_password:
                flash('All fields are required', 'danger')
                return redirect(url_for('register'))

            if not User.is_valid_username(username):
                flash('Invalid username format. Use only letters, numbers, and underscores (3-64 characters)', 'danger')
                return redirect(url_for('register'))

            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))

            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('register'))

            if not User.is_valid_password(password):
                flash('Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character', 'danger')
                return redirect(url_for('register'))

            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

        except (SQLAlchemyError, ValueError) as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('register'))

    return render_template('register.html', csrf_token=session['csrf_token'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid form submission.', 'danger')
            return redirect(url_for('login'))

        try:
            username = request.form.get('username')
            password = request.form.get('password')

            if not username or not password:
                flash('Both username and password are required', 'danger')
                return redirect(url_for('login'))

            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                session.clear()
                session['username'] = username
                session['csrf_token'] = secrets.token_hex(32)
                session['last_activity'] = time.time()
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            
            flash('Invalid username or password', 'danger')
        except SQLAlchemyError as e:
            flash(f'An error occurred: {str(e)}', 'danger')

    return render_template('login.html', csrf_token=session['csrf_token'])

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', username=session['username'])

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid form submission.', 'danger')
            return redirect(url_for('profile'))

        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not all([current_password, new_password, confirm_password]):
                flash('All fields are required', 'danger')
                return redirect(url_for('profile'))

            user = User.query.filter_by(username=session['username']).first()

            if not user.check_password(current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('profile'))

            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                return redirect(url_for('profile'))

            if not User.is_valid_password(new_password):
                flash('Password must be at least 8 characters long and contain uppercase, lowercase, number, and special character', 'danger')
                return redirect(url_for('profile'))

            user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully', 'success')
            return redirect(url_for('profile'))

        except (SQLAlchemyError, ValueError) as e:
            db.session.rollback()
            flash(f'An error occurred: {str(e)}', 'danger')
            return redirect(url_for('profile'))

    return render_template('profile.html', username=session['username'], csrf_token=session['csrf_token'])

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/agente')
@login_required
def agente_main():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion')
@login_required
def agente_configuracion():
    return render_template('agente_configuracion.html')

@app.route('/agente/dashboard')
@login_required
def agente_dashboard():
    return render_template('agente_dashboard.html')
