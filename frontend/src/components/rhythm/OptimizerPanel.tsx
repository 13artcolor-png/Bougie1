import { useState } from "react";

interface OptimizerPanelProps {
  visible: boolean;
  onClose: () => void;
  symbol: string;
}

interface OptResult {
  success: boolean;
  error?: string;
  formule?: string;
  precision?: number;
  hc_precision?: number;
  hc_pct?: number;
  pct_avancement?: number;
  nb_bougies?: number;
  indicateurs?: string[];
  poids?: Record<string, number>;
  validation?: {
    train_precision: number;
    test_precision: number;
    train_hc: number;
    test_hc: number;
    ecart: number;
    status: string;
  };
  applied?: boolean;
  duree?: number;
}

export default function OptimizerPanel({ visible, onClose, symbol }: OptimizerPanelProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<OptResult | null>(null);

  const handleOptimize = () => {
    setLoading(true);
    setResult(null);
    fetch(`/api/optimize/${symbol}/M15`, { method: "POST" })
      .then(r => r.json())
      .then(data => {
        setResult(data);
        setLoading(false);
      })
      .catch(() => {
        setResult({ success: false, error: "Erreur de connexion" });
        setLoading(false);
      });
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[800px] max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[20px] text-white font-bold">
            Optimiseur de formule - {symbol}
          </span>
          <div className="flex gap-2">
            <button
              onClick={handleOptimize}
              disabled={loading}
              className={`px-4 py-2 rounded text-[16px] font-bold cursor-pointer ${
                loading
                  ? "bg-[#555] text-[#888]"
                  : "bg-[#8888ff] text-white hover:bg-[#6666dd]"
              }`}
            >
              {loading ? "Optimisation en cours..." : "Lancer l'optimisation"}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-2 bg-[#555] text-white rounded text-[16px] cursor-pointer hover:bg-[#666]"
            >
              Fermer
            </button>
          </div>
        </div>

        {/* Contenu */}
        <div className="flex-1 overflow-y-auto px-4 py-3">
          {loading && (
            <div className="text-center py-10">
              <div className="text-[24px] text-[#8888ff] mb-4">Optimisation en cours...</div>
              <div className="text-[#888] text-[16px]">
                Analyse des indicateurs, brute force des poids, validation train/test.
                Ca peut prendre 30s a 2min selon le nombre de bougies.
              </div>
            </div>
          )}

          {result && !result.success && (
            <div className="bg-red-900/30 border border-red-800 rounded p-4 text-red-300 text-[18px]">
              Erreur : {result.error}
            </div>
          )}

          {result && result.success && (
            <div className="flex flex-col gap-4">
              {/* Resume */}
              <div className="flex items-center gap-4 bg-[#1a1a2e] rounded p-4">
                <div className="text-center">
                  <div className="text-[#888] text-[14px]">Precision globale</div>
                  <div className="text-[32px] font-bold text-[#8888ff]">{result.precision}%</div>
                </div>
                <div className="w-[1px] h-[50px] bg-[#2a2a3e]" />
                <div className="text-center">
                  <div className="text-[#888] text-[14px]">Haute confiance</div>
                  <div className="text-[32px] font-bold text-[#22c55e]">{result.hc_precision}%</div>
                  <div className="text-[#555] text-[12px]">sur {result.hc_pct}% des cas</div>
                </div>
                <div className="w-[1px] h-[50px] bg-[#2a2a3e]" />
                <div className="text-center">
                  <div className="text-[#888] text-[14px]">Bougies</div>
                  <div className="text-[24px] font-bold text-white">{result.nb_bougies}</div>
                </div>
                <div className="w-[1px] h-[50px] bg-[#2a2a3e]" />
                <div className="text-center">
                  <div className="text-[#888] text-[14px]">Duree</div>
                  <div className="text-[24px] font-bold text-white">{result.duree}s</div>
                </div>
                <div className="w-[1px] h-[50px] bg-[#2a2a3e]" />
                <div className="text-center">
                  <div className="text-[#888] text-[14px]">Appliquee</div>
                  <div className={`text-[24px] font-bold ${result.applied ? "text-[#22c55e]" : "text-[#ef4444]"}`}>
                    {result.applied ? "OUI" : "NON"}
                  </div>
                </div>
              </div>

              {/* Validation */}
              {result.validation && (
                <div className="bg-[#1a1a2e] rounded p-4">
                  <div className="text-[18px] text-white font-bold mb-2">Validation train/test</div>
                  <div className="flex gap-4">
                    <div>
                      <span className="text-[#888]">Train : </span>
                      <span className="text-white font-bold">{result.validation.train_precision}%</span>
                      <span className="text-[#555] ml-2">HC: {result.validation.train_hc}%</span>
                    </div>
                    <div>
                      <span className="text-[#888]">Test : </span>
                      <span className="text-white font-bold">{result.validation.test_precision}%</span>
                      <span className="text-[#555] ml-2">HC: {result.validation.test_hc}%</span>
                    </div>
                    <div>
                      <span className="text-[#888]">Ecart : </span>
                      <span className={`font-bold ${result.validation.ecart < 5 ? "text-[#22c55e]" : result.validation.ecart < 10 ? "text-[#f97316]" : "text-[#ef4444]"}`}>
                        {result.validation.ecart}%
                      </span>
                    </div>
                    <span className={`px-2 py-0.5 rounded font-bold ${
                      result.validation.status === "SOLIDE" ? "bg-green-900/50 text-green-400" :
                      result.validation.status === "CORRECT" ? "bg-yellow-900/50 text-yellow-400" :
                      "bg-red-900/50 text-red-400"
                    }`}>
                      {result.validation.status}
                    </span>
                  </div>
                </div>
              )}

              {/* Poids */}
              {result.poids && (
                <div className="bg-[#1a1a2e] rounded p-4">
                  <div className="text-[18px] text-white font-bold mb-2">Poids optimises</div>
                  <div className="flex gap-3 flex-wrap">
                    {Object.entries(result.poids).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
                      <span key={k} className="bg-[#2a2a4e] px-3 py-1 rounded text-[16px]">
                        <span className="text-[#8888ff] font-bold">{k}</span>
                        <span className="text-white ml-2">{v}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Formule generee */}
              {result.formule && (
                <div className="bg-[#1a1a2e] rounded p-4">
                  <div className="text-[18px] text-white font-bold mb-2">Formule generee</div>
                  <pre className="text-[12px] text-[#ccc] bg-[#0a0a0f] p-3 rounded overflow-x-auto max-h-[300px] overflow-y-auto">
                    {result.formule}
                  </pre>
                </div>
              )}
            </div>
          )}

          {!loading && !result && (
            <div className="text-center py-10 text-[#888] text-[18px]">
              <p>L'optimiseur analyse les donnees historiques en base pour trouver</p>
              <p>la meilleure combinaison d'indicateurs et de poids.</p>
              <p className="mt-4 text-[#555]">
                Il teste 7 indicateurs, brute force toutes les combinaisons de poids,
                valide sur un split train/test, et applique la formule si elle est meilleure.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
