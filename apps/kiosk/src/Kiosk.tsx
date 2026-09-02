import { useEffect, useMemo, useState } from "react";
import { present, type Snapshot } from "./present";

const params = new URLSearchParams(window.location.search);
const SIM = params.get("sim") === "1";
const KIOSK = params.get("kiosk") === "1";

function clockNow(): string {
  return new Date().toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Hong_Kong",
  });
}

async function loadSnap(): Promise<Snapshot> {
  const r = await fetch("/api/v1/snapshot");
  if (!r.ok) throw new Error("snapshot");
  return r.json();
}

type CaseBtn = { id: string; labelZh: string };

function Sign({ rel, label, hero }: { rel: string; label: string; hero?: boolean }) {
  return (
    <span className={hero ? "sign sign-hero" : "sign"}>
      <img src={"/" + rel} alt={label} />
    </span>
  );
}

export function Kiosk({ snapshot }: { snapshot?: Snapshot }) {
  const [snap, setSnap] = useState<Snapshot | null>(snapshot ?? null);
  const [err, setErr] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseBtn[]>([]);
  const [clock, setClock] = useState(clockNow);

  useEffect(() => {
    document.documentElement.classList.toggle("kiosk", KIOSK);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setClock(clockNow()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (snapshot) {
      setSnap(snapshot);
      return;
    }
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
  }, [snapshot]);

  useEffect(() => {
    if (!SIM || KIOSK) return;
    fetch("/api/v1/sim/cases")
      .then((r) => r.json())
      .then((d) => {
        setCases((d.cases || []).map((c: CaseBtn) => ({ id: c.id, labelZh: c.labelZh })));
      })
      .catch(() => undefined);
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
      <div className="stage" data-tone="idle" data-layout={layout}>
        <div className="boot">{err || "載入中…"}</div>
      </div>
    );
  }

  const view = present(snap);
  const trade = [snap.site.tradeZh, snap.site.workloadZh, "勞工處建議"].filter(Boolean).join(" · ");

  return (
    <div
      className="stage"
      data-layout={layout}
      data-heat={view.heat}
      data-band={view.band}
      data-signal={view.signal}
      data-tone={view.tone}
    >
      {SIM && !KIOSK && (
        <div className="simbar">
          <a className="sim-link" href="/?gallery=1">
            全部預覽
          </a>
          {(cases.length
            ? cases
            : [
                { id: "none", labelZh: "無警告" },
                { id: "amber", labelZh: "黃色暑熱" },
                { id: "red", labelZh: "紅色暑熱" },
                { id: "black", labelZh: "黑色暑熱" },
                { id: "tc8ne", labelZh: "八號東北" },
                { id: "rain-black", labelZh: "黑色暴雨" },
              ]
          ).map((n) => (
            <button key={n.id} type="button" onClick={() => sim(n.id)}>
              {n.labelZh}
            </button>
          ))}
        </div>
      )}
      {view.stale && <div className="stale">資料過期 — 請以我的天文台為準</div>}
      <div className="hero">
        {view.heroIcon && <Sign rel={view.heroIcon} label="" hero />}
        <div>
          <p className="action">{view.action}</p>
          {view.actionSub && <p className="action-sub">{view.actionSub}</p>}
          <p className="trade">{trade}</p>
        </div>
      </div>
      <div className="footer">
        <div className="rail">
          {view.rail.map((s) => s.rel && <Sign key={s.code} rel={s.rel} label={s.labelZh} />)}
        </div>
        <span className="clock">{clock}</span>
      </div>
    </div>
  );
}
