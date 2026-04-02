import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "./app/providers/AuthProvider";
import { router } from "./routes/router";
import { registerServiceWorker } from "./pwa/registerServiceWorker";
import "./app/styles.css";

registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
    </AuthProvider>
  </React.StrictMode>,
);
