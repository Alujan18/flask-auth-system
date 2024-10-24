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

# Load environment variables
load_dotenv()

# Global variables for bot control
email_bot_thread = None
bot_running = False
email_client = None
bot_lock = threading.Lock()

# Upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt'}

# Create uploads directory if it doesn't exist
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER, 'prompt'), exist_ok=True)
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER, 'info'), exist_ok=True)

def allowed_file(filename):
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

[... rest of the existing code ...]

@app.route('/agente/recursos')
def agente_recursos():
    return render_template('agente_recursos.html')

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
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('agente_recursos'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.root_path, UPLOAD_FOLDER, upload_type, filename)
        file.save(file_path)
        flash(f'File uploaded successfully to {upload_type}', 'success')
        add_log('SUCCESS', f'File {filename} uploaded to {upload_type} directory')
    else:
        flash('Invalid file type. Only .txt files are allowed.', 'danger')
        add_log('ERROR', f'Invalid file upload attempt to {upload_type} directory')
    
    return redirect(url_for('agente_recursos'))

[... rest of the existing routes ...]
