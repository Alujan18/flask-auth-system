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
