import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles.css";
import * as Sentry from "@sentry/react";

const sentryDsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    environment: import.meta.env.MODE,
    release: "market-intelligence-lab@0.10.0",
    sendDefaultPii: false,
    tracesSampleRate: 0,
    beforeSend(event) {
      if (event.request) {
        delete event.request.cookies;
        delete event.request.data;
        if (event.request.headers) {
          for (const key of Object.keys(event.request.headers)) {
            if (["authorization", "cookie", "set-cookie"].includes(key.toLowerCase())) {
              event.request.headers[key] = "[Filtered]";
            }
          }
        }
      }
      return event;
    },
  });
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
