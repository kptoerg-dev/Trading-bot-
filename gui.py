import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import threading
import sys

class TradingBotGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Crypto Trading Bot - Control Panel")
        self.root.geometry("750x550")
        
        # Dunkles Theme für die GUI
        self.root.configure(bg="#2b2b2b")
        style = ttk.Style()
        style.theme_use('clam')
        
        self.process = None

        # --- OBERER BEREICH: Buttons ---
        btn_frame = tk.Frame(root, bg="#2b2b2b")
        btn_frame.pack(pady=15)

        self.btn_backtest = ttk.Button(btn_frame, text="📊 Backtest starten", command=self.run_backtest)
        self.btn_backtest.grid(row=0, column=0, padx=10, ipadx=10, ipady=5)

        self.btn_bot = ttk.Button(btn_frame, text="🚀 Live/Dry-Run Bot starten", command=self.run_bot)
        self.btn_bot.grid(row=0, column=1, padx=10, ipadx=10, ipady=5)

        self.btn_stop = ttk.Button(btn_frame, text="🛑 Stoppen", command=self.stop_process, state=tk.DISABLED)
        self.btn_stop.grid(row=0, column=2, padx=10, ipadx=10, ipady=5)

        # --- UNTERER BEREICH: Konsolen-Ausgabe ---
        self.console = scrolledtext.ScrolledText(
            root, width=90, height=25, 
            bg="#1e1e1e", fg="#00ff00",  # Hacker-Terminal Look (Schwarz/Grün)
            font=("Consolas", 10)
        )
        self.console.pack(padx=15, pady=5, fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)

    def log(self, message):
        """Schreibt eine Nachricht in das Textfeld."""
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)  # Auto-Scroll nach unten
        self.console.config(state=tk.DISABLED)

    def read_output(self, pipe):
        """Liest die Konsolenausgabe des Bots in Echtzeit."""
        for line in iter(pipe.readline, ''):
            # after(0, ...) stellt sicher, dass Tkinter aus dem Thread sicher aktualisiert wird
            self.root.after(0, self.log, line.strip())
        pipe.close()

    def start_process(self, script_name):
        self.stop_process() # Falls noch was läuft -> beenden
        
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END) # Konsole leeren
        self.console.config(state=tk.DISABLED)
        
        self.log(f"=== STARTE {script_name.upper()} ===")

        # Den Python-Befehl je nach Betriebssystem anpassen (python oder python3)
        python_cmd = "python" if sys.platform == "win32" else "python3"

        # Startet das Skript im Hintergrund
        self.process = subprocess.Popen(
            [python_cmd, "-u", script_name], # -u erzwingt unbuffered output
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # Thread starten, damit die GUI nicht einfriert, während der Bot läuft
        threading.Thread(target=self.read_output, args=(self.process.stdout,), daemon=True).start()
        
        self.btn_stop.config(state=tk.NORMAL)

    def run_backtest(self):
        self.start_process("backtest.py")

    def run_bot(self):
        self.start_process("bot.py")

    def stop_process(self):
        if self.process:
            self.process.terminate()
            self.log("\n=== PROZESS GESTOPPT ===")
            self.process = None
            self.btn_stop.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = TradingBotGUI(root)
    root.mainloop()
