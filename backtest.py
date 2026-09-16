import ccxt
import pandas as pd
import numpy as np

# Parameter
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'
FEE_RATE = 0.001  # 0.1% Börsengebühr pro Trade (Kauf + Verkauf)

print(f"Lade historische 15m-Kerzen für {SYMBOL} herunter...")
exchange = ccxt.binance()
candles = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=1000)

df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

# Indikatoren
df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()

delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / (loss + 1e-9)
df['rsi'] = 100 - (100 / (1 + rs))

high_low = df['high'] - df['low']
high_close = np.abs(df['high'] - df['close'].shift())
low_close = np.abs(df['low'] - df['close'].shift())
tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
df['atr'] = tr.rolling(window=14).mean()

df = df.dropna().reset_index(drop=True)

# Simulation
capital = 100.0
position_size = 5.0
trades = []

in_pos = False
entry_price = 0.0
stop_loss = 0.0
highest = 0.0
trailing_active = False

for i in range(len(df)):
    row = df.iloc[i]

    if not in_pos:
        # Einstiegssignal
        if row['close'] > row['ema_200'] and row['rsi'] < 35:
            in_pos = True
            entry_price = row['close']
            stop_loss = entry_price - (row['atr'] * 1.5)
            highest = entry_price
            trailing_active = False
    else:
        # Kerzen-Extrema prüfen
        if row['high'] > highest:
            highest = row['high']

        # Break-Even Prüfung
        if row['high'] >= (entry_price + (row['atr'] * 1.5)) and stop_loss < entry_price:
            stop_loss = entry_price

        # Trailing TP aktivieren
        if not trailing_active and row['high'] >= (entry_price + (row['atr'] * 2.5)):
            trailing_active = True

        exit_price = None

        # Stop-Loss Treffer?
        if row['low'] <= stop_loss:
            exit_price = stop_loss
            reason = "Stop-Loss"
        # Trailing Take-Profit Treffer?
        elif trailing_active and row['low'] <= (highest * 0.985):
            exit_price = highest * 0.985
            reason = "Trailing-TP"

        if exit_price:
            raw_pnl_pct = (exit_price - entry_price) / entry_price
            net_pnl_pct = raw_pnl_pct - (2 * FEE_RATE)  # Kauf- + Verkaufsgebühr
            profit_eur = position_size * net_pnl_pct
            capital += profit_eur

            trades.append({
                'entry_time': row['timestamp'],
                'entry': entry_price,
                'exit': exit_price,
                'pnl_pct': net_pnl_pct * 100,
                'profit_eur': profit_eur,
                'reason': reason
            })
            in_pos = False

# Auswertung
results_df = pd.DataFrame(trades)
print("\n" + "="*45)
print("           BACKTESTING ERGEBNIS")
print("="*45)
if len(results_df) == 0:
    print("Keine Trades im Betrachtungszeitraum ausgelöst.")
else:
    wins = results_df[results_df['pnl_pct'] > 0]
    losses = results_df[results_df['pnl_pct'] <= 0]
    win_rate = (len(wins) / len(results_df)) * 100
    gross_profit = wins['profit_eur'].sum()
    gross_loss = abs(losses['profit_eur'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.nan

    print(f"Anzahl Trades:        {len(results_df)}")
    print(f"Gewinn-Trades:        {len(wins)} ({win_rate:.1f}%)")
    print(f"Verlust-Trades:       {len(losses)} ({100 - win_rate:.1f}%)")
    print(f"Endkapital (von 100€): {capital:.2f} €")
    print(f"Netto-Gewinn/Verlust:  {capital - 100.0:+.2f} €")
    print(f"Profit-Faktor:        {profit_factor:.2f}")
    print("="*45)
