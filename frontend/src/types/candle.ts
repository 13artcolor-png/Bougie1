/** Bougie standard (OHLCV) */
export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/** Tick en temps reel */
export interface Tick {
  bid: number;
  ask: number;
  last: number;
  time: number;
}

/** Symbole disponible */
export interface SymbolInfo {
  name: string;
  description: string;
  digits: number;
}

/** Signature rythmique d'une bougie cloturee */
export interface RhythmSignature {
  signature: string;
  category: string;
  timing: string;
  detail: string;
  open_row: number;
  high_col: string;
  low_col: string;
  close_row: number;
  order_type: string;
}

/** Probabilite de transition vers un rythme suivant */
export interface TransitionProb {
  signature: string;
  count: number;
  probability: number;
}

/** Transitions groupees (global, par session, par contexte) */
export interface TransitionData {
  all: TransitionProb[];
  session: TransitionProb[];
  context: TransitionProb[];
  session_name: string;
  prev_sig: string;
}

/** Message WebSocket recu du backend */
export interface WsMessage {
  type: "update" | "error";
  symbol?: string;
  timeframe?: string;
  current_candle?: Candle;
  last_closed_candle?: Candle;
  micro_candles?: Candle[];
  tick?: Tick;
  history?: Candle[];
  message?: string;
  closed_signature?: RhythmSignature;
  transition_probs?: TransitionData;
  prediction_result?: PredictionResult;
  prediction_stats?: PredictionStats;
  live_estimate?: LiveEstimate[];
  micro_prediction?: MicroPrediction;
  close_prediction?: ClosePrediction;
  close_stats?: CloseStats;
  candle_progress?: number;
}

/** Prediction de la couleur finale de la bougie */
export interface ClosePrediction {
  prediction: string | null;
  pct_hausse: number;
  pct_baisse: number;
  confidence: number;
  total_samples: number;
  pattern_length: number;
  pattern_used: string;
  progress: number;
  message?: string;
}

/** Prediction du prochain mouvement de grille */
export interface MicroPrediction {
  prediction: string | null;
  confidence: number;
  ngram: string;
  ngram_size: number;
  total_samples: number;
  current_moves: string[];
  details: Record<string, { probability: number; count: number }>;
  message?: string;
}

/** Stats de Win Rate des predictions de cloture */
export interface CloseStats {
  total: number;
  wins: number;
  losses: number;
  wr: number;
  history: Array<{
    candle_time: number;
    predicted: string;
    actual: string;
    correct: number;
    pct_predicted: number;
    samples: number;
  }>;
}

/** Estimation en temps reel de la signature en cours */
export interface LiveEstimate {
  signature: string;
  probability: number;
  count: number;
  context?: string;
}

/** Resultat de verification d'une prediction */
export interface PredictionResult {
  predicted: string;
  actual: string;
  predicted_direction: string;
  actual_direction: string;
  direction_correct: boolean;
  category_correct: boolean;
  signature_correct: boolean;
  direction_na: boolean;
}

/** Statistiques de reussite des predictions */
export interface PredictionStats {
  total: number;
  direction_pct: number;
  category_pct: number;
  signature_pct: number;
  direction_total?: number;
  history: PredictionHistory[];
}

export interface PredictionHistory {
  candle_time: number;
  predicted: string;
  actual: string;
  direction_correct: boolean;
  category_correct: boolean;
  signature_correct: boolean;
  direction_na: boolean;
  session: string;
}
