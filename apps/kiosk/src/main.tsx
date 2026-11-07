import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Gallery } from "./Gallery";
import { Kiosk } from "./Kiosk";
import "./kiosk.css";

const gallery = new URLSearchParams(window.location.search).get("gallery") === "1";

// public/sw.js keeps a copy of the page (never the data), so a screen that powers on before the site's
// internet is up still opens it and recovers by itself. Built pages on https or localhost only.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {gallery ? <Gallery /> : <Kiosk />}
  </StrictMode>,
);
