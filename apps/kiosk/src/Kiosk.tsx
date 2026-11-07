import { useEffect, useRef, useState } from "react";
import { Guard } from "./guard";
import { useAutoUpdate, useWakeLock } from "./keepalive";
import { useFix, type Fix } from "./locate";
import { clockNow, dateZh, isStale, type Snapshot } from "./present";
import { Screen } from "./Screen";

const params = new URLSearchParams(window.location.search);
const flag = (...keys: string[]) => keys.some((k) => params.get(k) === "1");
const PREVIEW = flag("preview", "sim");
const LIVE = !PREVIEW || flag("live", "kiosk");
const FIXTURE = params.get("fixture");
// ?bar=0 hides the preview buttons, for screenshots and showing a case on a real screen.
const SHOW_BAR = params.get("bar") !== "0";
// ?loc=0 never asks for this screen's location; the weather then shows the site's station or 香港天文台.
const LOCATE = LIVE && params.get("loc") !== "0";
// ?site=<siteId> picks this screen's site file on the server: its trades and fallback stations.
const SITE = params.get("site");
const POLL_MS = 30_000;
// The device clock is corrected only when it is this far from the server's, so a right clock never jitters.
const CLOCK_SLACK_MS = 2_000;

type CaseBtn = { id: string; labelZh: string };

const FALLBACK_CASES: CaseBtn[] = [
  { id: "none", labelZh: "無警告" },
  { id: "amber", labelZh: "黃色暑熱" },
  { id: "red", labelZh: "紅色暑熱" },
  { id: "black", labelZh: "黑色暑熱" },
  { id: "tc8ne", labelZh: "八號東北" },
  { id: "rain-black", labelZh: "黑色暴雨" },
];

function snapshotQuery(site: string | null, fix: Fix | null): string {
  const q = new URLSearchParams();
  if (site) q.set("site", site);
  if (fix) {
    q.set("lat", String(fix.lat));
    q.set("lon", String(fix.lon));
    q.set("acc", String(fix.acc));
  }
  const text = q.toString();
  return text ? `?${text}` : "";
}

async function loadSnap(query: string): Promise<Snapshot> {
  const r = await fetch(`/api/v1/snapshot${query}`);
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
  const [now, setNow] = useState(Date.now);
  const [holdSim, setHoldSim] = useState(false);
  const [layout, setLayout] = useState(readLayout);
  const query = snapshotQuery(SITE, useFix(LOCATE));
  // Once a preview case is requested, a late live response must never overwrite it.
  const holdSimRef = useRef(Boolean(PREVIEW && !LIVE && FIXTURE));
  // When the last live snapshot arrived (monotonic clock), and how far the device clock is from the server's.
  // Cheap TV boxes often boot with a wrong clock and never fix it; the screen shows the server's time instead.
  const receivedRef = useRef<number | null>(null);
  const offsetRef = useRef(0);
  useWakeLock(LIVE);
  useAutoUpdate(LIVE);

  useEffect(() => {
    document.documentElement.classList.toggle("live", LIVE);
    document.documentElement.classList.toggle("kiosk", LIVE);
  }, []);

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
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
        const s = await loadSnap(query);
        if (alive && !holdSimRef.current) {
          receivedRef.current = performance.now();
          const offset = Date.parse(s.generatedAt) - Date.now();
          if (Number.isFinite(offset) && Math.abs(offset - offsetRef.current) > CLOCK_SLACK_MS) {
            offsetRef.current = offset;
          }
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
  }, [holdSim, query]);

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
      body: JSON.stringify(SITE ? { fixture: name, site: SITE } : { fixture: name }),
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

  const shown = new Date(now + offsetRef.current);
  const received = receivedRef.current;
  // A live screen goes stale when no snapshot has arrived for a while; a preview case only when it says so.
  const stale = !holdSim && received !== null ? isStale(snap, performance.now() - received) : isStale(snap, 0);

  return (
    <Guard resetKey={snap.generatedAt} layout={layout}>
      <Screen
        snap={snap}
        clock={clockNow(shown)}
        date={dateZh(shown)}
        layout={layout}
        simbar={simbar}
        stale={stale}
      />
    </Guard>
  );
}
