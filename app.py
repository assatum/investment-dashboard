from flask import Flask, render_template, request
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import os

app = Flask(__name__)

DEFAULT_STOCK = "CSPX.AS"
DEFAULT_BOND = "SXRC.MU"
DEFAULT_GOLD = "4GLD.DE"
DEFAULT_MA = 12
INITIAL_CAPITAL = 100000


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

    return data["Close"].dropna()


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


def get_fx_rate(pair):

    data = yf.download(
        pair,
        period="5d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=False
    )

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return float(data["Close"].dropna().iloc[-1])


def build_dataframe(stock, bond, gold, ma_months):

    df = pd.concat([stock, bond, gold], axis=1, join="inner")
    df.columns = ["Stock close", "Bond close", "Gold close"]

    df[["Stock close", "Bond close", "Gold close"]] = \
        df[["Stock close", "Bond close", "Gold close"]].shift(1)

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

            if prev["Signal"] == "DEFENSIVE":
                ratio = curr["Bond close"] / prev["Bond close"]
            else:
                ratio = curr["Stock close"] / prev["Stock close"]

        elif mode == "stock_gold":

            if prev["Signal"] == "DEFENSIVE":
                ratio = curr["Gold close"] / prev["Gold close"]
            else:
                ratio = curr["Stock close"] / prev["Stock close"]

        capital *= ratio

    return round(capital, 2)


@app.route("/", methods=["GET", "POST"])
def index():

    errors = {}
    results = None

    stock = DEFAULT_STOCK
    bond = DEFAULT_BOND
    gold = DEFAULT_GOLD
    ma = DEFAULT_MA

    if request.method == "POST":

        stock = request.form.get("stock") or DEFAULT_STOCK
        bond = request.form.get("bond") or DEFAULT_BOND
        gold = request.form.get("gold") or DEFAULT_GOLD

        try:
            ma = int(request.form.get("ma") or DEFAULT_MA)
            if ma <= 0:
                raise ValueError
        except ValueError:
            errors["ma"] = "MA months must be positive"

        for ticker, name in zip(
                [stock, bond, gold],
                ["stock", "bond", "gold"]):

            if not validate_ticker(ticker):
                errors[name] = "Invalid or unsupported ticker"

        if not errors:

            try:

                start_date = datetime.now() - timedelta(days=50*365)

                stock_data = download_monthly(stock, start_date)
                bond_data = download_monthly(bond, start_date)
                gold_data = download_monthly(gold, start_date)

                df = build_dataframe(
                    stock_data,
                    bond_data,
                    gold_data,
                    ma
                )

                current_signal = df.iloc[-1]["Signal"]

                if current_signal == "STOCK":
                    current_position = stock
                else:
                    current_position = f"{bond} or {gold}"

                strategies = {

                    "Stock → Bond":
                        simulate_strategy(df, "stock_bond"),

                    "Stock → Gold":
                        simulate_strategy(df, "stock_gold"),

                    "Stock Only":
                        simulate_strategy(df, "stock_only"),

                    "Bond Only":
                        simulate_strategy(df, "bond_only"),

                    "Gold Only":
                        simulate_strategy(df, "gold_only"),
                }

                last_24 = df.tail(24).round(2)

                chart_data = {

                    "dates":
                        last_24.index.strftime("%Y-%m").tolist(),

                    "stock":
                        last_24["Stock close"].tolist(),

                    "bond":
                        last_24["Bond close"].tolist(),

                    "gold":
                        last_24["Gold close"].tolist()
                }

                eur_huf = round(get_fx_rate("EURHUF=X"), 2)
                usd_huf = round(get_fx_rate("USDHUF=X"), 2)

                results = {

                    "strategies": strategies,

                    "stock_price":
                        round(get_daily_close(stock), 2),

                    "bond_price":
                        round(get_daily_close(bond), 2),

                    "gold_price":
                        round(get_daily_close(gold), 2),

                    "eur_huf": eur_huf,
                    "usd_huf": usd_huf,

                    "timestamp":
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

                    "current_position": current_position,
                    "signal": current_signal,

                    "chart": chart_data,

                    "table":
                        last_24.to_html(
                            classes="table table-striped table-sm dataframe",
                            border=0
                        )
                }

            except Exception as e:
                errors["general"] = str(e)

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

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )