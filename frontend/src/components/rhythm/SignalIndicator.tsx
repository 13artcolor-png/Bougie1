import { useState, useEffect, useRef } from "react";

interface QuarterPred {
  quarter: number;
  prediction: string;
  pct: number;
}

interface SignalIndicatorProps {
  prediction: string | null;
  pctHausse: number;
  pctBaisse: number;
  progress: number;
  threshold: number;
  onThresholdChange: (t: number) => void;
  quarterPreds?: QuarterPred[];
}

export default function SignalIndicator({
  prediction, pctHausse, pctBaisse, progress, threshold, onThresholdChange, quarterPreds,
}: SignalIndicatorProps) {
  const [lastSignal, setLastSignal] = useState<string | null>(null);
  const [signalTime, setSignalTime] = useState("");
  const [flash, setFlash] = useState(false);
  const prevPrediction = useRef<string | null>(null);

  // Analyser la tendance entre les quarts
  const [trend, setTrend] = useState<"ACCEL" | "DECEL" | "RETOURNE" | "STABLE">("STABLE");

  useEffect(() => {
    if (!quarterPreds || quarterPreds.length < 2) {
      setTrend("STABLE");
      return;
    }

    const sorted = [...quarterPreds].sort((a, b) => a.quarter - b.quarter);
    const last = sorted[sorted.length - 1];
    const prev = sorted[sorted.length - 2];

    if (!last || !prev) {
      setTrend("STABLE");
      return;
    }

    // Changement de direction = retournement
    if (last.prediction !== prev.prediction) {
      setTrend("RETOURNE");
      return;
    }

    // Meme direction : comparer la confiance
    const diff = last.pct - prev.pct;
    if (diff > 2) {
      setTrend("ACCEL");
    } else if (diff < -2) {
      setTrend("DECEL");
    } else {
      setTrend("STABLE");
    }
  }, [quarterPreds]);

  // Determiner le signal actuel
  const confidence = Math.max(pctHausse, pctBaisse);
  const isStrong = confidence >= threshold;
  const direction = prediction === "HAUSSE" ? "LONG" : prediction === "BAISSE" ? "SHORT" : null;
  const isReversal = trend === "RETOURNE" || trend === "DECEL";

  // Detecter un changement de signal
  useEffect(() => {
    if (!isStrong || !direction) {
      if (lastSignal !== null) {
        setLastSignal(null);
      }
      return;
    }

    const newSignal = direction;
    if (newSignal !== prevPrediction.current) {
      prevPrediction.current = newSignal;
      setLastSignal(newSignal);
      setSignalTime(new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }));
      setFlash(true);
      setTimeout(() => setFlash(false), 2000);

      // Son d'alerte
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = newSignal === "LONG" ? 800 : 400;
        gain.gain.value = 0.3;
        osc.start();
        osc.stop(ctx.currentTime + 0.15);
        setTimeout(() => {
          const osc2 = ctx.createOscillator();
          const gain2 = ctx.createGain();
          osc2.connect(gain2);
          gain2.connect(ctx.destination);
          osc2.frequency.value = newSignal === "LONG" ? 1000 : 300;
          gain2.gain.value = 0.3;
          osc2.start();
          osc2.stop(ctx.currentTime + 0.2);
        }, 180);
      } catch {}
    }
  }, [direction, isStrong]);

  // Son d'alerte pour retournement
  useEffect(() => {
    if (trend === "RETOURNE") {
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = 600;
        osc.type = "sawtooth";
        gain.gain.value = 0.2;
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      } catch {}
    }
  }, [trend]);

  // Couleurs
  const isLong = lastSignal === "LONG";
  const isShort = lastSignal === "SHORT";
  const noSignal = lastSignal === null;

  const trendInfo = {
    "ACCEL": { color: "#22c55e", label: "\u25B2 ACCELERATION", bg: "rgba(34,197,94,0.1)" },
    "DECEL": { color: "#f97316", label: "\u25BC RALENTISSEMENT", bg: "rgba(249,115,22,0.15)" },
    "RETOURNE": { color: "#ef4444", label: "\u26A0 RETOURNEMENT", bg: "rgba(239,68,68,0.2)" },
    "STABLE": { color: "#888", label: "", bg: "transparent" },
  };
  const ti = trendInfo[trend];

  return (
    <div className="flex items-center gap-3">
      {/* Indicateur principal */}
      <div
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-bold text-[20px] transition-all ${
          flash ? "scale-110" : "scale-100"
        }`}
        style={{
          backgroundColor: noSignal
            ? "rgba(100,100,100,0.15)"
            : isLong
            ? "rgba(34,197,94,0.25)"
            : "rgba(239,68,68,0.25)",
          color: noSignal ? "#888" : isLong ? "#22c55e" : "#ef4444",
          border: noSignal
            ? "2px solid #333"
            : isReversal
            ? "2px solid #f97316"
            : isLong
            ? "2px solid #22c55e"
            : "2px solid #ef4444",
          animation: flash ? "pulse 0.5s ease-in-out 3" : "none",
        }}
      >
        {noSignal ? (
          <span>PAS DE SIGNAL</span>
        ) : (
          <>
            <span className="text-[28px]">{isLong ? "\u2191" : "\u2193"}</span>
            <span>{isLong ? "LONG" : "SHORT"}</span>
            <span className="text-[16px] opacity-70">{confidence}%</span>
          </>
        )}
      </div>

      {/* Indicateur de tendance entre les quarts */}
      {trend !== "STABLE" && (
        <div className="px-3 py-1 rounded font-bold text-[16px]"
          style={{ backgroundColor: ti.bg, color: ti.color, border: `1px solid ${ti.color}40` }}>
          {ti.label}
        </div>
      )}

      {/* Heure du signal */}
      {lastSignal && signalTime && (
        <span className="text-[#555] text-[14px]">{signalTime}</span>
      )}

      {/* Seuil configurable */}
      <div className="flex items-center gap-1 ml-2">
        <span className="text-[#888] text-[14px]">Seuil:</span>
        <input
          type="range"
          min={51}
          max={80}
          step={1}
          value={threshold}
          onChange={(e) => onThresholdChange(parseInt(e.target.value))}
          className="w-[80px] accent-[#8888ff]"
        />
        <span className="text-[#8888ff] text-[14px] font-bold w-[35px]">{threshold}%</span>
      </div>
    </div>
  );
}
