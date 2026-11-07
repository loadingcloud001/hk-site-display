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

// A wrapped tile label breaks between trade names, never inside one, and "+N" stays with the name before it.
function Trades({ label }: { label: string }) {
  const names = label.split(" · ");
  return (
    <div className="trades">
      {names.map((name, i) => (
        <Fragment key={`${i}-${name}`}>
          {i > 0 && " "}
          <span className="tn">{i < names.length - 1 ? `${name}\u00A0·` : name}</span>
        </Fragment>
      ))}
    </div>
  );
}

function Tile({ tile }: { tile: RestTile }) {
  if (tile.kind === "suspend") {
    return (
      <div className="tile stop">
        <Trades label={tile.tradesZh} />
        <div className="big big-word">暫停工作</div>
        <div className="small" />
      </div>
    );
  }
  return (
    <div className="tile">
      <Trades label={tile.tradesZh} />
      <div className="big">
        休息<b>{tile.rest}</b>分鐘
      </div>
      <div className="small">{tile.kind === "baseline" ? `每 ${tile.perHours} 小時` : `工作 ${tile.work} 分鐘`}</div>
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

// Scale the centre down when its content is taller than the room left by the bar (portrait heat-stress days with
// a supervisor line, six tiles, two lines...), so it never runs over the warning icons. Nothing is hidden: every
// line in the centre is official wording. A transform does not change the measured size, so this cannot loop.
function useCenterScale(box: RefObject<HTMLDivElement>, inner: RefObject<HTMLDivElement>): number {
  const [scale, setScale] = useState(1);
  const [, setTick] = useState(0);
  useLayoutEffect(() => {
    const outer = box.current;
    const content = inner.current;
    if (!outer || !content) return;
    const style = getComputedStyle(outer);
    const room = outer.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom) - CENTER_MARGIN;
    const need = content.offsetHeight;
    const next = need > room && room > 0 ? Math.max(0.6, Math.floor((room / need) * 100) / 100) : 1;
    if (Math.abs(next - scale) > 0.005) setScale(next);
  });
  useEffect(() => {
    const outer = box.current;
    const content = inner.current;
    if (!outer || !content || typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(() => setTick((t) => t + 1));
    watch.observe(outer);
    watch.observe(content);
    return () => watch.disconnect();
  }, [box, inner]);
  return scale;
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
  const rail = railSignals(snap);
  const stageRef = useRef<HTMLDivElement>(null);
  const centerRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<HTMLDivElement>(null);
  const drop = useFit(stageRef, JSON.stringify([rail.map((s) => s.code), weather, wind, forecast]));
  const scale = useCenterScale(centerRef, fitRef);

  return (
    <div
      ref={stageRef}
      className="stage"
      data-tone={snap.tone || "idle"}
      data-mode={mode}
      data-sup={supervisor.length || undefined}
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
              {(snap.notes || []).map((note) => (
                <div key={note} className="note">
                  {note}
                </div>
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
              {display.meta && <div className="meta">{display.meta}</div>}
            </>
          )}
          {supervisor.map((line) => (
            <div key={line.text} className="sup">
              <span className="lab">主管注意</span>
              <span className="txt">{line.text}</span>
              <span className="src">{line.fromZh}</span>
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
