import { useEffect, useState } from "react";

// Where this screen is, as sent to the service so it can pick the nearest HKO weather station.
// Rounded to about 1 km: stations are several km apart, so nothing finer is needed.
export type Fix = { lat: number; lon: number; acc: number };

const CACHE_KEY = "hksd.fix";
const REFRESH_MS = 30 * 60_000;
const RETRY_MS = [60_000, 5 * 60_000, 15 * 60_000, 30 * 60_000];
const PERMISSION_DENIED = 1;
// A rough position is plenty and spares the battery; a minutes-old browser fix is fine for a fixed screen.
const OPTIONS: PositionOptions = { enableHighAccuracy: false, timeout: 30_000, maximumAge: 5 * 60_000 };

export function toFix(c: { latitude: number; longitude: number; accuracy: number }): Fix {
  return {
    lat: Math.round(c.latitude * 100) / 100,
    lon: Math.round(c.longitude * 100) / 100,
    acc: Math.ceil(c.accuracy / 100) * 100,
  };
}

export function fixQuery(fix: Fix | null): string {
  return fix ? `?lat=${fix.lat}&lon=${fix.lon}&acc=${fix.acc}` : "";
}

// The last fix, so a reloaded screen shows the right station at once instead of after the browser answers.
function readCache(): Fix | null {
  try {
    const value = JSON.parse(window.localStorage.getItem(CACHE_KEY) || "null");
    return value && [value.lat, value.lon, value.acc].every(Number.isFinite)
      ? { lat: value.lat, lon: value.lon, acc: value.acc }
      : null;
  } catch {
    return null;
  }
}

function writeCache(fix: Fix | null) {
  try {
    if (fix) window.localStorage.setItem(CACHE_KEY, JSON.stringify(fix));
    else window.localStorage.removeItem(CACHE_KEY);
  } catch {
    // Storage can be blocked; the screen still works, it just asks again on reload.
  }
}

async function permission(): Promise<PermissionStatus | null> {
  try {
    return await navigator.permissions.query({ name: "geolocation" });
  } catch {
    return null; // not supported: just ask
  }
}

type Reading = { fix: Fix } | { code: number };

function read(): Promise<Reading> {
  return new Promise((resolve) =>
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ fix: toFix(p.coords) }),
      (e) => resolve({ code: e.code }),
      OPTIONS,
    ),
  );
}

// Asks the browser for the screen's location once the page loads (the browser shows its own permission
// prompt) and keeps it fresh. Never blocks the screen: until there is a fix, the weather shows the
// site's station or 香港天文台. Refused, unavailable or insecure (plain http) all mean "no fix".
export function useFix(enabled: boolean): Fix | null {
  const [fix, setFix] = useState<Fix | null>(() => (enabled ? readCache() : null));

  useEffect(() => {
    if (!enabled || !window.isSecureContext || !("geolocation" in navigator)) return;
    let alive = true;
    let timer: number | undefined;
    let failures = 0;
    let status: PermissionStatus | null = null;

    const publish = (next: Fix | null) => {
      writeCache(next);
      if (alive) setFix(next);
    };

    const attempt = async () => {
      window.clearTimeout(timer);
      if (status?.state === "denied") return publish(null);
      const reading = await read();
      if (!alive) return;
      if ("fix" in reading) {
        failures = 0;
        publish(reading.fix);
        timer = window.setTimeout(attempt, REFRESH_MS);
      } else if (reading.code === PERMISSION_DENIED) {
        publish(null); // asked again on the next reload, or when the permission changes
      } else {
        timer = window.setTimeout(attempt, RETRY_MS[Math.min(failures++, RETRY_MS.length - 1)]);
      }
    };

    void (async () => {
      status = await permission();
      if (!alive) return;
      if (status) {
        const watched = status;
        watched.onchange = () => {
          if (watched.state === "granted") void attempt();
          else if (watched.state === "denied") publish(null);
        };
      }
      void attempt();
    })();

    return () => {
      alive = false;
      window.clearTimeout(timer);
      if (status) status.onchange = null;
    };
  }, [enabled]);

  return fix;
}
