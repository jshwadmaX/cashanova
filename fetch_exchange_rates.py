import requests
import mysql.connector
import os
from datetime import datetime, timezone

api_key = os.getenv("EXCHANGE_RATE_API_KEY")
if not api_key:
    raise SystemExit("Set EXCHANGE_RATE_API_KEY before fetching exchange rates.")

# Database connection
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root123",
    database="currency_trend_management",
)
cursor = conn.cursor()

api_url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"

response = requests.get(api_url, timeout=10)
response.raise_for_status()
data = response.json()

if data["result"] == "success":
    base_currency = data["base_code"]
    exchange_rates = data["conversion_rates"]
    updated_at = datetime.fromtimestamp(
        data["time_last_update_unix"], timezone.utc
    ).replace(tzinfo=None)

    for target_currency, rate in exchange_rates.items():
        cursor.execute(
            "INSERT IGNORE INTO currencies (currency_code, currency_name) VALUES (%s, %s)",
            (target_currency, target_currency),
        )
        cursor.execute(
            """
            INSERT INTO exchange_rates (base_currency, target_currency, exchange_rate, timestamp)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE exchange_rate = VALUES(exchange_rate), timestamp = VALUES(timestamp)
        """,
            (base_currency, target_currency, rate, updated_at),
        )
else:
    raise SystemExit(f"Exchange-rate API error: {data.get('error-type', 'unknown error')}")

# Commit and close connection
conn.commit()
cursor.close()
conn.close()
