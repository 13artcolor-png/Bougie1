"""Vide la base et re-backfill avec le nouveau classifieur."""
import sqlite3
import os

DB_PATH = os.path.join("data", "signatures.db")

# Vider la table
print("Suppression des anciennes signatures...")
conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM signatures")
conn.commit()
count = conn.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
print(f"Table videe : {count} lignes restantes")
conn.close()

# Re-backfill
print("\nLancement du backfill avec le nouveau classifieur...")
from rhythm.backfill import backfill
backfill("XAUUSD", "M15", 10000)
