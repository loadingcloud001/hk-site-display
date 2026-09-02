import { useEffect, useMemo, useState } from "react";
import { present, type Snapshot } from "./present";

const params = new URLSearchParams(window.location.search);
const SIM = params.get("sim") === "1";
const KIOSK = params.get("kiosk") === "1";

async function loadSnap(): Promise<Snapshot> {
  const r = await fetch("/api/v1/snapshot");
  if (!r.ok) throw new Error("snapshot");
  return r.json();
}

type CaseBtn = { id: string; labelZh: string };

export function Kiosk({ snapshot }: { snapshot?: Snapshot }) {
  const [snap, setSnap] = useState<Snapshot | null>(snapshot ?? null);
  const [err, setErr] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseBtn[]>([]);

  useEffect(() => {
    document.documentElement.classList.toggle("kiosk", KIOSK);
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
    if (!SIM) return;
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

  return (
    <div
      className="stage"
      data-layout={layout}
      data-heat={view.heat}
      data-band={view.band}
      data-signal={view.signal}
      data-tone={view.tone}
    >
      {SIM && (
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
        {view.heroIcon && <img className="icon-hero" src={"/" + view.heroIcon} alt="" />}
        <div>
          <p className="action">{view.action}</p>
          {view.actionSub && <p className="action-sub">{view.actionSub}</p>}
          <p className="trade">紮鐵 · 極重勞動 · 勞工處建議</p>
        </div>
      </div>
      <div className="footer">
        {view.warnIcon && !view.p0 && <img src={"/" + view.warnIcon.rel} alt="" />}
        <span>{view.p0 ? view.caption : view.caption || "留意天氣"}</span>
        <span className="clock">{snap.clock || ""}</span>
      </div>
    </div>
  );
}
