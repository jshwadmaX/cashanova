import mysql.connector
import requests
import os
from datetime import datetime, timezone

# Database connection details
DB_CONFIG = {
    "host": "localhost",
    "user": "root",  # Replace with your MySQL username
    "password": "root123",  # Replace with your MySQL password
    "database": "currency_trend_management",
}

# API details
BASE_CURRENCY = "USD"  # Change base currency if needed
API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
API_URL = (
    f"https://v6.exchangerate-api.com/v6/{API_KEY}/latest/{BASE_CURRENCY}"
    if API_KEY
    else None
)


def fetch_exchange_rates():
    """Fetch the provider's latest published exchange rates."""
    if not API_URL:
        print("Set EXCHANGE_RATE_API_KEY before fetching exchange rates.")
        return None

    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("result") != "success":
            print("❌ Error fetching exchange rates:", data)
            return None
        updated_at = datetime.fromtimestamp(
            data["time_last_update_unix"], timezone.utc
        ).replace(tzinfo=None)
        return data["conversion_rates"], updated_at

    except requests.exceptions.RequestException as e:
        print("❌ API Request Error:", e)
        return None


def update_database(rates, updated_at):
    """Update the exchange_rates table with new data."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Ensure currencies exist in the table
        for currency_code in rates.keys():
            cursor.execute(
                "INSERT IGNORE INTO currencies (currency_code, currency_name) VALUES (%s, %s)",
                (currency_code, currency_code),
            )

        # Update exchange rates
        for target_currency, rate in rates.items():
            cursor.execute(
                """
                INSERT INTO exchange_rates (base_currency, target_currency, exchange_rate, timestamp)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE exchange_rate = VALUES(exchange_rate), timestamp = VALUES(timestamp)
            """,
                (BASE_CURRENCY, target_currency, rate, updated_at),
            )

        conn.commit()
        cursor.close()
        conn.close()
        print(f"✅ Provider rates saved; published at {updated_at} UTC")

    except mysql.connector.Error as e:
        print("❌ Database Error:", e)


def main():
    """Fetch once; schedule no more often than the provider's update cadence."""
    result = fetch_exchange_rates()
    if result:
        rates, updated_at = result
        update_database(rates, updated_at)


if __name__ == "__main__":
    main()
