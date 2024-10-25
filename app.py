import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Add secret key for Flask sessions
app.secret_key = os.environ.get('SECRET_KEY') or os.urandom(24)

# Setup configuration
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Load email configuration
email_config = {
    'IMAP_SERVER': os.getenv('IMAP_SERVER', ''),
    'IMAP_PORT': os.getenv('IMAP_PORT', ''),
    'SMTP_SERVER': os.getenv('SMTP_SERVER', ''),
    'SMTP_PORT': os.getenv('SMTP_PORT', ''),
    'EMAIL_ADDRESS': os.getenv('EMAIL_ADDRESS', ''),
    'EMAIL_PASSWORD': os.getenv('EMAIL_PASSWORD', '')
}

# Add email configuration to app.config
app.config.update(email_config)

db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        from models import User
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('base.html')

with app.app_context():
    import models
    db.create_all()
