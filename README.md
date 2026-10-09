# Cashanova

Cashanova is a currency trend management web app for looking up exchange rates, converting amounts between currencies, and reviewing recent conversions. It uses a Flask and MySQL backend with server-rendered Jinja templates.

> **Data freshness:** Rates come from ExchangeRate-API's `latest/USD` endpoint. The app checks for an update when a rates-related page is requested and caches the provider response for up to 20 hours. The provider's free plan updates about once per day, so these are not live, tick-by-tick market prices.

## Screenshots

Add screenshots in the spaces below. Suggested location: `docs/images/`.

### Dashboard

<!-- Add dashboard screenshot here -->

### Exchange rates

<!-- Add exchange rates screenshot here -->

### Currency converter

<!-- Add currency converter screenshot here -->

## Features

- User registration, login, logout, and profile pages.
- Dashboard summaries for available currencies, the signed-in user's monthly conversions, selected USD rates, and recent conversion history.
- Exchange-rate table with currency search and provider update timestamp.
- Currency converter that supports direct, inverse, and USD cross-rate calculations.
- Conversion history associated with the signed-in user.
- Daily rate retrieval with a provider timestamp and a 20-hour cache window.

## Technology

- Python and Flask
- MySQL with Flask-MySQLdb
- Jinja, Bootstrap, and Font Awesome
- ExchangeRate-API via Python Requests

## Project layout

```text
app.py                       Main Flask application and routes
templates/                   Flask/Jinja pages
currencies.sql               Currency seed data
fetch_currencies.py          Fetch supported currency codes and names
fetch_exchange_rates.py      One-shot exchange-rate fetcher
update_exchange_rates.py     One-shot updater for the MySQL rate table
trend_analysis.py            Copies saved rates into the trend table
user_alerts.py               Currency alert helper
requirements.txt             Python dependencies
backend/app.py               Separate minimal Flask prototype
frontend/                    Separate Vite/React frontend project
```

Run the root `app.py` for the application documented here. `backend/app.py` and `frontend/` are separate project paths and are not wired into this Flask/Jinja application.

## Requirements

- Python 3.10 or newer
- MySQL Server
- An ExchangeRate-API account and API key

## Setup

### 1. Create a virtual environment

From the project root in Command Prompt:

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If using the repository's existing `venv`, activate it instead:

```cmd
venv\Scripts\activate
```

### 2. Create the MySQL database and tables

The app currently connects to `localhost` and the `currency_trend_management` database. Update the MySQL settings near the top of `app.py` to match your local server before running the app.

Run this schema in MySQL. The `conversion_history` table is also created automatically by the app if it is missing.

```sql
CREATE DATABASE IF NOT EXISTS currency_trend_management;
USE currency_trend_management;

CREATE TABLE IF NOT EXISTS users (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS currencies (
    currency_code CHAR(3) NOT NULL PRIMARY KEY,
    currency_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS exchange_rates (
    base_currency CHAR(3) NOT NULL,
    target_currency CHAR(3) NOT NULL,
    exchange_rate DECIMAL(24, 12) NOT NULL,
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (base_currency, target_currency)
);
```

The included [`currencies.sql`](currencies.sql) file can seed currency names after the `currencies` table exists. Alternatively, `fetch_currencies.py` retrieves supported codes from the API.

### 3. Set the API key

Set `EXCHANGE_RATE_API_KEY` in the same terminal session used to start Flask. Use a newly rotated key; never commit it to source control.

**Command Prompt:**

```cmd
set "EXCHANGE_RATE_API_KEY=YOUR_API_KEY"
```

**PowerShell:**

```powershell
$env:EXCHANGE_RATE_API_KEY = "YOUR_API_KEY"
```

### 4. Start the application

In the same terminal where the environment variable is set:

```cmd
python app.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000), register an account, and sign in.

## Rate updates

The dashboard, exchange-rates page, and converter check the saved USD rates when requested. If the latest saved provider timestamp is older than 20 hours, the app requests the provider's latest published rates and saves them. Reloading the page does not make the provider publish newer data.

The standalone `update_exchange_rates.py` and `fetch_exchange_rates.py` scripts also perform a single fetch when run; they are not background schedulers. The included free API data generally refreshes once per day.

## Main routes

| Route | Purpose |
| --- | --- |
| `/register` | Create an account |
| `/login` | Sign in |
| `/dashboard` | View account activity and selected rates |
| `/exchange_rates` | Browse and search saved rates |
| `/currency_converter` | Open the converter |
| `/convert` | Convert an amount (POST) |
| `/get_currencies` | Return available currencies (JSON) |
| `/get_conversions` | Return the signed-in user's history (JSON) |
| `/profile` | View the account profile |

## Notes for development and deployment

- The Flask development server runs with debug mode enabled. Do not expose it to the public internet.
- Configure database credentials and Flask's session secret securely before deployment; the current app contains development-oriented configuration.
- The API key previously shared during development should be revoked and replaced.
- Exchange-rate data is suitable for indicative conversion and learning purposes, not financial execution or guaranteed live pricing.
- Some legacy analysis helpers expect additional trend and alert tables that are not part of the core dashboard setup above.