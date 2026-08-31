import { createContext, useContext, type PropsWithChildren } from "react";

import type { PlanningWorkspaceClient } from "../api/client";
import type { RuntimeConfig } from "../api/runtime";
import type { DynamicReplanningClient } from "../features/replanning/client";

interface AppServices {
  client: PlanningWorkspaceClient;
  runtime: RuntimeConfig;
  dynamicReplanningClient?: DynamicReplanningClient;
}

const AppServicesContext = createContext<AppServices | null>(null);

export function AppServicesProvider({
  children,
  services,
}: PropsWithChildren<{ services: AppServices }>) {
  return (
    <AppServicesContext.Provider value={services}>
      {children}
    </AppServicesContext.Provider>
  );
}

export function useAppServices(): AppServices {
  const services = useContext(AppServicesContext);
  if (services === null) {
    throw new Error("Planning Workspace app services are not configured");
  }
  return services;
}
