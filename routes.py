from flask import render_template, redirect, url_for, flash, request, session
from app import app, db
from models import User
import imaplib
import email
from email.header import decode_header
import os
from datetime import datetime

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['username'] = username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        user = User.query.filter_by(username=session['username']).first()

        if not user.check_password(current_password):
            flash('Current password is incorrect', 'danger')
            return redirect(url_for('profile'))

        if new_password != confirm_password:
            flash('New passwords do not match', 'danger')
            return redirect(url_for('profile'))

        user.set_password(new_password)
        db.session.commit()
        flash('Password updated successfully', 'success')
        return redirect(url_for('profile'))

    return render_template('profile.html', username=session['username'])

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/agente')
def agente_main():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('agente_dashboard'))

@app.route('/agente/configuracion', methods=['GET', 'POST'])
def agente_configuracion():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(username=session['username']).first()
    
    if request.method == 'POST':
        user.email = request.form.get('email')
        user.email_server = request.form.get('email_server')
        user.email_port = int(request.form.get('email_port'))
        
        email_password = request.form.get('email_password')
        if email_password:  # Only update if new password provided
            user.email_password = email_password
            
        try:
            # Test the email connection
            imap = imaplib.IMAP4_SSL(user.email_server, user.email_port)
            imap.login(user.email, user.email_password)
            imap.logout()
            
            db.session.commit()
            flash('Email configuration updated successfully', 'success')
        except Exception as e:
            flash(f'Failed to connect to email server: {str(e)}', 'danger')
            return redirect(url_for('agente_configuracion'))
            
        return redirect(url_for('agente_dashboard'))
    
    return render_template('agente_configuracion.html',
                         email=user.email or '',
                         email_server=user.email_server or '',
                         email_port=user.email_port or 993)

def get_email_subject(msg):
    subject = ''
    if 'subject' in msg:
        subject, encoding = decode_header(msg['subject'])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or 'utf-8')
    return subject or 'No Subject'

def get_email_date(msg):
    date_str = msg.get('date', '')
    try:
        # Parse the email date string into a datetime object
        date = email.utils.parsedate_to_datetime(date_str)
        # Format the date
        return date.strftime('%Y-%m-%d %H:%M')
    except:
        return 'Unknown Date'

@app.route('/agente/dashboard')
def agente_dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
        
    user = User.query.filter_by(username=session['username']).first()
    email_configured = bool(user.email and user.email_password and user.email_server)
    
    recent_emails = []
    if email_configured:
        try:
            # Connect to the email server
            imap = imaplib.IMAP4_SSL(user.email_server, user.email_port)
            imap.login(user.email, user.email_password)
            
            # Select the inbox
            imap.select('INBOX')
            
            # Search for all emails and get the latest 10
            _, messages = imap.search(None, 'ALL')
            email_ids = messages[0].split()
            
            # Get the last 10 emails
            for email_id in email_ids[-10:]:
                _, msg_data = imap.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                msg = email.message_from_bytes(email_body)
                
                recent_emails.append({
                    'subject': get_email_subject(msg),
                    'from': msg.get('from', 'Unknown'),
                    'date': get_email_date(msg)
                })
            
            recent_emails.reverse()  # Show newest first
            imap.logout()
            
        except Exception as e:
            flash(f'Error fetching emails: {str(e)}', 'danger')
    
    return render_template('agente_dashboard.html', 
                         email_configured=email_configured,
                         recent_emails=recent_emails)
