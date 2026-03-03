from flask import Flask, render_template, request, url_for
import pandas as pd
import numpy as np
from datetime import datetime
import os

app = Flask(__name__)

# Példa alap logika, helyettesítheted a saját számításokkal
DEFAULT_STOCK = "SPY"
DEFAULT_BOND = "TLT"
DEFAULT_GOLD = "GLD"

@app.route("/", methods=["GET", "POST"])
def index():
    errors = {}
    stock = request.form.get("stock", DEFAULT_STOCK)
    bond = request.form.get("bond", DEFAULT_BOND)
    gold = request.form.get("gold", DEFAULT_GOLD)
    ma = request.form.get("ma", 20)

    # Dummy adatok táblázathoz
    dates = pd.date_range(end=datetime.today(), periods=24, freq='MS')
    prices = np.random.rand(24) * 100 + 100
    df = pd.DataFrame({"Date": dates.strftime("%Y-%m-%d"), "Close": prices})

    # Legújabb dátum legyen felül
    df = df.iloc[::-1]

    # HTML táblázat
    table_html = df.to_html(classes="table table-sm table-hover table-striped", index=False, border=0)

    results = {
        "signal": "STOCK",
        "current_position": "Hold",
        "strategies": {"Strategy A": 10500, "Strategy B": 10800},
        "stock_price": round(prices[-1],2),
        "bond_price": 105.12,
        "gold_price": 2012.34,
        "table": table_html,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return render_template("index.html",
                           stock=stock,
                           bond=bond,
                           gold=gold,
                           ma=ma,
                           DEFAULT_STOCK=DEFAULT_STOCK,
                           DEFAULT_BOND=DEFAULT_BOND,
                           DEFAULT_GOLD=DEFAULT_GOLD,
                           errors=errors,
                           results=results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)