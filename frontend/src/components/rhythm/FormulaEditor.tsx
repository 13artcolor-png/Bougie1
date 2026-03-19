import { useState, useEffect } from "react";

interface FormulaEditorProps {
  visible: boolean;
  onClose: () => void;
}

export default function FormulaEditor({ visible, onClose }: FormulaEditorProps) {
  const [code, setCode] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  // Charger la formule au montage
  useEffect(() => {
    if (visible) {
      fetch("/api/formula")
        .then((r) => r.json())
        .then((data) => setCode(data.code || ""))
        .catch(() => setError("Erreur de chargement"));
    }
  }, [visible]);

  const handleSave = () => {
    fetch("/api/formula", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.success) {
          setSaved(true);
          setError("");
          setTimeout(() => setSaved(false), 2000);
        } else {
          setError("Erreur de sauvegarde");
        }
      })
      .catch(() => setError("Erreur de sauvegarde"));
  };

  const handleResetWR = () => {
    fetch("/api/close-stats/reset", { method: "POST" })
      .then((r) => r.json())
      .then(() => {
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      });
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 bg-black/70 z-[200] flex items-center justify-center">
      <div className="bg-[#12121a] border border-[#4a4a6e] rounded-lg w-[800px] max-h-[80vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2a3e]">
          <span className="text-[18px] text-white font-bold">Formule de prediction</span>
          <div className="flex gap-2">
            <button
              onClick={handleResetWR}
              className="px-3 py-1 bg-[#ef4444] text-white rounded text-[14px] cursor-pointer hover:bg-[#dc2626]"
            >
              Reset WR
            </button>
            <button
              onClick={handleSave}
              className="px-3 py-1 bg-[#22c55e] text-white rounded text-[14px] cursor-pointer hover:bg-[#16a34a]"
            >
              {saved ? "Sauvegarde !" : "Sauvegarder"}
            </button>
            <button
              onClick={onClose}
              className="px-3 py-1 bg-[#555] text-white rounded text-[14px] cursor-pointer hover:bg-[#666]"
            >
              Fermer
            </button>
          </div>
        </div>

        {/* Erreur */}
        {error && (
          <div className="px-4 py-2 bg-red-900/50 text-red-300 text-[14px]">{error}</div>
        )}

        {/* Variables disponibles */}
        <div className="px-4 py-2 bg-[#1a1a2e] text-[12px] text-[#888] border-b border-[#2a2a3e]">
          Variables : <span className="text-[#8888ff]">moves</span> (list mouvements),{" "}
          <span className="text-[#8888ff]">progress</span> (0-1),{" "}
          <span className="text-[#8888ff]">candle_open/high/low/close</span>,{" "}
          <span className="text-[#8888ff]">prev_close</span> |{" "}
          Retourner : <span className="text-[#22c55e]">result = {`{"pct_hausse": X, "pct_baisse": Y}`}</span>
        </div>

        {/* Editeur */}
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          className="flex-1 bg-[#0a0a0f] text-[#e0e0e0] font-mono text-[14px] p-4 resize-none outline-none border-none"
          style={{ minHeight: "400px", tabSize: 4 }}
          spellCheck={false}
        />
      </div>
    </div>
  );
}
