
from app import app, db
from models import User

def create_test_user():
    with app.app_context():
        test_user = User.query.filter_by(username='testuser').first()
        if not test_user:
            test_user = User()
            test_user.username = 'testuser'
            test_user.set_password('password123')
            db.session.add(test_user)
            db.session.commit()
            print("Test user created")
        else:
            print("Test user already exists")

if __name__ == "__main__":
    create_test_user()
