import sqlite3
conn = sqlite3.connect("data/signatures.db")
conn.execute("""CREATE TABLE IF NOT EXISTS external_alerts (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS active_trades (
    id INTEGER PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    strategy TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    confidence REAL NOT NULL,
    candle_time INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)""")
conn.commit()
conn.close()
print("Tables created")
