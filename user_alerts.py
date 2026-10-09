import mysql.connector


def check_alerts():
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="currency_trend_management",
    )
    cursor = db.cursor()

    cursor.execute(
        """
        UPDATE user_alerts ua
        JOIN exchange_rates er
        ON ua.base_currency = er.base_currency AND ua.target_currency = er.target_currency
        SET ua.alert_status = 'Triggered'
        WHERE er.exchange_rate >= ua.threshold_rate AND ua.alert_status = 'Pending'
    """
    )

    db.commit()
    print("✅ Checked and updated user alerts.")

    cursor.close()
    db.close()


if __name__ == "__main__":
    check_alerts()
