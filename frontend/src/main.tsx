import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConfigProvider } from "antd";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { createPlanningWorkspaceClient } from "./api/client";
import { loadRuntimeConfig } from "./api/runtime";
import { resolveHeadlessSessionProvider } from "./headless/session";
import { AppServicesProvider } from "./app/context";
import { PlanningWorkspaceApp } from "./app/PlanningWorkspaceApp";
import { createDynamicReplanningClient } from "./features/replanning/client";
import { LocaleProvider, useLocale } from "./i18n/locale";
import "./styles/app.css";

const runtime = loadRuntimeConfig();
const session = resolveHeadlessSessionProvider();
const client = createPlanningWorkspaceClient(runtime, session);
const dynamicReplanningClient = createDynamicReplanningClient(
  runtime,
  session,
);
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, refetchOnWindowFocus: false, staleTime: 0 },
  },
});

const root = document.getElementById("root");
if (root === null) {
  throw new Error("PlantNexus APS root element is absent");
}

export function LocalizedApplication() {
  const { antDesignLocale } = useLocale();
  return (
    <ConfigProvider
      locale={antDesignLocale}
      theme={{
        token: {
          colorPrimary: "#146b58",
          colorInfo: "#146b58",
          borderRadius: 6,
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <AppServicesProvider services={{ client, dynamicReplanningClient, runtime }}>
          <BrowserRouter>
            <PlanningWorkspaceApp />
          </BrowserRouter>
        </AppServicesProvider>
      </QueryClientProvider>
    </ConfigProvider>
  );
}

ReactDOM.createRoot(root).render(
  <React.StrictMode>
    <LocaleProvider>
      <LocalizedApplication />
    </LocaleProvider>
  </React.StrictMode>,
);
