import time
import ccxt
import pandas as pd
import numpy as np
import logging
import requests
from datetime import datetime

# ==========================================
# KONFIGURATION & RISIKO-PARAMETER
# ==========================================
EXCHANGE_ID = 'kraken'  # 'kraken' oder 'binance'
SYMBOL = 'BTC/USDT'
TIMEFRAME = '15m'

DRY_RUN = True          # True = Nur simulieren, False = Echte Orders platzieren
MAX_POSITION_EUR = 5.0  # Max. Einsatz pro Trade

# ==========================================
# TELEGRAM KONFIGURATION
# ==========================================
TELEGRAM_TOKEN = '8970011732:AAFGRUAOE3upiNiBzJBI6j71dbXbuWBo5hw'
TELEGRAM_CHAT_ID = '8952651770'

def send_telegram_message(msg: str):
    """Sendet eine Nachricht an deinen Telegram-Chat."""
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == 'DEIN_API_TOKEN_HIER':
        return  # Überspringen, falls nicht konfiguriert
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, data=data)
    except Exception as e:
        logging.error(f"Konnte Telegram-Nachricht nicht senden: {e}")

# Strategie-Parameter
EMA_TREND_PERIOD = 200
RSI_PERIOD = 14
RSI_OVERSOLD = 35
ATR_PERIOD = 14
ATR_SL_MULTIPLIER = 1.5   
ATR_TP_ACTIVATION = 2.5  
TRAILING_CALLBACK = 0.015 

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] %(message)s')

# ==========================================
# INDIKATOR-BERECHNUNGEN
# ==========================================
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df['ema_200'] = df['close'].ewm(span=EMA_TREND_PERIOD, adjust=False).mean()
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

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
        self.exchange = exchange_class({'enableRateLimit': True})
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
        if row['close'] > row['ema_200'] and row['rsi'] < RSI_OVERSOLD:
            current_price = row['close']
            current_atr = row['atr']

            self.in_position = True
            self.entry_price = current_price
            self.stop_loss = current_price - (current_atr * ATR_SL_MULTIPLIER)
            self.highest_price = current_price
            self.trailing_active = False

            msg = f"🚀 <b>KAUF-SIGNAL ({SYMBOL})</b>\nEinstieg: {current_price:.2f} USDT\nStop-Loss: {self.stop_loss:.2f} USDT"
            logging.info(msg)
            send_telegram_message(msg)

    def evaluate_exit(self, current_price: pd.Series, current_atr: float):
        if current_price > self.highest_price:
            self.highest_price = current_price

        # Break-Even
        if current_price >= (self.entry_price + (current_atr * 1.5)):
            if self.stop_loss < self.entry_price:
                self.stop_loss = self.entry_price
                msg = f"🛡️ <b>BREAK-EVEN AKTIVIERT</b>\nStop-Loss auf Einstiegskurs ({self.entry_price:.2f}) angehoben."
                logging.info(msg)
                send_telegram_message(msg)

        # Trailing TP Aktivierung
        if not self.trailing_active and current_price >= (self.entry_price + (current_atr * ATR_TP_ACTIVATION)):
            self.trailing_active = True
            send_telegram_message("🎯 <b>TRAILING TAKE-PROFIT SCHARFGESCHALTET</b>")

        # Stop-Loss greift
        if current_price <= self.stop_loss:
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            msg = f"🛑 <b>STOP-LOSS AUSGELÖST</b>\nVerkauf bei: {current_price:.2f} USDT\nPnL: {pnl_pct:.2f}%"
            logging.info(msg)
            send_telegram_message(msg)
            self.in_position = False

        # Trailing TP greift
        elif self.trailing_active and current_price <= (self.highest_price * (1 - TRAILING_CALLBACK)):
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            msg = f"💰 <b>TAKE-PROFIT AUSGELÖST</b>\nVerkauf bei: {current_price:.2f} USDT\nPnL: +{pnl_pct:.2f}%"
            logging.info(msg)
            send_telegram_message(msg)
            self.in_position = False

    def run_cycle(self):
        try:
            df = self.fetch_ohlcv()
            last_closed = df.iloc[-2]  
            current_tick = df.iloc[-1]['close'] 

            if not self.in_position:
                self.evaluate_entry(last_closed)
            else:
                self.evaluate_exit(current_tick, last_closed['atr'])

        except Exception as e:
            logging.error(f"Fehler im Zyklus: {e}")

    def start(self):
        start_msg = f"✅ Bot gestartet auf Server.\nModus: {'DRY RUN' if DRY_RUN else 'LIVE'}\nWarte auf Signale..."
        logging.info(start_msg)
        send_telegram_message(start_msg)
        
        while True:
            self.run_cycle()
            time.sleep(15)  

if __name__ == '__main__':
    bot = RobustTradingBot()
    bot.start()
