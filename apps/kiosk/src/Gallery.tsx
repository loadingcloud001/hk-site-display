import { useEffect, useState } from "react";
import type { Snapshot } from "./present";
import { Screen } from "./Screen";
import "./gallery.css";

type Icon = { code: string; labelZh: string; rel: string; kind: string };
type Case = { id: string; labelZh: string; group: string; snapshot: Snapshot };

const GROUPS: { id: string; label: string }[] = [
  { id: "hsww", label: "工作暑熱" },
  { id: "tc", label: "熱帶氣旋" },
  { id: "rain", label: "暴雨" },
  { id: "other", label: "其他天氣" },
  { id: "combo", label: "同時生效" },
];

export function Gallery() {
  const [icons, setIcons] = useState<Icon[]>([]);
  const [cases, setCases] = useState<Case[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    document.documentElement.classList.add("gallery-page");
    document.documentElement.classList.remove("kiosk", "live");
    fetch("/api/v1/sim/cases")
      .then((r) => {
        if (!r.ok) throw new Error("cases");
        return r.json();
      })
      .then((d) => {
        setIcons(d.icons || []);
        setCases(d.cases || []);
      })
      .catch(() => setErr("無法載入預覽 — 請確認 ingest API 已開"));
  }, []);

  function openCase(id: string) {
    window.location.href = "/?preview=1&fixture=" + encodeURIComponent(id);
  }

  if (err || !cases.length) {
    return (
      <div className="gallery">
        <p className="gallery-err">{err || "載入中…"}</p>
      </div>
    );
  }

  return (
    <div className="gallery">
      <header className="gallery-head">
        <h1>全部訊號</h1>
        <a href="/">Live</a>
        <a href="/?preview=1">Preview</a>
      </header>

      <h2>官方圖示</h2>
      {["hsww", "warning", "wx"].map((kind) => (
        <div key={kind} className="icon-wall">
          {icons
            .filter((i) => i.kind === kind)
            .map((i) => (
              <figure key={i.code} className="icon-card">
                <img src={"/" + i.rel} alt={i.labelZh} />
                <figcaption>
                  {i.labelZh}
                  <small>{i.code}</small>
                </figcaption>
              </figure>
            ))}
        </div>
      ))}

      <h2>全部訊號</h2>
      {GROUPS.map((g) => {
        const rows = cases.filter((c) => c.group === g.id);
        if (!rows.length) return null;
        return (
          <section key={g.id}>
            <h3>{g.label}</h3>
            <div className="case-grid">
              {rows.map((c) => (
                <button key={c.id} type="button" className="case-tile" onClick={() => openCase(c.id)}>
                  <Screen snap={c.snapshot} clock={c.snapshot.clock || ""} date="" />
                  <span className="case-label">{c.labelZh}</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
