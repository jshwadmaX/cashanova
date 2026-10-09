import mysql.connector
from datetime import datetime

# Database Configuration
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root123",
    "database": "currency_trend_management",
}


def insert_transaction(user_id, base_currency, target_currency, amount, exchange_rate):
    """Insert a new transaction into the database"""
    exchanged_amount = round(amount * exchange_rate, 6)  # Calculate exchanged amount

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # Insert into transactions table
        cursor.execute(
            """
            INSERT INTO transactions (user_id, base_currency, target_currency, amount, exchanged_amount, exchange_rate, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                user_id,
                base_currency,
                target_currency,
                amount,
                exchanged_amount,
                exchange_rate,
                datetime.now(),
            ),
        )

        conn.commit()
        print(
            f"✅ Transaction added: {amount} {base_currency} → {exchanged_amount} {target_currency} @ {exchange_rate}"
        )

    except mysql.connector.Error as e:
        print("Database Error:", e)

    finally:
        cursor.close()
        conn.close()


# Simulating User Transactions
insert_transaction(5, "USD", "EUR", 100, 0.92)  # Example: User converts 100 USD to EUR
insert_transaction(6, "JPY", "USD", 10000, 0.0072)  # Example: 10,000 JPY to USD
