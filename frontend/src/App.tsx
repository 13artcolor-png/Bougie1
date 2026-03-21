import { useState, useMemo, useRef, useCallback, useEffect } from "react";
import TopBar from "./components/layout/TopBar";
import RadiographyPanel from "./components/radiography/RadiographyPanel";
import VisualAnalysisPanel from "./components/visual-analysis/VisualAnalysisPanel";
import TransitionPanel from "./components/rhythm/TransitionPanel";
import FormulaEditor from "./components/rhythm/FormulaEditor";
import HistoryPanel from "./components/rhythm/HistoryPanel";
import QuartersPanel from "./components/rhythm/QuartersPanel";
import OptimizerPanel from "./components/rhythm/OptimizerPanel";
import PositionsPanel from "./components/rhythm/PositionsPanel";
import { useWebSocket } from "./hooks/useWebSocket";
import type { Candle } from "./types/candle";

// Lire une valeur du localStorage avec fallback
function stored(key: string, fallback: string): string {
  return localStorage.getItem(key) || fallback;
}

// Setter qui sauvegarde aussi dans le localStorage
function usePersistedState(key: string, fallback: string) {
  const [value, setValue] = useState(() => stored(key, fallback));
  const set = (v: string) => {
    setValue(v);
    localStorage.setItem(key, v);
  };
  return [value, set] as const;
}

export default function App() {
  const [symbol, setSymbol] = usePersistedState("bougie1_symbol", "XAUUSD");
  const [timeframe, setTimeframe] = usePersistedState("bougie1_timeframe", "M15");
  const [microTf, setMicroTf] = usePersistedState("bougie1_microTf", "M1");

  const { data, connected } = useWebSocket(symbol, timeframe, microTf);

  // Signaux de trading (prix + direction)
  const [signalLines, setSignalLines] = useState<Array<{ price: number; direction: string; time: string }>>([]);
  const lastSignalRef = useRef<string | null>(null);
  const [signalThreshold, setSignalThreshold] = useState(() => {
    const saved = localStorage.getItem("bougie1_signal_threshold");
    return saved ? parseInt(saved) : 51;
  });

  // Detecter les signaux et ajouter les lignes
  useEffect(() => {
    if (!data?.close_prediction?.prediction || !data?.current_candle) return;
    const cp = data.close_prediction as any;
    const confidence = Math.max(cp.pct_hausse || 50, cp.pct_baisse || 50);
    const threshold = signalThreshold;

    if (confidence >= threshold) {
      const direction = cp.prediction === "HAUSSE" ? "LONG" : "SHORT";
      if (direction !== lastSignalRef.current) {
        lastSignalRef.current = direction;
        const price = data.current_candle.close;
        const time = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
        setSignalLines(prev => [...prev.slice(-10), { price, direction, time }]); // Garder les 10 derniers
      }
    } else {
      lastSignalRef.current = null;
    }
  }, [data?.close_prediction, data?.current_candle]);

  // Reset les lignes a chaque nouvelle bougie
  useEffect(() => {
    if (data?.current_candle?.time && data.current_candle.time !== lastCandleTimeRef.current) {
      setSignalLines([]);
      lastSignalRef.current = null;
    }
  }, [data?.current_candle?.time]);

  // Predictions par quart pour la bougie en cours
  const [quarterPreds, setQuarterPreds] = useState<Array<{ quarter: number; prediction: string; pct: number; nextQ?: string; nextQpct?: number } | null>>([]);
  const lastCandleTimeRef = useRef(0);

  // Capturer les predictions a chaque quart
  useEffect(() => {
    if (!data?.close_prediction?.prediction || !data?.current_candle) return;

    const candleTime = data.current_candle.time;
    const progress = data.candle_progress ?? 0;
    const cp = data.close_prediction as any;

    // Reset si nouvelle bougie
    if (candleTime !== lastCandleTimeRef.current) {
      lastCandleTimeRef.current = candleTime;
      setQuarterPreds([]);
    }

    // Determiner tous les quarts qui devraient etre remplis
    const currentQuarter = Math.min(4, Math.floor(progress * 4) + 1);

    setQuarterPreds(prev => {
      const updated = [...prev];
      // Prediction next quarter
      const nqp = (data as any)?.next_quarter_prediction;

      // Remplir tous les quarts jusqu'au quart actuel
      for (let q = 1; q <= currentQuarter; q++) {
        const existing = updated.find(p => p?.quarter === q);
        if (!existing) {
          // Quart passe : prediction actuelle, NQ si disponible
          const isCurrentQ = q === currentQuarter;
          updated.push({
            quarter: q,
            prediction: cp.prediction,
            pct: cp.prediction === "HAUSSE" ? cp.pct_hausse : cp.pct_baisse,
            nextQ: isCurrentQ && q < 4 ? (nqp?.prediction || "") : "",
            nextQpct: isCurrentQ && q < 4 ? (nqp?.pct || 0) : 0,
          });
        } else if (q === currentQuarter) {
          // Mettre a jour le quart en cours
          const idx = updated.findIndex(p => p?.quarter === q);
          if (idx >= 0) {
            updated[idx] = {
              ...updated[idx]!,
              prediction: cp.prediction,
              pct: cp.prediction === "HAUSSE" ? cp.pct_hausse : cp.pct_baisse,
              nextQ: updated[idx]!.nextQ || (q < 4 ? (nqp?.prediction || "") : ""),
              nextQpct: updated[idx]!.nextQpct || (q < 4 ? (nqp?.pct || 0) : 0),
            };
          }
        }
      }
      return updated.sort((a, b) => (a?.quarter || 0) - (b?.quarter || 0));
    });
  }, [data?.close_prediction, data?.candle_progress, data?.current_candle]);

  // Editeur de formule et historique
  const [showFormula, setShowFormula] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showQuarters, setShowQuarters] = useState(false);
  const [showOptimizer, setShowOptimizer] = useState(false);
  const [showPositions, setShowPositions] = useState(false);

  // Zoom vertical (1 = normal, < 1 = zoom in, > 1 = zoom out)
  const [zoomY, setZoomY] = useState(1);

  // Bornes de prix partagees entre les 2 panneaux (verrouillees)
  // Inclut les bougies ET les micro-bougies pour que tout soit visible
  const priceBounds = useMemo(() => {
    let minPrice = Infinity;
    let maxPrice = -Infinity;

    // Bougies principales
    if (data?.last_closed_candle) {
      minPrice = Math.min(minPrice, data.last_closed_candle.low);
      maxPrice = Math.max(maxPrice, data.last_closed_candle.high);
    }
    if (data?.current_candle) {
      minPrice = Math.min(minPrice, data.current_candle.low);
      maxPrice = Math.max(maxPrice, data.current_candle.high);
    }

    // Micro-bougies (courbe)
    if (data?.micro_candles) {
      for (const mc of data.micro_candles) {
        minPrice = Math.min(minPrice, mc.low);
        maxPrice = Math.max(maxPrice, mc.high);
      }
    }

    if (minPrice === Infinity) return { minPrice: 0, maxPrice: 0 };

    // Marge de base 10%, modifiee par le zoom
    const range = maxPrice - minPrice || 1;
    const margin = range * 0.1 * zoomY;
    minPrice -= margin;
    maxPrice += margin;
    return { minPrice, maxPrice };
  }, [data?.last_closed_candle, data?.current_candle, data?.micro_candles, zoomY]);

  // Separateur vertical draggable (gauche/droite)
  const [splitPercent, setSplitPercent] = useState(50);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Separateur horizontal draggable (haut/bas)
  const [canvasHeight, setCanvasHeight] = useState(75); // en vh
  const hDragging = useRef(false);

  // Callback zoom vertical depuis l'echelle de prix
  const handleZoomY = useCallback((factor: number) => {
    setZoomY((prev) => Math.max(0.1, Math.min(10, prev * factor)));
  }, []);

  // Handler separateur horizontal (haut/bas)
  const onHSplitMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    hDragging.current = true;

    const onMouseMove = (ev: MouseEvent) => {
      if (!hDragging.current) return;
      const pct = (ev.clientY / window.innerHeight) * 100;
      setCanvasHeight(Math.max(30, Math.min(85, pct)));
    };

    const onMouseUp = () => {
      hDragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "row-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  // Handler separateur vertical (gauche/droite)
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setSplitPercent(Math.max(20, Math.min(80, pct)));
    };

    const onMouseUp = () => {
      dragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  return (
    <div className="flex flex-col">
      <TopBar
        symbol={symbol}
        timeframe={timeframe}
        connected={connected}
        onSymbolChange={setSymbol}
        onTimeframeChange={setTimeframe}
      />

      <div ref={containerRef} className="flex" style={{ height: `${canvasHeight}vh` }}>
        {/* Ecran 1 : Radiographie */}
        <div style={{ width: `${splitPercent}%` }} className="h-full">
          <RadiographyPanel
            currentCandle={data?.current_candle ?? null}
            lastClosedCandle={data?.last_closed_candle ?? null}
            microCandles={data?.micro_candles ?? []}
            timeframe={timeframe}
            microTf={microTf}
            onMicroTfChange={setMicroTf}
            priceBounds={priceBounds}
            quarterPredictions={quarterPreds}
            signalLines={signalLines}
          />
        </div>

        {/* Separateur draggable */}
        <div
          onMouseDown={onMouseDown}
          className="w-[6px] h-full cursor-col-resize bg-[#2a2a3e] hover:bg-[#4a4a6e] active:bg-[#6a6a8e] flex-shrink-0 transition-colors"
        />

        {/* Ecran 2 : Analyse visuelle */}
        <div style={{ width: `${100 - splitPercent}%` }} className="h-full">
          <VisualAnalysisPanel
            currentCandle={data?.current_candle ?? null}
            lastClosedCandle={data?.last_closed_candle ?? null}
            history={data?.history ?? []}
            tick={data?.tick ?? null}
            priceBounds={priceBounds}
            closedSignature={data?.closed_signature ?? null}
            transitionProbs={data?.transition_probs?.all ?? []}
            onZoomY={handleZoomY}
            liveEstimate={data?.live_estimate ?? []}
            signalLines={signalLines}
          />
        </div>
      </div>

      {/* Separateur horizontal draggable */}
      <div
        onMouseDown={onHSplitMouseDown}
        className="h-[6px] w-full cursor-row-resize bg-[#2a2a3e] hover:bg-[#4a4a6e] active:bg-[#6a6a8e] flex-shrink-0 transition-colors"
      />

      {/* Panneau temps reel : pattern en formation */}
      <TransitionPanel
        progress={data?.candle_progress ?? 0}
        microPrediction={data?.micro_prediction ?? null}
        closePrediction={(data?.close_prediction as any) ?? null}
        closeStats={(data?.close_stats as any) ?? null}
        onOpenFormula={() => setShowFormula(true)}
        onOpenHistory={() => setShowHistory(true)}
        onOpenQuarters={() => setShowQuarters(true)}
        onOpenOptimizer={() => setShowOptimizer(true)}
        onOpenPositions={() => setShowPositions(true)}
        symbol={symbol}
        quarterPreds={quarterPreds.filter(q => q !== null) as Array<{ quarter: number; prediction: string; pct: number }>}
        signalThreshold={signalThreshold}
        onSignalThresholdChange={(t) => {
          setSignalThreshold(t);
          localStorage.setItem("bougie1_signal_threshold", String(t));
        }}
      />

      <FormulaEditor
        visible={showFormula}
        onClose={() => setShowFormula(false)}
      />

      <HistoryPanel
        visible={showHistory}
        onClose={() => setShowHistory(false)}
      />

      <QuartersPanel
        visible={showQuarters}
        onClose={() => setShowQuarters(false)}
      />

      <OptimizerPanel
        visible={showOptimizer}
        onClose={() => setShowOptimizer(false)}
        symbol={symbol}
      />

      <PositionsPanel
        visible={showPositions}
        onClose={() => setShowPositions(false)}
        symbol={symbol}
      />

      {/* Barre d'erreur si deconnecte ou erreur */}
      {data?.type === "error" && (
        <div className="bg-red-900/50 text-red-300 px-4 py-2 text-center">
          {data.message}
        </div>
      )}
    </div>
  );
}
