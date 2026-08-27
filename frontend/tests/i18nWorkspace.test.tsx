import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import type { PlanningWorkspaceClient } from "../src/api/client";
import type { RuntimeConfig } from "../src/api/runtime";
import { AppServicesProvider } from "../src/app/context";
import { PlanningWorkspaceApp } from "../src/app/PlanningWorkspaceApp";
import { ScheduleVersionPanel } from "../src/components/ScheduleVersionPanel";
import {
  LocaleProvider,
  localePreferenceKey,
  useLocale,
} from "../src/i18n/locale";
import { testScheduleVersion } from "./fixtures";

const runtime: RuntimeConfig = {
  apiBaseUrl: "/api/v1",
  dataPlane: "PRODUCTION",
  environment: "PRODUCTION",
  synthetic: false,
};

const unusedClient = {} as PlanningWorkspaceClient;

function LocaleProbe() {
  const { locale, setLocale, antDesignLocale, t } = useLocale();
  return (
    <div data-testid="probe" data-locale={locale} data-antd-locale={antDesignLocale.locale}>
      <span>{t("app.workspace")}</span>
      <button type="button" onClick={() => setLocale(locale === "zh-CN" ? "en-US" : "zh-CN")}>
        switch
      </button>
    </div>
  );
}

describe("TEST-FRONTEND-I18N-001 locale workspace integration", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = "";
  });

  it("defaults to zh-CN, binds document and Ant Design locale, then persists only locale preference", async () => {
    const { unmount } = render(
      <LocaleProvider>
        <LocaleProbe />
      </LocaleProvider>,
    );
    expect(screen.getByText("计划工作区")).toBeInTheDocument();
    await waitFor(() => expect(document.documentElement.lang).toBe("zh-CN"));
    expect(screen.getByTestId("probe")).toHaveAttribute("data-antd-locale", "zh-cn");
    await userEvent.click(screen.getByRole("button", { name: "switch" }));
    expect(screen.getByText("Planning Workspace")).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en-US");
    expect(screen.getByTestId("probe")).toHaveAttribute("data-antd-locale", "en");
    expect([...Array(localStorage.length)].map((_, index) => localStorage.key(index))).toEqual([
      localePreferenceKey,
    ]);
    expect(localStorage.getItem(localePreferenceKey)).toBe("en-US");
    unmount();
    render(<LocaleProvider><LocaleProbe /></LocaleProvider>);
    expect(screen.getByText("Planning Workspace")).toBeInTheDocument();
  });

  it("switches menus, controls and accessibility text without changing routes", async () => {
    render(
      <LocaleProvider initialLocale="zh-CN">
        <LocaleProbe />
        <AppServicesProvider services={{ client: unusedClient, runtime }}>
          <MemoryRouter initialEntries={["/outside-p3"]}>
            <PlanningWorkspaceApp />
          </MemoryRouter>
        </AppServicesProvider>
      </LocaleProvider>,
    );
    expect(screen.getByRole("navigation", { name: "计划工作区导航" })).toBeInTheDocument();
    expect(screen.getByText("数据健康")).toBeInTheDocument();
    expect(screen.getByLabelText("语言")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "switch" }));
    expect(screen.getByRole("navigation", { name: "Planning Workspace navigation" })).toBeInTheDocument();
    expect(screen.getByText("Data health")).toBeInTheDocument();
    expect(screen.getByLabelText("Language")).toBeInTheDocument();
  });

  it("shows official labels together with raw state, IDs, fingerprints and UTC", () => {
    render(
      <LocaleProvider initialLocale="zh-CN">
        <ScheduleVersionPanel version={testScheduleVersion} />
      </LocaleProvider>,
    );
    expect(screen.getByText("草稿")).toBeInTheDocument();
    expect(screen.getByText("DRAFT")).toBeInTheDocument();
    expect(screen.getByText(testScheduleVersion.schedule_version_id)).toBeInTheDocument();
    expect(screen.getByText(testScheduleVersion.content_fingerprint)).toBeInTheDocument();
    expect(screen.getByText(testScheduleVersion.created_at_utc)).toBeInTheDocument();
  });
});
