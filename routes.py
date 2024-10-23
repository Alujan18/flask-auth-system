from flask import render_template, redirect, url_for, flash, request, session
from app import app, db
from models import User
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from functools import wraps
import secrets
import time
from datetime import datetime

# Dictionary to store login attempts
login_attempts = {}
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_TIME = 300  # 5 minutes in seconds

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login to access this page.', 'warning')
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
    
    # Clear old login attempts
    current_time = time.time()
    for ip in list(login_attempts.keys()):
        if current_time - login_attempts[ip]['timestamp'] > LOCKOUT_TIME:
            del login_attempts[ip]

def validate_csrf_token():
    if request.method == 'POST':
        token = session.get('csrf_token')
        if not token or token != request.form.get('csrf_token'):
            return False
    return True

def check_login_attempts(ip):
    if ip in login_attempts:
        attempts = login_attempts[ip]
        if attempts['count'] >= MAX_LOGIN_ATTEMPTS:
            if time.time() - attempts['timestamp'] < LOCKOUT_TIME:
                remaining_time = int(LOCKOUT_TIME - (time.time() - attempts['timestamp']))
                return False, f'Too many login attempts. Please try again in {remaining_time} seconds.'
            else:
                del login_attempts[ip]
    return True, None

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid form submission. Please try again.', 'danger')
            return redirect(url_for('register'))

        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            # Validate required fields
            if not all([username, password, confirm_password]):
                flash('All fields are required', 'danger')
                return redirect(url_for('register'))

            # Validate username format
            if not User.is_valid_username(username):
                flash('Invalid username format. Use only letters, numbers, and underscores (3-64 characters)', 'danger')
                return redirect(url_for('register'))

            # Check if username exists
            if User.query.filter_by(username=username).first():
                flash('Username already exists', 'danger')
                return redirect(url_for('register'))

            # Validate password match
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('register'))

            # Validate password complexity
            if not User.is_valid_password(password):
                flash('Password must contain at least 8 characters, including uppercase, lowercase, number, and special character', 'danger')
                return redirect(url_for('register'))

            # Create user
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()

            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('login'))

        except IntegrityError:
            db.session.rollback()
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f'Database error during registration: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('register'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('register'))

    return render_template('register.html', csrf_token=session['csrf_token'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not validate_csrf_token():
            flash('Invalid form submission. Please try again.', 'danger')
            return redirect(url_for('login'))

        ip = request.remote_addr
        can_login, error_message = check_login_attempts(ip)
        
        if not can_login:
            flash(error_message, 'danger')
            return redirect(url_for('login'))

        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password')

            if not username or not password:
                flash('Both username and password are required', 'danger')
                return redirect(url_for('login'))

            user = User.query.filter_by(username=username).first()
            
            if not user or not user.check_password(password):
                # Update login attempts
                if ip not in login_attempts:
                    login_attempts[ip] = {'count': 1, 'timestamp': time.time()}
                else:
                    login_attempts[ip]['count'] += 1
                    login_attempts[ip]['timestamp'] = time.time()
                
                remaining_attempts = MAX_LOGIN_ATTEMPTS - login_attempts[ip]['count']
                flash(f'Invalid username or password. {remaining_attempts} attempts remaining.', 'danger')
                return redirect(url_for('login'))

            # Reset login attempts on successful login
            if ip in login_attempts:
                del login_attempts[ip]

            session.clear()
            session['username'] = username
            session['csrf_token'] = secrets.token_hex(32)
            session['last_activity'] = time.time()
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))

        except SQLAlchemyError as e:
            app.logger.error(f'Database error during login: {str(e)}')
            flash('An error occurred during login. Please try again.', 'danger')
            return redirect(url_for('login'))

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
            flash('Invalid form submission. Please try again.', 'danger')
            return redirect(url_for('profile'))

        try:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')

            if not all([current_password, new_password, confirm_password]):
                flash('All fields are required', 'danger')
                return redirect(url_for('profile'))

            user = User.query.filter_by(username=session['username']).first()
            if not user:
                session.clear()
                flash('User account not found. Please login again.', 'danger')
                return redirect(url_for('login'))

            if not user.check_password(current_password):
                flash('Current password is incorrect', 'danger')
                return redirect(url_for('profile'))

            if new_password != confirm_password:
                flash('New passwords do not match', 'danger')
                return redirect(url_for('profile'))

            if not User.is_valid_password(new_password):
                flash('New password must contain at least 8 characters, including uppercase, lowercase, number, and special character', 'danger')
                return redirect(url_for('profile'))

            if current_password == new_password:
                flash('New password must be different from current password', 'danger')
                return redirect(url_for('profile'))

            user.set_password(new_password)
            db.session.commit()
            
            flash('Password updated successfully', 'success')
            return redirect(url_for('profile'))

        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f'Database error during password update: {str(e)}')
            flash('An error occurred while updating password. Please try again.', 'danger')
            return redirect(url_for('profile'))

    return render_template('profile.html', username=session['username'], csrf_token=session['csrf_token'])

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
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
