from app import db
from datetime import datetime

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    level = db.Column(db.String(20), nullable=False)  # 'INFO', 'ERROR', etc.
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
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.String(255), unique=True, nullable=False)
    subject = db.Column(db.String(255))
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)

class EmailMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(255), unique=True, nullable=False)
    thread_id = db.Column(db.String(255), db.ForeignKey('email_thread.thread_id'))
    from_name = db.Column(db.String(255))
    from_email = db.Column(db.String(255))
    subject = db.Column(db.String(255))
    body = db.Column(db.Text)
    date = db.Column(db.DateTime)
    in_reply_to = db.Column(db.String(255))
    references = db.Column(db.Text)  # Store as JSON string
