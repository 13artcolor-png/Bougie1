"""Ajouter les nouvelles colonnes a close_tracker_quarters."""
import sqlite3

conn = sqlite3.connect("data/signatures.db")

# Ajouter les colonnes manquantes une par une (ignorer si deja existante)
columns = [
    ("price_at_quarter", "REAL DEFAULT 0"),
    ("moves_count_up", "INTEGER DEFAULT 0"),
    ("moves_count_down", "INTEGER DEFAULT 0"),
    ("next_q_predicted", "TEXT DEFAULT ''"),
    ("next_q_pct", "REAL DEFAULT 0"),
    ("next_q_actual", "TEXT DEFAULT ''"),
    ("next_q_correct", "INTEGER DEFAULT 0"),
]

for col_name, col_type in columns:
    try:
        conn.execute(f"ALTER TABLE close_tracker_quarters ADD COLUMN {col_name} {col_type}")
        print(f"  Colonne {col_name} ajoutee")
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print(f"  Colonne {col_name} existe deja")
        else:
            print(f"  Erreur {col_name}: {e}")

conn.commit()
conn.close()
print("Migration terminee")
