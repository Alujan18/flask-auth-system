#routes.py

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
from werkzeug.utils import secure_filename
from prompt_builder import build_prompt


# Load environment variables
load_dotenv()

# Global variables for bot control
email_bot_thread = None
bot_running = False
email_client = None
bot_lock = threading.Lock()

# Upload configuration
AGENTE_IA_FOLDER = 'agente_ia'
ALLOWED_EXTENSIONS = {'txt'}

# Create uploads directory if it doesn't exist
os.makedirs(os.path.join(app.root_path, AGENTE_IA_FOLDER, 'prompt'), exist_ok=True)
os.makedirs(os.path.join(app.root_path, AGENTE_IA_FOLDER, 'info'), exist_ok=True)

def allowed_file(filename):
    if filename is None:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
            # Check if Log table exists
            inspector = inspect(db.engine)
            if 'log' not in inspector.get_table_names():
                db.create_all()
                app.logger.info('Log table created')
            
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

def read_file_content(file_type, filename):
    try:
        file_path = os.path.join(app.root_path, AGENTE_IA_FOLDER, file_type, filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        app.logger.error(f'Error reading {file_type} file: {str(e)}')
    return None

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

                add_log('INFO', f'New email processed:\nThread ID: {thread_id}\nFrom: {from_name} <{from_email}>\nDate: {date_str}\nSubject: {subject}\nMessage-ID: {message_id}\nIn-Reply-To: {in_reply_to or "N/A"}\n----------------------------------------\n{body[:50] + "..." if len(body) > 50 else body}')

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
        add_log('INFO', 'Bot started')
        connection_retry_count = 0
        max_retries = 3
        check_interval = 60  # Check every minute
        
        while bot_running:
            try:
                if not email_client:
                    email_client = EmailClient()
                    try:
                        email_client.connect()
                        add_log('SUCCESS', 'Connection established with email server')
                        connection_retry_count = 0
                    except Exception as e:
                        connection_retry_count += 1
                        add_log('ERROR', f'Connection error (attempt {connection_retry_count}): {str(e)}')
                        if connection_retry_count >= max_retries:
                            add_log('ERROR', 'Maximum connection attempts reached')
                            bot_running = False
                            break
                        time.sleep(check_interval)
                        continue
                
                try:
                    emails = email_client.fetch_emails()
                    if emails:
                        add_log('INFO', f'Retrieved {len(emails)} new emails')
                        process_emails(emails)
                    else:
                        add_log('INFO', 'No new emails to process')
                except Exception as e:
                    add_log('ERROR', f'Error fetching/processing emails: {str(e)}')
                    if email_client:
                        try:
                            email_client.close_connection()
                            add_log('WARNING', 'Connection closed due to error')
                        except:
                            pass
                    email_client = None
                    time.sleep(check_interval)
                    continue
                
                time.sleep(check_interval)
                
            except Exception as e:
                add_log('ERROR', f'Bot error: {str(e)}')
                if email_client:
                    try:
                        email_client.close_connection()
                        add_log('WARNING', 'Connection closed due to error')
                    except:
                        pass
                email_client = None
                time.sleep(check_interval)
        
        if email_client:
            try:
                email_client.close_connection()
                add_log('INFO', 'Connection closed successfully')
            except Exception as e:
                add_log('ERROR', f'Error closing connection: {str(e)}')
        add_log('INFO', 'Bot stopped')

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
            flash('All fields are required.', 'danger')
            return render_template('agente/agente_configuracion.html', config=config_data)
        
        try:
            imap_port = int(config_data['IMAP_PORT'] or 0)
            smtp_port = int(config_data['SMTP_PORT'] or 0)
            if not (0 <= imap_port <= 65535 and 0 <= smtp_port <= 65535):
                raise ValueError("Invalid port")
        except ValueError:
            flash('Ports must be valid numbers between 0 and 65535.', 'danger')
            return render_template('agente/agente_configuracion.html', config=config_data)
        
        try:
            save_to_env_file(config_data)
            app.config.update(config_data)
            flash('Configuration saved successfully', 'success')
            return redirect(url_for('agente_configuracion'))
        except Exception as e:
            app.logger.error(f'Error saving configuration: {str(e)}')
            flash(f'Error saving configuration: {str(e)}', 'danger')
            return render_template('agente/agente_configuracion.html', config=config_data)
    
    return render_template('agente/agente_configuracion.html', config=load_email_config())

@app.route('/agente/test-connection', methods=['POST'])
def test_connection():
    try:
        client = EmailClient()
        client.connect()
        client.close_connection()
        return jsonify({'status': 'success', 'message': 'Successfully connected to IMAP and SMTP'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Connection error: {str(e)}'})

@app.route('/agente/clear-database', methods=['POST'])
def clear_database():
    try:
        # Stop bot if running
        global bot_running
        bot_running = False
        
        # Drop and recreate all tables
        db.drop_all()
        db.create_all()
        
        # Add success log
        add_log('INFO', 'Database cleared successfully')
        
        return jsonify({
            'status': 'success',
            'message': 'Database cleared successfully'
        })
    except Exception as e:
        app.logger.error(f'Error clearing database: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': f'Error clearing database: {str(e)}'
        }), 500

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
                        'message': 'Configure email server data first'
                    })
                
                bot_running = True
                email_bot_thread = threading.Thread(target=bot_process)
                email_bot_thread.daemon = True
                email_bot_thread.start()
                return jsonify({'status': 'success', 'message': 'Bot started', 'running': True})
            else:
                bot_running = False
                if email_bot_thread:
                    email_bot_thread.join(timeout=2)
                return jsonify({'status': 'success', 'message': 'Bot stopped', 'running': False})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Error: {str(e)}'})

@app.route('/agente/bot/status')
def bot_status():
    return jsonify({'running': bot_running})

@app.route('/agente/logs')
def agente_logs():
    try:
        # Check if Log table exists
        inspector = inspect(db.engine)
        if 'log' not in inspector.get_table_names():
            db.create_all()
            app.logger.info('Log table created')
        
        logs = Log.query.order_by(Log.timestamp.desc()).limit(50).all()
        return render_template('agente/agente_logs.html', logs=logs)
    except Exception as e:
        app.logger.error(f'Error loading logs: {str(e)}')
        return render_template('agente/agente_logs.html', logs=[])

@app.route('/agente/logs/latest')
def latest_logs():
    try:
        # Check if Log table exists
        inspector = inspect(db.engine)
        if 'log' not in inspector.get_table_names():
            db.create_all()
            app.logger.info('Log table created')
            
        logs = Log.query.order_by(Log.timestamp.desc()).limit(5).all()
        log_list = []
        for log in logs:
            log_list.append({
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'level': log.level,
                'level_class': log.level_class,
                'message': log.message
            })
        return jsonify({
            'status': 'success',
            'logs': log_list
        })
    except Exception as e:
        app.logger.error(f'Error fetching latest logs: {str(e)}')
        return jsonify({
            'status': 'error',
            'message': str(e),
            'logs': []
        })

@app.route('/agente/dashboard')
def agente_dashboard():
    return render_template('agente/agente_dashboard.html')

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
            # Get all threads where this person is either sender or recipient
            threads = db.session.query(EmailThread).join(
                EmailMessage,
                EmailThread.thread_id == EmailMessage.thread_id
            ).filter(
                or_(
                    EmailMessage.from_email == from_email,
                    and_(
                        EmailMessage.folder == 'Sent',
                        EmailMessage.thread_id.in_(
                            db.session.query(EmailMessage.thread_id).filter(
                                EmailMessage.from_email == from_email
                            )
                        )
                    )
                )
            ).distinct().order_by(EmailThread.last_updated.desc()).all()
            
            if threads:
                thread_data = []
                for thread in threads:
                    # Get all messages in this thread
                    messages = EmailMessage.query.filter(
                        EmailMessage.thread_id == thread.thread_id,
                        or_(
                            EmailMessage.from_email == from_email,
                            EmailMessage.folder == 'Sent'
                        )
                    ).order_by(EmailMessage.date.asc()).all()
                    
                    if messages:
                        thread_data.append({
                            'thread': thread,
                            'messages': messages
                        })
                
                if thread_data:
                    sender_data.append({
                        'email': from_email,
                        'name': from_name or from_email,
                        'threads': thread_data
                    })
        
        return render_template('agente/agente_database.html', sender_data=sender_data)
    except Exception as e:
        app.logger.error(f'Error in agente_database: {str(e)}')
        flash(f'Error loading data: {str(e)}', 'danger')
        return render_template('agente/agente_database.html', sender_data=[])

@app.route('/agente/recursos')
def agente_recursos():
    # Get list of files and their contents
    prompt_files = []
    info_files = []
    
    prompt_dir = os.path.join(app.root_path, AGENTE_IA_FOLDER, 'prompt')
    info_dir = os.path.join(app.root_path, AGENTE_IA_FOLDER, 'info')
    
    if os.path.exists(prompt_dir):
        for filename in os.listdir(prompt_dir):
            if filename.endswith('.txt'):
                content = read_file_content('prompt', filename)
                if content:
                    prompt_files.append({
                        'name': filename,
                        'content': content[:1000] + '...' if len(content) > 1000 else content
                    })
    
    if os.path.exists(info_dir):
        for filename in os.listdir(info_dir):
            if filename.endswith('.txt'):
                content = read_file_content('info', filename)
                if content:
                    info_files.append({
                        'name': filename,
                        'content': content[:1000] + '...' if len(content) > 1000 else content
                    })
    
    return render_template('agente/agente_recursos.html', 
                         prompt_files=prompt_files,
                         info_files=info_files)

@app.route('/agente/upload/prompt', methods=['POST'])
def upload_prompt():
    return handle_upload('prompt')

@app.route('/agente/upload/info', methods=['POST'])
def upload_info():
    return handle_upload('info')

def handle_upload(upload_type):
    if 'file' not in request.files:
        flash('No file selected', 'danger')
        return redirect(url_for('agente_recursos'))
    
    file = request.files['file']
    if not file or file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('agente_recursos'))
    
    if allowed_file(file.filename):
        if file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.root_path, AGENTE_IA_FOLDER, upload_type, filename)
            file.save(file_path)
            flash(f'File uploaded successfully', 'success')
            add_log('SUCCESS', f'File {filename} uploaded to {upload_type} directory')
    else:
        flash('Invalid file type. Only .txt files are allowed.', 'danger')
        add_log('ERROR', f'Invalid file upload attempt to {upload_type} directory')
    
    return redirect(url_for('agente_recursos'))


@app.route('/agente/prompt')
def agente_prompt():
    # Leer archivos de prompt
    prompt_files_dir = os.path.join(app.root_path, AGENTE_IA_FOLDER, 'prompt')
    prompt_files_contents = []
    if os.path.exists(prompt_files_dir):
        for filename in os.listdir(prompt_files_dir):
            if filename.endswith('.txt'):
                file_path = os.path.join(prompt_files_dir, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    prompt_files_contents.append(content)

    # Leer info_principal
    info_principal_path = os.path.join(app.root_path, AGENTE_IA_FOLDER, 'info', 'info_principal.txt')
    if os.path.exists(info_principal_path):
        with open(info_principal_path, 'r', encoding='utf-8') as f:
            info_principal_content = f.read()
    else:
        info_principal_content = ''

    # Obtener un hilo de mensajes "no procesado"
    thread = EmailThread.query.filter_by(reply_by_ia=False).first()
    if thread:
        # Obtener mensajes en este hilo
        messages = EmailMessage.query.filter_by(thread_id=thread.thread_id).order_by(EmailMessage.date.asc()).all()
        # Construir el contenido del hilo de mensajes
        message_thread_content = ''
        for message in messages:
            sender = f"{message.from_name} <{message.from_email}>"
            date_str = message.date.strftime('%Y-%m-%d %H:%M:%S') if message.date else 'Fecha desconocida'
            subject = message.subject or 'Sin Asunto'
            message_content = message.body or ''
            message_thread_content += f"From: {sender}\n"
            message_thread_content += f"Date: {date_str}\n"
            message_thread_content += f"Subject: {subject}\n"
            message_thread_content += f"Body:\n{message_content}\n"
            message_thread_content += "-"*80 + "\n"
    else:
        message_thread_content = 'No se encontraron hilos no procesados.'

    # Construir el prompt
    prompt = build_prompt(prompt_files_contents, info_principal_content, message_thread_content)

    return render_template('agente/agente_prompt.html', prompt=prompt)
