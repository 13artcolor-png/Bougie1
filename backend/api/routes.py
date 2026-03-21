"""Routes REST de l'API"""

import os
from fastapi import APIRouter
from mt5 import connection, market_data
from rhythm.storage import get_last_signatures, get_transition_probs
from rhythm.stats import get_global_stats
from rhythm.direction import analyze_direction
from rhythm.custom_formula import get_formula, save_formula
from rhythm.auto_optimize import optimize_formula
from rhythm.trade_tracker import get_trade_stats as get_trades
from rhythm.entry_timing import analyze_entry
from rhythm.close_tracker import get_close_stats
from fastapi import Body

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    """Verifie l'etat du serveur et de la connexion MT5"""
    mt5_ok = connection.is_connected()
    return {
        "status": "ok",
        "mt5_connected": mt5_ok,
    }


@router.get("/symbols")
async def symbols():
    """Retourne la liste des symboles disponibles"""
    if not connection.is_connected():
        connection.connect()
    syms = market_data.get_symbols()
    return {"symbols": syms}


@router.get("/signatures/{symbol}/{timeframe}")
async def signatures(symbol: str, timeframe: str, limit: int = 50):
    """Historique des signatures pour un symbole/timeframe"""
    sigs = get_last_signatures(symbol, timeframe, limit)
    return {"signatures": sigs}


@router.get("/signatures/{symbol}/{timeframe}/transitions")
async def transitions(symbol: str, timeframe: str, after: str = "",
                      session: str = "", prev: str = "", lookback: int = 0):
    """Probabilites de transition avec filtres optionnels"""
    if not after:
        return {"error": "Parametre 'after' requis", "transitions": []}
    probs = get_transition_probs(symbol, timeframe, after,
                                 session=session, lookback=lookback,
                                 prev_signature=prev)
    return {"transitions": probs, "lookback": lookback}


@router.get("/signatures/{symbol}/{timeframe}/stats")
async def stats(symbol: str, timeframe: str):
    """Statistiques globales des signatures"""
    return get_global_stats(symbol, timeframe)


@router.get("/signatures/{symbol}/{timeframe}/direction")
async def direction(symbol: str, timeframe: str, lookback: int = 0):
    """Analyse de la direction de depart avec tous les facteurs"""
    return analyze_direction(symbol, timeframe, lookback)


@router.get("/formula")
async def get_formula_code(symbol: str = ""):
    """Retourne le code de la formule pour un actif"""
    return {"code": get_formula(symbol), "symbol": symbol}


@router.post("/formula")
async def save_formula_code(body: dict = Body(...)):
    """Sauvegarde le code de la formule pour un actif"""
    code = body.get("code", "")
    sym = body.get("symbol", "")
    ok = save_formula(code, sym)
    return {"success": ok, "symbol": sym}


@router.post("/close-stats/reset")
async def reset_close_stats():
    """Reset le compteur WR"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM close_tracker")
    conn.execute("DELETE FROM close_tracker_quarters")
    conn.commit()
    conn.close()
    return {"success": True}


@router.get("/grid-history/{symbol}/{timeframe}")
async def grid_history(symbol: str, timeframe: str, limit: int = 50):
    """Historique des mouvements de grille avec etat de cloture"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    if limit > 0:
        rows = conn.execute("""
            SELECT gs.candle_time, gs.moves, gs.move_count, cp.closed_bullish
            FROM grid_sequences gs
            LEFT JOIN close_patterns cp
                ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
            WHERE gs.symbol = ? AND gs.timeframe = ?
            ORDER BY gs.candle_time DESC
            LIMIT ?
        """, (symbol, timeframe, limit)).fetchall()
    else:
        rows = conn.execute("""
            SELECT gs.candle_time, gs.moves, gs.move_count, cp.closed_bullish
            FROM grid_sequences gs
            LEFT JOIN close_patterns cp
                ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
            WHERE gs.symbol = ? AND gs.timeframe = ?
            ORDER BY gs.candle_time DESC
        """, (symbol, timeframe)).fetchall()
    conn.close()
    return {"history": [dict(r) for r in rows]}


@router.get("/quarters-detail/{symbol}/{timeframe}")
async def quarters_detail(symbol: str, timeframe: str):
    """Detail des predictions par quart pour chaque bougie"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Recuperer toutes les bougies qui ont des predictions par quart
    candle_times = conn.execute("""
        SELECT DISTINCT candle_time FROM close_tracker_quarters
        WHERE symbol = ? AND timeframe = ?
        ORDER BY candle_time DESC
        LIMIT 100
    """, (symbol, timeframe)).fetchall()

    entries = []
    for ct in candle_times:
        t = ct["candle_time"]
        quarters = conn.execute("""
            SELECT quarter, predicted, pct_predicted, actual
            FROM close_tracker_quarters
            WHERE symbol = ? AND timeframe = ? AND candle_time = ?
            ORDER BY quarter
        """, (symbol, timeframe, t)).fetchall()

        entry = {
            "candle_time": t,
            "q1_pred": "", "q1_pct": 0,
            "q2_pred": "", "q2_pct": 0,
            "q3_pred": "", "q3_pct": 0,
            "q4_pred": "", "q4_pct": 0,
            "actual": "",
        }

        for q in quarters:
            qn = q["quarter"]
            entry[f"q{qn}_pred"] = q["predicted"]
            entry[f"q{qn}_pct"] = round(q["pct_predicted"], 1)
            if q["actual"]:
                entry["actual"] = q["actual"]

        entries.append(entry)

    conn.close()
    return {"entries": entries}


@router.get("/export/{symbol}/{timeframe}")
async def export_history(symbol: str, timeframe: str):
    """Exporte l'historique au format standard pour l'outil de formule.
    Format : Date | Cloture | Mouvements"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "..", "data", "signatures.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT gs.candle_time, gs.moves, cp.closed_bullish
        FROM grid_sequences gs
        LEFT JOIN close_patterns cp
            ON gs.symbol = cp.symbol AND gs.timeframe = cp.timeframe AND gs.candle_time = cp.candle_time
        WHERE gs.symbol = ? AND gs.timeframe = ?
        ORDER BY gs.candle_time ASC
    """, (symbol, timeframe)).fetchall()

    conn.close()

    lines = []
    lines.append(f"# Historique {symbol} {timeframe} - {len(rows)} bougies")
    lines.append(f"# Format standard pour l'outil de formule")
    lines.append(f"# Heures en heure de Paris (UTC+2 ete / UTC+1 hiver)")
    lines.append(f"#")
    lines.append("Date | Cloture | Mouvements")

    from datetime import datetime, timedelta, timezone
    from config import BROKER_UTC_OFFSET
    for r in rows:
        # Broker time -> UTC -> formater
        utc_ts = r["candle_time"] - (BROKER_UTC_OFFSET * 3600)
        dt = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        cloture = "HAUSSE" if r["closed_bullish"] else "BAISSE"
        lines.append(f"{date_str} | {cloture} | {r['moves']}")

    return {"content": "\n".join(lines), "filename": f"{symbol}_{timeframe}_export.txt", "count": len(rows)}


@router.get("/trades/{symbol}/{timeframe}")
async def trades(symbol: str, timeframe: str, limit: int = 100):
    """Historique des trades"""
    return get_trades(symbol, timeframe, limit)


@router.post("/alert/{symbol}")
async def receive_alert(symbol: str, body: dict = Body(...)):
    """Recoit une alerte d'un agent externe et retourne le timing d'entree.

    Body : {"direction": "LONG" ou "SHORT"}
    """
    direction = body.get("direction", "").upper()
    if direction not in ("LONG", "SHORT"):
        return {"error": "Direction requise: LONG ou SHORT"}

    # Recuperer les donnees actuelles
    from mt5 import market_data
    candles = market_data.get_candles(symbol, "M15", 3)
    if not candles or len(candles) < 2:
        return {"error": "Pas de donnees"}

    current = candles[-1]
    last_closed = candles[-2]

    # Recuperer les micro-bougies et calculer les mouvements
    from rhythm.grid_moves import compute_grid_moves
    micro = market_data.get_micro_candles(symbol, "M15", "M1", current["time"])
    grid_moves = []
    if micro and len(micro) >= 2:
        grid_moves = compute_grid_moves(micro, current["high"], current["low"])

    # Calculer la progression
    import time
    tf_seconds = 900
    last_micro_time = micro[-1]["time"] if micro else current["time"]
    elapsed = max(0, last_micro_time - current["time"])
    progress = min(elapsed / tf_seconds, 1.0)

    # Analyser le timing
    result = analyze_entry(direction, current, last_closed, grid_moves, progress)
    result["symbol"] = symbol
    result["direction_demandee"] = direction
    result["progress"] = round(progress * 100, 1)

    return result


@router.post("/optimize/{symbol}/{timeframe}")
async def optimize(symbol: str, timeframe: str):
    """Lance l'optimisation de la formule pour un actif"""
    import asyncio
    result = await asyncio.to_thread(optimize_formula, symbol, timeframe)
    return result


@router.post("/export-mt5/{symbol}/{timeframe}")
async def export_from_mt5(symbol: str, timeframe: str):
    """Lance l'extraction complete depuis MT5 et retourne le fichier."""
    import asyncio
    from extract_history import extract_history

    output = f"data/{symbol}_{timeframe}_export.txt"

    await asyncio.to_thread(extract_history, symbol, timeframe, output)

    if not os.path.exists(output):
        return {"error": "Extraction echouee"}

    with open(output, "r", encoding="utf-8") as f:
        content = f.read()

    # Compter les lignes de donnees
    data_lines = [l for l in content.split("\n") if l and not l.startswith("#") and "|" in l and not l.startswith("Date")]
    return {"content": content, "filename": f"{symbol}_{timeframe}_export.txt", "count": len(data_lines)}
