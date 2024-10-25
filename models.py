from app import db
from flask_login import UserMixin
from datetime import datetime
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Log(db.Model):
    __tablename__ = 'log'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    level = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)

    @property
    def level_class(self):
        return {
            'INFO': 'info',
            'SUCCESS': 'success',
            'WARNING': 'warning',
            'ERROR': 'danger'
        }.get(self.level, 'secondary')

class EmailThread(db.Model):
    __tablename__ = 'email_thread'
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.String(255), unique=True, nullable=False)
    subject = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    reply_by_ia = db.Column(db.Boolean, nullable=False, default=False)

class EmailMessage(db.Model):
    __tablename__ = 'email_message'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(255), unique=True, nullable=False)
    thread_id = db.Column(db.String(255), db.ForeignKey('email_thread.thread_id'), nullable=False)
    from_name = db.Column(db.String(255))
    from_email = db.Column(db.String(255), nullable=False)
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    in_reply_to = db.Column(db.String(255))
    references = db.Column(db.Text)
    folder = db.Column(db.String(50), nullable=False, default='INBOX')
    reply_by_ia = db.Column(db.Boolean, nullable=False, default=False)
