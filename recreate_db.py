from app import app, db

with app.app_context():
    # Drop all tables
    db.drop_all()
    print("Tables dropped successfully")
    
    # Create all tables
    db.create_all()
    print("Tables recreated successfully")
