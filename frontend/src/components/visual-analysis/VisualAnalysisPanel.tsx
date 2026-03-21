import { useEffect, useRef, useState, useCallback } from "react";
import type { Candle, Tick, RhythmSignature, TransitionProb, LiveEstimate } from "../../types/candle";

interface VisualAnalysisPanelProps {
  currentCandle: Candle | null;
  lastClosedCandle: Candle | null;
  history: Candle[];
  tick: Tick | null;
  priceBounds: { minPrice: number; maxPrice: number };
  closedSignature: RhythmSignature | null;
  transitionProbs: TransitionProb[];
  onZoomY?: (factor: number) => void;
  liveEstimate?: LiveEstimate[];
  signalLines?: Array<{ price: number; direction: string; time: string }>;
}

interface HLine {
  id: number;
  price: number;
}

/** Ecran 2 : Analyse visuelle
 * Affiche les bougies avec Canvas 2D, echelle graduee, et lignes horizontales deplacables */
export default function VisualAnalysisPanel({
  currentCandle,
  lastClosedCandle,
  history,
  tick,
  priceBounds,
  closedSignature,
  transitionProbs,
  onZoomY,
  liveEstimate,
  signalLines,
}: VisualAnalysisPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [hLines, setHLines] = useState<HLine[]>([]);
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [scaleDragging, setScaleDragging] = useState(false);
  const scaleDragStartY = useRef(0);
  const nextIdRef = useRef(1);
  const sizeRef = useRef({ w: 0, h: 0 });

  // Convertir prix -> coordonnee Y (utilise les bornes partagees)
  const priceToY = useCallback(
    (price: number, h: number) => {
      const { minPrice, maxPrice } = priceBounds;
      const range = maxPrice - minPrice || 1;
      return h - ((price - minPrice) / range) * h;
    },
    [priceBounds]
  );

  // Convertir coordonnee Y -> prix
  const yToPrice = useCallback(
    (y: number, h: number) => {
      const { minPrice, maxPrice } = priceBounds;
      const range = maxPrice - minPrice || 1;
      return minPrice + ((h - y) / h) * range;
    },
    [priceBounds]
  );

  // Dessiner une bougie sur le canvas
  const drawCandle = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      candle: Candle,
      x: number,
      width: number,
      h: number
    ) => {
      const isUp = candle.close >= candle.open;
      const color = isUp ? "#22c55e" : "#ef4444";
      const bodyTop = priceToY(isUp ? candle.close : candle.open, h);
      const bodyBottom = priceToY(isUp ? candle.open : candle.close, h);
      const wickTop = priceToY(candle.high, h);
      const wickBottom = priceToY(candle.low, h);

      // Meche
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x + width / 2, wickTop);
      ctx.lineTo(x + width / 2, wickBottom);
      ctx.stroke();

      // Corps
      ctx.fillStyle = color;
      const bodyHeight = Math.max(bodyBottom - bodyTop, 1);
      ctx.fillRect(x + 2, bodyTop, width - 4, bodyHeight);
    },
    [priceToY]
  );

  // Dessiner l'echelle graduee a droite
  const drawScale = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      const { minPrice, maxPrice } = priceBounds;
      const range = maxPrice - minPrice;
      if (range === 0) return;

      const scaleWidth = 90;
      ctx.fillStyle = "#12121a";
      ctx.fillRect(w - scaleWidth, 0, scaleWidth, h);
      ctx.strokeStyle = "#2a2a3e";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(w - scaleWidth, 0);
      ctx.lineTo(w - scaleWidth, h);
      ctx.stroke();

      // Graduation automatique
      const steps = 8;
      const stepSize = range / steps;
      ctx.fillStyle = "#888";
      ctx.font = "14px monospace";
      ctx.textAlign = "right";

      for (let i = 0; i <= steps; i++) {
        const price = minPrice + stepSize * i;
        const y = priceToY(price, h);
        // Ligne de grille
        ctx.strokeStyle = "#1a1a2e";
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w - scaleWidth, y);
        ctx.stroke();
        // Label prix
        ctx.fillStyle = "#888";
        ctx.fillText(price.toFixed(2), w - 8, y + 4);
      }

      // Marqueurs speciaux pour la bougie en cours
      if (currentCandle) {
        const markers = [
          { price: currentCandle.high, label: "H", color: "#22c55e" },
          { price: currentCandle.low, label: "L", color: "#ef4444" },
          {
            price: Math.max(currentCandle.open, currentCandle.close),
            label: "BC",
            color: "#8888ff",
          },
          {
            price: Math.min(currentCandle.open, currentCandle.close),
            label: "bc",
            color: "#8888ff",
          },
        ];

        for (const m of markers) {
          const y = priceToY(m.price, h);
          ctx.fillStyle = m.color;
          ctx.font = "bold 13px monospace";
          ctx.fillText(`${m.label} ${m.price.toFixed(2)}`, w - 8, y - 6);
          // Tirets sur l'echelle
          ctx.strokeStyle = m.color;
          ctx.setLineDash([3, 3]);
          ctx.beginPath();
          ctx.moveTo(w - scaleWidth, y);
          ctx.lineTo(w - scaleWidth + 10, y);
          ctx.stroke();
          ctx.setLineDash([]);
        }
      }
    },
    [priceBounds, priceToY, currentCandle]
  );

  // Dessiner les lignes horizontales (outils de dessin)
  const drawHLines = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      for (const line of hLines) {
        const y = priceToY(line.price, h);
        ctx.strokeStyle = "#ff8800";
        ctx.lineWidth = 1;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w - 90, y);
        ctx.stroke();
        ctx.setLineDash([]);
        // Label prix
        ctx.fillStyle = "#ff8800";
        ctx.font = "13px monospace";
        ctx.fillText(line.price.toFixed(2), 8, y - 5);
      }
    },
    [hLines, priceToY]
  );

  // Dessiner le prix actuel (tick)
  const drawCurrentPrice = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      if (!tick) return;
      const price = tick.bid;
      const y = priceToY(price, h);

      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w - 90, y);
      ctx.stroke();
      ctx.setLineDash([]);

      // Badge prix actuel
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 14px monospace";
      ctx.textAlign = "left";
      ctx.fillText(`>> ${price.toFixed(2)}`, w - 88, y + 4);
      ctx.textAlign = "right";
    },
    [tick, priceToY]
  );

  // Rendu principal du canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const w = container.clientWidth;
    const h = container.clientHeight;
    const dpr = window.devicePixelRatio || 1;

    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    sizeRef.current = { w, h };

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(dpr, dpr);

    // Fond
    ctx.fillStyle = "#0a0a0f";
    ctx.fillRect(0, 0, w, h);

    if (!currentCandle && !lastClosedCandle) {
      ctx.fillStyle = "#888";
      ctx.font = "18px sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("En attente de donnees...", w / 2, h / 2);
      return;
    }

    const scaleWidth = 90;
    const chartWidth = w - scaleWidth;
    // 2 grosses bougies centrees dans l'espace disponible
    const candleWidth = Math.min(120, chartWidth / 4);
    const gap = candleWidth * 0.4;
    const totalWidth = 2 * candleWidth + gap;
    const startX = (chartWidth - totalWidth) / 2;

    // Bougie cloturee (a gauche)
    if (lastClosedCandle) {
      const x1 = startX;
      drawCandle(ctx, lastClosedCandle, x1, candleWidth, h);
      // Label "Cloturee" + signature
      ctx.textAlign = "center";
      ctx.fillStyle = "#666";
      ctx.font = "16px sans-serif";
      ctx.fillText("Cloturee", x1 + candleWidth / 2, h - 30);

      // Afficher la signature rythmique si disponible
      if (closedSignature) {
        const sigColor = closedSignature.close_row <= 2 ? "#22c55e" : "#ef4444";
        ctx.fillStyle = sigColor;
        ctx.font = "bold 14px monospace";
        ctx.fillText(closedSignature.signature, x1 + candleWidth / 2, h - 10);
      }
      ctx.textAlign = "right";
    }

    // Separateur entre les 2 bougies
    const sepX = startX + candleWidth + gap / 2;
    ctx.strokeStyle = "#2a2a3e";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(sepX, 0);
    ctx.lineTo(sepX, h);
    ctx.stroke();
    ctx.setLineDash([]);

    // Bougie en cours (a droite)
    if (currentCandle) {
      const x2 = startX + candleWidth + gap;
      drawCandle(ctx, currentCandle, x2, candleWidth, h);
      // Label "En cours"
      ctx.textAlign = "center";
      ctx.fillStyle = "#8888ff";
      ctx.font = "16px sans-serif";
      ctx.fillText("En cours", x2 + candleWidth / 2, h - 12);
      ctx.textAlign = "right";
    }

    // Echelle graduee
    drawScale(ctx, w, h);
    // Lignes horizontales utilisateur
    drawHLines(ctx, w, h);
    // Prix actuel
    drawCurrentPrice(ctx, w, h);

    // Lignes de signal (LONG=vert, SHORT=rouge)
    if (signalLines && signalLines.length > 0) {
      for (const sig of signalLines) {
        const y = priceToY(sig.price, h);
        const color = sig.direction === "LONG" ? "#22c55e" : "#ef4444";
        const scaleW = 90;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.setLineDash([8, 4]);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w - scaleW, y);
        ctx.stroke();
        ctx.setLineDash([]);

        // Label sur l'echelle
        ctx.fillStyle = color;
        ctx.font = "bold 12px sans-serif";
        ctx.textAlign = "right";
        ctx.fillText(`${sig.direction} ${sig.time}`, w - scaleW - 5, y - 5);
      }
    }
  }, [currentCandle, lastClosedCandle, history, tick, hLines, liveEstimate, signalLines, drawCandle, drawScale, drawHLines, drawCurrentPrice]);

  // Redimensionnement
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(() => {
      // Force un re-render via un state update factice
      setHLines((prev) => [...prev]);
    });
    observer.observe(container);
    return () => observer.disconnect();
  }, []);

  // Gestion des evenements souris pour les lignes horizontales
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const y = e.clientY - rect.top;
      const price = yToPrice(y, sizeRef.current.h);
      const id = nextIdRef.current++;
      setHLines((prev) => [...prev, { id, price }]);
    },
    [yToPrice]
  );

  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (e.detail === 2) return; // Double-click gere separement
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const w = sizeRef.current.w;
      const h = sizeRef.current.h;
      const scaleWidth = 90;

      // Si le clic est dans la zone de l'echelle de prix (90px a droite) -> drag zoom vertical
      if (x >= w - scaleWidth) {
        setScaleDragging(true);
        scaleDragStartY.current = e.clientY;
        // Empecher la selection de texte pendant le drag
        document.body.style.userSelect = "none";
        document.body.style.cursor = "ns-resize";
        return;
      }

      // Sinon, gerer les lignes horizontales
      let closest: HLine | null = null;
      let closestDist = 10;
      for (const line of hLines) {
        const lineY = priceToY(line.price, h);
        const dist = Math.abs(lineY - y);
        if (dist < closestDist) {
          closest = line;
          closestDist = dist;
        }
      }
      if (closest) {
        setDraggingId(closest.id);
      }
    },
    [hLines, priceToY]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      // Drag sur l'echelle de prix -> zoom vertical
      if (scaleDragging && onZoomY) {
        const deltaY = e.clientY - scaleDragStartY.current;
        // Chaque pixel de mouvement = 0.5% de zoom
        // Vers le haut = decompresser (zoom in), vers le bas = comprimer (zoom out)
        const factor = 1 + deltaY * 0.005;
        onZoomY(factor);
        scaleDragStartY.current = e.clientY;
        return;
      }

      // Drag d'une ligne horizontale
      if (draggingId === null) return;
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const y = e.clientY - rect.top;
      const price = yToPrice(y, sizeRef.current.h);
      setHLines((prev) =>
        prev.map((l) => (l.id === draggingId ? { ...l, price } : l))
      );
    },
    [draggingId, scaleDragging, yToPrice, onZoomY]
  );

  const handleMouseUp = useCallback(() => {
    setDraggingId(null);
    if (scaleDragging) {
      setScaleDragging(false);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    }
  }, [scaleDragging]);

  // Supprimer une ligne avec clic droit
  const handleContextMenu = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      e.preventDefault();
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const y = e.clientY - rect.top;
      const h = sizeRef.current.h;

      // Supprimer la ligne la plus proche (rayon 10px)
      let closestId: number | null = null;
      let closestDist = 10;
      for (const line of hLines) {
        const lineY = priceToY(line.price, h);
        const dist = Math.abs(lineY - y);
        if (dist < closestDist) {
          closestId = line.id;
          closestDist = dist;
        }
      }
      if (closestId !== null) {
        setHLines((prev) => prev.filter((l) => l.id !== closestId));
      }
    },
    [hLines, priceToY]
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-4 bg-[#0e0e18] border-b border-[#2a2a3e] h-[42px] min-h-[42px]">
        <span className="text-[#888]">Analyse visuelle</span>
        <span className="text-[#666] text-[14px]">
          Double-clic = ajouter ligne | Glisser = deplacer | Clic droit = supprimer
        </span>
      </div>
      <div ref={containerRef} className="flex-1 relative">
        <canvas
          ref={canvasRef}
          className="absolute inset-0"
          style={{ cursor: scaleDragging || draggingId !== null ? "ns-resize" : "crosshair" }}
          onDoubleClick={handleDoubleClick}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onContextMenu={handleContextMenu}
        />
      </div>
    </div>
  );
}
