import { useEffect, useMemo, useState } from "react";

type Icon = { code: string; rel: string };

type Snapshot = {
  generatedAt: string;
  staleAfterSec: number;
  stale?: boolean;
  site: { id: string; nameZh: string };
  hsww: {
    level: string;
    inForce: boolean;
    noticeZh: string;
    noticeLeadZh: string;
    titleZh: string;
    iconRel: string | null;
    ldLogoRel: string;
  };
  hko: {
    icons: Icon[];
    warningInfo: { code: string; contents: string[] }[];
    wxIconRel: string | null;
  };
  priority: { band: string; headlineZh: string };
  rest: { work: number; rest: number; suspend: boolean; perHours?: number };
};

const params = new URLSearchParams(window.location.search);
const SIM = params.get("sim") === "1";
const THEME = params.get("theme") || "canteen";

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
    let alive = true;
    const tick = async () => {
      try {
        const s = await loadSnap();
        if (alive) {
          setSnap(s);
          setErr(null);
        }
      } catch (e) {
        if (alive) setErr("無法取得資料");
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
        <div className="title" style={{ padding: "8vh" }}>
          {err || "載入中…"}
        </div>
      </div>
    );
  }

  const stale = isStale(snap);
  const p0 = snap.priority.band === "P0";
  const p1 = snap.priority.band === "P1";
  const heat = snap.hsww.inForce;
  const firstWarn = snap.hko.warningInfo[0]?.contents?.[0] || snap.priority.headlineZh;
  const warnIcon = snap.hko.icons[0];

  return (
    <div className="stage" data-layout={layout} data-theme={THEME}>
      {stale && <div className="stale">資料過期 — 請以我的天文台為準</div>}
      {p0 && (
        <div className="overlay">
          {warnIcon && <img className="icon-lg" src={"/" + warnIcon.rel} alt={warnIcon.code} />}
          <div className="stop">停工／勿外出</div>
          <p className="notice">{firstWarn}</p>
        </div>
      )}
      {p1 && !p0 && (
        <div className="overlay p1">
          {warnIcon && <img className="icon-lg" src={"/" + warnIcon.rel} alt={warnIcon.code} />}
          <div className="stop">限制戶外工作</div>
          <p className="notice">{firstWarn}</p>
        </div>
      )}
      <div className="main">
        <div className="left">
          <img className="ld" src={"/" + snap.hsww.ldLogoRel} alt="勞工處" />
          {heat && snap.hsww.iconRel && (
            <img className="icon-lg" src={"/" + snap.hsww.iconRel} alt={snap.hsww.titleZh} />
          )}
          <h1 className="title">
            {heat ? snap.hsww.titleZh : "現時無工作暑熱警告"}
          </h1>
          {heat && <p className="notice">{snap.hsww.noticeZh}</p>}
        </div>
        <div className="right">
          {snap.rest.suspend ? (
            <>
              <div className="rest-num">暫停工作</div>
              <div className="rest-label">重／極重勞動（勞工處建議）</div>
            </>
          ) : heat ? (
            <>
              <div className="rest-num">
                {snap.rest.work}/{snap.rest.rest}
              </div>
              <div className="rest-label">分鐘工作 / 分鐘休息 · 紮鐵（極重）</div>
            </>
          ) : (
            <>
              <div className="rest-num">{snap.rest.rest} 分</div>
              <div className="rest-label">
                每 {snap.rest.perHours || 2} 小時休息（無暑熱警告）
              </div>
            </>
          )}
        </div>
      </div>
      <div className="footer">
        {warnIcon && <img src={"/" + warnIcon.rel} alt="" />}
        {snap.hko.wxIconRel && <img src={"/" + snap.hko.wxIconRel} alt="" />}
        <span>{firstWarn}</span>
        <span style={{ marginLeft: "auto", opacity: 0.6 }}>{snap.generatedAt}</span>
      </div>
      {SIM && (
        <div className="simbar">
          {["none", "amber", "red", "black", "tc8", "black-rain"].map((n) => (
            <button key={n} type="button" onClick={() => sim(n)}>
              {n}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
