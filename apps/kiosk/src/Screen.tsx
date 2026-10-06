import { Fragment, type CSSProperties, type ReactNode } from "react";
import { formatUv, isStale, railSignals, type RestTile, type Snapshot } from "./present";

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

type ScreenProps = {
  snap: Snapshot;
  clock: string;
  date: string;
  layout?: string;
  simbar?: ReactNode;
};

export function Screen({ snap, clock, date, layout, simbar }: ScreenProps) {
  const stale = isStale(snap);
  const display = snap.display;
  const mode = display.mode || "normal";
  const main = display.main || display.action || "";
  const banner = stale ? null : snap.banner;
  const weather = snap.weather;
  const forecast = snap.forecast;
  const supervisor = snap.supervisor || [];

  return (
    <div
      className="stage"
      data-tone={snap.tone || "idle"}
      data-mode={mode}
      data-sup={supervisor.length || undefined}
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

      <div className="center">
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

      <div className="bar">
        <div className="rail">
          {railSignals(snap).map((s) => (
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
          {forecast && (
            <>
              {weather && <div className="sep" />}
              <div className="wx tmr">
                {forecast.iconRel && <Plate rel={forecast.iconRel} />}
                <div className="range">
                  <small>明日</small>
                  {forecast.minC}–{forecast.maxC}°
                </div>
              </div>
            </>
          )}
          <div className="sep sep-clock" />
          <div className="clock">
            <div className="t">{clock}</div>
            <div className="d">{date}</div>
          </div>
        </div>
      </div>
    </div>
  );
}
