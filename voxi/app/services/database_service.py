import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()


def get_customer_by_phone(phone_number):
    """Fetches a customer record from the T7Touch database."""
    try:
        conn = psycopg2.connect(
            user=os.getenv("DB_USER"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            database=os.getenv("DB_NAME"),
            # password=os.getenv("DB_PASSWORD") # Optional
        )
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        query = "SELECT * FROM customers WHERE phone_number = %s;"
        cursor.execute(query, (phone_number,))
        customer = cursor.fetchone()
        cursor.close()
        conn.close()

        return customer

    except Exception as e:
        print(f"❌ DB Service Error: {e}")

        return None
