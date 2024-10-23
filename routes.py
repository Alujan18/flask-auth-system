from flask import render_template, redirect, url_for, request, flash, jsonify
from app import app
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
import imaplib
import smtplib

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

@app.route('/')
def index():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente')
def agente_main():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion', methods=['GET', 'POST'])
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
def test_connection():
    try:
        # Get current config
        config = load_email_config()
        
        # Try IMAP connection
        imap = imaplib.IMAP4_SSL(config['IMAP_SERVER'], int(config['IMAP_PORT']))
        imap.login(config['EMAIL_ADDRESS'], config['EMAIL_PASSWORD'])
        imap.logout()
        
        # Try SMTP connection
        smtp = smtplib.SMTP(config['SMTP_SERVER'], int(config['SMTP_PORT']))
        smtp.starttls()
        smtp.login(config['EMAIL_ADDRESS'], config['EMAIL_PASSWORD'])
        smtp.quit()
        
        return jsonify({'status': 'success', 'message': 'Conexión exitosa a IMAP y SMTP'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error de conexión: {str(e)}'})

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente_dashboard.html')
