import { useEffect } from "react";

// Keeps a live screen on: tablets, TV boxes and laptops otherwise dim or sleep after a few minutes.
export function useWakeLock(enabled: boolean) {
  useEffect(() => {
    if (!enabled || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let alive = true;
    const acquire = async () => {
      if (document.visibilityState !== "visible" || (lock && !lock.released)) return;
      try {
        const next = await navigator.wakeLock.request("screen");
        if (alive) lock = next;
        else void next.release();
      } catch {
        // Refused (battery saver, no user gesture on some browsers): the screen still works.
      }
    };
    const onVisible = () => void acquire();
    document.addEventListener("visibilitychange", onVisible);
    void acquire();
    return () => {
      alive = false;
      document.removeEventListener("visibilitychange", onVisible);
      void lock?.release().catch(() => undefined);
    };
  }, [enabled]);
}

const CHECK_MS = 5 * 60_000;
// Vite names the entry script after its content (/assets/index-<hash>.js), so a new deploy has a new name.
const ENTRY = /<script[^>]+src="([^"]*\/assets\/[^"]+\.js)"/;

function currentEntry(): string | null {
  const script = document.querySelector<HTMLScriptElement>('script[type="module"][src*="/assets/"]');
  return script?.getAttribute("src") ?? null;
}

// Reloads a live screen when a new version of the page has been deployed, so screens on site pick up fixes
// without anyone touching them. It only reloads after the server has answered, never while offline.
export function useAutoUpdate(enabled: boolean) {
  useEffect(() => {
    const running = currentEntry();
    if (!enabled || !running) return; // the dev server has no hashed entry script
    const check = async () => {
      try {
        const r = await fetch("/", { cache: "no-store" });
        if (!r.ok) return;
        const deployed = (await r.text()).match(ENTRY)?.[1];
        if (deployed && deployed !== running) window.location.reload();
      } catch {
        // Offline or the server is restarting: try again at the next check.
      }
    };
    const id = window.setInterval(check, CHECK_MS);
    return () => window.clearInterval(id);
  }, [enabled]);
}
