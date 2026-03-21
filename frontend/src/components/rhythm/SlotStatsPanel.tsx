import { useState, useEffect, useRef } from "react";

interface SlotStatsProps {
  visible: boolean;
  onClose: () => void;
  symbol: string;
}

interface SlotData {
  slot_idx: number;
  time_str: string;
  hour: number;
  minute: number;
  green_pct: number;
  cont_pct: number;
  rev_pct: number;
  samples: number;
  bias: string;
  broker_timestamp: number;
}

export default function SlotStatsPanel({ visible, onClose, symbol }: SlotStatsProps) {
  const [slots, setSlots] = useState<SlotData[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentSlotIdx, setCurrentSlotIdx] = useState(-1);
  const [slotDuration, setSlotDuration] = useState(900);
  const [now, setNow] = useState(Date.now());

  // Parametres
  const [lookback, setLookback] = useState(() => parseInt(localStorage.getItem("slot_lookback") || "5000"));
  const [biasLong, setBiasLong] = useState(() => parseInt(localStorage.getItem("slot_bias_long") || "55"));
  const [biasShort, setBiasShort] = useState(() => parseInt(localStorage.getItem("slot_bias_short") || "45"));
  const [timeframe] = useState("M15");

  // Timer pour compte a rebours
  useEffect(() => {
    if (!visible) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [visible]);

  const saveParams = () => {
    localStorage.setItem("slot_lookback", String(lookback));
    localStorage.setItem("slot_bias_long", String(biasLong));
    localStorage.setItem("slot_bias_short", String(biasShort));
  };

  const loadStats = () => {
    setLoading(true);
    saveParams();
    fetch(`/api/slot-stats/${symbol}/${timeframe}?lookback=${lookback}`)
      .then(r => r.json())
      .then(data => {
        if (data.slots) {
          const updated = data.slots.map((s: SlotData) => ({
            ...s,
            bias: s.green_pct > biasLong ? "LONG" : s.green_pct < biasShort ? "SHORT" : "NEUTRE",
          }));
          setSlots(updated);
          setCurrentSlotIdx(data.current_slot_idx || -1);
          setSlotDuration(data.slot_duration || 900);
        }
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    if (visible) loadStats();
  }, [visible]);

  if (!visible) return null;

  // Calculer le compte a rebours pour chaque slot a venir
  const getCountdown = (slot: SlotData) => {
    // Secondes depuis minuit broker time
    // Heure actuelle broker = UTC + 3
    const nowUtcSec = Math.floor(now / 1000);
    const brokerNow = (nowUtcSec + 3 * 3600) % 86400;
    const slotStart = slot.broker_timestamp;

    let diff = slotStart - brokerNow;
    if (diff < 0) diff += 86400; // Demain

    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    const s = diff % 60;
    return { h, m, s, total: diff, isPast: diff > 82800 }; // > 23h = vient de passer
  };

  // Filtrer les trades a venir (avec signal)
  const upcomingTrades = slots
    .filter(s => s.bias !== "NEUTRE")
    .map(s => ({ ...s, countdown: getCountdown(s) }))
    .filter(s => !s.countdown.isPast)
    .sort((a, b) => a.countdown.total - b.countdown.total);

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[850px] max-h-[85vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[20px] text-white font-bold">
            Slots M15 - {symbol}
          </span>
          <div className="flex gap-2">
            <button onClick={loadStats} disabled={loading}
              className="px-3 py-1 bg-[#8888ff] text-white rounded text-[16px] cursor-pointer hover:bg-[#6666dd]">
              {loading ? "..." : "Analyser"}
            </button>
            <button onClick={onClose}
              className="px-3 py-1 bg-[#555] text-white rounded text-[16px] cursor-pointer hover:bg-[#666]">
              Fermer
            </button>
          </div>
        </div>

        {/* Parametres */}
        <div className="flex items-center gap-4 px-4 py-2 border-b border-[#2a2a3e] bg-[#0e0e18]">
          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">Lookback :</span>
            <input type="number" value={lookback} onChange={e => setLookback(parseInt(e.target.value) || 5000)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[70px] border border-[#2a2a3e]" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[#888] text-[14px]">LONG &gt;</span>
            <input type="number" value={biasLong} onChange={e => setBiasLong(parseInt(e.target.value) || 55)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[45px] border border-[#2a2a3e]" />
            <span className="text-[#888] text-[14px]">% | SHORT &lt;</span>
            <input type="number" value={biasShort} onChange={e => setBiasShort(parseInt(e.target.value) || 45)}
              className="bg-[#1a1a2e] text-white px-2 py-1 rounded text-[14px] w-[45px] border border-[#2a2a3e]" />
            <span className="text-[#888] text-[14px]">%</span>
          </div>
        </div>

        {/* Trades a venir avec compte a rebours */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading ? (
            <span className="text-[#888] text-[18px]">Analyse de {lookback} bougies...</span>
          ) : upcomingTrades.length === 0 ? (
            <span className="text-[#888] text-[18px]">Cliquez sur Analyser</span>
          ) : (
            <>
              <div className="text-[#888] text-[14px] mb-2">
                {upcomingTrades.length} trades a venir sur 24h
              </div>
              <table className="w-full text-[15px]">
                <thead>
                  <tr className="text-[#888] border-b border-[#2a2a3e]">
                    <th className="text-center py-2 px-2 w-[100px]">Compte a rebours</th>
                    <th className="text-left py-2 px-2">Heure</th>
                    <th className="text-center py-2 px-2">Signal</th>
                    <th className="text-center py-2 px-2">% Vertes</th>
                    <th className="text-center py-2 px-2">Continuation</th>
                    <th className="text-center py-2 px-2">Retournement</th>
                    <th className="text-center py-2 px-2">Echantillons</th>
                  </tr>
                </thead>
                <tbody>
                  {upcomingTrades.map((s, i) => {
                    const cd = s.countdown;
                    const isImminent = cd.total < 900; // < 15min
                    const isNext = i === 0;

                    return (
                      <tr key={i} className={`border-b border-[#1a1a2e] ${isNext ? "bg-[#1a1a2e]" : ""}`}>
                        <td className="py-2 px-2 text-center font-mono font-bold text-[16px]"
                          style={{ color: isImminent ? "#f97316" : isNext ? "#8888ff" : "#555" }}>
                          {cd.h > 0 ? `${cd.h}h${String(cd.m).padStart(2, "0")}m` : `${cd.m}m${String(cd.s).padStart(2, "0")}s`}
                        </td>
                        <td className="py-2 px-2 font-mono font-bold text-white text-[16px]">
                          {s.time_str}
                        </td>
                        <td className="py-2 px-2 text-center">
                          <span className="font-bold px-3 py-1 rounded text-[16px]"
                            style={{
                              color: s.bias === "LONG" ? "#22c55e" : "#ef4444",
                              backgroundColor: s.bias === "LONG" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                            }}>
                            {s.bias === "LONG" ? "\u2191 LONG" : "\u2193 SHORT"}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-center font-bold"
                          style={{ color: s.green_pct > 55 ? "#22c55e" : s.green_pct < 45 ? "#ef4444" : "#888" }}>
                          {s.green_pct}%
                        </td>
                        <td className="py-2 px-2 text-center text-[#888]">{s.cont_pct}%</td>
                        <td className="py-2 px-2 text-center text-[#888]">{s.rev_pct}%</td>
                        <td className="py-2 px-2 text-center text-[#555]">{s.samples}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
