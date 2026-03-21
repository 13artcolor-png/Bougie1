"""WebSocket endpoint pour le streaming de bougies en temps reel"""

import asyncio
import json
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import get_logger
from mt5 import connection, market_data
from config import WS_UPDATE_INTERVAL
from rhythm.classifier import classify_candle
from rhythm.storage import save_signature, get_last_signatures as get_last_sigs_func
from rhythm.stats import get_next_probabilities
from rhythm.predictions import save_prediction, verify_prediction, get_prediction_stats
from rhythm.partial_match import estimate_signature
from rhythm.grid_moves import compute_grid_moves, predict_next_grid_move
from rhythm.custom_formula import execute_formula
from rhythm.close_tracker import save_close_result, get_close_stats, save_quarter_prediction, finalize_quarter_predictions
from rhythm.next_quarter_formula import predict_next_quarter
from rhythm.auto_backfill import auto_backfill
from rhythm.auto_optimize import optimize_formula
from rhythm.pattern_memory import learn_from_candle, backfill_patterns
from rhythm.trade_tracker import save_trade, get_trade_stats
from rhythm.entry_timing import analyze_entry

logger = get_logger("ws.candle_stream")


async def candle_websocket(websocket: WebSocket):
    """Endpoint WebSocket principal.
    Le client envoie un message de config : {"symbol": "XAUUSD", "timeframe": "M15"}
    Le serveur envoie ensuite les donnees en continu toutes les secondes."""
    await websocket.accept()
    logger.info("Client WebSocket connecte")

    # Config par defaut
    symbol = "XAUUSD"
    timeframe = "M15"
    micro_tf = "M1"

    # Cache pour ne classifier qu'une fois par bougie cloturee
    last_classified_time = 0
    cached_signature = None
    cached_transitions = None
    cached_prediction_result = None
    cached_prediction_stats = None
    # Charger les stats WR au demarrage
    cached_close_stats = get_close_stats(symbol, timeframe, 50)
    last_close_prediction = None  # Garder la derniere prediction pour la verifier a la cloture
    quarters_saved = set()  # Quarts deja sauvegardes pour la bougie en cours
    current_candle_time_for_quarters = 0
    quarter_prices = {}  # Prix a chaque quart pour verification next_q
    candles_since_optimize = 0  # Compteur pour auto-optimisation
    # Trade tracking - 2 strategies en parallele
    active_trade_s1 = None  # Strategie 1 : bord de cage
    active_trade_s2 = None  # Strategie 2 : signal externe + pullback central
    cached_trade_stats = None
    # Alerte externe (direction demandee par l'agent)
    external_alert = None  # {"direction": "LONG/SHORT"}
    entry_timing = None  # Resultat de l'analyse de timing

    try:
        while True:
            # Verifier si le client a envoye un changement de config (non-bloquant)
            try:
                msg = await asyncio.wait_for(
                    websocket.receive_text(), timeout=0.05
                )
                data = json.loads(msg)
                if "symbol" in data:
                    symbol = data["symbol"]
                    last_classified_time = 0  # Reset le cache
                    logger.info(f"Symbole change: {symbol}")
                    # Backfill automatique en arriere-plan
                    asyncio.create_task(asyncio.to_thread(auto_backfill, symbol, timeframe))
                    asyncio.create_task(asyncio.to_thread(backfill_patterns, symbol, timeframe))
                if "timeframe" in data:
                    timeframe = data["timeframe"]
                    last_classified_time = 0
                    logger.info(f"Timeframe change: {timeframe}")
                if "micro_tf" in data:
                    micro_tf = data["micro_tf"]
                    logger.info(f"Micro TF change: {micro_tf}")
                if "alert" in data:
                    alert_dir = data["alert"].upper()
                    if alert_dir in ("LONG", "SHORT"):
                        external_alert = {"direction": alert_dir}
                        logger.info(f"Alerte externe recue: {alert_dir}")
                    elif alert_dir == "CLEAR":
                        external_alert = None
                        entry_timing = None
                        logger.info("Alerte externe effacee")
            except asyncio.TimeoutError:
                pass

            # Verifier la connexion MT5
            if not connection.is_connected():
                if not connection.connect():
                    await websocket.send_json({
                        "type": "error",
                        "message": "Connexion MT5 perdue"
                    })
                    await asyncio.sleep(WS_UPDATE_INTERVAL)
                    continue

            # Recuperer les bougies principales
            candles = await asyncio.to_thread(
                market_data.get_candles, symbol, timeframe, 25
            )

            if candles is None or len(candles) < 2:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Pas de donnees pour {symbol} {timeframe}"
                })
                await asyncio.sleep(WS_UPDATE_INTERVAL)
                continue

            # La derniere bougie est celle en cours
            current_candle = candles[-1]
            last_closed = candles[-2]
            history = candles[:-1]

            # Recuperer les micro-bougies de la bougie en cours
            candle_start = current_candle["time"]
            micro = await asyncio.to_thread(
                market_data.get_micro_candles, symbol, timeframe, micro_tf,
                candle_start
            )
            tick = await asyncio.to_thread(
                market_data.get_current_tick, symbol
            )

            # --- Classification de la bougie cloturee ---
            # Ne classifier qu'une fois (quand last_closed change)
            closed_time = last_closed["time"]
            if closed_time != last_classified_time:
                # Recuperer les micro-bougies M1 de la bougie cloturee
                # (toujours M1 pour la classification, plus fiable)
                closed_micro = await asyncio.to_thread(
                    market_data.get_micro_candles, symbol, timeframe, "M1",
                    closed_time
                )

                # Verifier la prediction de cloture de la bougie qui vient de se fermer
                if last_close_prediction and last_close_prediction.get("prediction"):
                    actual_bullish = last_closed["close"] > last_closed["open"]
                    await asyncio.to_thread(
                        save_close_result, symbol, timeframe, closed_time,
                        last_close_prediction["prediction"],
                        last_close_prediction.get("pct_hausse", 50) if last_close_prediction["prediction"] == "HAUSSE" else last_close_prediction.get("pct_baisse", 50),
                        actual_bullish,
                        last_close_prediction.get("total_samples", 0)
                    )
                    # Finaliser les predictions par quart
                    await asyncio.to_thread(
                        finalize_quarter_predictions, symbol, timeframe,
                        current_candle_time_for_quarters, actual_bullish, quarter_prices
                    )
                    cached_close_stats = await asyncio.to_thread(
                        get_close_stats, symbol, timeframe, 50
                    )
                    # Cloturer les trades actifs a la fin de la bougie
                    avg_range = last_closed["high"] - last_closed["low"]
                    for trade, label in [(active_trade_s1, "S1"), (active_trade_s2, "S2")]:
                        if trade:
                            await asyncio.to_thread(
                                save_trade, symbol, timeframe, trade["candle_time"],
                                trade["direction"], trade["entry_price"],
                                last_closed["close"], trade["confidence"],
                                1.0, f"{label}_close", avg_range
                            )
                    active_trade_s1 = None
                    active_trade_s2 = None
                    cached_trade_stats = await asyncio.to_thread(
                        get_trade_stats, symbol, timeframe, 50
                    )

                    last_close_prediction = None
                    quarters_saved = set()
                    current_candle_time_for_quarters = 0
                    quarter_prices = {}

                    # Apprendre cette bougie dans les dictionnaires
                    if grid_moves and len(grid_moves) >= 3:
                        actual_close = "HAUSSE" if last_closed["close"] > last_closed["open"] else "BAISSE"
                        await asyncio.to_thread(
                            learn_from_candle, symbol, timeframe, grid_moves, actual_close
                        )

                    # Auto-optimisation toutes les 100 bougies
                    candles_since_optimize += 1
                    if candles_since_optimize >= 100:
                        candles_since_optimize = 0
                        logger.info("Auto-optimisation lancee (100 bougies)")
                        asyncio.create_task(asyncio.to_thread(optimize_formula, symbol, timeframe))

                if closed_micro and len(closed_micro) >= 2:
                    last_closed_with_symbol = {**last_closed, "symbol": symbol}
                    sig = classify_candle(last_closed_with_symbol, closed_micro, timeframe)

                    if sig:
                        # 1. Verifier la prediction precedente
                        cached_prediction_result = await asyncio.to_thread(
                            verify_prediction, symbol, timeframe,
                            closed_time, sig["signature"]
                        )

                        # 2. Ajouter le contexte et sauvegarder
                        prev_sigs = await asyncio.to_thread(
                            get_last_sigs_func, symbol, timeframe, 2
                        )
                        if len(prev_sigs) >= 1:
                            sig["prev_signature"] = prev_sigs[0].get("signature", "")
                        else:
                            sig["prev_signature"] = ""

                        await asyncio.to_thread(save_signature, sig)
                        cached_signature = sig

                        # 3. Calculer les transitions
                        trans_all = await asyncio.to_thread(
                            get_next_probabilities, symbol, timeframe, sig["signature"]
                        )
                        trans_session = await asyncio.to_thread(
                            get_next_probabilities, symbol, timeframe,
                            sig["signature"], sig.get("session", "")
                        )
                        trans_ctx = await asyncio.to_thread(
                            get_next_probabilities, symbol, timeframe,
                            sig["signature"], "", sig.get("prev_signature", "")
                        )
                        cached_transitions = {
                            "all": trans_all,
                            "session": trans_session,
                            "context": trans_ctx,
                            "session_name": sig.get("session", ""),
                            "prev_sig": sig.get("prev_signature", ""),
                        }

                        # 4. Sauvegarder la prediction pour la PROCHAINE bougie
                        if trans_all:
                            best = trans_all[0]["signature"]
                            next_candle_time = current_candle["time"]
                            await asyncio.to_thread(
                                save_prediction, symbol, timeframe,
                                next_candle_time, best, sig.get("session", "")
                            )

                        # 5. Stats de predictions
                        cached_prediction_stats = await asyncio.to_thread(
                            get_prediction_stats, symbol, timeframe, 100
                        )

                    else:
                        cached_signature = None
                        cached_transitions = None
                else:
                    cached_signature = None
                    cached_transitions = None

                last_classified_time = closed_time

            # Estimation en temps reel de la signature en cours
            # Toujours utiliser les micro-bougies M1 pour des timestamps coherents
            micro_m1_for_estimate = micro
            if micro_tf != "M1":
                micro_m1_for_estimate = await asyncio.to_thread(
                    market_data.get_micro_candles, symbol, timeframe, "M1", candle_start
                )
            live_estimate = await asyncio.to_thread(
                estimate_signature, current_candle, micro_m1_for_estimate or [], timeframe, symbol
            )

            # Calcul de la progression pour le frontend
            tf_seconds = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800, "H1": 3600, "H4": 14400, "D1": 86400}
            dur = tf_seconds.get(timeframe, 900)
            m1_micros = micro_m1_for_estimate or []
            if m1_micros:
                last_mt = m1_micros[-1]["time"]
                candle_progress = max(0, min(1.0, (last_mt - candle_start) / dur))
            else:
                candle_progress = 0

            # Prediction par franchissements de lignes de grille
            micro_prediction = None
            close_prediction = None
            grid_moves = []
            if micro_m1_for_estimate and len(micro_m1_for_estimate) >= 3:
                candle_h = current_candle["high"]
                candle_l = current_candle["low"]
                grid_moves = compute_grid_moves(micro_m1_for_estimate, candle_h, candle_l)
                if len(grid_moves) >= 2:
                    micro_prediction = predict_next_grid_move(symbol, timeframe, grid_moves)
                    if micro_prediction.get("prediction"):
                        micro_prediction["current_moves"] = grid_moves

                    # --- Prediction par formule (specifique a l'actif) ---
                    prev_c = last_closed["close"] if last_closed else current_candle["open"]
                    prev_h = last_closed["high"] if last_closed else current_candle["high"]
                    prev_l = last_closed["low"] if last_closed else current_candle["low"]
                    close_prediction = await asyncio.to_thread(
                        execute_formula,
                        grid_moves, candle_progress,
                        current_candle["open"], current_candle["high"],
                        current_candle["low"], current_candle["close"],
                        prev_c, symbol, prev_h, prev_l
                    )
                    if close_prediction:
                        close_prediction["source"] = "formule"
                        close_prediction["current_moves"] = grid_moves
                    else:
                        close_prediction = {"prediction": None, "source": "aucun"}

                    # --- Trade tracking (2 strategies en parallele) ---
                    if close_prediction.get("prediction"):
                        cp_dir = "LONG" if close_prediction["prediction"] == "HAUSSE" else "SHORT"
                        cp_conf = max(close_prediction.get("pct_hausse", 50), close_prediction.get("pct_baisse", 50))

                        current_quarter = min(4, int(candle_progress * 4) + 1)
                        candle_range = current_candle["high"] - current_candle["low"]
                        price_now = current_candle["close"]
                        mid_price = (current_candle["high"] + current_candle["low"]) / 2

                        near_low = candle_range > 0 and (price_now - current_candle["low"]) < candle_range * 0.15
                        near_high = candle_range > 0 and (current_candle["high"] - price_now) < candle_range * 0.15
                        near_mid = candle_range > 0 and abs(price_now - mid_price) < candle_range * 0.10

                        # === STRATEGIE 1 : Bord de cage ===
                        can_s1_long = current_quarter >= 2 and cp_dir == "LONG" and near_low
                        can_s1_short = current_quarter >= 2 and cp_dir == "SHORT" and near_high

                        if active_trade_s1 is None and cp_conf > 50 and (can_s1_long or can_s1_short):
                            active_trade_s1 = {
                                "direction": cp_dir,
                                "entry_price": price_now,
                                "confidence": cp_conf,
                                "candle_time": candle_start,
                                "strategy": "S1_bord",
                            }

                        elif active_trade_s1 and cp_dir != active_trade_s1["direction"] and cp_conf > 50:
                            avg_range = candle_range
                            await asyncio.to_thread(
                                save_trade, symbol, timeframe, active_trade_s1["candle_time"],
                                active_trade_s1["direction"], active_trade_s1["entry_price"],
                                price_now, active_trade_s1["confidence"],
                                0.5, "S1_retournement", avg_range
                            )
                            active_trade_s1 = None

                        # === STRATEGIE 2 : Signal externe + confirmation B1 + pullback central ===
                        if external_alert and active_trade_s2 is None and current_quarter >= 2:
                            alert_dir = external_alert["direction"]
                            # Condition : B1 confirme la meme direction ET prix pres de la ligne centrale
                            if cp_dir == alert_dir and near_mid and cp_conf > 50:
                                active_trade_s2 = {
                                    "direction": alert_dir,
                                    "entry_price": price_now,
                                    "confidence": cp_conf,
                                    "candle_time": candle_start,
                                    "strategy": "S2_pullback",
                                }

                        elif active_trade_s2 and cp_dir != active_trade_s2["direction"] and cp_conf > 50:
                            avg_range = candle_range
                            await asyncio.to_thread(
                                save_trade, symbol, timeframe, active_trade_s2["candle_time"],
                                active_trade_s2["direction"], active_trade_s2["entry_price"],
                                price_now, active_trade_s2["confidence"],
                                0.5, "S2_retournement", avg_range
                            )
                            active_trade_s2 = None

                        cached_trade_stats = await asyncio.to_thread(
                            get_trade_stats, symbol, timeframe, 50
                        )
                    # Garder la derniere prediction pour la verifier a la cloture
                    if close_prediction and close_prediction.get("prediction"):
                        last_close_prediction = close_prediction
                        current_candle_time_for_quarters = candle_start

                        # Sauvegarder la prediction a chaque quart
                        current_quarter = min(4, int(candle_progress * 4) + 1)
                        if current_quarter not in quarters_saved:
                            quarters_saved.add(current_quarter)

                            # Prix a ce quart
                            price_now = current_candle["close"]
                            quarter_prices[current_quarter] = price_now

                            # Compter les mouvements U/D
                            moves_up = sum(len(m) for m in grid_moves if m[0] == "U")
                            moves_down = sum(len(m) for m in grid_moves if m[0] == "D")

                            # Prediction next quarter
                            nq_pred = ""
                            nq_pct = 0
                            if current_quarter < 4:
                                nq_result = await asyncio.to_thread(
                                    predict_next_quarter, grid_moves, current_quarter,
                                    current_candle["open"], price_now,
                                    current_candle["high"], current_candle["low"]
                                )
                                nq_pred = nq_result.get("prediction", "")
                                nq_pct = nq_result.get("pct", 0)

                            pct_val = close_prediction.get("pct_hausse", 50) if close_prediction["prediction"] == "HAUSSE" else close_prediction.get("pct_baisse", 50)

                            await asyncio.to_thread(
                                save_quarter_prediction, symbol, timeframe,
                                candle_start, current_quarter,
                                close_prediction["prediction"], pct_val,
                                price_now, moves_up, moves_down,
                                nq_pred, nq_pct
                            )

            # Payload leger : seulement les donnees temps reel
            payload = {
                "type": "update",
                "symbol": symbol,
                "timeframe": timeframe,
                "current_candle": current_candle,
                "last_closed_candle": last_closed,
                "micro_candles": micro or [],
                "tick": tick,
                "micro_prediction": micro_prediction,
                "close_prediction": close_prediction,
                "candle_progress": round(candle_progress, 3),
                "trade_stats": cached_trade_stats,
                "active_trade_s1": active_trade_s1,
                "active_trade_s2": active_trade_s2,
                "external_alert": external_alert,
                "entry_timing": (
                    analyze_entry(
                        external_alert["direction"], current_candle, last_closed,
                        grid_moves, candle_progress
                    ) if external_alert and grid_moves else None
                ),
            }

            # Donnees statiques : envoyees seulement quand elles changent
            if closed_time == last_classified_time or not hasattr(candle_websocket, '_last_sent_closed'):
                payload["history"] = history
                payload["closed_signature"] = cached_signature
                payload["transition_probs"] = cached_transitions
                payload["prediction_result"] = cached_prediction_result
                payload["prediction_stats"] = cached_prediction_stats
                payload["close_stats"] = cached_close_stats

            # Next quarter prediction (seulement si en cours)
            if grid_moves and len(grid_moves) >= 2 and candle_progress < 0.75:
                payload["next_quarter_prediction"] = await asyncio.to_thread(
                    predict_next_quarter, grid_moves,
                    min(4, int(candle_progress * 4) + 1),
                    current_candle["open"], current_candle["close"],
                    current_candle["high"], current_candle["low"]
                )

            await websocket.send_json(payload)
            await asyncio.sleep(WS_UPDATE_INTERVAL)

    except WebSocketDisconnect:
        logger.info("Client WebSocket deconnecte")
    except Exception as e:
        logger.error(f"Erreur WebSocket: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
