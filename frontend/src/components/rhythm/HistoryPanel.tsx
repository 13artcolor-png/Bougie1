import { useState, useEffect } from "react";

interface HistoryEntry {
  candle_time: number;
  moves: string;
  move_count: number;
  closed_bullish: number;
}

interface HistoryPanelProps {
  visible: boolean;
  onClose: () => void;
}

function formatTime(timestamp: number): string {
  // Timestamp en broker time (UTC+3)
  // Soustraire 3h pour revenir en UTC, puis JavaScript convertit en heure locale Paris
  const utcTimestamp = timestamp - (3 * 3600);
  const d = new Date(utcTimestamp * 1000);
  return d.toLocaleString("fr-FR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
    timeZone: "Europe/Paris",
  });
}

export default function HistoryPanel({ visible, onClose }: HistoryPanelProps) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [limit, setLimit] = useState(50);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible) {
      setLoading(true);
      fetch(`/api/grid-history/XAUUSD/M15?limit=${limit}`)
        .then((r) => r.json())
        .then((data) => {
          setEntries(data.history || []);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [visible, limit]);

  const exportText = () => {
    let text = "Date | Cloture | Mouvements\n";
    for (const e of entries) {
      const time = formatTime(e.candle_time);
      const color = e.closed_bullish ? "HAUSSE" : "BAISSE";
      text += `${time} | ${color} | ${e.moves}\n`;
    }

    // Telecharger en fichier texte
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bougie1_historique_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[900px] max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[18px] text-white font-bold">
            Historique des mouvements ({entries.length} bougies) - Heure Paris
          </span>
          <div className="flex gap-2 items-center">
            <span className="text-[#888] text-[14px]">Nombre :</span>
            {[50, 100, 200, 500, 0].map((n) => (
              <button
                key={n}
                onClick={() => setLimit(n)}
                className={`px-2 py-1 rounded text-[14px] cursor-pointer ${
                  limit === n
                    ? "bg-[#8888ff] text-white"
                    : "bg-[#1a1a2e] text-[#888] hover:bg-[#2a2a4e]"
                }`}
              >
                {n === 0 ? "Tout" : n}
              </button>
            ))}
            <button
              onClick={exportText}
              className="px-3 py-1 bg-[#22c55e] text-white rounded text-[14px] cursor-pointer hover:bg-[#16a34a]"
            >
              Exporter .txt
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1 bg-[#555] text-white rounded text-[14px] cursor-pointer hover:bg-[#666]"
            >
              Fermer
            </button>
          </div>
        </div>

        {/* Liste */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading ? (
            <span className="text-[#888]">Chargement...</span>
          ) : (
            <table className="w-full text-[14px]">
              <thead>
                <tr className="text-[#888] border-b border-[#2a2a3e]">
                  <th className="text-left py-1 w-[120px]">Date</th>
                  <th className="text-center py-1 w-[80px]">Cloture</th>
                  <th className="text-center py-1 w-[50px]">Mvts</th>
                  <th className="text-left py-1">Mouvements</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => (
                  <tr key={i} className="border-b border-[#1a1a2e] hover:bg-[#1a1a2e]">
                    <td className="py-1 text-[#888] font-mono">{formatTime(e.candle_time)}</td>
                    <td className="py-1 text-center">
                      <span
                        className="font-bold px-2 py-0.5 rounded text-[12px]"
                        style={{
                          color: e.closed_bullish ? "#22c55e" : "#ef4444",
                          backgroundColor: e.closed_bullish ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                        }}
                      >
                        {e.closed_bullish ? "HAUSSE" : "BAISSE"}
                      </span>
                    </td>
                    <td className="py-1 text-center text-[#555]">{e.move_count}</td>
                    <td className="py-1 font-mono text-[12px]">
                      {e.moves.split(",").map((m, j) => (
                        <span
                          key={j}
                          className="mr-1"
                          style={{ color: m.trim()[0] === "U" ? "#22c55e" : m.trim()[0] === "D" ? "#ef4444" : "#f97316" }}
                        >
                          {m.trim()}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
