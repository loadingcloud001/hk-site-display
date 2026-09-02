export type Icon = { code: string; rel: string };

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
  priority: { band: string; headlineZh: string };
  rest: { work: number; rest: number; suspend: boolean; perHours?: number };
};

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
  const warnIcon = snap.hko.icons[0];
  const signal = warnIcon?.code || "";
  const caption = snap.hko.headlineZh || "";
  const p0 = band === "P0";
  const restLine = `每 ${snap.rest.perHours || 2} 小時休息 ${snap.rest.rest} 分鐘`;

  let action = "正常工作";
  let actionSub = restLine;
  // Weather condition PNGs (pic60 etc.) have a white tile — never use as hero.
  let heroIcon: string | null = null;
  if (p0) {
    action = "停工／勿外出";
    actionSub = caption;
    heroIcon = warnIcon?.rel || null;
  } else if (snap.rest.suspend) {
    action = "暫停工作";
    actionSub = snap.hsww.titleZh || "工作暑熱警告";
    heroIcon = snap.hsww.iconRel;
  } else if (heat) {
    action = `休息 ${snap.rest.rest} 分鐘`;
    actionSub = `工作 ${snap.rest.work} 分鐘`;
    heroIcon = snap.hsww.iconRel;
  } else if (caption) {
    action = caption;
    actionSub = restLine;
    heroIcon = warnIcon?.rel || null;
  }

  return {
    stale,
    band,
    heat,
    signal,
    caption,
    p0,
    tone: snap.tone || (p0 ? "p0-tc" : heat || "idle"),
    action,
    actionSub,
    heroIcon,
    warnIcon,
  };
}
