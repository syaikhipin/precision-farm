from database import create_user, init_database
import asyncio

def seed_database():
    # Initialize database tables
    init_database()
    
    # Create default admin user
    try:
        admin_email = 'admin@agridata.com'
        admin_password = 'Admin@123'
        
        # Create admin user with admin role
        response = create_user(admin_email, admin_password, role='admin')
        print(f"Admin user created successfully: {admin_email}")
        
    except Exception as e:
        if 'User already registered' in str(e):
            print(f"Admin user already exists: {admin_email}")
        else:
            print(f"Error creating admin user: {e}")

if __name__ == '__main__':
    seed_database()