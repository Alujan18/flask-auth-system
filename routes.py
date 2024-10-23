from flask import render_template, redirect, url_for, request, flash, jsonify, session
from app import app, db
from models import User
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
from email_client import EmailClient
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps

# Load environment variables
load_dotenv()

def load_email_config():
    """Load email configuration from environment variables"""
    return {
        'IMAP_SERVER': os.getenv('IMAP_SERVER', ''),
        'IMAP_PORT': os.getenv('IMAP_PORT', ''),
        'SMTP_SERVER': os.getenv('SMTP_SERVER', ''),
        'SMTP_PORT': os.getenv('SMTP_PORT', ''),
        'EMAIL_ADDRESS': os.getenv('EMAIL_ADDRESS', ''),
        'EMAIL_PASSWORD': os.getenv('EMAIL_PASSWORD', '')
    }

def save_to_env_file(config_data):
    """Save configuration to .env file"""
    env_path = Path('.env')
    
    # Create .env file if it doesn't exist
    if not env_path.exists():
        env_path.touch()
    
    # Update each configuration value
    for key, value in config_data.items():
        set_key(str(env_path), key, str(value))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('login.html')

        try:
            # Check if username is actually an email
            if '@' in username:
                user = User.query.filter_by(email=username).first()
            else:
                user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                if not user.is_active:
                    flash('This account has been deactivated. Please contact support.', 'danger')
                    return render_template('login.html')
                
                session['user_id'] = user.id
                flash('Successfully logged in!', 'success')
                next_page = request.args.get('next')
                if next_page and next_page.startswith('/'):
                    return redirect(next_page)
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username/email or password.', 'danger')
        except SQLAlchemyError as e:
            app.logger.error(f'Database error during login: {str(e)}')
            flash('An error occurred. Please try again.', 'danger')
        except Exception as e:
            app.logger.error(f'Unexpected error during login: {str(e)}')
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if not all([username, email, password, confirm_password]):
            flash('Please fill in all fields.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        try:
            user = User()
            user.username = username
            user.email = email
            user.set_password(password)

            db.session.add(user)
            db.session.commit()

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

        except ValueError as e:
            flash(str(e), 'danger')
        except SQLAlchemyError as e:
            db.session.rollback()
            app.logger.error(f'Database error during registration: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'danger')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Unexpected error during registration: {str(e)}')
            flash('An unexpected error occurred. Please try again.', 'danger')

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Successfully logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente')
@login_required
def agente_main():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion', methods=['GET', 'POST'])
@login_required
def agente_configuracion():
    if request.method == 'POST':
        try:
            # Get form data
            config_data = {
                'IMAP_SERVER': request.form.get('imap_server'),
                'IMAP_PORT': request.form.get('imap_port'),
                'SMTP_SERVER': request.form.get('smtp_server'),
                'SMTP_PORT': request.form.get('smtp_port'),
                'EMAIL_ADDRESS': request.form.get('email_address'),
                'EMAIL_PASSWORD': request.form.get('email_password')
            }
            
            # Validate required fields
            if not all(config_data.values()):
                flash('Todos los campos son requeridos.', 'danger')
                return render_template('agente_configuracion.html', config=config_data)
            
            # Validate port numbers
            try:
                imap_port = int(config_data['IMAP_PORT'])
                smtp_port = int(config_data['SMTP_PORT'])
                if not (0 <= imap_port <= 65535 and 0 <= smtp_port <= 65535):
                    raise ValueError
            except ValueError:
                flash('Los puertos deben ser números válidos entre 0 y 65535.', 'danger')
                return render_template('agente_configuracion.html', config=config_data)
            
            # Save configuration
            save_to_env_file(config_data)
            
            # Update app configuration
            for key, value in config_data.items():
                app.config[key] = value
            
            flash('Configuración guardada exitosamente.', 'success')
            return redirect(url_for('agente_configuracion'))
            
        except Exception as e:
            app.logger.error(f'Error saving configuration: {str(e)}')
            flash('Error al guardar la configuración. Por favor intente nuevamente.', 'danger')
    
    # Load current configuration for GET request
    config = load_email_config()
    return render_template('agente_configuracion.html', config=config)

@app.route('/agente/test-connection', methods=['POST'])
@login_required
def test_connection():
    try:
        client = EmailClient()
        client.connect()
        client.close_connection()
        return jsonify({'status': 'success', 'message': 'Conexión exitosa a IMAP y SMTP'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error de conexión: {str(e)}'})

@app.route('/agente/logs')
@login_required
def agente_logs():
    logs = []
    return render_template('agente_logs.html', logs=logs)

@app.route('/agente/dashboard')
@login_required
def agente_dashboard():
    return render_template('agente_dashboard.html')