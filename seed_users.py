import os
import bcrypt
from backend.db import DatabaseManager

# Use the same DATABASE_URL logic
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://neondb_owner:npg_Os3FTICbd5pf@ep-fancy-frog-ax8qmowu-pooler.c-4.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

def seed_users():
    users = [
        {"username": "jdoe", "name": "John Doe", "password": "Password123!", "role": "resident", "floors": [1, 2]},
        {"username": "asmith", "name": "Alice Smith", "password": "Password123!", "role": "resident", "floors": [3]},
        {"username": "bwayne", "name": "Bruce Wayne", "password": "Password123!", "role": "resident", "floors": [5]},
    ]
    
    print("Seeding sample users...")
    for user in users:
        # Check if exists
        exists = DatabaseManager.execute_one("SELECT 1 FROM users WHERE username = %s", (user["username"],))
        if exists:
            print(f"User {user['username']} already exists, skipping.")
            continue
            
        hashed = bcrypt.hashpw(user["password"].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        with DatabaseManager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (username, password_hash, name, role) VALUES (%s, %s, %s, %s) RETURNING id",
                    (user["username"], hashed, user["name"], user["role"])
                )
                user_id = cur.fetchone()[0]
                
                # permissions
                for f in user["floors"]:
                    cur.execute(
                        "INSERT INTO floor_permissions (user_id, floor) VALUES (%s, %s)",
                        (user_id, f)
                    )
            conn.commit()
        print(f"Added {user['name']}.")
        
    print("Done seeding users.")

if __name__ == "__main__":
    seed_users()
