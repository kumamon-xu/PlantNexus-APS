import React from "react";
import ReactDOM from "react-dom/client";

import { DemoApp } from "./DemoApp";
import "./styles/demo.css";

const root = document.getElementById("root");
if (root === null) throw new Error("Demo root element is absent");

const profile = import.meta.env.VITE_DEMO_PROFILE === "smoke" ? "smoke" : "showcase";

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <DemoApp profile={profile} />
  </React.StrictMode>,
);
