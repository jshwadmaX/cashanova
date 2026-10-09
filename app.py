from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import hashlib
import os
from functools import wraps
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests

app = Flask(__name__)

# Secret key for sessions
app.secret_key = os.urandom(24)

# MySQL configuration
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = "root123"
app.config["MYSQL_DB"] = "currency_trend_management"

# Initialize MySQL
mysql = MySQL(app)

EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
EXCHANGE_RATE_API_URL = "https://v6.exchangerate-api.com/v6/{}/latest/USD"


def refresh_exchange_rates():
    """Refresh the USD-based rates when the provider's daily data is stale."""
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cursor.execute(
            "SELECT MAX(timestamp) AS updated_at FROM exchange_rates WHERE base_currency = 'USD'"
        )
        cached_at = cursor.fetchone()["updated_at"]
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        if cached_at and (now_utc - cached_at) < timedelta(hours=20):
            return {"updated_at": cached_at, "message": "Provider rates are refreshed daily."}

        if not EXCHANGE_RATE_API_KEY:
            return {
                "updated_at": cached_at,
                "message": "Set EXCHANGE_RATE_API_KEY to refresh rates from the provider.",
            }

        response = requests.get(
            EXCHANGE_RATE_API_URL.format(EXCHANGE_RATE_API_KEY), timeout=10
        )
        response.raise_for_status()
        payload = response.json()
        rates = payload.get("conversion_rates")
        if payload.get("result") != "success" or not isinstance(rates, dict):
            raise ValueError("The exchange-rate provider returned an invalid response.")

        provider_timestamp = payload.get("time_last_update_unix")
        if not provider_timestamp:
            raise ValueError("The provider response did not include its update time.")
        updated_at = datetime.fromtimestamp(
            int(provider_timestamp), timezone.utc
        ).replace(tzinfo=None)

        for currency_code, rate in rates.items():
            cursor.execute(
                "INSERT IGNORE INTO currencies (currency_code, currency_name) VALUES (%s, %s)",
                (currency_code, currency_code),
            )
            cursor.execute(
                """
                INSERT INTO exchange_rates
                    (base_currency, target_currency, exchange_rate, timestamp)
                VALUES ('USD', %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    exchange_rate = VALUES(exchange_rate), timestamp = VALUES(timestamp)
                """,
                (currency_code, rate, updated_at),
            )

        mysql.connection.commit()
        return {"updated_at": updated_at, "message": "Rates loaded from ExchangeRate-API."}
    except Exception as error:
        mysql.connection.rollback()
        print(f"Exchange-rate refresh failed: {error}")
        return {
            "updated_at": locals().get("cached_at"),
            "message": "Could not refresh rates; showing saved rates when available.",
        }
    finally:
        cursor.close()


def ensure_conversion_history_table():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversion_history (
                id INT NOT NULL AUTO_INCREMENT,
                user_id INT NOT NULL,
                from_currency CHAR(3) NOT NULL,
                to_currency CHAR(3) NOT NULL,
                amount DECIMAL(24, 8) NOT NULL,
                converted_amount DECIMAL(24, 8) NOT NULL,
                rate_used DECIMAL(24, 12) NOT NULL,
                conversion_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX idx_conversion_history_user_date (user_id, conversion_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        mysql.connection.commit()
    finally:
        cursor.close()


# Helper: Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "loggedin" not in session:
            flash("Please login to access this page", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return decorated_function


# Home route
@app.route("/")
def home():
    if "loggedin" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_hash = hash_password(password)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            "SELECT * FROM users WHERE username = %s AND password_hash = %s",
            (username, password_hash),
        )
        user = cursor.fetchone()

        if user:
            session["loggedin"] = True
            session["id"] = user["id"]
            session["username"] = user["username"]
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            msg = "Incorrect username/password!"

    return render_template("login.html", msg=msg)


# Signup
@app.route("/signup", methods=["GET", "POST"])
def signup():
    msg = ""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        email = request.form.get("email")
        password_hash = hash_password(password)

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        cursor.execute(
            "SELECT * FROM users WHERE username = %s OR email = %s",
            (username, email),
        )
        account = cursor.fetchone()

        if account:
            msg = "Account already exists!"
        elif not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            msg = "Invalid email address!"
        elif not re.match(r"[A-Za-z0-9]+", username):
            msg = "Username must contain only characters and numbers!"
        elif not username or not password or not email:
            msg = "Please fill out the form!"
        else:
            cursor.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                (username, email, password_hash),
            )
            mysql.connection.commit()
            flash("You have successfully registered!", "success")
            return redirect(url_for("login"))

    return render_template("signup.html", msg=msg)


# Logout
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out", "info")
    return redirect(url_for("login"))


# Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    ensure_conversion_history_table()
    refresh_status = refresh_exchange_rates()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session["id"],))
    account = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as count FROM currencies")
    currency_count = cursor.fetchone()["count"]
    cursor.execute(
        """
        SELECT COUNT(*) AS count FROM conversion_history
        WHERE user_id = %s
          AND conversion_date >= DATE_FORMAT(CURDATE(), '%%Y-%%m-01')
        """,
        (session["id"],),
    )
    monthly_conversions = cursor.fetchone()["count"]
    cursor.execute(
        """
        SELECT target_currency, exchange_rate, timestamp
        FROM exchange_rates
        WHERE base_currency = 'USD'
          AND target_currency IN ('EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'INR', 'CHF', 'CNY')
        ORDER BY target_currency
        """
    )
    featured_rates = cursor.fetchall()
    cursor.execute(
        """
        SELECT from_currency, to_currency, amount, converted_amount, conversion_date
        FROM conversion_history
        WHERE user_id = %s
        ORDER BY conversion_date DESC
        LIMIT 5
        """,
        (session["id"],),
    )
    recent_conversions = cursor.fetchall()

    stats = {
        "total_currencies": currency_count,
        "monthly_conversions": monthly_conversions,
        "latest_rate_update": refresh_status["updated_at"],
    }

    return render_template(
        "dashboard.html",
        account=account,
        stats=stats,
        featured_rates=featured_rates,
        recent_conversions=recent_conversions,
        refresh_message=refresh_status["message"],
    )


# Add a new route to get currencies
@app.route("/get_currencies")
@login_required
def get_currencies():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        "SELECT currency_code, currency_name FROM currencies ORDER BY currency_code"
    )
    currencies = cursor.fetchall()
    return jsonify({"success": True, "currencies": currencies})


# Add a route to get conversion history
@app.route("/get_conversions")
@login_required
def get_conversions():
    try:
        ensure_conversion_history_table()
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(
            """
            SELECT 
                DATE_FORMAT(conversion_date, '%Y-%m-%d %H:%i') as conversion_date,
                from_currency,
                to_currency,
                amount,
                converted_amount,
                rate_used
            FROM conversion_history
            WHERE user_id = %s
            ORDER BY conversion_date DESC
            LIMIT 50
        """,
            (session["id"],),
        )

        conversions = cursor.fetchall()
        return jsonify({"success": True, "conversions": conversions})

    except Exception as e:
        print(f"Error fetching conversions: {e}")
        return jsonify({"success": False, "message": str(e)})


# Add a route to get trend data
@app.route("/get_trend_data")
@login_required
def get_trend_data():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Get the last 30 days of data for some major currencies against USD
        cursor.execute(
            """
            SELECT base_currency, target_currency, exchange_rate, DATE(timestamp) as date
            FROM trend_analysis
            WHERE base_currency = 'USD' AND target_currency IN ('EUR', 'GBP', 'JPY', 'CAD', 'AUD')
            AND timestamp >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY target_currency, timestamp ASC
        """
        )

        trend_data = cursor.fetchall()

        if not trend_data:
            return jsonify({"success": False, "message": "No trend data available"})

        # Process the data for Chart.js
        dates = []
        datasets = {}

        for record in trend_data:
            date_str = record["date"].strftime("%Y-%m-%d")
            if date_str not in dates:
                dates.append(date_str)

            currency = record["target_currency"]
            if currency not in datasets:
                datasets[currency] = {
                    "label": f"{currency}/USD",
                    "data": [],
                    "borderColor": get_color_for_currency(currency),
                    "fill": False,
                    "tension": 0.1,
                }

            datasets[currency]["data"].append(record["exchange_rate"])

        # Convert datasets dict to list for Chart.js
        datasets_list = list(datasets.values())

        return jsonify({"success": True, "labels": dates, "datasets": datasets_list})

    except Exception as e:
        print(f"Error fetching trend data: {e}")
        return jsonify({"success": False, "message": str(e)})


# Helper function to assign consistent colors to currencies
def get_color_for_currency(currency):
    colors = {
        "EUR": "rgb(54, 162, 235)",
        "GBP": "rgb(255, 99, 132)",
        "JPY": "rgb(75, 192, 192)",
        "CAD": "rgb(255, 159, 64)",
        "AUD": "rgb(153, 102, 255)",
        "CHF": "rgb(255, 205, 86)",
        "CNY": "rgb(201, 203, 207)",
        "INR": "rgb(255, 99, 71)",
    }
    return colors.get(currency, "rgb(0, 0, 0)")


# Function to update increased and decreased rates tables
@app.route("/update_rate_tables", methods=["POST"])
@login_required
def update_rate_tables():
    try:
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

        # Clear existing data from the tables
        cursor.execute("TRUNCATE TABLE increased_rates")
        cursor.execute("TRUNCATE TABLE decreased_rates")

        # Get the latest rates and previous rates from trend_analysis
        cursor.execute(
            """
            SELECT 
                t1.base_currency, 
                t1.target_currency, 
                t2.exchange_rate AS old_rate, 
                t1.exchange_rate AS new_rate,
                t1.timestamp
            FROM 
                (SELECT * FROM trend_analysis WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 1 DAY)) t1
            JOIN 
                (SELECT * FROM trend_analysis WHERE timestamp < DATE_SUB(NOW(), INTERVAL 1 DAY) 
                 AND timestamp >= DATE_SUB(NOW(), INTERVAL 2 DAY)) t2
            ON 
                t1.base_currency = t2.base_currency AND t1.target_currency = t2.target_currency
            """
        )
        rates = cursor.fetchall()

        # Separate into increased and decreased rates
        for rate in rates:
            if rate["new_rate"] > rate["old_rate"]:
                cursor.execute(
                    """
                    INSERT INTO increased_rates 
                    (base_currency, target_currency, old_rate, new_rate, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        rate["base_currency"],
                        rate["target_currency"],
                        rate["old_rate"],
                        rate["new_rate"],
                        rate["timestamp"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO decreased_rates 
                    (base_currency, target_currency, old_rate, new_rate, timestamp)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        rate["base_currency"],
                        rate["target_currency"],
                        rate["old_rate"],
                        rate["new_rate"],
                        rate["timestamp"],
                    ),
                )

        mysql.connection.commit()
        return jsonify({"success": True, "message": "Rate tables updated successfully"})

    except Exception as e:
        print(f"Error updating rate tables: {e}")
        return jsonify({"success": False, "message": str(e)})


# Exchange Rates
@app.route("/exchange_rates")
@login_required
def exchange_rates():
    refresh_status = refresh_exchange_rates()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(
        """
        SELECT base_currency, target_currency, exchange_rate, timestamp
        FROM exchange_rates
        WHERE base_currency = 'USD'
        ORDER BY target_currency
        """
    )
    rates = cursor.fetchall()
    return render_template(
        "exchange_rates.html",
        rates=rates,
        refresh_message=refresh_status["message"],
        latest_update=refresh_status["updated_at"],
    )


# Currency Converter Page
@app.route("/currency_converter")
@login_required
def currency_converter():
    refresh_exchange_rates()
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT currency_code FROM currencies ORDER BY currency_code")
    currencies = cursor.fetchall()
    currency_codes = [currency["currency_code"] for currency in currencies]

    return render_template("currency_converter.html", currencies=currency_codes)


# Conversion Logic
@app.route("/convert", methods=["POST"])
@login_required
def convert():
    cursor = None
    try:
        amount = Decimal(request.form.get("amount", ""))
        from_currency = request.form.get("from_currency", "").upper()
        to_currency = request.form.get("to_currency", "").upper()

        if not amount.is_finite() or amount <= 0:
            return jsonify(
                {"success": False, "message": "Amount must be greater than 0"}
            )
        if len(from_currency) != 3 or len(to_currency) != 3:
            return jsonify({"success": False, "message": "Select valid currencies."})

        ensure_conversion_history_table()
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        exchange_rate = Decimal("1")

        if from_currency != to_currency:
            cursor.execute(
                """
                SELECT exchange_rate FROM exchange_rates
                WHERE base_currency = %s AND target_currency = %s
                ORDER BY timestamp DESC LIMIT 1
                """,
                (from_currency, to_currency),
            )
            direct_result = cursor.fetchone()

            if direct_result:
                exchange_rate = Decimal(str(direct_result["exchange_rate"]))
            else:
                cursor.execute(
                    """
                    SELECT exchange_rate FROM exchange_rates
                    WHERE base_currency = %s AND target_currency = %s
                    ORDER BY timestamp DESC LIMIT 1
                    """,
                    (to_currency, from_currency),
                )
                inverse_result = cursor.fetchone()

                if inverse_result:
                    inverse_rate = Decimal(str(inverse_result["exchange_rate"]))
                    if inverse_rate == 0:
                        return jsonify({"success": False, "message": "Invalid exchange rate."})
                    exchange_rate = Decimal("1") / inverse_rate
                else:
                    cursor.execute(
                        """
                        SELECT target_currency, exchange_rate FROM exchange_rates
                        WHERE base_currency = 'USD'
                          AND target_currency IN (%s, %s)
                        """,
                        (from_currency, to_currency),
                    )
                    usd_rates = {
                        row["target_currency"]: Decimal(str(row["exchange_rate"]))
                        for row in cursor.fetchall()
                    }
                    source_rate = Decimal("1") if from_currency == "USD" else usd_rates.get(from_currency)
                    target_rate = Decimal("1") if to_currency == "USD" else usd_rates.get(to_currency)
                    if not source_rate or not target_rate:
                        return jsonify(
                            {
                                "success": False,
                                "message": f"Exchange rate not found for {from_currency} to {to_currency}.",
                            }
                        )
                    exchange_rate = target_rate / source_rate

        converted_amount = (amount * exchange_rate).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        try:
            cursor.execute(
                """
                INSERT INTO conversion_history 
                (user_id, from_currency, to_currency, amount, converted_amount, rate_used, conversion_date)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    session["id"],
                    from_currency,
                    to_currency,
                    amount,
                    converted_amount,
                    exchange_rate,
                ),
            )
            mysql.connection.commit()
        except Exception as error:
            mysql.connection.rollback()
            print(f"Error logging conversion: {error}")

        return jsonify(
            {
                "success": True,
                "converted_amount": float(converted_amount),
                "rate_used": float(exchange_rate),
            }
        )

    except (InvalidOperation, ValueError):
        return jsonify(
            {
                "success": False,
                "message": "Invalid amount format. Please enter a valid number.",
            }
        )
    except Exception as error:
        print(f"Conversion error: {error}")
        return jsonify(
            {
                "success": False,
                "message": "An error occurred during conversion. Please try again.",
            }
        )
    finally:
        if cursor:
            cursor.close()


# User Profile
@app.route("/profile")
@login_required
def profile():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE id = %s", (session["id"],))
    account = cursor.fetchone()
    return render_template("profile.html", account=account)


# Edit Profile
@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    if request.method == "POST":
        new_username = request.form["username"]
        new_email = request.form["email"]

        cursor.execute(
            "SELECT * FROM users WHERE (username = %s OR email = %s) AND id != %s",
            (new_username, new_email, session["id"]),
        )
        existing = cursor.fetchone()

        if existing:
            flash("Username or email already in use.", "danger")
            return redirect(url_for("edit_profile"))

        cursor.execute(
            "UPDATE users SET username = %s, email = %s WHERE id = %s",
            (new_username, new_email, session["id"]),
        )
        mysql.connection.commit()
        session["username"] = new_username
        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    cursor.execute("SELECT * FROM users WHERE id = %s", (session["id"],))
    account = cursor.fetchone()
    return render_template("edit_profile.html", account=account)


# Run the app
if __name__ == "__main__":
    app.run(debug=True, port=3000)
