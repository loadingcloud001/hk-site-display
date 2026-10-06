import { useEffect, useRef, useState } from "react";
import { clockNow, dateZh, type Snapshot } from "./present";
import { Screen } from "./Screen";

const params = new URLSearchParams(window.location.search);
const flag = (...keys: string[]) => keys.some((k) => params.get(k) === "1");
const PREVIEW = flag("preview", "sim");
const LIVE = !PREVIEW || flag("live", "kiosk");
const FIXTURE = params.get("fixture");
// ?bar=0 hides the preview buttons, for screenshots and showing a case on a real screen.
const SHOW_BAR = params.get("bar") !== "0";
const POLL_MS = 30_000;

type CaseBtn = { id: string; labelZh: string };

const FALLBACK_CASES: CaseBtn[] = [
  { id: "none", labelZh: "無警告" },
  { id: "amber", labelZh: "黃色暑熱" },
  { id: "red", labelZh: "紅色暑熱" },
  { id: "black", labelZh: "黑色暑熱" },
  { id: "tc8ne", labelZh: "八號東北" },
  { id: "rain-black", labelZh: "黑色暴雨" },
];

async function loadSnap(): Promise<Snapshot> {
  const r = await fetch("/api/v1/snapshot");
  if (!r.ok) throw new Error("snapshot");
  return r.json();
}

function readLayout(): "portrait" | "landscape" {
  return window.innerWidth / Math.max(window.innerHeight, 1) < 0.75 ? "portrait" : "landscape";
}

export function Kiosk() {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cases, setCases] = useState<CaseBtn[]>([]);
  const [clock, setClock] = useState(clockNow);
  const [date, setDate] = useState(dateZh);
  const [holdSim, setHoldSim] = useState(false);
  const [layout, setLayout] = useState(readLayout);
  // Once a preview case is requested, a late live response must never overwrite it.
  const holdSimRef = useRef(Boolean(PREVIEW && !LIVE && FIXTURE));

  useEffect(() => {
    document.documentElement.classList.toggle("live", LIVE);
    document.documentElement.classList.toggle("kiosk", LIVE);
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setClock(clockNow());
      setDate(dateZh());
    }, 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const onResize = () => setLayout(readLayout());
    window.addEventListener("resize", onResize);
    window.addEventListener("orientationchange", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("orientationchange", onResize);
    };
  }, []);

  useEffect(() => {
    if (holdSim || holdSimRef.current) return;
    let alive = true;
    const tick = async () => {
      try {
        const s = await loadSnap();
        if (alive && !holdSimRef.current) {
          setSnap(s);
          setErr(null);
        }
      } catch {
        if (alive && !holdSimRef.current) setErr("無法取得資料 — 請以我的天文台為準");
      }
    };
    tick();
    const id = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [holdSim]);

  useEffect(() => {
    if (!PREVIEW || LIVE) return;
    fetch("/api/v1/sim/cases")
      .then((r) => r.json())
      .then((d) => setCases((d.cases || []).map((c: CaseBtn) => ({ id: c.id, labelZh: c.labelZh }))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!PREVIEW || LIVE || !FIXTURE) return;
    void sim(FIXTURE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sim(name: string) {
    holdSimRef.current = true;
    const r = await fetch("/api/v1/sim", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fixture: name }),
    });
    if (!r.ok) return;
    setHoldSim(true);
    setSnap(await r.json());
    setErr(null);
  }

  if (!snap) {
    return (
      <div className="stage" data-tone="idle" data-layout={layout}>
        <div className="boot">{err || "載入中…"}</div>
      </div>
    );
  }

  const simbar =
    PREVIEW && !LIVE && SHOW_BAR ? (
      <div className="simbar">
        <a className="sim-link" href="/">
          Live
        </a>
        <a className="sim-link" href="/?gallery=1">
          Gallery
        </a>
        {(cases.length ? cases : FALLBACK_CASES).map((n) => (
          <button key={n.id} type="button" onClick={() => sim(n.id)}>
            {n.labelZh}
          </button>
        ))}
      </div>
    ) : null;

  return <Screen snap={snap} clock={clock} date={date} layout={layout} simbar={simbar} />;
}
