import sys
import os

from main import SessionLocal, User
from auth import verify_password, get_password_hash

def seed_users():
    db = SessionLocal()
    users = [
        {"name": "Citizen John", "email": "citizen@city.com", "role": "CITIZEN", "password": "password", "eco_points": 1240},
        {"name": "Driver Dave", "email": "driver@city.com", "role": "DRIVER", "password": "password", "eco_points": 0},
        {"name": "Admin Alice", "email": "admin@city.com", "role": "ADMIN", "password": "password", "eco_points": 0},
        {"name": "Elena Santos", "email": "elena@city.com", "role": "CITIZEN", "password": "password", "eco_points": 2410},
    ]

    for u in users:
        existing_user = db.query(User).filter(User.email == u["email"]).first()
        hashed_pwd = get_password_hash(u["password"])
        if not existing_user:
            new_user = User(
                name=u["name"],
                email=u["email"],
                password_hash=hashed_pwd,
                role=u["role"],
                eco_points=u["eco_points"]
            )
            db.add(new_user)
            print(f"Added {u['role']} user: {u['email']}")
        else:
            if not verify_password(u["password"], existing_user.password_hash):
                existing_user.password_hash = hashed_pwd
                print(f"Updated password hash for existing user: {u['email']}")
            else:
                print(f"User {u['email']} already exists and password is correct.")
            
    db.commit()
    db.close()
    print("Database seeded with credentials successfully.")

if __name__ == "__main__":
    seed_users()

