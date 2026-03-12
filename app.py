from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Szükséges a session használatához

# ----- Defaults -----
DEFAULT_STOCK = "CSPX.AS"
DEFAULT_BOND = "SXRC.MU"
DEFAULT_GOLD = "4GLD.DE"
DEFAULT_MA = 12
INITIAL_CAPITAL = 100000

# ------------------ Helper functions ------------------

def validate_ticker(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.history(period="1mo")
        return not info.empty
    except:
        return False

def download_monthly(ticker, start_date):
    data = yf.download(
        ticker,
        start=start_date,
        interval="1mo",
        auto_adjust=True,
        progress=False,
        threads=False
    )
    if data.empty:
        raise ValueError(f"No historical data for {ticker}")
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if "Close" not in data.columns:
        raise ValueError(f"No valid price data for {ticker}")
    return data["Close"].dropna()

def build_dataframe(stock, bond, gold, ma_months):
    df = pd.concat([stock, bond, gold], axis=1, join="inner")
    df.columns = ["Stock close", "Bond close", "Gold close"]
    df[["Stock close", "Bond close", "Gold close"]] = df[["Stock close", "Bond close", "Gold close"]].shift(1)
    df["Stock MA"] = df["Stock close"].rolling(ma_months).mean()
    df["Bond MA"] = df["Bond close"].rolling(ma_months).mean()
    df["Gold MA"] = df["Gold close"].rolling(ma_months).mean()
    df["Signal"] = "STOCK"
    df.loc[df["Stock close"] < df["Stock MA"], "Signal"] = "DEFENSIVE"
    df = df.dropna()
    return df

def simulate_strategy(df, mode):
    capital = INITIAL_CAPITAL
    for i in range(1, len(df)):
        prev = df.iloc[i-1]
        curr = df.iloc[i]
        if mode == "stock_only":
            ratio = curr["Stock close"] / prev["Stock close"]
        elif mode == "bond_only":
            ratio = curr["Bond close"] / prev["Bond close"]
        elif mode == "gold_only":
            ratio = curr["Gold close"] / prev["Gold close"]
        elif mode == "stock_bond":
            ratio = (curr["Bond close"] / prev["Bond close"]
                     if prev["Signal"]=="DEFENSIVE" else curr["Stock close"]/prev["Stock close"])
        elif mode == "stock_gold":
            ratio = (curr["Gold close"] / prev["Gold close"]
                     if prev["Signal"]=="DEFENSIVE" else curr["Stock close"]/prev["Stock close"])
        capital *= ratio
    return round(capital,2)

def get_daily_close(ticker):
    data = yf.download(
        ticker,
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return float(data["Close"].dropna().iloc[-1])

def get_currency_rate(symbol):
    """Lekéri az EURHUF vagy USDHUF árfolyamot."""
    try:
        rate = yf.download(symbol, period="1d", interval="1d", progress=False, auto_adjust=True)["Close"].iloc[-1]
        return round(rate,2)
    except:
        return None

# ------------------ Flask route ------------------

@app.route("/", methods=["GET","POST"])
def index():
    errors = {}
    results = None

    if request.method=="POST":
        # POST feldolgozás
        stock = request.form.get("stock") or DEFAULT_STOCK
        bond = request.form.get("bond") or DEFAULT_BOND
        gold = request.form.get("gold") or DEFAULT_GOLD
        try:
            ma = int(request.form.get("ma") or DEFAULT_MA)
            if ma <= 0: raise ValueError
        except ValueError:
            errors["ma"] = "MA months must be positive"

        for ticker,name in zip([stock,bond,gold],["stock","bond","gold"]):
            if not validate_ticker(ticker):
                errors[name] = "Invalid or unsupported ticker"

        if not errors:
            try:
                start_date = datetime.now() - timedelta(days=50*365)
                stock_data = download_monthly(stock, start_date)
                bond_data = download_monthly(bond, start_date)
                gold_data = download_monthly(gold, start_date)
                df = build_dataframe(stock_data, bond_data, gold_data, ma)
                current_signal = df.iloc[-1]["Signal"]
                current_position = stock if current_signal=="STOCK" else f"{bond} or {gold}"
                strategies = {
                    "Stock → Bond": simulate_strategy(df,"stock_bond"),
                    "Stock → Gold": simulate_strategy(df,"stock_gold"),
                    "Stock Only": simulate_strategy(df,"stock_only"),
                    "Bond Only": simulate_strategy(df,"bond_only"),
                    "Gold Only": simulate_strategy(df,"gold_only"),
                }
                last_24 = df.tail(24).round(2)
                results = {
                    "strategies": strategies,
                    "stock_price": round(get_daily_close(stock),2),
                    "bond_price": round(get_daily_close(bond),2),
                    "gold_price": round(get_daily_close(gold),2),
                    "eurhuf": get_currency_rate("EURHUF=X"),
                    "usdhuf": get_currency_rate("USDHUF=X"),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "current_position": current_position,
                    "signal": current_signal,
                    "table": last_24.to_html(classes="table table-striped table-sm dataframe", border=0)
                }
                session['results'] = results
                return redirect(url_for('index'))  # <-- PRG: átirányítás GET-re
            except Exception as e:
                errors["general"] = str(e)
                session['errors'] = errors
                return redirect(url_for('index'))

        session['errors'] = errors
        return redirect(url_for('index'))

    # GET kérés: session-ből olvas
    results = session.pop('results', None)
    errors = session.pop('errors', {})

    stock = DEFAULT_STOCK
    bond = DEFAULT_BOND
    gold = DEFAULT_GOLD
    ma = DEFAULT_MA

    return render_template(
        "index.html",
        stock=stock,
        bond=bond,
        gold=gold,
        ma=ma,
        DEFAULT_STOCK=DEFAULT_STOCK,
        DEFAULT_BOND=DEFAULT_BOND,
        DEFAULT_GOLD=DEFAULT_GOLD,
        DEFAULT_MA=DEFAULT_MA,
        errors=errors,
        results=results
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)