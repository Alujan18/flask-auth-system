import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

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

with app.app_context():
    import models
    import routes
    db.create_all()
