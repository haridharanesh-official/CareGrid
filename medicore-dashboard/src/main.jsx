import React from "react";
import { createRoot } from "react-dom/client";
import App from "./app/App.jsx";
import "./styles/tokens.css";
import "./styles/globals.css";
import "./styles/components.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
