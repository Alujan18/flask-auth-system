from app import app, db
from models import User
from sqlalchemy.exc import SQLAlchemyError

def create_test_user():
    try:
        with app.app_context():
            # Check if test user already exists
            test_user = User.query.filter_by(username="testuser").first()
            
            if test_user:
                # Update password if user exists
                try:
                    test_user.set_password("Test@123")
                    db.session.commit()
                    return "Test user password updated successfully"
                except (SQLAlchemyError, ValueError) as e:
                    db.session.rollback()
                    return "Error updating test user password: " + str(e)
            else:
                # Create new test user
                try:
                    test_user = User(username="testuser")  # Use constructor properly
                    test_user.set_password("Test@123")
                    db.session.add(test_user)
                    db.session.commit()
                    return "Test user created successfully"
                except (SQLAlchemyError, ValueError) as e:
                    db.session.rollback()
                    return "Error creating test user: " + str(e)
    except Exception as e:
        return "Error accessing database: " + str(e)

if __name__ == "__main__":
    result = create_test_user()
    print(result)
