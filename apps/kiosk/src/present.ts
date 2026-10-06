export type Signal = {
  code: string;
  rel: string | null;
  labelZh: string;
  kind: string;
  impact?: "high" | "low";
};

export type RestTile = {
  kind: "suspend" | "rest" | "baseline";
  rest: number;
  work: number | null;
  perHours: number;
  trades: string[];
  tradesZh: string;
};

export type Banner = { time: string; textZh: string; kind: "issue" | "cancel"; code: string };

export type SupervisorLine = { text: string; fromZh: string };

export type WeatherNow = {
  iconRel: string | null;
  tempC: number;
  placeZh: string;
  humidity: number | null;
  uvValue: number | null;
  uvDescZh: string | null;
  updatedAt: string;
};

export type Forecast = { date: string; iconRel: string | null; minC: number | null; maxC: number | null };

export type Display = {
  mode: "normal" | "heat" | "weather";
  main: string | null;
  sub: string[];
  meta: string | null;
  heroRel: string | null;
  action: string;
  actionSub: string;
};

export type Snapshot = {
  generatedAt: string;
  clock?: string;
  staleAfterSec: number;
  stale?: boolean;
  tone?: string;
  signals?: Signal[];
  display: Display;
  restTiles?: RestTile[];
  notes?: string[];
  supervisor?: SupervisorLine[];
  banner?: Banner | null;
  weather?: WeatherNow | null;
  forecast?: Forecast | null;
};

const HK = "Asia/Hong_Kong";
const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

export function isStale(s: Snapshot, now = Date.now()): boolean {
  if (s.stale) return true;
  const t = Date.parse(s.generatedAt);
  if (Number.isNaN(t)) return true;
  return now - t > (s.staleAfterSec || 600) * 1000;
}

export function railSignals(s: Snapshot): (Signal & { rel: string })[] {
  return (s.signals || []).filter((x): x is Signal & { rel: string } => Boolean(x.rel));
}

export function formatUv(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export function clockNow(d = new Date()): string {
  return d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: HK });
}

export function dateZh(d = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: HK,
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).formatToParts(d);
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  const day = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(get("weekday"));
  return `${get("month")}月${get("day")}日 星期${WEEKDAYS[day] ?? ""}`;
}
