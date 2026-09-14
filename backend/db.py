import os
import logging
import psycopg2
from psycopg2 import pool
from contextlib import contextmanager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Neon DB Connection string from environment variable
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/elevator_db" # Fallback for local testing
)

class DatabaseManager:
    @classmethod
    @contextmanager
    def get_connection(cls):
        # In Serverless environments (like Vercel), connection pooling can lead to 
        # 'server closed connection unexpectedly' errors when the function freezes.
        # It's safer to open a new connection per invocation.
        connection = psycopg2.connect(DATABASE_URL)
        try:
            yield connection
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            connection.close()

    @classmethod
    def execute_query(cls, query, params=None, fetch=False):
        """Execute a query and optionally return results."""
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                if fetch:
                    try:
                        return cur.fetchall()
                    except psycopg2.ProgrammingError:
                        return None
                conn.commit()
                return None

    @classmethod
    def execute_one(cls, query, params=None):
        """Execute a query and return a single row."""
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params or ())
                try:
                    return cur.fetchone()
                except psycopg2.ProgrammingError:
                    return None

    @classmethod
    def init_db(cls, migrations_dir="../database/migrations"):
        """Run all migrations in order to initialize the database tables (REQ-46)."""
        logger.info("Initializing database schema...")
        if not os.path.exists(migrations_dir):
            # Fallback path if run from backend/ directory
            migrations_dir = os.path.join(os.path.dirname(__file__), "..", "database", "migrations")
        
        if not os.path.exists(migrations_dir):
            logger.warning(f"Migrations directory not found at {migrations_dir}")
            return

        migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith(".sql")])
        
        with cls.get_connection() as conn:
            with conn.cursor() as cur:
                for file_name in migration_files:
                    file_path = os.path.join(migrations_dir, file_name)
                    logger.info(f"Applying migration: {file_name}")
                    with open(file_path, "r", encoding="utf-8") as f:
                        sql = f.read()
                        if sql.strip():
                            cur.execute(sql)
            conn.commit()
        logger.info("Database migrations applied successfully.")
