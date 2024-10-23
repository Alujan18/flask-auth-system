from app import app, db
from models import User
from sqlalchemy.exc import SQLAlchemyError

def create_test_user():
    try:
        with app.app_context():
            # Create a test user if it doesn't exist
            test_user = User.query.filter_by(username='testuser').first()
            if not test_user:
                try:
                    test_user = User()
                    test_user.username = 'testuser'
                    test_user.set_password('password123')
                    db.session.add(test_user)
                    db.session.commit()
                    return "Test user created successfully"
                except SQLAlchemyError as e:
                    db.session.rollback()
                    return f"Error creating test user: {str(e)}"
            return "Test user already exists"
    except Exception as e:
        return f"Error accessing database: {str(e)}"

if __name__ == "__main__":
    result = create_test_user()
    print(result)
