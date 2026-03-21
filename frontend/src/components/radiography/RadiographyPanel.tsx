import { useEffect, useRef, useState } from "react";
import type { Candle } from "../../types/candle";

// Sous-timeframes disponibles selon le TF principal
const MICRO_TF_OPTIONS: Record<string, { value: string; label: string }[]> = {
  M1:  [{ value: "S15", label: "15s (4)" }],
  M5:  [{ value: "M1", label: "M1 (5)" }, { value: "S30", label: "30s (10)" }, { value: "S15", label: "15s (20)" }],
  M15: [{ value: "M1", label: "M1 (15)" }, { value: "S30", label: "30s (30)" }, { value: "S15", label: "15s (60)" }],
  M30: [{ value: "M1", label: "M1 (30)" }, { value: "S30", label: "30s (60)" }, { value: "S15", label: "15s (120)" }],
  H1:  [{ value: "M5", label: "M5 (12)" }, { value: "M1", label: "M1 (60)" }, { value: "S30", label: "30s (120)" }],
  H4:  [{ value: "M15", label: "M15 (16)" }, { value: "M5", label: "M5 (48)" }, { value: "M1", label: "M1 (240)" }],
  D1:  [{ value: "H1", label: "H1 (24)" }, { value: "M15", label: "M15 (96)" }, { value: "M5", label: "M5 (288)" }],
};

interface RadiographyPanelProps {
  currentCandle: Candle | null;
  lastClosedCandle: Candle | null;
  microCandles: Candle[];
  timeframe: string;
  microTf: string;
  onMicroTfChange: (tf: string) => void;
  priceBounds: { minPrice: number; maxPrice: number };
  quarterPredictions?: Array<{ quarter: number; prediction: string; pct: number; nextQ?: string; nextQpct?: number } | null>;
  signalLines?: Array<{ price: number; direction: string; time: string }>;
}

/** Ecran 1 : Radiographie de bougie (Canvas)
 * Courbe alignee sur la meme echelle de prix que le panneau droit */
export default function RadiographyPanel({
  currentCandle,
  lastClosedCandle,
  microCandles,
  timeframe,
  microTf,
  onMicroTfChange,
  priceBounds,
  quarterPredictions,
  signalLines,
}: RadiographyPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  // State factice pour forcer le re-render au resize (meme pattern que VisualAnalysisPanel)
  const [, setForceRender] = useState(0);

  // Duree totale du timeframe en secondes
  const TF_SECONDS: Record<string, number> = {
    M1: 60, M5: 300, M15: 900, M30: 1800, H1: 3600, H4: 14400, D1: 86400,
  };

  // Fonction de dessin
  function draw() {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const w = container.clientWidth;
    const h = container.clientHeight;
    if (w === 0 || h === 0) return;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    // Fond
    ctx.fillStyle = "#0a0a0f";
    ctx.fillRect(0, 0, w, h);

    const { minPrice, maxPrice } = priceBounds;
    if (minPrice === 0 && maxPrice === 0) {
      ctx.fillStyle = "#888";
      ctx.font = "18px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("En attente de donnees...", w / 2, h / 2);
      return;
    }

    // Convertir prix -> Y
    const priceRange = maxPrice - minPrice || 1;
    function priceToY(price: number) {
      return h - ((price - minPrice) / priceRange) * h;
    }

    // Marges et zone de dessin
    const marginX = 40;
    const drawWidth = w - marginX * 2;
    const totalSeconds = TF_SECONDS[timeframe] || 900;

    // Convertir temps -> X (position basee sur le temps ecoule dans la bougie)
    const candleStart = currentCandle ? currentCandle.time : 0;
    function timeToX(t: number) {
      const elapsed = t - candleStart;
      return marginX + (elapsed / totalSeconds) * drawWidth;
    }

    // --- Quadrillage fin ---
    ctx.strokeStyle = "#1a1a2e";
    ctx.lineWidth = 0.5;

    // Grille horizontale (prix) - 12 lignes
    const hSteps = 12;
    const hStepSize = priceRange / hSteps;
    for (let i = 0; i <= hSteps; i++) {
      const y = priceToY(minPrice + hStepSize * i);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }

    // Grille verticale (temps) - 1 ligne par minute
    const vStepSeconds = totalSeconds <= 300 ? 30 : 60;
    const vSteps = Math.floor(totalSeconds / vStepSeconds);
    for (let i = 0; i <= vSteps; i++) {
      const x = marginX + (i * vStepSeconds / totalSeconds) * drawWidth;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();

      // Labels temps (chaque 1 ou 5 minutes)
      if (i > 0 && i < vSteps) {
        const minutes = (i * vStepSeconds) / 60;
        ctx.fillStyle = "#444";
        ctx.font = "11px monospace";
        ctx.textAlign = "center";
        ctx.fillText(`${minutes.toFixed(0)}m`, x, h - 4);
      }
    }

    // Ligne horizontale du prix d'ouverture
    if (currentCandle) {
      const openY = priceToY(currentCandle.open);
      ctx.strokeStyle = "#555";
      ctx.lineWidth = 1;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(0, openY);
      ctx.lineTo(w, openY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = "#666";
      ctx.font = "13px monospace";
      ctx.textAlign = "left";
      ctx.fillText(`Open ${currentCandle.open.toFixed(2)}`, 4, openY - 5);
    }

    // --- Cadre de la bougie : rectangle high/low x debut/fin ---
    if (currentCandle) {
      const frameLeft = marginX;
      const frameRight = marginX + drawWidth;
      const frameTop = priceToY(currentCandle.high);
      const frameBottom = priceToY(currentCandle.low);
      const frameW = frameRight - frameLeft;
      const frameH = frameBottom - frameTop;

      // Cadre exterieur
      ctx.strokeStyle = "#3a3a5e";
      ctx.lineWidth = 1;
      ctx.strokeRect(frameLeft, frameTop, frameW, frameH);

      // Divisions : 32 colonnes et 32 lignes
      const gridSize = 32;

      // Colonnes verticales
      for (let i = 1; i < gridSize; i++) {
        const isMid = i === 16;
        const isQuarter = i === 8 || i === 24;
        const isEighth = i % 4 === 0;
        if (!isMid && !isQuarter && !isEighth) continue; // Ne dessiner que les reperes principaux
        ctx.strokeStyle = isMid ? "#6a6a9e" : isQuarter ? "#4a4a6e" : "#2a2a3e";
        ctx.lineWidth = isMid ? 2 : isQuarter ? 1 : 0.5;
        ctx.setLineDash(isMid || isQuarter ? [] : [2, 3]);

        const x = frameLeft + (frameW * i) / gridSize;
        ctx.beginPath();
        ctx.moveTo(x, frameTop);
        ctx.lineTo(x, frameBottom);
        ctx.stroke();
      }

      // Lignes horizontales
      for (let i = 1; i < gridSize; i++) {
        const isMid = i === 16;
        const isQuarter = i === 8 || i === 24;
        const isEighth = i % 4 === 0;
        if (!isMid && !isQuarter && !isEighth) continue;
        ctx.strokeStyle = isMid ? "#6a6a9e" : isQuarter ? "#4a4a6e" : "#2a2a3e";
        ctx.lineWidth = isMid ? 2 : isQuarter ? 1 : 0.5;
        ctx.setLineDash(isMid || isQuarter ? [] : [2, 3]);

        const y = frameTop + (frameH * i) / gridSize;
        ctx.beginPath();
        ctx.moveTo(frameLeft, y);
        ctx.lineTo(frameRight, y);
        ctx.stroke();
      }
      ctx.setLineDash([]);

      // Labels tous les 8 cases
      ctx.font = "9px monospace";
      ctx.fillStyle = "#555";

      // Colonnes en bas (1 label tous les 8)
      ctx.textAlign = "center";
      for (let col = 0; col < gridSize; col += 8) {
        const cx = frameLeft + (frameW * (col + 4)) / gridSize;
        ctx.fillText(String(col + 1), cx, frameBottom + 12);
      }

      // Lignes a gauche (1 label tous les 8)
      ctx.textAlign = "right";
      for (let row = 0; row < gridSize; row += 8) {
        const cy = frameTop + (frameH * (row + 4)) / gridSize;
        const label = String(gridSize - row);
        ctx.fillText(label, frameLeft - 3, cy + 3);
      }

      // Predictions par quart - affichees AU-DESSUS du cadre
      if (quarterPredictions && quarterPredictions.length > 0) {
        ctx.textAlign = "center";
        for (const qp of quarterPredictions) {
          if (!qp) continue;
          // Position : milieu de chaque quart
          // Q1 = centre du 1er quart (colonne 4), Q2 = centre du 2e (12), Q3 = 3e (20), Q4 = 4e (28)
          const qCenter = (qp.quarter - 1) * (gridSize / 4) + (gridSize / 8);
          const cx = frameLeft + (frameW * qCenter) / gridSize;

          const isHausse = qp.prediction === "HAUSSE";
          const color = isHausse ? "#22c55e" : "#ef4444";
          const arrow = isHausse ? "\u2191" : "\u2193";

          // Fond - positionne bien au-dessus du cadre
          const yBase = frameTop - 75;

          ctx.fillStyle = isHausse ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)";
          ctx.fillRect(cx - 40, yBase, 80, 28);

          // Texte principal
          ctx.fillStyle = color;
          ctx.font = "bold 20px sans-serif";
          ctx.fillText(`${arrow}${qp.pct}%`, cx, yBase + 20);

          // Label Q
          ctx.fillStyle = "#888";
          ctx.font = "11px monospace";
          ctx.fillText(`Q${qp.quarter}`, cx, yBase - 4);

          // Next Quarter prediction
          if (qp.nextQ && qp.quarter < 4) {
            const nqHausse = qp.nextQ === "HAUSSE";
            const nqColor = nqHausse ? "#22c55e" : "#ef4444";
            const nqArrow = nqHausse ? "\u2191" : "\u2193";

            ctx.fillStyle = "rgba(136,136,255,0.15)";
            ctx.fillRect(cx - 35, yBase + 30, 70, 18);

            ctx.fillStyle = nqColor;
            ctx.font = "bold 11px sans-serif";
            ctx.fillText(`NQ ${nqArrow}${qp.nextQpct}%`, cx, yBase + 44);
          }
        }
      }
    }

    // --- Coloriage des cases par mouvement ---
    if (currentCandle && candleStart > 0 && microCandles.length > 0) {
      const frameLeft = marginX;
      const frameTop2 = priceToY(currentCandle.high);
      const frameBottom2 = priceToY(currentCandle.low);
      const frameW2 = marginX + drawWidth - frameLeft;
      const frameH2 = frameBottom2 - frameTop2;
      const gSize = 32;
      const cellW = frameW2 / gSize;
      const cellH = frameH2 / gSize;

      const priceToGridRow = (price: number) => {
        const h = currentCandle.high;
        const l = currentCandle.low;
        if (h === l) return 8;
        const ratio = (price - l) / (h - l);
        return Math.max(1, Math.min(gSize, Math.ceil(ratio * gSize)));
      };

      const timeToGridCol = (t: number) => {
        const elapsed = t - candleStart;
        const ratio = elapsed / 900;
        return Math.max(0, Math.min(gSize - 1, Math.floor(ratio * gSize)));
      };

      // Construire les mouvements : chaque mouvement = direction + liste de cases
      interface GridMove {
        direction: string; // "U" ou "D"
        cells: Array<{ col: number; row: number }>;
        moveNum: number;
      }

      const movements: GridMove[] = [];
      let prevGridRow = priceToGridRow(currentCandle.open);
      let currentMove: GridMove | null = null;
      let moveCount = 0;
      const visitedCells = new Set<string>();

      for (const mc of microCandles) {
        const col = timeToGridCol(mc.time);
        const closeRow = priceToGridRow(mc.close);
        const highRow = priceToGridRow(mc.high);
        const lowRow = priceToGridRow(mc.low);

        // Determiner les checkpoints dans l'ordre
        let checkpoints: number[];
        if (mc.close >= mc.open) {
          checkpoints = [lowRow, highRow, closeRow];
        } else {
          checkpoints = [highRow, lowRow, closeRow];
        }

        for (const targetRow of checkpoints) {
          if (targetRow === prevGridRow) continue;

          const dir = targetRow > prevGridRow ? "U" : "D";
          const step = targetRow > prevGridRow ? 1 : -1;

          // Parcourir chaque case entre prevGridRow et targetRow
          let r = prevGridRow + step;
          while (true) {
            const cellKey = `${col},${r}`;

            if (!visitedCells.has(cellKey)) {
              visitedCells.add(cellKey);

              // Meme direction que le mouvement en cours ?
              if (currentMove && currentMove.direction === dir) {
                currentMove.cells.push({ col, row: r });
              } else {
                // Nouveau mouvement
                moveCount++;
                currentMove = { direction: dir, cells: [{ col, row: r }], moveNum: moveCount };
                movements.push(currentMove);
              }
            }

            if (r === targetRow) break;
            r += step;
          }
          prevGridRow = targetRow;
        }
      }

      // Dessiner les cases colorees avec le numero du mouvement
      for (const move of movements) {
        const isUp = move.direction === "U";
        const bgColor = isUp ? "rgba(34, 197, 94, 0.18)" : "rgba(239, 68, 68, 0.18)";
        const numColor = isUp ? "rgba(34, 197, 94, 0.7)" : "rgba(239, 68, 68, 0.7)";

        for (const cell of move.cells) {
          const displayRow = gSize - cell.row;

          ctx.fillStyle = bgColor;
          ctx.fillRect(
            frameLeft + cell.col * cellW,
            frameTop2 + displayRow * cellH,
            cellW,
            cellH
          );

          ctx.fillStyle = numColor;
          ctx.font = "6px monospace";
          ctx.textAlign = "center";
          ctx.fillText(
            String(move.moveNum),
            frameLeft + cell.col * cellW + cellW / 2,
            frameTop2 + displayRow * cellH + cellH / 2 + 3
          );
        }
      }
    }

    // --- Courbe des micro-bougies (axe X = temps) ---
    if (currentCandle && candleStart > 0) {
      // Construire tous les points de la courbe :
      // Point 0 = open de la bougie (en dur)
      // Pour chaque micro-bougie : high, low, close (pour capturer les extremes)
      const allPoints: { x: number; y: number; price: number; isMarker: boolean }[] = [];

      // Premier point : open de la bougie, position X = debut
      allPoints.push({
        x: marginX,
        y: priceToY(currentCandle.open),
        price: currentCandle.open,
        isMarker: true,
      });

      // Pour chaque micro-bougie : tracer high, low puis close
      for (let i = 0; i < microCandles.length; i++) {
        const mc = microCandles[i];
        // Position X au milieu de l'intervalle pour high/low
        const xStart = timeToX(mc.time);
        const microDuration = i < microCandles.length - 1
          ? microCandles[i + 1].time - mc.time
          : (microTf === "S15" ? 15 : microTf === "S30" ? 30 : 60);
        const xMid = timeToX(mc.time + microDuration / 2);
        const xEnd = timeToX(mc.time + microDuration);

        // Determiner l'ordre : si le prix est monte d'abord (open < close), high avant low
        if (mc.close >= mc.open) {
          // Haussier : open -> high -> low -> close
          allPoints.push({ x: xMid - 5, y: priceToY(mc.high), price: mc.high, isMarker: false });
          allPoints.push({ x: xMid + 5, y: priceToY(mc.low), price: mc.low, isMarker: false });
        } else {
          // Baissier : open -> low -> high -> close
          allPoints.push({ x: xMid - 5, y: priceToY(mc.low), price: mc.low, isMarker: false });
          allPoints.push({ x: xMid + 5, y: priceToY(mc.high), price: mc.high, isMarker: false });
        }
        // Close = marqueur visible
        allPoints.push({ x: xEnd, y: priceToY(mc.close), price: mc.close, isMarker: true });
      }

      // Tracer la courbe
      ctx.strokeStyle = "#8888ff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < allPoints.length; i++) {
        if (i === 0) ctx.moveTo(allPoints[i].x, allPoints[i].y);
        else ctx.lineTo(allPoints[i].x, allPoints[i].y);
      }
      ctx.stroke();

      // Dessiner les marqueurs (seulement sur les close et l'open)
      for (let i = 0; i < allPoints.length; i++) {
        const p = allPoints[i];
        if (!p.isMarker) continue;
        const isLast = i === allPoints.length - 1;
        const isFirst = i === 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, isLast ? 6 : 4, 0, Math.PI * 2);
        ctx.fillStyle = isLast ? "#ffffff" : isFirst ? "#ffaa00" : "#8888ff";
        ctx.fill();
        ctx.strokeStyle = isLast ? "#8888ff" : "#0a0a0f";
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Prix du dernier point
      const last = allPoints[allPoints.length - 1];
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 14px monospace";
      ctx.textAlign = "left";
      ctx.fillText(last.price.toFixed(2), last.x + 10, last.y + 4);
    }

    // --- Lignes de signal (LONG=vert, SHORT=rouge) ---
    if (signalLines && signalLines.length > 0) {
      for (const sig of signalLines) {
        const y = priceToY(sig.price);
        const color = sig.direction === "LONG" ? "#22c55e" : "#ef4444";

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label
        ctx.fillStyle = color;
        ctx.font = "bold 12px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(`${sig.direction} ${sig.time}`, w - 5, y - 5);
      }
    }
  }

  // Redessiner a chaque changement de donnees
  useEffect(() => {
    draw();
  });

  // Redimensionnement
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      setForceRender((n) => n + 1);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Calculer la variation
  const variation = currentCandle ? currentCandle.close - currentCandle.open : 0;
  const variationPct = currentCandle && currentCandle.open !== 0
    ? (variation / currentCandle.open) * 100 : 0;
  const isUp = variation >= 0;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-4 bg-[#0e0e18] border-b border-[#2a2a3e] h-[42px] min-h-[42px]">
        <span className="text-[#888]">Radiographie {timeframe}</span>
        <div className="flex gap-1">
          {(MICRO_TF_OPTIONS[timeframe] || MICRO_TF_OPTIONS["M15"]).map((opt) => (
            <button
              key={opt.value}
              onClick={() => onMicroTfChange(opt.value)}
              className={`px-2 py-0.5 rounded text-[16px] cursor-pointer transition-colors ${
                microTf === opt.value
                  ? "bg-[#8888ff] text-white"
                  : "bg-[#1a1a2e] text-[#888] hover:bg-[#2a2a4e] hover:text-[#ccc]"
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {currentCandle && (
          <>
            <span className="text-[#888]">
              O: <span className="text-white">{currentCandle.open.toFixed(2)}</span>
            </span>
            <span className="text-[#888]">
              H: <span className="text-white">{currentCandle.high.toFixed(2)}</span>
            </span>
            <span className="text-[#888]">
              L: <span className="text-white">{currentCandle.low.toFixed(2)}</span>
            </span>
            <span className="text-[#888]">
              C: <span className={isUp ? "text-green-400" : "text-red-400"}>
                {currentCandle.close.toFixed(2)}
              </span>
            </span>
            <span className={isUp ? "text-green-400" : "text-red-400"}>
              {isUp ? "+" : ""}{variation.toFixed(2)} ({variationPct.toFixed(3)}%)
            </span>
          </>
        )}
      </div>
      <div ref={containerRef} className="flex-1 relative">
        <canvas ref={canvasRef} className="absolute inset-0" />
      </div>
    </div>
  );
}
