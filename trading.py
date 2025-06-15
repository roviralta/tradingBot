import time
import hmac
import hashlib
import requests
import os
from dotenv import load_dotenv
import base64
import csv
from flask import Flask, request, jsonify, render_template

load_dotenv()

# --- Bitget credentials (not used in simulation) ---
API_KEY = os.getenv("BITGET_API_KEY")
API_SECRET = os.getenv("BITGET_API_SECRET")
API_PASSPHRASE = os.getenv("BITGET_API_PASSPHRASE")
SYMBOL = os.getenv('SYMBOL', 'BTCUSDT')
MARGIN_COIN = os.getenv('MARGIN_COIN', 'USDT')
BASE_URL = "https://api.bitget.com"
LEVERAGE = 10  

# --- Initialize Flask app ---
app = Flask(__name__)

# --- Simulated Trading State ---
sim_balance = 100.0
sim_position = None
sim_entry_price = 0.0
csv_file = 'sim_trades.csv'

# --- Initialize CSV log ---
if not os.path.exists(csv_file):
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["timestamp", "action", "price", "position", "pnl", "balance"])

# --- Log to CSV ---
def log_to_csv(timestamp, action, price, position, pnl, balance):
    with open(csv_file, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, action, f"{price:.2f}", position, f"{pnl:.2f}", f"{balance:.2f}"])

# --- Simulated Trade Function ---
def simulate_trade(action, price):
    global sim_balance, sim_position, sim_entry_price

    print(f"\n🔁 Simulating trade: {action.upper()} at ${price:.2f}")
    trade_amount = sim_balance * 0.10

    if trade_amount < 1:
        print("⚠️ WARNING: Trade amount is very small, skipping trade.")
        return None

    position_size = round((trade_amount * LEVERAGE) / price, 6)
    pnl = 0.0
    closed = False
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

    # --- Close existing position if opposite action ---
    if sim_position == 'long' and action == 'sell':
        pnl = round((price - sim_entry_price) * position_size, 2)
        sim_balance = round(sim_balance + pnl, 2)
        print(f"✅ Closed LONG at {price:.2f}, PnL: {pnl:.2f} USDT")
        log_to_csv(timestamp, "close_long", price, "none", pnl, sim_balance)
        sim_position = None
        closed = True

    elif sim_position == 'short' and action == 'buy':
        pnl = round((sim_entry_price - price) * position_size, 2)
        sim_balance = round(sim_balance + pnl, 2)
        print(f"✅ Closed SHORT at {price:.2f}, PnL: {pnl:.2f} USDT")
        log_to_csv(timestamp, "close_short", price, "none", pnl, sim_balance)
        sim_position = None
        closed = True

    # --- Open new position only if no active one ---
    if sim_position is None:
        if action == 'buy':
            sim_position = 'long'
            sim_entry_price = price
            print(f"📈 Opened LONG at {price:.2f}")
            log_to_csv(timestamp, "open_long", price, "long", 0.0, sim_balance)

        elif action == 'sell':
            sim_position = 'short'
            sim_entry_price = price
            print(f"📉 Opened SHORT at {price:.2f}")
            log_to_csv(timestamp, "open_short", price, "short", 0.0, sim_balance)

    print(f"💰 Simulated Balance: {sim_balance:.2f} USDT\n")
    return pnl if closed else None

# --- Webhook Endpoint ---
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        if data and 'symbol' in data and data['symbol'] == 'BTCUSDT' and 'action' in data and 'price' in data:
            action = data['action'].lower()
            price = float(data['price'])

            pnl = simulate_trade(action, price)

            return jsonify({
                "status": "success",
                "action": action,
                "price_used": round(price, 2),
                "simulated_balance": round(sim_balance, 2),
                "position": sim_position,
                "entry_price": sim_entry_price,
                "pnl": pnl
            }), 200
        else:
            return jsonify({"status": "error", "message": "Invalid data received"}), 400
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Check Simulation Status ---
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "simulated_balance": round(sim_balance, 2),
        "position": sim_position,
        "entry_price": sim_entry_price
    })


@app.route('/')
def dashboard():
    try:
        trades = []
        if os.path.exists(csv_file):
            with open(csv_file, mode='r') as file:
                reader = csv.reader(file)
                next(reader)  # skip header
                trades = list(reader)

        return render_template(
            'dashboard.html',
            balance=round(sim_balance, 2),
            position=sim_position,
            entry_price=sim_entry_price,
            trades=trades[::-1]  # show latest trade first
        )
    except Exception as e:
        return f"<h1>Error loading dashboard</h1><p>{e}</p>", 500


# --- Reset Simulation State ---
@app.route('/reset', methods=['POST'])
def reset():
    global sim_balance, sim_position, sim_entry_price
    sim_balance = 100.0
    sim_position = None
    sim_entry_price = 0.0

    if os.path.exists(csv_file):
        os.remove(csv_file)
        with open(csv_file, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "action", "price", "position", "pnl", "balance"])

    return jsonify({"status": "reset", "simulated_balance": sim_balance}), 200

# --- Run Flask server ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
