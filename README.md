# Trading-bot-
Krypto Trading bot 
# Crypto Trading Bot (Multi-Faktor Strategie)

Ein automatisierter Trading-Bot in Python für Kryptowährungen (Fokus: BTC/ETH) basierend auf der `ccxt`-Bibliothek. 
Das System ist auf ein geringes Startkapital (Max. 100€) und strenges Risikomanagement ausgelegt.

## 📈 Strategie
- **Trend-Filter:** Kauf nur im übergeordneten Aufwärtstrend (Kurs > EMA 200).
- **Einstieg:** "Buy the Dip" bei Überverkaufung (RSI < 35) auf dem 15m-Chart.
- **Risikomanagement:** Harter Stop-Loss bei -2%.
- **Gewinnsicherung:** Trailing Take-Profit (Aktivierung bei +4%, Trailing-Abstand 2%).
- **Max. Positionsgröße:** 5€ pro Trade.

## 🚀 Setup & Installation
1. Repository klonen: `git clone <deine-gitlab-repo-url>`
2. Virtuelle Umgebung erstellen: `python -m venv venv`
3. Umgebung aktivieren: `source venv/bin/activate` (Mac/Linux) oder `venv\Scripts\activate` (Windows)
4. Abhängigkeiten installieren: `pip install -r requirements.txt`
5. `config_template.py` zu `config.py` umbenennen und API-Keys eintragen.

## 📂 Dateien
- `bot.py`: Das Live-/Sandbox-Skript.
- `backtest.py`: Überprüft die Historie der letzten 1000 Kerzen.
