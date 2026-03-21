import { useState, useEffect } from "react";

interface SlotStatsProps {
  visible: boolean;
  onClose: () => void;
  symbol: string;
}

interface SlotData {
  hour: number;
  time_str: string;
  green_pct: number;
  cont_pct: number;
  rev_pct: number;
  samples: number;
  bias: string;
}

export default function SlotStatsPanel({ visible, onClose, symbol }: SlotStatsProps) {
  const [slots, setSlots] = useState<SlotData[]>([]);
  const [loading, setLoading] = useState(false);
  const [signal, setSignal] = useState<any>(null);

  // Parametres configurables
  const [lookback, setLookback] = useState(() => parseInt(localStorage.getItem("slot_lookback") || "2000"));
  const [biasLong, setBiasLong] = useState(() => parseInt(localStorage.getItem("slot_bias_long") || "58"));
  const [biasShort, setBiasShort] = useState(() => parseInt(localStorage.getItem("slot_bias_short") || "42"));
  const [contThreshold, setContThreshold] = useState(() => parseInt(localStorage.getItem("slot_cont_threshold") || "65"));
  const [timeframe, setTimeframe] = useState(() => localStorage.getItem("slot_timeframe") || "M15");

  // Sauvegarder les parametres
  const saveParams = () => {
    localStorage.setItem("slot_lookback", String(lookback));
    localStorage.setItem("slot_bias_long", String(biasLong));
    localStorage.setItem("slot_bias_short", String(biasShort));
    localStorage.setItem("slot_cont_threshold", String(contThreshold));
    localStorage.setItem("slot_timeframe", timeframe);
  };

  // Charger les stats
  const loadStats = () => {
    setLoading(true);
    saveParams();
    fetch(`/api/slot-stats/${symbol}/${timeframe}?lookback=${lookback}`)
      .then(r => r.json())
      .then(data => {
        if (data.slots) {
          // Recalculer le biais avec les seuils personnalises
          const updated = data.slots.map((s: SlotData) => ({
            ...s,
            bias: s.green_pct > biasLong ? "LONG" : s.green_pct < biasShort ? "SHORT" : "NEUTRE",
          }));
          setSlots(updated);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  // Charger le signal actuel
  const loadSignal = () => {
    fetch(`/api/slot-signal/${symbol}/${timeframe}`)
      .then(r => r.json())
      .then(data => setSignal(data))
      .catch(() => {});
  };

  useEffect(() => {
    if (visible) {
      loadStats();
      loadSignal();
    }
  }, [visible]);

  if (!visible) return null;

  // Stats globales
  const longSlots = slots.filter(s => s.green_pct > biasLong);
  const shortSlots = slots.filter(s => s.green_pct < biasShort);
  const contSlots = slots.filter(s => s.cont_pct > contThreshold);

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[950px] max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[20px] text-white font-bold">
            Slot Stats - {symbol}
          </span>
          <div className="flex gap-2">
            <button onClick={loadStats} disabled={loading}
              className="px-3 py-1 bg-[#8888ff] text-white rounded text-[16px] cursor-pointer hover:bg-[#6666dd]">
              {loading ? "Chargement..." : "Analyser"}
            </button>
            <button onClick={onClose}
              className="px-3 py-1 bg-[#555] text-white rounded text-[16px] cursor-pointer hover:bg-[#666]">
              Fermer
            </button>
          </div>
        </div>

        {/* Parametres */}
        <div className="flex items-center gap-4 px-4 py-3 border-b border-[#2a2a3e] bg-[#0e0e18] flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">TF :</span>
            <select value={timeframe} onChange={e => setTimeframe(e.target.value)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] border border-[#2a2a3e]">
              <option value="M15">M15</option>
              <option value="M30">M30</option>
              <option value="H1">H1</option>
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">Lookback :</span>
            <input type="number" value={lookback} onChange={e => setLookback(parseInt(e.target.value) || 2000)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[80px] border border-[#2a2a3e]" />
          </div>

          <div className="w-[1px] h-[25px] bg-[#2a2a3e]" />

          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">Biais LONG si vertes &gt; :</span>
            <input type="number" value={biasLong} onChange={e => setBiasLong(parseInt(e.target.value) || 58)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[50px] border border-[#2a2a3e]" />
            <span className="text-[#888] text-[14px]">%</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">Biais SHORT si vertes &lt; :</span>
            <input type="number" value={biasShort} onChange={e => setBiasShort(parseInt(e.target.value) || 42)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[50px] border border-[#2a2a3e]" />
            <span className="text-[#888] text-[14px]">%</span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">Seuil continuation :</span>
            <input type="number" value={contThreshold} onChange={e => setContThreshold(parseInt(e.target.value) || 65)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[50px] border border-[#2a2a3e]" />
            <span className="text-[#888] text-[14px]">%</span>
          </div>
        </div>

        {/* Signal actuel */}
        {signal && (
          <div className="flex items-center gap-4 px-4 py-2 border-b border-[#2a2a3e]">
            <span className="text-[#888] text-[16px]">Signal actuel :</span>
            {signal.signal ? (
              <>
                <span className="font-bold text-[20px] px-3 py-1 rounded"
                  style={{
                    color: signal.signal === "LONG" ? "#22c55e" : signal.signal === "SHORT" ? "#ef4444" : "#f97316",
                    backgroundColor: signal.signal === "LONG" ? "rgba(34,197,94,0.15)" : signal.signal === "SHORT" ? "rgba(239,68,68,0.15)" : "rgba(249,115,22,0.15)",
                  }}>
                  {signal.signal} {signal.confidence}%
                </span>
                <span className="text-[#888] text-[14px]">{signal.raison}</span>
              </>
            ) : (
              <span className="text-[#555] text-[16px]">Pas de signal pour ce creneau</span>
            )}
            {signal.current_slot && (
              <span className="text-[#555] text-[14px] ml-auto">
                Heure broker: {signal.broker_hour}h | Vertes: {signal.current_slot.green_pct}%
              </span>
            )}
          </div>
        )}

        {/* Resume */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-[#2a2a3e]">
          <span className="text-[#22c55e] font-bold">{longSlots.length} creneaux LONG</span>
          <span className="text-[#ef4444] font-bold">{shortSlots.length} creneaux SHORT</span>
          <span className="text-[#f97316] font-bold">{contSlots.length} forte continuation</span>
          <span className="text-[#555]">{slots.length} creneaux total</span>
        </div>

        {/* Tableau des slots */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading ? (
            <span className="text-[#888] text-[18px]">Analyse en cours...</span>
          ) : slots.length === 0 ? (
            <span className="text-[#888] text-[18px]">Cliquez sur Analyser</span>
          ) : (
            <table className="w-full text-[15px]">
              <thead>
                <tr className="text-[#888] border-b border-[#2a2a3e]">
                  <th className="text-left py-2 px-2">Heure</th>
                  <th className="text-center py-2 px-2">Biais</th>
                  <th className="text-center py-2 px-2">% Vertes</th>
                  <th className="text-center py-2 px-2">Continuation</th>
                  <th className="text-center py-2 px-2">Retournement</th>
                  <th className="text-center py-2 px-2">Echantillons</th>
                  <th className="text-left py-2 px-2">Barre</th>
                </tr>
              </thead>
              <tbody>
                {slots.map((s, i) => {
                  const barWidth = Math.round(s.green_pct);
                  return (
                    <tr key={i} className="border-b border-[#1a1a2e] hover:bg-[#1a1a2e]">
                      <td className="py-2 px-2 font-mono font-bold text-white">{s.time_str}</td>
                      <td className="py-2 px-2 text-center">
                        {s.bias !== "NEUTRE" && (
                          <span className="font-bold px-2 py-0.5 rounded text-[13px]"
                            style={{
                              color: s.bias === "LONG" ? "#22c55e" : "#ef4444",
                              backgroundColor: s.bias === "LONG" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                            }}>
                            {s.bias}
                          </span>
                        )}
                      </td>
                      <td className="py-2 px-2 text-center font-bold"
                        style={{ color: s.green_pct > 55 ? "#22c55e" : s.green_pct < 45 ? "#ef4444" : "#888" }}>
                        {s.green_pct}%
                      </td>
                      <td className="py-2 px-2 text-center"
                        style={{ color: s.cont_pct > contThreshold ? "#f97316" : "#555" }}>
                        {s.cont_pct}%
                      </td>
                      <td className="py-2 px-2 text-center text-[#555]">{s.rev_pct}%</td>
                      <td className="py-2 px-2 text-center text-[#555]">{s.samples}</td>
                      <td className="py-2 px-2">
                        <div className="relative w-[120px] h-[14px] bg-[#1a1a2e] rounded overflow-hidden">
                          <div className="absolute inset-y-0 left-0 rounded"
                            style={{
                              width: `${barWidth}%`,
                              backgroundColor: s.green_pct > 55 ? "rgba(34,197,94,0.5)" : s.green_pct < 45 ? "rgba(239,68,68,0.5)" : "rgba(136,136,136,0.3)",
                            }} />
                          <div className="absolute top-0 left-[50%] w-[1px] h-full bg-[#555]" />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
