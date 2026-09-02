import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Gallery } from "./Gallery";
import { Kiosk } from "./Kiosk";
import "./kiosk.css";

const gallery = new URLSearchParams(window.location.search).get("gallery") === "1";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {gallery ? <Gallery /> : <Kiosk />}
  </StrictMode>,
);
