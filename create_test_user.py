from app import app, db
from models import User

def create_test_user():
    with app.app_context():
        # Create a test user if it doesn't exist
        test_user = User.query.filter_by(username='testuser').first()
        if not test_user:
            test_user = User(username='testuser')
            test_user.set_password('password123')
            db.session.add(test_user)
            db.session.commit()
            return "Test user created"
        return "Test user already exists"

if __name__ == "__main__":
    print(create_test_user())
