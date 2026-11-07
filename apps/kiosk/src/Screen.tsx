import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from "react";
import { formatUv, isStale, railSignals, windNameZh, type RestTile, type Snapshot, type Wind } from "./present";

const STALE_TEXT = "資料過期 — 請以我的天文台為準";

function Plate({ rel, className }: { rel: string; className?: string }) {
  return (
    <span className={className ? `plate ${className}` : "plate"}>
      <img src={"/" + rel} alt="" />
    </span>
  );
}

// A hyphenated word ("re-acclimate", "15-minute") never breaks at its hyphen, which would read as two words. The
// text itself is unchanged.
function Words({ text }: { text: string }) {
  return (
    <>
      {text.split(/(\S+-\S+)/).map((part, i) =>
        i % 2 ? (
          <span key={i} className="nb">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  );
}

// Official English, on sites whose file asks for it ("languages": ["zh", "en"]). The server sends only words quoted
// from LD's and HKO's English documents and feeds; nothing is translated here, and a missing line shows nothing.
function En({ text, className }: { text?: string | null; className?: string }) {
  if (!text) return null;
  return (
    <div className={className ? `en ${className}` : "en"} lang="en">
      <Words text={text} />
    </div>
  );
}

// A wrapped label breaks between trade names, never inside one, and "+N" stays with the name before it.
function Names({ label }: { label: string }) {
  const names = label.split(" · ");
  return (
    <>
      {names.map((name, i) => (
        <Fragment key={`${i}-${name}`}>
          {i > 0 && " "}
          <span className="tn">{i < names.length - 1 ? `${name}\u00A0·` : name}</span>
        </Fragment>
      ))}
    </>
  );
}

function Trades({ label, en }: { label: string; en?: string | null }) {
  return (
    <div className="trades">
      <Names label={label} />
      {en && (
        <div className="trades-en" lang="en">
          <Names label={en} />
        </div>
      )}
    </div>
  );
}

// A tile's English goes under its Chinese lines, as one block: "45 mins rest" and "15 mins work" side by side when
// they fit, "Suspension of work", or the 2-hour baseline's one sentence.
function TileEn({ lines }: { lines?: string[] }) {
  if (!lines?.length) return null;
  return (
    <div className="tile-en" lang="en">
      {lines.map((line) => (
        <div key={line} className="en">
          <Words text={line} />
        </div>
      ))}
    </div>
  );
}

function Tile({ tile }: { tile: RestTile }) {
  if (tile.kind === "suspend") {
    return (
      <div className="tile stop">
        <Trades label={tile.tradesZh} en={tile.en?.trades} />
        <div className="big big-word">暫停工作</div>
        <div className="small" />
        <TileEn lines={tile.en?.lines} />
      </div>
    );
  }
  return (
    <div className="tile">
      <Trades label={tile.tradesZh} en={tile.en?.trades} />
      <div className="big">
        休息<b>{tile.rest}</b>分鐘
      </div>
      <div className="small">{tile.kind === "baseline" ? `每 ${tile.perHours} 小時` : `工作 ${tile.work} 分鐘`}</div>
      <TileEn lines={tile.en?.lines} />
    </div>
  );
}

// HKO's 10-minute wind at a nearby station: the gust is what matters for cranes and gondolas, so it is the big
// number; the mean wind and the station's name sit under it. No limit or advice: equipment limits differ.
function WindBlock({ wind }: { wind: Wind }) {
  const mean = `${windNameZh(wind.dirZh)} ${wind.speedKmh}`;
  return (
    <div className="wind">
      {wind.gustKmh !== null ? (
        <div className="gust">
          <small>陣風</small>
          {wind.gustKmh}
          <small>公里/小時</small>
        </div>
      ) : (
        <div className="gust">
          {mean}
          <small>公里/小時</small>
        </div>
      )}
      <div className="mean">{wind.gustKmh !== null ? `${mean} · ${wind.placeZh}` : wind.placeZh}</div>
    </div>
  );
}

// The bar's extras, hidden in this order when the warning icons need the room: humidity and UV, then tomorrow's
// forecast, then the wind. The warning icons and the clock are never hidden.
const EXTRAS = 3;

// How many extras to hide so the warning icons fit (landscape; the portrait rail wraps instead). Measured, so it
// copes with any number of warnings and any station name. Runs before paint, so nothing visibly jumps.
// New content or a new screen size starts again from nothing hidden; the rail narrowing for any other reason
// (the web font arriving late makes the text wider) only ever hides more.
function useFit(stage: RefObject<HTMLDivElement>, content: string): number {
  const [drop, setDrop] = useState(0);
  const [size, setSize] = useState("");
  const [, setTick] = useState(0);
  useLayoutEffect(() => setDrop(0), [content, size]);
  useLayoutEffect(() => {
    const rail = stage.current?.querySelector<HTMLElement>(".rail");
    if (rail && drop < EXTRAS && rail.scrollWidth > rail.clientWidth + 1) setDrop(drop + 1);
  });
  useEffect(() => {
    const el = stage.current;
    const rail = el?.querySelector<HTMLElement>(".rail");
    if (!el || !rail || typeof ResizeObserver === "undefined") return;
    const stageWatch = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize(`${Math.round(width)}x${Math.round(height)}`);
    });
    const railWatch = new ResizeObserver(() => setTick((t) => t + 1));
    stageWatch.observe(el);
    railWatch.observe(rail);
    return () => {
      stageWatch.disconnect();
      railWatch.disconnect();
    };
  }, [stage]);
  return drop;
}

// Breathing room kept between the centre content and the bar, in CSS pixels.
const CENTER_MARGIN = 8;
// The smallest the centre is scaled; below this the Chinese gets too small to read from the gate.
const MIN_SCALE = 0.6;
// The English the centre gives up, lowest value first, when it does not fit even at MIN_SCALE: 1 the warning's
// and the note's English, 2 also the supervisor lines', 3 all of it (kiosk.css, data-en-shed). The Chinese always
// keeps its room: with everything given up, the centre is no taller than on a Chinese-only site.
const EN_SHED = 3;

// Scale the centre down when its content is taller than the room left by the bar (portrait heat-stress days with
// a supervisor line, six tiles, two lines...), so it never runs over the warning icons. No Chinese is hidden: every
// line in the centre is official wording. A transform does not change the measured size, so this cannot loop.
function useCenterScale(
  box: RefObject<HTMLDivElement>,
  inner: RefObject<HTMLDivElement>,
  content: string,
  english: boolean,
): { scale: number; shed: number } {
  const [scale, setScale] = useState(1);
  const [size, setSize] = useState("");
  const [given, setGiven] = useState({ key: "", shed: 0 });
  const [, setTick] = useState(0);
  // What was given up belongs to the content and size it was measured for; anything new starts from nothing.
  const key = `${size}|${content}`;
  const shed = given.key === key ? given.shed : 0;
  useLayoutEffect(() => {
    const outer = box.current;
    const fit = inner.current;
    if (!outer || !fit) return;
    const style = getComputedStyle(outer);
    const room = outer.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - CENTER_MARGIN;
    const need = fit.offsetHeight;
    if (english && shed < EN_SHED && room > 0 && need * MIN_SCALE > room) {
      setGiven({ key, shed: shed + 1 });
      return;
    }
    const next = need > room && room > 0 ? Math.max(MIN_SCALE, Math.floor((room / need) * 100) / 100) : 1;
    if (Math.abs(next - scale) > 0.005) setScale(next);
  });
  useEffect(() => {
    const outer = box.current;
    const fit = inner.current;
    if (!outer || !fit || typeof ResizeObserver === "undefined") return;
    const outerWatch = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize(`${Math.round(width)}x${Math.round(height)}`);
    });
    const watch = new ResizeObserver(() => setTick((t) => t + 1));
    outerWatch.observe(outer);
    watch.observe(fit);
    return () => {
      outerWatch.disconnect();
      watch.disconnect();
    };
  }, [box, inner]);
  return { scale, shed };
}

type ScreenProps = {
  snap: Snapshot;
  clock: string;
  date: string;
  layout?: string;
  simbar?: ReactNode;
  // Decided by the live screen from when it last heard from the server; without it, from the snapshot.
  stale?: boolean;
};

export function Screen({ snap, clock, date, layout, simbar, stale: staleProp }: ScreenProps) {
  const stale = staleProp ?? isStale(snap);
  const display = snap.display;
  const mode = display.mode || "normal";
  const main = display.main || display.action || "";
  const banner = stale ? null : snap.banner;
  const weather = snap.weather;
  const wind = snap.wind;
  const forecast = snap.forecast;
  const supervisor = snap.supervisor || [];
  const english = Boolean(snap.site?.languages?.includes("en"));
  const enLines = display.en || [];
  const rail = railSignals(snap);
  const stageRef = useRef<HTMLDivElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<HTMLDivElement>(null);
  const drop = useFit(stageRef, JSON.stringify([rail.map((s) => s.code), weather, wind, forecast]));
  const centre = JSON.stringify([display, snap.restTiles, snap.notes, snap.notesEn, supervisor]);
  const { scale, shed } = useCenterScale(centerRef, fitRef, centre, english);

  return (
    <div
      ref={stageRef}
      className="stage"
      data-tone={snap.tone || "idle"}
      data-mode={mode}
      data-sup={supervisor.length || undefined}
      data-en={english || undefined}
      data-en-shed={shed || undefined}
      data-drop={drop || undefined}
      data-layout={layout}
    >
      {simbar}
      {stale ? (
        <div className="banner banner-stale">
          <span className="msg">{STALE_TEXT}</span>
        </div>
      ) : banner ? (
        <div className="banner">
          <span className="tag">最新</span>
          <span className="msg">
            {banner.time}　{banner.textZh}
          </span>
        </div>
      ) : null}

      <div className="center" ref={centerRef}>
        <div
          className="fit"
          ref={fitRef}
          style={scale < 1 ? { transform: `scale(${scale})` } : undefined}
        >
          {display.heroRel && <Plate rel={display.heroRel} className="hero" />}
          {mode === "heat" ? (
            <>
              <div className="tiles">
                {(snap.restTiles || []).map((tile) => (
                  <Tile key={`${tile.kind}-${tile.rest}`} tile={tile} />
                ))}
              </div>
              {display.meta && <div className="meta">{display.meta}</div>}
              <En text={display.metaEn} className="meta-en" />
              {(snap.notes || []).map((note, i) => (
                <Fragment key={note}>
                  <div className="note">{note}</div>
                  <En text={snap.notesEn?.[i]} className="note-en" />
                </Fragment>
              ))}
            </>
          ) : (
            <>
              <div className="action" style={{ "--chars": [...main].length } as CSSProperties}>
                {main}
              </div>
              {(display.sub || []).map((line) => (
                <div key={line} className="sub">
                  {line}
                </div>
              ))}
              {enLines.length > 0 && (
                <div className="en-lines" lang="en">
                  {enLines.map((line) => (
                    <div key={line} className="en">
                      <Words text={line} />
                    </div>
                  ))}
                </div>
              )}
              {display.meta && <div className="meta">{display.meta}</div>}
              <En text={display.metaEn} className="meta-en" />
            </>
          )}
          {supervisor.map((line) => (
            <div key={line.text} className="sup">
              <span className="lab">主管注意</span>
              <span className="txt">{line.text}</span>
              <span className="src">{line.fromZh}</span>
              {line.textEn && (
                <div className="en sup-en" lang="en">
                  <span className="txt">
                    <Words text={line.textEn} />
                  </span>
                  {line.fromEn && (
                    <>
                      {" "}
                      <span className="src">{line.fromEn}</span>
                    </>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="bar">
        <div className="rail">
          {rail.map((s) => (
            <Plate key={s.code} rel={s.rel} />
          ))}
        </div>
        <div className="info">
          {weather && (
            <div className="wx">
              {weather.iconRel && <Plate rel={weather.iconRel} />}
              <div className="temp">
                {weather.tempC}°<small>{weather.placeZh}</small>
              </div>
              <div className="metaw">
                {weather.humidity !== null && <div>濕度 {weather.humidity}%</div>}
                {weather.uvValue !== null && (
                  <div>
                    紫外線 {formatUv(weather.uvValue)} {weather.uvDescZh || ""}
                  </div>
                )}
              </div>
            </div>
          )}
          {wind && <WindBlock wind={wind} />}
          {forecast && (
            <div className="wx tmr">
              {forecast.iconRel && <Plate rel={forecast.iconRel} />}
              <div className="range">
                <small>明日</small>
                {forecast.minC}–{forecast.maxC}°
                {forecast.psrZh && <small className="psr">顯著降雨概率 {forecast.psrZh}</small>}
              </div>
            </div>
          )}
          <div className="clock">
            <div className="t">{clock}</div>
            <div className="d">{date}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
