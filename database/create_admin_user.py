"""
Create an admin user in the central database.

Usage:
    python database/create_admin_user.py <email> <password> [full_name]

Example:
    python database/create_admin_user.py admin@pricing.local MyPassword123 "System Admin"
"""

import sys
import os
import bcrypt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from sqlalchemy import create_engine, text


def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def create_admin(email, password, full_name="System Admin"):
    uri = Config.get_central_db_uri()
    engine = create_engine(uri)

    with engine.connect() as conn:
        # Check if user already exists
        result = conn.execute(text("SELECT id, email FROM users WHERE email = :email"), {"email": email})
        existing = result.fetchone()
        if existing:
            print(f"User '{email}' already exists (id: {existing[0]})")
            return

        # Hash the password
        password_hash = hash_password(password)

        # Insert admin user
        conn.execute(text("""
            INSERT INTO users (email, password_hash, full_name, role, is_active, email_verified)
            VALUES (:email, :password_hash, :full_name, 'admin', TRUE, TRUE)
        """), {
            "email": email,
            "password_hash": password_hash,
            "full_name": full_name,
        })
        conn.commit()

        print(f"Admin user created successfully!")
        print(f"  Email:    {email}")
        print(f"  Name:     {full_name}")
        print(f"  Role:     admin")
        print(f"\nYou can now log in with these credentials.")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python database/create_admin_user.py <email> <password> [full_name]")
        print("Example: python database/create_admin_user.py admin@pricing.local MyPassword123")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]
    full_name = sys.argv[3] if len(sys.argv) > 3 else "System Admin"

    # Validate password strength
    if len(password) < 8:
        print("Error: Password must be at least 8 characters")
        sys.exit(1)

    create_admin(email, password, full_name)
