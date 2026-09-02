import { useEffect, useMemo, useState } from "react";

type Icon = { code: string; rel: string };

type Snapshot = {
  generatedAt: string;
  clock?: string;
  staleAfterSec: number;
  stale?: boolean;
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

const params = new URLSearchParams(window.location.search);
const SIM = params.get("sim") === "1";
const KIOSK = params.get("kiosk") === "1";

async function loadSnap(): Promise<Snapshot> {
  const r = await fetch("/api/v1/snapshot");
  if (!r.ok) throw new Error("snapshot");
  return r.json();
}

function isStale(s: Snapshot): boolean {
  if (s.stale) return true;
  const t = Date.parse(s.generatedAt);
  if (Number.isNaN(t)) return true;
  return Date.now() - t > (s.staleAfterSec || 600) * 1000;
}

export function Kiosk() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.toggle("kiosk", KIOSK);
  }, []);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const s = await loadSnap();
        if (alive) {
          setSnap(s);
          setErr(null);
        }
      } catch {
        if (alive) setErr("無法取得資料 — 請以我的天文台為準");
      }
    };
    tick();
    const id = setInterval(tick, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const layout = useMemo(() => {
    const r = window.innerWidth / Math.max(window.innerHeight, 1);
    if (r > 2.5) return "ultrawide";
    if (r < 0.75) return "portrait";
    return "landscape";
  }, [snap]);

  async function sim(name: string) {
    await fetch("/api/v1/sim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fixture: name }),
    });
    setSnap(await loadSnap());
  }

  if (!snap) {
    return (
      <div className="stage">
        <div className="boot">{err || "載入中…"}</div>
      </div>
    );
  }

  const stale = isStale(snap);
  const band = snap.priority.band;
  const heat = snap.hsww.inForce ? snap.hsww.level : "";
  const warnIcon = snap.hko.icons[0];
  const signal = warnIcon?.code || "";
  const caption = snap.hko.headlineZh || "";
  const p0 = band === "P0";

  let action = "正常工作";
  let actionSub = "";
  let heroIcon = snap.hsww.iconRel;
  if (p0) {
    action = "停工／勿外出";
    actionSub = caption;
    heroIcon = warnIcon?.rel || heroIcon;
  } else if (snap.rest.suspend) {
    action = "暫停工作";
    actionSub = snap.hsww.titleZh || "工作暑熱警告";
  } else if (heat) {
    action = `休息 ${snap.rest.rest} 分鐘`;
    actionSub = `工作 ${snap.rest.work} 分鐘`;
  } else if (caption) {
    action = caption;
    actionSub = "現時無工作暑熱警告";
    heroIcon = warnIcon?.rel || snap.hko.wxIconRel;
  } else {
    action = "現時無工作暑熱警告";
    actionSub = `每 ${snap.rest.perHours || 2} 小時休息 ${snap.rest.rest} 分鐘`;
    heroIcon = snap.hko.wxIconRel;
  }

  return (
    <div
      className="stage"
      data-layout={layout}
      data-heat={heat}
      data-band={band}
      data-signal={signal}
    >
      {SIM && (
        <div className="simbar">
          {["none", "amber", "red", "black", "tc8", "black-rain"].map((n) => (
            <button key={n} type="button" onClick={() => sim(n)}>
              {n}
            </button>
          ))}
        </div>
      )}
      {stale && <div className="stale">資料過期 — 請以我的天文台為準</div>}
      <div className="hero">
        {heroIcon && (
          <img className="icon-hero" src={"/" + heroIcon} alt="" />
        )}
        <div>
          <p className="action">{action}</p>
          {actionSub && <p className="action-sub">{actionSub}</p>}
          <p className="trade">紮鐵 · 極重勞動 · 勞工處建議</p>
        </div>
      </div>
      <div className="footer">
        {warnIcon && !p0 && <img src={"/" + warnIcon.rel} alt="" />}
        <span>{p0 ? caption : caption || "留意天氣"}</span>
        <span className="clock">{snap.clock || ""}</span>
      </div>
    </div>
  );
}
