from flask import render_template, redirect, url_for, request, flash, jsonify
from app import app, db
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
from email_client import EmailClient
from models import Log
from datetime import datetime
import threading
import time
from email_utils import decode_str, get_email_body
from email.utils import parseaddr

# Load environment variables
load_dotenv()

# Global variables for bot control
email_bot_thread = None
bot_running = False
email_client = None

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

def add_log(level, message):
    """Add a log entry to the database"""
    try:
        with app.app_context():
            log = Log(level=level, message=message)
            db.session.add(log)
            db.session.commit()
    except Exception as e:
        print(f"Error adding log: {str(e)}")

def bot_process():
    """Email bot process that runs in the background"""
    global bot_running, email_client
    
    add_log('INFO', 'Bot iniciado')
    connection_retry_count = 0
    max_retries = 3
    
    while bot_running:
        try:
            if not email_client:
                email_client = EmailClient()
                try:
                    email_client.connect()
                    add_log('SUCCESS', 'Conexión establecida con el servidor de correo')
                    connection_retry_count = 0
                except Exception as e:
                    connection_retry_count += 1
                    add_log('ERROR', f'Error de conexión (intento {connection_retry_count}): {str(e)}')
                    if connection_retry_count >= max_retries:
                        add_log('ERROR', 'Número máximo de intentos de conexión alcanzado')
                        bot_running = False
                        break
                    time.sleep(60)  # Wait before retry
                    continue
            
            # Fetch and process emails
            emails = email_client.fetch_emails()
            if emails:
                for email_id, msg, folder in emails:
                    try:
                        # Parse email headers
                        from_raw = msg.get("From")
                        name, email_addr = parseaddr(from_raw)
                        from_name = decode_str(name)
                        from_email = decode_str(email_addr)
                        subject = decode_str(msg.get("Subject"))
                        message_id = msg.get("Message-ID")
                        in_reply_to = msg.get("In-Reply-To")
                        references = msg.get("References")
                        date_str = msg.get("Date")

                        # Extract email body
                        body = get_email_body(msg)
                        
                        # Log email details
                        add_log('INFO', f'Nuevo email de: {from_name} <{from_email}>')
                        add_log('INFO', f'Fecha: {date_str}')
                        add_log('INFO', f'Asunto: {subject}')
                        
                        # Log first 50 chars of body
                        body_preview = body[:50] + '...' if len(body) > 50 else body
                        add_log('INFO', f'Contenido: {body_preview}')
                        
                        # Log reference info if available
                        if message_id:
                            add_log('INFO', f'Message-ID: {message_id}')
                        if in_reply_to:
                            add_log('INFO', f'En respuesta a: {in_reply_to}')
                        
                    except Exception as e:
                        add_log('ERROR', f'Error procesando email {email_id}: {str(e)}')
            
            time.sleep(60)  # Check emails every minute
            
        except Exception as e:
            add_log('ERROR', f'Error en el bot: {str(e)}')
            if email_client:
                try:
                    email_client.close_connection()
                    add_log('WARNING', 'Conexión cerrada debido a error')
                except:
                    pass
            email_client = None
            time.sleep(60)  # Wait before retrying
    
    if email_client:
        try:
            email_client.close_connection()
            add_log('INFO', 'Conexión cerrada correctamente')
        except Exception as e:
            add_log('ERROR', f'Error al cerrar la conexión: {str(e)}')
    add_log('INFO', 'Bot detenido')

@app.route('/')
def index():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente')
def agente_main():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion', methods=['GET', 'POST'])
def agente_configuracion():
    if request.method == 'POST':
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
        
        # Validate ports
        try:
            imap_port = int(config_data['IMAP_PORT'])
            smtp_port = int(config_data['SMTP_PORT'])
            if not (0 <= imap_port <= 65535 and 0 <= smtp_port <= 65535):
                raise ValueError("Puerto inválido")
        except ValueError:
            flash('Los puertos deben ser números válidos entre 0 y 65535.', 'danger')
            return render_template('agente_configuracion.html', config=config_data)
        
        try:
            # Save to .env file
            save_to_env_file(config_data)
            
            # Update current session config
            app.config.update(config_data)
            
            flash('Configuración guardada exitosamente', 'success')
            return redirect(url_for('agente_configuracion'))
        except Exception as e:
            app.logger.error(f'Error saving configuration: {str(e)}')
            flash(f'Error al guardar la configuración: {str(e)}', 'danger')
            return render_template('agente_configuracion.html', config=config_data)
    
    # GET request - load current config
    return render_template('agente_configuracion.html', config=load_email_config())

@app.route('/agente/test-connection', methods=['POST'])
def test_connection():
    try:
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
            return jsonify({
                'status': 'error',
                'message': 'Todos los campos son requeridos para probar la conexión'
            })

        # Create temporary EmailClient with form data
        client = EmailClient()
        client.connect()
        client.close_connection()
        return jsonify({'status': 'success', 'message': 'Conexión exitosa a IMAP y SMTP'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error de conexión: {str(e)}'})

@app.route('/agente/bot/toggle', methods=['POST'])
def toggle_bot():
    global bot_running, email_bot_thread
    
    try:
        if not bot_running:
            # Check if configuration exists
            config = load_email_config()
            if not all(config.values()):
                return jsonify({
                    'status': 'error',
                    'message': 'Configure los datos del servidor de correo primero'
                })
            
            # Start bot
            bot_running = True
            email_bot_thread = threading.Thread(target=bot_process)
            email_bot_thread.daemon = True
            email_bot_thread.start()
            return jsonify({'status': 'success', 'message': 'Bot iniciado', 'running': True})
        else:
            # Stop bot
            bot_running = False
            if email_bot_thread:
                email_bot_thread.join(timeout=2)
            return jsonify({'status': 'success', 'message': 'Bot detenido', 'running': False})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})

@app.route('/agente/bot/status')
def bot_status():
    return jsonify({'running': bot_running})

@app.route('/agente/logs')
def agente_logs():
    logs = Log.query.order_by(Log.timestamp.desc()).limit(100).all()
    return render_template('agente_logs.html', logs=logs)

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente_dashboard.html', bot_running=bot_running)
