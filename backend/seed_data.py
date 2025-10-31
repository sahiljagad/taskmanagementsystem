from database import SessionLocal, init_db
from models import User, Project
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def seed_database():
    
    # Initialize database first
    init_db()
    
    db = SessionLocal()
    
    try:
        # Create users
        users = [
            User(
                username="Han",
                email="han@example.com",
                full_name="Han Solo",
                hashed_password=hash_password("password123")
            ),
            User(
                username="Chewy",
                email="chewbacca@example.com",
                full_name="Chewbacca",
                hashed_password=hash_password("password123")
            ),
            User(
                username="Luke",
                email="luke@example.com",
                full_name="Luke Skywalker",
                hashed_password=hash_password("password123")
            )
        ]
        
        for user in users:
            db.add(user)
        
        db.commit()
        print(f"Created users")
        
        # Refresh to get IDs
        for user in users:
            db.refresh(user)
        
        # Create projects
        projects = [
            Project(
                name="Fix Hyperdrive",
                description="Improve hyperdrive performance and reliability",
                owner_id=users[0].id
            ),
        ]
        
        for project in projects:
            db.add(project)
        
        db.commit()
        print(f"Created project")
        
        # Refresh to get IDs
        for project in projects:
            db.refresh(project)

        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()