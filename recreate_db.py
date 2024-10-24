from app import app, db

def recreate_database():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("Tables dropped successfully")
        
        # Create all tables with new schema
        db.create_all()
        print("Tables recreated successfully")

if __name__ == "__main__":
    recreate_database()
