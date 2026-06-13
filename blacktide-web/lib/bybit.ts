// Bybit 線性永續（USDT 本位）符號對照。div：1000PEPE 這類合約價要除回原幣價。
export interface CoinCfg { symbol: string; name: string; bybit: string; div: number; }

export const COINS: CoinCfg[] = [
  { symbol: "BTC", name: "Bitcoin", bybit: "BTCUSDT", div: 1 },
  { symbol: "ETH", name: "Ethereum", bybit: "ETHUSDT", div: 1 },
  { symbol: "SOL", name: "Solana", bybit: "SOLUSDT", div: 1 },
  { symbol: "BNB", name: "BNB", bybit: "BNBUSDT", div: 1 },
  { symbol: "XRP", name: "Ripple", bybit: "XRPUSDT", div: 1 },
  { symbol: "SUI", name: "Sui", bybit: "SUIUSDT", div: 1 },
  { symbol: "DOGE", name: "Dogecoin", bybit: "DOGEUSDT", div: 1 },
  { symbol: "PEPE", name: "Pepe", bybit: "1000PEPEUSDT", div: 1000 },
];

export const BYBIT_REST = "https://api.bybit.com";
export const BYBIT_WS = "wss://stream.bybit.com/v5/public/linear";

export const coinBySymbol = (s: string) => COINS.find((c) => c.symbol === s);
export const coinByBybit = (s: string) => COINS.find((c) => c.bybit === s);
