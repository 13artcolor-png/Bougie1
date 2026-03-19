import { useEffect, useState } from "react";
import type { SymbolInfo } from "../types/candle";

/** Hook pour charger la liste des symboles depuis l'API */
export function useSymbols() {
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/symbols")
      .then((res) => res.json())
      .then((data) => {
        setSymbols(data.symbols || []);
        setLoading(false);
      })
      .catch(() => {
        setLoading(false);
      });
  }, []);

  return { symbols, loading };
}
