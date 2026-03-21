import { useRef } from "react";

interface EntryTimingProps {
  alert: { direction: string } | null;
  timing: {
    signal: string;
    raison: string;
    entry_price?: number;
    stop_loss?: number;
    confidence?: number;
  } | null;
  onSendAlert: (direction: string) => void;
}

export default function EntryTiming({ alert, timing, onSendAlert }: EntryTimingProps) {
  const signalColors: Record<string, { bg: string; color: string; border: string }> = {
    "ENTRE": { bg: "rgba(34,197,94,0.2)", color: "#22c55e", border: "#22c55e" },
    "ATTENDS": { bg: "rgba(249,115,22,0.15)", color: "#f97316", border: "#f97316" },
    "N_ENTRE_PAS": { bg: "rgba(239,68,68,0.2)", color: "#ef4444", border: "#ef4444" },
  };

  const signalLabels: Record<string, string> = {
    "ENTRE": "ENTRE MAINTENANT",
    "ATTENDS": "ATTENDS",
    "N_ENTRE_PAS": "N'ENTRE PAS",
  };

  return (
    <div className="flex items-center gap-3">
      {/* Boutons d'alerte manuelle */}
      <div className="flex gap-1">
        <button onClick={() => onSendAlert("LONG")}
          className={`px-2 py-1 rounded text-[14px] cursor-pointer transition-colors ${
            alert?.direction === "LONG" ? "bg-green-700 text-white" : "bg-[#1a1a2e] text-[#888] hover:bg-[#2a2a4e]"
          }`}>
          LONG
        </button>
        <button onClick={() => onSendAlert("SHORT")}
          className={`px-2 py-1 rounded text-[14px] cursor-pointer transition-colors ${
            alert?.direction === "SHORT" ? "bg-red-700 text-white" : "bg-[#1a1a2e] text-[#888] hover:bg-[#2a2a4e]"
          }`}>
          SHORT
        </button>
        <button onClick={() => onSendAlert("CLEAR")}
          className="px-2 py-1 rounded text-[14px] cursor-pointer bg-[#1a1a2e] text-[#555] hover:bg-[#2a2a4e]">
          X
        </button>
      </div>

      {/* Resultat du timing */}
      {alert && timing && timing.signal && (
        <>
          <div className="w-[1px] h-[30px] bg-[#2a2a3e]" />
          <div className="px-3 py-1 rounded font-bold text-[18px]"
            style={{
              backgroundColor: signalColors[timing.signal]?.bg || "transparent",
              color: signalColors[timing.signal]?.color || "#888",
              border: `2px solid ${signalColors[timing.signal]?.border || "#333"}`,
            }}>
            {signalLabels[timing.signal] || timing.signal}
          </div>
          <span className="text-[#888] text-[14px] max-w-[200px]">{timing.raison}</span>
          {timing.entry_price && (
            <span className="text-[#ccc] text-[14px] font-mono">
              Prix: {timing.entry_price.toFixed(2)}
            </span>
          )}
          {timing.stop_loss && (
            <span className="text-[#ef4444] text-[14px] font-mono">
              SL: {timing.stop_loss.toFixed(2)}
            </span>
          )}
          {timing.confidence && (
            <span className="text-[#555] text-[14px]">
              ({timing.confidence}%)
            </span>
          )}
        </>
      )}
    </div>
  );
}
