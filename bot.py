import time
import ccxt
import pandas as pd
import numpy as np
import logging
from datetime import datetime

# ==========================================
# KONFIGURATION & RISIKO-PARAMETER
# ==========================================
EXCHANGE_ID = 'kraken'  # 'kraken' oder 'binance'
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'

DRY_RUN = True          # True = Nur simulieren, False = Echte Orders platzieren
MAX_POSITION_EUR = 5.0  # Max. Einsatz pro Trade

# Strategie-Parameter
EMA_TREND_PERIOD = 200
RSI_PERIOD = 14
RSI_OVERSOLD = 35
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5   # Stop-Loss = 1.5x ATR unter Einstieg
ATR_TP_ACTIVATION = 2.5  # Trailing TP aktiviert sich ab 2.5x ATR
TRAILING_CALLBACK = 0.015 # 1.5% Rücksetzer vom Hoch löst TP aus

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

# ==========================================
# INDIKATOR-BERECHNUNGEN (Reines Pandas)
# ==========================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    # 1. EMA 200 (Trend-Filter)
    df['ema_200'] = df['close'].ewm(span=EMA_TREND_PERIOD, adjust=False).mean()

    # 2. RSI 14 (Momentum)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    # 3. ATR 14 (Volatilität für dynamische Stopps)
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=ATR_PERIOD).mean()

    return df

# ==========================================
# TRADING BOT KLASSE
# ==========================================
class RobustTradingBot:
    def __init__(self):
        exchange_class = getattr(ccxt, EXCHANGE_ID)
        self.exchange = exchange_class({
            'enableRateLimit': True,
            # 'apiKey': 'DEIN_KEY',
            # 'secret': 'DEIN_SECRET',
        })
        self.in_position = False
        self.entry_price = 0.0
        self.stop_loss = 0.0
        self.highest_price = 0.0
        self.trailing_active = False

    def fetch_ohlcv(self) -> pd.DataFrame:
        candles = self.exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=250)
        df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return calculate_indicators(df)

    def evaluate_entry(self, row: pd.Series):
        # Regel: Kurs > EMA 200 (Aufwärtstrend) UND RSI < 35 (Kurzfristiger Dip)
        if row['close'] > row['ema_200'] and row['rsi'] < RSI_OVERSOLD:
            current_price = row['close']
            current_atr = row['atr']

            self.in_position = True
            self.entry_price = current_price
            self.stop_loss = current_price - (current_atr * ATR_SL_MULTIPLIER)
            self.highest_price = current_price
            self.trailing_active = False

            logging.info(f"🚀 KAUF-SIGNAL bei {current_price:.2f} USDT | SL: {self.stop_loss:.2f} (ATR: {current_atr:.2f})")

    def evaluate_exit(self, current_price: pd.Series, current_atr: float):
        # 1. Höchststand tracken für Trailing TP
        if current_price > self.highest_price:
            self.highest_price = current_price

        # 2. Break-Even-Schutz: Wenn Kurs 1.5x ATR über Einstieg -> SL mindestens auf Einstiegskurs
        if current_price >= (self.entry_price + (current_atr * 1.5)):
            if self.stop_loss < self.entry_price:
                self.stop_loss = self.entry_price
                logging.info(f"🛡️ BREAK-EVEN AKTIVIERT: Stop-Loss auf Einstieg ({self.entry_price:.2f}) angehoben.")

        # 3. Trailing Take-Profit Prüfung
        if not self.trailing_active and current_price >= (self.entry_price + (current_atr * ATR_TP_ACTIVATION)):
            self.trailing_active = True
            logging.info("🎯 TRAILING TAKE-PROFIT SCHARFGESCHALTET.")

        # 4. Ausstiegs-Bedingungen prüfen
        # A) Harter Stop-Loss
        if current_price <= self.stop_loss:
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            logging.info(f"🛑 STOP-LOSS AUSGELÖST bei {current_price:.2f} USDT | PnL: {pnl_pct:.2f}%")
            self.in_position = False

        # B) Trailing Take-Profit Rücksetzer
        elif self.trailing_active and current_price <= (self.highest_price * (1 - TRAILING_CALLBACK)):
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            logging.info(f"💰 TAKE-PROFIT AUSGELÖST bei {current_price:.2f} USDT | PnL: +{pnl_pct:.2f}%")
            self.in_position = False

    def run_cycle(self):
        try:
            df = self.fetch_ohlcv()
            last_closed = df.iloc[-2]  # Abgeschlossene Kerze für Signale
            current_tick = df.iloc[-1]['close'] # Aktueller Live-Tick

            if not self.in_position:
                self.evaluate_entry(last_closed)
            else:
                self.evaluate_exit(current_tick, last_closed['atr'])

        except Exception as e:
            logging.error(f"Fehler im Abfragezyklus: {e}")

    def start(self):
        logging.info(f"Bot initialisiert ({'DRY RUN' if DRY_RUN else 'LIVE'}). Warte auf Marktsignale...")
        while True:
            self.run_cycle()
            time.sleep(15)  # 15 Sekunden Polling-Intervall

if __name__ == '__main__':
    bot = RobustTradingBot()
    bot.start()
