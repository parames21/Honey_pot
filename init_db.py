from app import db, app, User

def init_database():
    with app.app_context():
        # Create all database tables
        db.create_all()
        
        # Check if admin user exists
        admin = User.query.filter_by(email='admin@gmail.com').first()
        if not admin:
            # Create admin user
            admin = User(
                email='admin@gmail.com',
                password='admin123',
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully")
        
        print("Database initialized successfully")

if __name__ == "__main__":
    init_database()