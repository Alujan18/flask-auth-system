from app import db
from werkzeug.security import generate_password_hash, check_password_hash
import re

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    @staticmethod
    def is_valid_username(username):
        # Username should be 3-64 chars long and contain only letters, numbers, and underscores
        pattern = re.compile(r'^[a-zA-Z0-9_]{3,64}$')
        return bool(pattern.match(username))

    @staticmethod
    def is_valid_password(password):
        # Password should be at least 8 chars long and contain at least one uppercase, 
        # one lowercase, one number, and one special character
        if len(password) < 8:
            return False
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'[0-9]', password):
            return False
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            return False
        return True

    def set_password(self, password):
        if not self.is_valid_password(password):
            raise ValueError("Password does not meet security requirements")
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
