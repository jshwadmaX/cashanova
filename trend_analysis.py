import mysql.connector


def update_trend_analysis():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="currency_trend_management",
    )
    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO trend_analysis (base_currency, target_currency, exchange_rate, timestamp)
        SELECT base_currency, target_currency, exchange_rate, timestamp FROM exchange_rates
    """
    )

    db.commit()
    print("✅ Trend analysis table updated.")

    cursor.close()
    db.close()


if __name__ == "__main__":
    update_trend_analysis()
