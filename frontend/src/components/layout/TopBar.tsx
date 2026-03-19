import { useSymbols } from "../../hooks/useSymbols";

interface TopBarProps {
  symbol: string;
  timeframe: string;
  connected: boolean;
  onSymbolChange: (s: string) => void;
  onTimeframeChange: (tf: string) => void;
}

const TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"];

export default function TopBar({
  symbol,
  timeframe,
  connected,
  onSymbolChange,
  onTimeframeChange,
}: TopBarProps) {
  const { symbols } = useSymbols();

  return (
    <div className="flex items-center gap-4 px-4 py-2 bg-[#12121a] border-b border-[#2a2a3e]">
      {/* Titre */}
      <span className="font-bold text-[#8888ff] mr-2">BOUGIE1</span>

      {/* Selecteur de symbole */}
      <select
        value={symbol}
        onChange={(e) => onSymbolChange(e.target.value)}
        className="bg-[#1a1a2e] text-[#e0e0e0] border border-[#3a3a5e] rounded px-3 py-1 text-[18px] cursor-pointer"
      >
        {symbols.length === 0 && <option value={symbol}>{symbol}</option>}
        {symbols.map((s) => (
          <option key={s.name} value={s.name}>
            {s.name}
          </option>
        ))}
      </select>

      {/* Selecteur de timeframe */}
      <div className="flex gap-1">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            onClick={() => onTimeframeChange(tf)}
            className={`px-3 py-1 rounded text-[18px] cursor-pointer transition-colors ${
              timeframe === tf
                ? "bg-[#8888ff] text-white"
                : "bg-[#1a1a2e] text-[#888] hover:bg-[#2a2a4e] hover:text-[#ccc]"
            }`}
          >
            {tf}
          </button>
        ))}
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Statut de connexion */}
      <div className="flex items-center gap-2">
        <div
          className={`w-3 h-3 rounded-full ${
            connected ? "bg-green-500" : "bg-red-500"
          }`}
        />
        <span className="text-[16px] text-[#888]">
          {connected ? "Connecte" : "Deconnecte"}
        </span>
      </div>
    </div>
  );
}
