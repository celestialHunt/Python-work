import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

# Initialize a Connection Pool (1 to 10 connections)
# This stays alive for the life of your FastAPI app
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20,  # Min 1, Max 20 connections
        user=os.getenv("DB_USER"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        password=os.getenv("DB_PASSWORD")
    )
    print("✅ Database connection pool created")
except Exception as e:
    print(f"❌ Failed to create DB pool: {e}")
    db_pool = None


def get_customer_by_phone(phone_number):
    """Fetches a customer record from the T7Touch database."""
    if not db_pool:
        print("❌ DB Pool not initialized")
        return None

    # Vapi Web Call fallback
    search_number = str(phone_number) if phone_number is not None else "None"
    print(f"DATABASE LOOKUP FOR: {search_number}")

    conn = None
    try:
        # Get a connection from the pool instead of creating a new one
        conn = db_pool.getconn()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM customers WHERE phone_number = %s;"
        cursor.execute(query, (search_number,))
        customer = cursor.fetchone()
        cursor.close()
        # conn.close()

        return customer

    except Exception as e:
        print(f"❌ DB Service Error: {e}")
        return None
    finally:
        # ALWAYS put the connection back in the pool, even if there was an error
        if conn:
            db_pool.putconn(conn)
