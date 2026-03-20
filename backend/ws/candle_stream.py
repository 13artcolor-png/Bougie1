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
from rhythm.pattern_memory import learn_from_candle, predict_close as pattern_predict_close, backfill_patterns

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
                    last_close_prediction = None
                    quarters_saved = set()
                    current_candle_time_for_quarters = 0
                    quarter_prices = {}

                    # Apprendre cette bougie dans le dictionnaire de patterns
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

                    # --- Systeme de prediction : FORMULE uniquement ---
                    # Le dictionnaire de patterns est en developpement (desactive pour l'instant)
                    prev_c = last_closed["close"] if last_closed else current_candle["open"]
                    close_prediction = await asyncio.to_thread(
                        execute_formula,
                        grid_moves, candle_progress,
                        current_candle["open"], current_candle["high"],
                        current_candle["low"], current_candle["close"],
                        prev_c
                    )
                    if close_prediction:
                        close_prediction["source"] = "formule"
                        close_prediction["current_moves"] = grid_moves
                    else:
                        close_prediction = {"prediction": None, "source": "aucun"}
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
