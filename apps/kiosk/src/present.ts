export type Signal = {
  code: string;
  rel: string | null;
  labelZh: string;
  kind: string;
  impact?: "high" | "low";
};

// The official English for a tile, on sites that show English: the trades' English names (null unless every
// trade on the tile has one) and its lines (guidance notes Appendix 4, or §5.5.4 for the 2-hour baseline).
export type RestTileEn = { trades: string | null; lines: string[] };

export type RestTile = {
  kind: "suspend" | "rest" | "baseline";
  rest: number;
  work: number | null;
  perHours: number;
  trades: string[];
  tradesZh: string;
  en?: RestTileEn | null;
};

export type Banner = { time: string; textZh: string; kind: "issue" | "cancel"; code: string };

export type SupervisorLine = { text: string; fromZh: string; textEn?: string | null; fromEn?: string | null };

export type WeatherNow = {
  iconRel: string | null;
  tempC: number;
  placeZh: string;
  humidity: number | null;
  uvValue: number | null;
  uvDescZh: string | null;
  updatedAt: string;
};

export type Forecast = {
  date: string;
  iconRel: string | null;
  minC: number | null;
  maxC: number | null;
  psrZh?: string | null;
};

export type Wind = {
  placeZh: string;
  dirZh: string | null;
  speedKmh: number;
  gustKmh: number | null;
  updatedAt: string;
};

// 「極端情況」 in force: the Government's announcement, switched on by the operator. It has no official icon, so the
// screen shows its name and the announced period instead. startZh / endZh are HH:MM, dated when not today.
export type Extreme = {
  nameZh: string;
  startsAt: string;
  endsAt: string;
  startZh: string;
  endZh: string;
};

export type Display = {
  mode: "normal" | "heat" | "weather" | "extreme";
  main: string | null;
  sub: string[];
  meta: string | null;
  heroRel: string | null;
  action: string;
  actionSub: string;
  // Sites that show English: official English lines under the instruction, and HKO's English warning name.
  en?: string[];
  metaEn?: string | null;
};

export type Snapshot = {
  generatedAt: string;
  clock?: string;
  staleAfterSec: number;
  stale?: boolean;
  tone?: string;
  signals?: Signal[];
  display: Display;
  extreme?: Extreme | null;
  restTiles?: RestTile[];
  notes?: string[];
  notesEn?: (string | null)[];
  supervisor?: SupervisorLine[];
  banner?: Banner | null;
  weather?: WeatherNow | null;
  wind?: Wind | null;
  forecast?: Forecast | null;
  site?: { id: string | null; known?: boolean; languages?: string[] };
};

const HK = "Asia/Hong_Kong";
const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

// `ageMs` is how long ago the screen last received a snapshot, on the browser's monotonic clock. A live screen
// passes it, so a wrong device clock (common on cheap TV boxes) can neither hide nor fake stale data.
export function isStale(s: Snapshot, ageMs?: number, now = Date.now()): boolean {
  if (s.stale) return true;
  const limit = (s.staleAfterSec || 600) * 1000;
  if (ageMs !== undefined) return ageMs > limit;
  const t = Date.parse(s.generatedAt);
  if (Number.isNaN(t)) return true;
  return now - t > limit;
}

// A live snapshot showing 「極端情況」 is out of date once the announced end has passed by a minute: a connected
// screen has a new snapshot within 30 s of the end. `now` must be the server's time (the kiosk's corrected clock).
const EXTREME_GRACE_MS = 60_000;

export function extremeOverdue(s: Snapshot, now: number): boolean {
  if (!s.extreme) return false;
  const end = Date.parse(s.extreme.endsAt);
  return Number.isFinite(end) && now > end + EXTREME_GRACE_MS;
}

const COMPASS = new Set(["北", "東北", "東", "東南", "南", "西南", "西", "西北"]);

// HKO's compass point as the usual Chinese wind name (東 -> 東風); anything else is shown as HKO wrote it.
export function windNameZh(dir: string | null): string {
  if (!dir) return "風速";
  return COMPASS.has(dir) ? `${dir}風` : dir;
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
