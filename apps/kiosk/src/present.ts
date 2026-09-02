export type Icon = { code: string; rel: string };

export type Signal = {
  code: string;
  rel: string | null;
  labelZh: string;
  kind: string;
  impact?: "high" | "low";
};

export type Snapshot = {
  generatedAt: string;
  clock?: string;
  staleAfterSec: number;
  stale?: boolean;
  tone?: string;
  site: { id: string; nameZh: string };
  hsww: {
    level: string;
    inForce: boolean;
    noticeZh: string;
    titleZh: string;
    iconRel: string | null;
    ldLogoRel: string;
  };
  hko: {
    icons: Icon[];
    headlineZh?: string;
    wxIconRel: string | null;
  };
  signals?: Signal[];
  priority: { band: string; headlineZh: string };
  rest: { work: number; rest: number; suspend: boolean; perHours?: number };
};

const P0 = new Set([
  "TC8NE",
  "TC8SE",
  "TC8NW",
  "TC8SW",
  "TC8",
  "TC9",
  "TC10",
  "WRAINB",
  "WL",
]);

function isHigh(s: Signal): boolean {
  if (s.impact) return s.impact === "high";
  return s.kind === "hsww" || P0.has(s.code);
}

export function isStale(s: Snapshot): boolean {
  if (s.stale) return true;
  const t = Date.parse(s.generatedAt);
  if (Number.isNaN(t)) return true;
  return Date.now() - t > (s.staleAfterSec || 600) * 1000;
}

export function present(snap: Snapshot) {
  const stale = isStale(snap);
  const band = snap.priority.band;
  const heat = snap.hsww.inForce ? snap.hsww.level : "";
  const caption = snap.hko.headlineZh || "";
  const p0 = band === "P0";
  const restLine = `每 ${snap.rest.perHours || 2} 小時休息 ${snap.rest.rest} 分鐘`;
  const signals = snap.signals || [];
  const rail = signals.filter((s) => s.rel);
  const high = rail.filter(isHigh);
  const hero = high[0] || null;

  let action = "正常工作";
  let actionSub = restLine;
  let heroIcon: string | null = null;

  if (p0) {
    heroIcon = hero?.rel || null;
    action = "停工／勿外出";
    actionSub = caption || hero?.labelZh || "";
  } else if (snap.rest.suspend) {
    heroIcon = rail.find((s) => s.kind === "hsww")?.rel || snap.hsww.iconRel;
    action = "暫停工作";
    actionSub = snap.hsww.titleZh || "工作暑熱警告";
  } else if (heat) {
    heroIcon = rail.find((s) => s.kind === "hsww")?.rel || snap.hsww.iconRel;
    action = `休息 ${snap.rest.rest} 分鐘`;
    actionSub = `工作 ${snap.rest.work} 分鐘`;
  }
  // Low-impact weather (T1, yellow rain, 酷熱, 雷暴…) stays in the rail only.

  const also = rail.map((s) => s.labelZh).filter(Boolean).join(" · ");

  return {
    stale,
    band,
    heat,
    signal: high[0]?.code || rail[0]?.code || "",
    caption,
    p0,
    tone: snap.tone || (p0 ? "p0-tc" : heat || "idle"),
    action,
    actionSub,
    heroIcon,
    warnIcon: snap.hko.icons[0],
    rail,
    also,
  };
}
