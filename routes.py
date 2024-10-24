from flask import render_template, request, jsonify, redirect, url_for, flash
from app import app, db
from models import EmailMessage, EmailThread, Log
from email_client import EmailClient
from email_utils import decode_str, get_email_body
from datetime import datetime
import json
import uuid
from email.utils import parseaddr, parsedate_to_datetime
from sqlalchemy.exc import SQLAlchemyError
import threading
import time
import os

# Global variable to control bot status
bot_running = False
bot_thread = None

def add_log(level, message):
    """Add a log entry to the database"""
    try:
        log = Log(level=level, message=message)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error adding log: {e}")
        db.session.rollback()

def save_to_env_file(config_data):
    """Save configuration to .env file"""
    env_content = []
    for key, value in config_data.items():
        if value:  # Only write non-empty values
            env_content.append(f"{key}={value}")
    
    with open('.env', 'w') as f:
        f.write('\n'.join(env_content))

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

def email_bot():
    """Email bot function to continuously check for new emails"""
    global bot_running
    
    add_log('INFO', 'Starting email bot')
    client = None
    
    while bot_running:
        try:
            if not client:
                client = EmailClient()
                client.connect()
                add_log('INFO', 'Email client connected successfully')
            
            # Fetch and process emails
            emails = client.fetch_emails()
            if emails:
                add_log('INFO', f'Found {len(emails)} new emails to process')
                process_emails(emails)
            
            # Wait for 30 seconds before next check
            time.sleep(30)
            
        except Exception as e:
            add_log('ERROR', f'Bot error: {str(e)}')
            if client:
                try:
                    client.close_connection()
                except:
                    pass
                client = None
            time.sleep(60)  # Wait longer after an error
    
    if client:
        client.close_connection()
    add_log('INFO', 'Email bot stopped')

@app.route('/')
def index():
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente_dashboard.html')

@app.route('/agente/bot/status')
def bot_status():
    return jsonify({'running': bot_running})

@app.route('/agente/bot/toggle', methods=['POST'])
def toggle_bot():
    global bot_running, bot_thread
    
    try:
        if bot_running:
            bot_running = False
            if bot_thread:
                bot_thread.join(timeout=5)
            return jsonify({
                'status': 'success',
                'running': False,
                'message': 'Bot stopped successfully'
            })
        else:
            # Check if email configuration exists
            config = load_email_config()
            if not all(config.values()):
                return jsonify({
                    'status': 'error',
                    'message': 'Please configure email settings first'
                })
            
            bot_running = True
            bot_thread = threading.Thread(target=email_bot)
            bot_thread.daemon = True
            bot_thread.start()
            
            return jsonify({
                'status': 'success',
                'running': True,
                'message': 'Bot started successfully'
            })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}'
        })

@app.route('/agente/logs')
def agente_logs():
    try:
        with app.app_context():
            logs = Log.query.order_by(Log.timestamp.desc()).all()
            return render_template('agente_logs.html', logs=logs)
    except Exception as e:
        app.logger.error(f'Error loading logs: {str(e)}')
        return render_template('agente_logs.html', logs=[])

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
            # Safe conversion of port numbers with default values
            imap_port = int(config_data.get('IMAP_PORT') or 0)
            smtp_port = int(config_data.get('SMTP_PORT') or 0)
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
        client.imap_server = request.form.get('imap_server')
        client.imap_port = int(request.form.get('imap_port') or 0)
        client.smtp_server = request.form.get('smtp_server')
        client.smtp_port = int(request.form.get('smtp_port') or 0)
        client.email_address = request.form.get('email_address')
        client.email_password = request.form.get('email_password')
        
        client.connect()
        client.close_connection()
        
        return jsonify({
            'status': 'success',
            'message': 'Conexión exitosa a los servidores de correo'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error de conexión: {str(e)}'
        })

@app.route('/agente/database')
def agente_database():
    try:
        # Get all unique senders
        senders = db.session.query(
            EmailMessage.from_email,
            EmailMessage.from_name
        ).distinct().all()
        
        sender_data = []
        for from_email, from_name in senders:
            # Get all threads for this sender
            threads = db.session.query(EmailThread).join(
                EmailMessage, EmailThread.thread_id == EmailMessage.thread_id
            ).filter(
                EmailMessage.from_email == from_email
            ).distinct().order_by(EmailThread.last_updated.desc()).all()
            
            # Get all messages for these threads
            thread_ids = [thread.thread_id for thread in threads]
            messages = EmailMessage.query.filter(
                EmailMessage.thread_id.in_(thread_ids)
            ).order_by(EmailMessage.date.desc()).all()
            
            sender_data.append({
                'email': from_email,
                'name': from_name,
                'threads': threads,
                'messages': messages
            })
        
        return render_template('agente_database.html', sender_data=sender_data)
    except Exception as e:
        app.logger.error(f'Error in agente_database: {str(e)}')
        flash(f'Error al cargar los datos: {str(e)}', 'danger')
        return render_template('agente_database.html', sender_data=[])

@app.route('/agente/clear-database', methods=['POST'])
def clear_database():
    try:
        # Stop the bot if it's running
        global bot_running
        bot_running = False
        
        with app.app_context():
            # Delete all records from tables
            EmailMessage.query.delete()
            EmailThread.query.delete()
            Log.query.delete()
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Base de datos limpiada exitosamente'
            })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Error al limpiar la base de datos: {str(e)}'
        })

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

                # Check for existing message
                existing_message = EmailMessage.query.filter_by(message_id=message_id).first()
                if existing_message:
                    add_log('WARNING', f'Email with message_id {message_id} already exists, skipping')
                    continue

                # Find or create thread
                thread = None
                if in_reply_to:
                    ref_msg = EmailMessage.query.filter_by(message_id=in_reply_to).first()
                    if ref_msg:
                        thread = EmailThread.query.filter_by(thread_id=ref_msg.thread_id).first()

                if not thread and references:
                    for ref in references:
                        ref_msg = EmailMessage.query.filter_by(message_id=ref).first()
                        if ref_msg:
                            thread = EmailThread.query.filter_by(thread_id=ref_msg.thread_id).first()
                            break

                if not thread:
                    thread_id = str(uuid.uuid4())
                    thread = EmailThread(
                        thread_id=thread_id,
                        subject=subject,
                        last_updated=datetime.utcnow()
                    )
                    db.session.add(thread)
                else:
                    thread.last_updated = datetime.utcnow()

                # Create new message
                email_msg = EmailMessage(
                    message_id=message_id,
                    thread_id=thread.thread_id,
                    from_name=from_name,
                    from_email=from_email,
                    subject=subject,
                    body=body,
                    date=date,
                    in_reply_to=in_reply_to,
                    references=json.dumps(references),
                    folder=folder
                )
                
                db.session.add(email_msg)
                db.session.commit()

                add_log('INFO', f'''Nuevo email procesado:
Thread ID: {thread.thread_id}
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
