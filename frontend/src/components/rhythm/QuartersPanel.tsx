import { useState, useEffect } from "react";

interface QuarterEntry {
  candle_time: number;
  q1_pred: string;
  q1_pct: number;
  q2_pred: string;
  q2_pct: number;
  q3_pred: string;
  q3_pct: number;
  q4_pred: string;
  q4_pct: number;
  actual: string;
  wr: number;
}

interface QuartersPanelProps {
  visible: boolean;
  onClose: () => void;
}

function formatTime(timestamp: number): string {
  const d = new Date(timestamp * 1000);
  return d.toLocaleString("fr-FR", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function PredCell({ pred, pct, actual }: { pred: string; pct: number; actual: string }) {
  if (!pred) return <td className="py-2 px-3 text-center text-[#555]">-</td>;

  const correct = pred === actual;
  const isHausse = pred === "HAUSSE";

  return (
    <td className="py-2 px-3 text-center">
      <div
        className="font-bold text-[16px] px-2 py-1 rounded"
        style={{
          color: correct ? "#22c55e" : "#ef4444",
          backgroundColor: correct ? "rgba(34,197,94,0.1)" : "rgba(239,68,68,0.1)",
        }}
      >
        {isHausse ? "\u2191" : "\u2193"} {pct}%
      </div>
    </td>
  );
}

export default function QuartersPanel({ visible, onClose }: QuartersPanelProps) {
  const [entries, setEntries] = useState<QuarterEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (visible) {
      setLoading(true);
      fetch("/api/quarters-detail/XAUUSD/M15")
        .then((r) => r.json())
        .then((data) => {
          setEntries(data.entries || []);
          setLoading(false);
        })
        .catch(() => setLoading(false));
    }
  }, [visible]);

  if (!visible) return null;

  // Calculer le WR total
  const totalBougies = entries.filter(e => e.actual).length;
  const totalWins = entries.filter(e => {
    if (!e.actual) return false;
    let correct = 0;
    if (e.q1_pred === e.actual) correct++;
    if (e.q2_pred === e.actual) correct++;
    if (e.q3_pred === e.actual) correct++;
    if (e.q4_pred === e.actual) correct++;
    return correct >= 3; // WR = au moins 3/4 corrects
  }).length;

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[900px] max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[20px] text-white font-bold">
            Detail des predictions par quart ({entries.length} bougies)
          </span>
          <button
            onClick={onClose}
            className="px-3 py-1 bg-[#555] text-white rounded text-[16px] cursor-pointer hover:bg-[#666]"
          >
            Fermer
          </button>
        </div>

        {/* Tableau */}
        <div className="flex-1 overflow-y-auto px-4 py-2">
          {loading ? (
            <span className="text-[#888] text-[18px]">Chargement...</span>
          ) : entries.length === 0 ? (
            <span className="text-[#888] text-[18px]">Aucune donnee. Attendez que des bougies cloturent.</span>
          ) : (
            <table className="w-full text-[16px] table-fixed">
              <colgroup>
                <col className="w-[100px]" />
                <col />
                <col />
                <col />
                <col />
                <col className="w-[130px]" />
                <col className="w-[80px]" />
              </colgroup>
              <thead>
                {/* Ligne globaux */}
                {(() => {
                  const completed = entries.filter(e => e.actual);
                  const totals = { q1: { ok: 0, n: 0 }, q2: { ok: 0, n: 0 }, q3: { ok: 0, n: 0 }, q4: { ok: 0, n: 0 } };
                  for (const e of completed) {
                    if (e.q1_pred) { totals.q1.n++; if (e.q1_pred === e.actual) totals.q1.ok++; }
                    if (e.q2_pred) { totals.q2.n++; if (e.q2_pred === e.actual) totals.q2.ok++; }
                    if (e.q3_pred) { totals.q3.n++; if (e.q3_pred === e.actual) totals.q3.ok++; }
                    if (e.q4_pred) { totals.q4.n++; if (e.q4_pred === e.actual) totals.q4.ok++; }
                  }
                  const wrGlobal = totals.q4.n > 0 ? Math.round(totals.q4.ok / totals.q4.n * 100) : 0;

                  return (
                    <tr className="bg-[#0e0e18] border-b-2 border-[#4a4a6e]">
                      <th className="py-3 px-3 text-left text-[#888] text-[16px]">
                        WR Global
                      </th>
                      {[totals.q1, totals.q2, totals.q3, totals.q4].map((q, i) => {
                        const wr = q.n > 0 ? Math.round(q.ok / q.n * 100) : 0;
                        return (
                          <th key={i} className="py-3 px-3 text-center">
                            <span className="font-bold text-[20px]"
                              style={{ color: wr >= 60 ? "#22c55e" : wr >= 50 ? "#f97316" : "#ef4444" }}>
                              {wr}%
                            </span>
                            <span className="text-[12px] text-[#555] ml-1">({q.ok}/{q.n})</span>
                          </th>
                        );
                      })}
                      <th className="py-3 px-3 text-center text-[#888] text-[14px]">
                        {completed.length} bougies
                      </th>
                      <th className="py-3 px-3 text-center">
                        <span className="font-bold text-[24px]"
                          style={{ color: wrGlobal >= 60 ? "#22c55e" : wrGlobal >= 50 ? "#f97316" : "#ef4444" }}>
                          {wrGlobal}%
                        </span>
                      </th>
                    </tr>
                  );
                })()}
                <tr className="text-[#888] border-b border-[#2a2a3e]">
                  <th className="text-left py-2 px-3">Date</th>
                  <th className="text-center py-2 px-3">Q1 (25%)</th>
                  <th className="text-center py-2 px-3">Q2 (50%)</th>
                  <th className="text-center py-2 px-3">Q3 (75%)</th>
                  <th className="text-center py-2 px-3">Q4 (100%)</th>
                  <th className="text-center py-2 px-3">Resultat</th>
                  <th className="text-center py-2 px-3">WR</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((e, i) => {
                  // Calculer le WR de cette bougie (combien de quarts corrects)
                  let correct = 0;
                  let total = 0;
                  if (e.q1_pred && e.actual) { total++; if (e.q1_pred === e.actual) correct++; }
                  if (e.q2_pred && e.actual) { total++; if (e.q2_pred === e.actual) correct++; }
                  if (e.q3_pred && e.actual) { total++; if (e.q3_pred === e.actual) correct++; }
                  if (e.q4_pred && e.actual) { total++; if (e.q4_pred === e.actual) correct++; }
                  const wrPct = total > 0 ? Math.round(correct / total * 100) : 0;

                  return (
                    <tr key={i} className="border-b border-[#1a1a2e] hover:bg-[#1a1a2e]">
                      <td className="py-2 px-3 text-[#888] font-mono text-[14px]">
                        {formatTime(e.candle_time)}
                      </td>
                      <PredCell pred={e.q1_pred} pct={e.q1_pct} actual={e.actual} />
                      <PredCell pred={e.q2_pred} pct={e.q2_pct} actual={e.actual} />
                      <PredCell pred={e.q3_pred} pct={e.q3_pct} actual={e.actual} />
                      <PredCell pred={e.q4_pred} pct={e.q4_pct} actual={e.actual} />
                      <td className="py-2 px-3 text-center">
                        {e.actual ? (
                          <span
                            className="font-bold text-[18px] px-3 py-1 rounded"
                            style={{
                              color: e.actual === "HAUSSE" ? "#22c55e" : "#ef4444",
                              backgroundColor: e.actual === "HAUSSE" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                            }}
                          >
                            {e.actual === "HAUSSE" ? "\u2191 HAUSSE" : "\u2193 BAISSE"}
                          </span>
                        ) : (
                          <span className="text-[#555]">En cours</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-center">
                        <span
                          className="font-bold text-[18px]"
                          style={{ color: wrPct >= 75 ? "#22c55e" : wrPct >= 50 ? "#f97316" : "#ef4444" }}
                        >
                          {wrPct}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              {/* Ligne totaux */}
              {(() => {
                const completed = entries.filter(e => e.actual);
                if (completed.length === 0) return null;
                const t = { q1: { ok: 0, n: 0 }, q2: { ok: 0, n: 0 }, q3: { ok: 0, n: 0 }, q4: { ok: 0, n: 0 }, all: { ok: 0, n: 0 } };
                for (const e of completed) {
                  if (e.q1_pred) { t.q1.n++; if (e.q1_pred === e.actual) t.q1.ok++; }
                  if (e.q2_pred) { t.q2.n++; if (e.q2_pred === e.actual) t.q2.ok++; }
                  if (e.q3_pred) { t.q3.n++; if (e.q3_pred === e.actual) t.q3.ok++; }
                  if (e.q4_pred) { t.q4.n++; if (e.q4_pred === e.actual) t.q4.ok++; }
                  let c = 0; let n = 0;
                  if (e.q1_pred) { n++; if (e.q1_pred === e.actual) c++; }
                  if (e.q2_pred) { n++; if (e.q2_pred === e.actual) c++; }
                  if (e.q3_pred) { n++; if (e.q3_pred === e.actual) c++; }
                  if (e.q4_pred) { n++; if (e.q4_pred === e.actual) c++; }
                  t.all.n++; if (n > 0 && c / n >= 0.75) t.all.ok++;
                }
                return (
                  <tfoot>
                    <tr className="border-t-2 border-[#4a4a6e] bg-[#1a1a2e]">
                      <td className="py-3 px-3 font-bold text-[18px] text-white">TOTAL</td>
                      {[t.q1, t.q2, t.q3, t.q4].map((q, i) => {
                        const wr = q.n > 0 ? Math.round(q.ok / q.n * 100) : 0;
                        return (
                          <td key={i} className="py-3 px-3 text-center">
                            <span className="font-bold text-[18px]"
                              style={{ color: wr >= 60 ? "#22c55e" : wr >= 50 ? "#f97316" : "#ef4444" }}>
                              {wr}%
                            </span>
                            <span className="text-[14px] text-[#555] ml-1">({q.ok}/{q.n})</span>
                          </td>
                        );
                      })}
                      <td className="py-3 px-3 text-center text-[#888]">{completed.length} bougies</td>
                      <td className="py-3 px-3 text-center">
                        <span className="font-bold text-[20px]"
                          style={{ color: t.all.n > 0 && t.all.ok / t.all.n >= 0.6 ? "#22c55e" : "#f97316" }}>
                          {t.all.n > 0 ? Math.round(t.all.ok / t.all.n * 100) : 0}%
                        </span>
                      </td>
                    </tr>
                  </tfoot>
                );
              })()}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
