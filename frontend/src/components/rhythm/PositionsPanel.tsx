import { useState, useEffect } from "react";

interface Trade {
  candle_time: number;
  direction: string;
  entry_price: number;
  exit_price: number;
  confidence: number;
  lot_size: number;
  points: number;
  exit_type: string;
  note: number;
}

interface PositionsPanelProps {
  visible: boolean;
  onClose: () => void;
  symbol: string;
}

function formatTime(timestamp: number): string {
  const utcTimestamp = timestamp - (3 * 3600);
  const d = new Date(utcTimestamp * 1000);
  return d.toLocaleString("fr-FR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Europe/Paris",
  });
}

function noteColor(note: number): string {
  if (note >= 8) return "#22c55e";
  if (note >= 6) return "#8888ff";
  if (note >= 4) return "#f97316";
  return "#ef4444";
}

function noteBar(note: number): string {
  return "\u2588".repeat(note) + "\u2591".repeat(10 - note);
}

export default function PositionsPanel({ visible, onClose, symbol }: PositionsPanelProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible) {
      setLoading(true);
      fetch(`/api/trades/${symbol}/M15?limit=100`)
        .then(r => r.json())
        .then(data => {
          setTrades(data.history || []);
          setStats(data);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [visible, symbol]);

  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[950px] max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[20px] text-white font-bold">
            Positions - {symbol} ({trades.length} trades)
          </span>
          <button onClick={onClose}
            className="px-3 py-1 bg-[#555] text-white rounded text-[16px] cursor-pointer hover:bg-[#666]">
            Fermer
          </button>
        </div>

        {/* Stats globales */}
        {stats && stats.total > 0 && (
          <div className="flex items-center gap-4 px-4 py-3 border-b border-[#2a2a3e] bg-[#0e0e18]">
            <div className="text-center">
              <div className="text-[#888] text-[14px]">WR</div>
              <div className="text-[28px] font-bold"
                style={{ color: stats.wr >= 60 ? "#22c55e" : stats.wr >= 50 ? "#f97316" : "#ef4444" }}>
                {stats.wr}%
              </div>
            </div>
            <div className="w-[1px] h-[40px] bg-[#2a2a3e]" />
            <div className="text-center">
              <div className="text-[#888] text-[14px]">W / L</div>
              <div className="text-[20px] font-bold">
                <span className="text-[#22c55e]">{stats.wins}</span>
                {" / "}
                <span className="text-[#ef4444]">{stats.losses}</span>
              </div>
            </div>
            <div className="w-[1px] h-[40px] bg-[#2a2a3e]" />
            <div className="text-center">
              <div className="text-[#888] text-[14px]">Points total</div>
              <div className="text-[20px] font-bold"
                style={{ color: stats.total_points >= 0 ? "#22c55e" : "#ef4444" }}>
                {stats.total_points > 0 ? "+" : ""}{stats.total_points}
              </div>
            </div>
            <div className="w-[1px] h-[40px] bg-[#2a2a3e]" />
            <div className="text-center">
              <div className="text-[#888] text-[14px]">Note moyenne</div>
              <div className="text-[20px] font-bold" style={{ color: noteColor(stats.avg_note) }}>
                {stats.avg_note}/10
              </div>
            </div>
          </div>
        )}

        {/* Tableau */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading ? (
            <span className="text-[#888] text-[18px]">Chargement...</span>
          ) : trades.length === 0 ? (
            <span className="text-[#888] text-[18px]">Aucun trade. Attendez qu'un signal se declenche.</span>
          ) : (
            <table className="w-full text-[15px]">
              <thead>
                <tr className="text-[#888] border-b border-[#2a2a3e]">
                  <th className="text-left py-2 px-2">Date</th>
                  <th className="text-center py-2 px-2">Direction</th>
                  <th className="text-right py-2 px-2">Entree</th>
                  <th className="text-right py-2 px-2">Sortie</th>
                  <th className="text-center py-2 px-2">Confiance</th>
                  <th className="text-center py-2 px-2">Lot</th>
                  <th className="text-right py-2 px-2">Points</th>
                  <th className="text-center py-2 px-2">Sortie</th>
                  <th className="text-center py-2 px-2">Note</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => {
                  const isWin = t.points > 0;
                  return (
                    <tr key={i} className="border-b border-[#1a1a2e] hover:bg-[#1a1a2e]">
                      <td className="py-2 px-2 text-[#888] font-mono text-[13px]">
                        {formatTime(t.candle_time)}
                      </td>
                      <td className="py-2 px-2 text-center">
                        <span className="font-bold px-2 py-0.5 rounded"
                          style={{
                            color: t.direction === "LONG" ? "#22c55e" : "#ef4444",
                            backgroundColor: t.direction === "LONG" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                          }}>
                          {t.direction === "LONG" ? "\u2191 LONG" : "\u2193 SHORT"}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-right font-mono">{t.entry_price.toFixed(2)}</td>
                      <td className="py-2 px-2 text-right font-mono">{t.exit_price.toFixed(2)}</td>
                      <td className="py-2 px-2 text-center text-[#888]">{t.confidence}%</td>
                      <td className="py-2 px-2 text-center text-[#888]">{t.lot_size}</td>
                      <td className="py-2 px-2 text-right font-bold font-mono"
                        style={{ color: isWin ? "#22c55e" : "#ef4444" }}>
                        {isWin ? "+" : ""}{t.points.toFixed(2)}
                      </td>
                      <td className="py-2 px-2 text-center">
                        <span className={`text-[12px] px-1 rounded ${
                          t.exit_type === "retournement" ? "bg-orange-900/30 text-orange-400" : "bg-[#1a1a2e] text-[#888]"
                        }`}>
                          {t.exit_type === "retournement" ? "Retournement" : "Cloture"}
                        </span>
                      </td>
                      <td className="py-2 px-2 text-center">
                        <span className="font-mono text-[12px]" style={{ color: noteColor(t.note) }}>
                          {noteBar(t.note)} {t.note}
                        </span>
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
