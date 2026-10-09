import mysql.connector
import requests
import os

# Database connection details
db_config = {
    "host": "localhost",  # Change if your MySQL is hosted elsewhere
    "user": "root",  # Change to your MySQL username
    "password": "root123",  # Change to your MySQL password
    "database": "currency_trend_management",  # Ensure this database exists
}

# API Key & URL
api_key = os.getenv("EXCHANGE_RATE_API_KEY")
if not api_key:
    raise SystemExit("Set EXCHANGE_RATE_API_KEY before fetching currencies.")
api_url = f"https://v6.exchangerate-api.com/v6/{api_key}/codes"

try:
    # Fetch currency data from API
    response = requests.get(api_url, timeout=10)
    response.raise_for_status()  # Raise an error for HTTP failures
    data = response.json()

    # Extract currency codes and names
    if "supported_codes" not in data:
        print("Error: 'supported_codes' not found in API response.")
    else:
        currencies = data["supported_codes"]

        # Connect to MySQL
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Create currencies table if not exists
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS currencies (
                currency_code VARCHAR(3) PRIMARY KEY,
                currency_name VARCHAR(100) NOT NULL
            )
        """
        )
        conn.commit()

        # Insert data into table
        insert_query = "INSERT INTO currencies (currency_code, currency_name) VALUES (%s, %s) ON DUPLICATE KEY UPDATE currency_name=VALUES(currency_name)"
        cursor.executemany(insert_query, currencies)
        conn.commit()

        print(f"Inserted {cursor.rowcount} currencies into the database.")

except requests.exceptions.RequestException as e:
    print(f"API Error: {e}")
except mysql.connector.Error as e:
    print(f"MySQL Error: {e}")
finally:
    if "conn" in locals() and conn.is_connected():
        cursor.close()
        conn.close()
