import { ConfigProvider } from "antd";
import React from "react";
import ReactDOM from "react-dom/client";

import { LocaleProvider, useLocale } from "../i18n/locale";
import { createHeadlessPlanningClient } from "./client";
import { HeadlessPlanningApp } from "./HeadlessPlanningApp";
import { loadHeadlessRuntimeConfig } from "./runtime";
import { resolveHeadlessSessionProvider } from "./session";
import "../styles/app.css";

const runtime = loadHeadlessRuntimeConfig();
const client = createHeadlessPlanningClient(
  runtime,
  resolveHeadlessSessionProvider(),
);

export function LocalizedHeadlessApplication() {
  const { antDesignLocale } = useLocale();
  return (
    <ConfigProvider locale={antDesignLocale}>
      <HeadlessPlanningApp client={client} runtime={runtime} />
    </ConfigProvider>
  );
}

const root = document.getElementById("root");
if (root === null) throw new Error("PlantNexus APS root element is absent");

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <LocaleProvider>
      <LocalizedHeadlessApplication />
    </LocaleProvider>
  </React.StrictMode>,
);
