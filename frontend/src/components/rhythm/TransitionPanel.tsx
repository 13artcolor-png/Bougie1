import type { MicroPrediction, ClosePrediction, CloseStats } from "../../types/candle";
import Tip from "../common/Tip";

interface TransitionPanelProps {
  microPrediction?: MicroPrediction | null;
  closePrediction?: ClosePrediction | null;
  closeStats?: CloseStats | null;
  progress: number;
  onOpenFormula?: () => void;
  onOpenHistory?: () => void;
  onOpenQuarters?: () => void;
  symbol?: string;
}

function moveColor(m: string): string {
  if (m === "U") return "#22c55e";
  if (m === "D") return "#ef4444";
  return "#f97316";
}

export default function TransitionPanel({ microPrediction, closePrediction, closeStats, progress, onOpenFormula, onOpenHistory, onOpenQuarters, symbol }: TransitionPanelProps) {
  const mp = microPrediction;
  const cp = closePrediction;
  const cs = closeStats;
  const pctProgress = Math.round(progress * 100);

  if (!mp?.current_moves && !cp?.prediction) {
    return (
      <div className="bg-[#0e0e18] border-t border-[#2a2a3e] px-4 py-3">
        <div className="flex items-center gap-3">
          <span className="text-[#888] text-[18px]">
            {progress < 0.05
              ? "Bougie en cours... en attente du premier mouvement"
              : "Analyse en cours..."}
          </span>
          <div className="inline-block relative w-[150px] h-[10px] bg-[#1a1a2e] rounded overflow-hidden">
            <div className="absolute inset-y-0 left-0 bg-[#8888ff] rounded transition-all" style={{ width: `${pctProgress}%` }} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[#0e0e18] border-t border-[#2a2a3e] px-4 py-2">
      {/* LIGNE 1 : Prediction + Parcours */}
      <div className="flex items-center gap-4 mb-2">
        {/* Prediction de cloture */}
        {cp?.prediction && (
          <>
            <span className="text-[#888] text-[18px]">
              Cloture
              <Tip text="Prediction de la couleur finale de la bougie M15 a sa cloture. HAUSSE = le close sera au-dessus de l'open (bougie verte). BAISSE = le close sera en-dessous (bougie rouge). Le pourcentage indique la confiance de la prediction basee sur la formule algorithmique appliquee au parcours de la courbe." />
              :
            </span>
            <div className="relative w-[220px] h-[36px] bg-[#1a1a2e] rounded overflow-hidden flex">
              <div className="h-full bg-green-600/60" style={{ width: `${cp.pct_hausse}%` }} />
              <div className="h-full bg-red-600/60" style={{ width: `${cp.pct_baisse}%` }} />
              <span className="absolute inset-0 flex items-center justify-center text-white font-bold text-[18px]">
                {cp.pct_hausse}% / {cp.pct_baisse}%
              </span>
            </div>
            <span
              className="font-bold text-[28px] px-4 py-1 rounded"
              style={{
                color: cp.prediction === "HAUSSE" ? "#22c55e" : "#ef4444",
                backgroundColor: cp.prediction === "HAUSSE" ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
              }}
            >
              {cp.prediction === "HAUSSE" ? "\u2191 HAUSSE" : "\u2193 BAISSE"} {cp.prediction === "HAUSSE" ? cp.pct_hausse : cp.pct_baisse}%
            </span>
          </>
        )}

        {/* Barre de progression */}
        <div className="flex items-center gap-2 ml-auto">
          <Tip text="Progression de la bougie M15 en cours. Les traits verticaux marquent les quarts (25%, 50%, 75%). A chaque quart, la prediction est capturee pour le calcul du WR par quart." />
          <div className="relative w-[120px] h-[10px] bg-[#1a1a2e] rounded overflow-hidden">
            <div className="absolute inset-y-0 left-0 bg-[#8888ff] rounded transition-all" style={{ width: `${pctProgress}%` }} />
            <div className="absolute top-0 left-[25%] w-[1px] h-full bg-[#333]" />
            <div className="absolute top-0 left-[50%] w-[1px] h-full bg-[#333]" />
            <div className="absolute top-0 left-[75%] w-[1px] h-full bg-[#333]" />
          </div>
          <span className="text-[#888] text-[18px] font-bold">{pctProgress}%</span>
        </div>

        {/* Boutons */}
        {onOpenFormula && (
          <button onClick={onOpenFormula}
            className="px-3 py-1 bg-[#2a2a3e] text-[#888] rounded text-[16px] cursor-pointer hover:bg-[#3a3a5e] hover:text-white transition-colors">
            Formule
          </button>
        )}
        {onOpenQuarters && (
          <button onClick={onOpenQuarters}
            className="px-3 py-1 bg-[#2a2a3e] text-[#888] rounded text-[16px] cursor-pointer hover:bg-[#3a3a5e] hover:text-white transition-colors">
            Quarts
          </button>
        )}
        {onOpenHistory && (
          <button onClick={onOpenHistory}
            className="px-3 py-1 bg-[#2a2a3e] text-[#888] rounded text-[16px] cursor-pointer hover:bg-[#3a3a5e] hover:text-white transition-colors">
            Historique
          </button>
        )}
        {symbol && (
          <button
            onClick={() => {
              fetch(`/api/export/${symbol}/M15`)
                .then(r => r.json())
                .then(data => {
                  if (data.content) {
                    const blob = new Blob([data.content], { type: "text/plain" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = data.filename;
                    a.click();
                    URL.revokeObjectURL(url);
                  }
                });
            }}
            className="px-3 py-1 bg-[#2a2a3e] text-[#888] rounded text-[16px] cursor-pointer hover:bg-[#22c55e] hover:text-white transition-colors"
            title="Exporter l'historique au format standard pour l'outil de formule"
          >
            Export
          </button>
        )}
      </div>

      {/* LIGNE 2 : WR + Quarts + Historique visuel + Parcours */}
      <div className="flex items-center gap-4">
        {/* WR global */}
        {cs && cs.total > 0 && (
          <>
            <Tip text="Win Rate : pourcentage de predictions correctes. Une prediction est correcte si la direction predite (HAUSSE ou BAISSE) correspond a la couleur reelle de la bougie a sa cloture. Au-dessus de 60% = bon signal. En-dessous de 50% = la formule se trompe plus qu'elle ne reussit." />
            <span
              className="font-bold text-[28px] px-3 rounded"
              style={{
                color: cs.wr >= 60 ? "#22c55e" : cs.wr >= 50 ? "#f97316" : "#ef4444",
                backgroundColor: cs.wr >= 60 ? "rgba(34,197,94,0.15)" : cs.wr >= 50 ? "rgba(249,115,22,0.15)" : "rgba(239,68,68,0.15)",
              }}
            >
              {cs.wr}%
            </span>
            <span className="text-[#888] text-[18px]">
              {cs.wins}W / {cs.losses}L ({cs.total})
            </span>

            <div className="w-[1px] h-[30px] bg-[#2a2a3e]" />

            {/* WR par quart */}
            {(cs as any).quarters && (
              <div className="flex gap-2 items-center">
                <Tip text="WR par quart de bougie. Q1 = prediction capturee a 25% de la bougie, Q2 = 50%, Q3 = 75%, Q4 = juste avant la cloture. Permet de voir a quel moment la formule devient fiable. Si Q1 est bas et Q4 est haut, la formule est plus precise en fin de bougie." />
                {["1", "2", "3", "4"].map((q) => {
                  const qd = (cs as any).quarters[q];
                  if (!qd || qd.total === 0) return (
                    <span key={q} className="text-[16px] text-[#555] px-2 py-1 bg-[#1a1a2e] rounded">
                      Q{q}: -
                    </span>
                  );
                  return (
                    <span
                      key={q}
                      className="text-[18px] font-bold px-2 py-1 rounded"
                      style={{
                        color: qd.wr >= 60 ? "#22c55e" : qd.wr >= 50 ? "#f97316" : "#ef4444",
                        backgroundColor: qd.wr >= 60 ? "rgba(34,197,94,0.12)" : qd.wr >= 50 ? "rgba(249,115,22,0.12)" : "rgba(239,68,68,0.12)",
                      }}
                      title={`Quart ${q}: ${qd.wins}W / ${qd.total - qd.wins}L`}
                    >
                      Q{q}: {qd.wr}%
                    </span>
                  );
                })}
              </div>
            )}

          </>
        )}
      </div>
    </div>
  );
}
