import { useEffect, useRef, useState } from "react";
import type { WsMessage } from "../types/candle";

/** Hook WebSocket simple et robuste */
export function useWebSocket(symbol: string, timeframe: string, microTf: string) {
  const [data, setData] = useState<WsMessage | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const configRef = useRef({ symbol, timeframe, microTf });

  // Toujours garder la config a jour
  configRef.current = { symbol, timeframe, microTf };

  // Connexion une seule fois au montage
  useEffect(() => {
    let ws: WebSocket | null = null;
    let retryDelay = 1000;
    let shouldReconnect = true;

    function createWs() {
      if (!shouldReconnect) return;

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const host = window.location.host;
      ws = new WebSocket(`${protocol}//${host}/ws/candles`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryDelay = 1000;
        const c = configRef.current;
        ws!.send(JSON.stringify({ symbol: c.symbol, timeframe: c.timeframe, micro_tf: c.microTf }));
      };

      ws.onmessage = (event) => {
        try {
          setData(JSON.parse(event.data));
        } catch {
          // ignorer
        }
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;
        if (shouldReconnect) {
          setTimeout(createWs, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 10000);
        }
      };

      ws.onerror = () => {
        if (ws) ws.close();
      };
    }

    createWs();

    return () => {
      shouldReconnect = false;
      if (ws && ws.readyState <= 1) {
        ws.onclose = null; // Empecher la reconnexion
        ws.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Envoyer un message quand la config change
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ symbol, timeframe, micro_tf: microTf }));
    }
  }, [symbol, timeframe, microTf]);

  return { data, connected };
}
