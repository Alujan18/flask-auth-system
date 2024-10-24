from flask import render_template, redirect, url_for, request, flash, jsonify
from app import app, db
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
from email_client import EmailClient
from models import Log, EmailThread, EmailMessage
from datetime import datetime
from email.utils import parseaddr, parsedate_to_datetime
from email_utils import decode_str, get_email_body
import threading
import time
import uuid
import json
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import inspect, or_, and_

# Load environment variables
load_dotenv()

# Global variables for bot control
email_bot_thread = None
bot_running = False
email_client = None
bot_lock = threading.Lock()

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
            log = Log()
            log.level = level
            log.message = message
            db.session.add(log)
            db.session.commit()
    except Exception as e:
        print(f"Error adding log: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass

def process_emails(emails):
    """Process incoming emails and store them in the database"""
    for email_id, msg, folder in emails:
        try:
            # Parse email headers
            from_raw = msg.get("From")
            name, email_addr = parseaddr(from_raw)
            from_name = decode_str(name)
            from_email = decode_str(email_addr)
            subject = decode_str(msg.get("Subject"))
            message_id = msg.get("Message-ID")
            
            # Generate UUID for empty message_id
            if not message_id or message_id.strip() == '':
                message_id = f"<{str(uuid.uuid4())}@generated>"
                add_log('WARNING', f'Generated new message_id for email from {from_email}: {message_id}')
            
            in_reply_to = msg.get("In-Reply-To")
            references = msg.get("References", "").split()
            date_str = msg.get("Date")
            body = get_email_body(msg)
            
            try:
                date = parsedate_to_datetime(date_str)
            except:
                date = datetime.utcnow()
                add_log('WARNING', f'Invalid date format for email from {from_email}, using current time')

            try:
                db.session.begin_nested()

                existing_message = EmailMessage.query.filter_by(message_id=message_id).first()
                if existing_message:
                    add_log('WARNING', f'Email with message_id {message_id} already exists, skipping')
                    continue

                thread_id = None
                if in_reply_to:
                    ref_email = EmailMessage.query.filter_by(message_id=in_reply_to).first()
                    if ref_email:
                        thread_id = ref_email.thread_id
                
                if not thread_id and references:
                    for ref in references:
                        ref_email = EmailMessage.query.filter_by(message_id=ref).first()
                        if ref_email:
                            thread_id = ref_email.thread_id
                            break

                if not thread_id:
                    thread_id = str(uuid.uuid4())
                    thread = EmailThread()
                    thread.thread_id = thread_id
                    thread.subject = subject
                    db.session.add(thread)
                    db.session.flush()
                else:
                    thread = EmailThread.query.filter_by(thread_id=thread_id).first()
                    if thread:
                        thread.last_updated = datetime.utcnow()
                
                email_msg = EmailMessage()
                email_msg.message_id = message_id
                email_msg.thread_id = thread_id
                email_msg.from_name = from_name
                email_msg.from_email = from_email
                email_msg.subject = subject
                email_msg.body = body
                email_msg.date = date
                email_msg.in_reply_to = in_reply_to
                email_msg.references = json.dumps(references)
                email_msg.folder = folder
                
                db.session.add(email_msg)
                db.session.commit()

                add_log('INFO', f'''Nuevo email procesado:
Thread ID: {thread_id}
De: {from_name} <{from_email}>
Fecha: {date_str}
Asunto: {subject}
Message-ID: {message_id}
In-Reply-To: {in_reply_to or 'N/A'}
----------------------------------------
{body[:50] + '...' if len(body) > 50 else body}
''')

            except SQLAlchemyError as e:
                db.session.rollback()
                add_log('ERROR', f'Database error processing email {message_id}: {str(e)}')
                continue
            except Exception as e:
                db.session.rollback()
                add_log('ERROR', f'Unexpected error processing email {message_id}: {str(e)}')
                continue

        except Exception as e:
            add_log('ERROR', f'Error processing email {email_id}: {str(e)}')
            continue

def bot_process():
    """Email bot process that runs in the background"""
    global bot_running, email_client
    
    with app.app_context():
        add_log('INFO', 'Bot iniciado')
        connection_retry_count = 0
        max_retries = 3
        check_interval = 60  # Check every minute
        
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
                        time.sleep(check_interval)
                        continue
                
                try:
                    emails = email_client.fetch_emails()
                    if emails:
                        add_log('INFO', f'Obtenidos {len(emails)} correos nuevos')
                        process_emails(emails)
                    else:
                        add_log('INFO', 'No hay correos nuevos para procesar')
                except Exception as e:
                    add_log('ERROR', f'Error al obtener/procesar correos: {str(e)}')
                    if email_client:
                        try:
                            email_client.close_connection()
                            add_log('WARNING', 'Conexión cerrada debido a error')
                        except:
                            pass
                    email_client = None
                    time.sleep(check_interval)
                    continue
                
                time.sleep(check_interval)
                
            except Exception as e:
                add_log('ERROR', f'Error en el bot: {str(e)}')
                if email_client:
                    try:
                        email_client.close_connection()
                        add_log('WARNING', 'Conexión cerrada debido a error')
                    except:
                        pass
                email_client = None
                time.sleep(check_interval)
        
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
        
        if not all(config_data.values()):
            flash('Todos los campos son requeridos.', 'danger')
            return render_template('agente_configuracion.html', config=config_data)
        
        try:
            imap_port = int(config_data['IMAP_PORT'])
            smtp_port = int(config_data['SMTP_PORT'])
            if not (0 <= imap_port <= 65535 and 0 <= smtp_port <= 65535):
                raise ValueError("Puerto inválido")
        except ValueError:
            flash('Los puertos deben ser números válidos entre 0 y 65535.', 'danger')
            return render_template('agente_configuracion.html', config=config_data)
        
        try:
            save_to_env_file(config_data)
            app.config.update(config_data)
            flash('Configuración guardada exitosamente', 'success')
            return redirect(url_for('agente_configuracion'))
        except Exception as e:
            app.logger.error(f'Error saving configuration: {str(e)}')
            flash(f'Error al guardar la configuración: {str(e)}', 'danger')
            return render_template('agente_configuracion.html', config=config_data)
    
    return render_template('agente_configuracion.html', config=load_email_config())

@app.route('/agente/test-connection', methods=['POST'])
def test_connection():
    try:
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
        with bot_lock:
            if not bot_running:
                config = load_email_config()
                if not all(config.values()):
                    return jsonify({
                        'status': 'error',
                        'message': 'Configure los datos del servidor de correo primero'
                    })
                
                bot_running = True
                email_bot_thread = threading.Thread(target=bot_process)
                email_bot_thread.daemon = True
                email_bot_thread.start()
                return jsonify({'status': 'success', 'message': 'Bot iniciado', 'running': True})
            else:
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
    try:
        logs = Log.query.order_by(Log.timestamp.desc()).limit(100).all()
        return render_template('agente_logs.html', logs=logs)
    except SQLAlchemyError as e:
        app.logger.error(f'Error fetching logs: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente_dashboard.html')

@app.route('/agente/database')
def agente_database():
    try:
        # Get all threads
        threads = EmailThread.query.order_by(EmailThread.last_updated.desc()).all()
        thread_data = []
        
        for thread in threads:
            # Get all messages in this thread
            messages = EmailMessage.query.filter(
                EmailMessage.thread_id == thread.thread_id
            ).order_by(EmailMessage.date.asc()).all()
            
            if messages:
                thread_data.append({
                    'thread': thread,
                    'messages': messages
                })
        
        return render_template('agente_database.html', thread_data=thread_data)
    except Exception as e:
        app.logger.error(f'Error in agente_database: {str(e)}')
        flash(f'Error al cargar los datos: {str(e)}', 'danger')
        return render_template('agente_database.html', thread_data=[])

@app.route('/agente/logs/latest')
def latest_logs():
    try:
        logs = Log.query.order_by(Log.timestamp.desc()).limit(5).all()
        return jsonify({
            'status': 'success',
            'logs': [{
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'level': log.level,
                'level_class': log.level_class,
                'message': log.message
            } for log in logs]
        })
    except Exception as e:
        app.logger.error(f'Error fetching latest logs: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': 'Error al cargar los registros',
            'logs': []
        }), 500
