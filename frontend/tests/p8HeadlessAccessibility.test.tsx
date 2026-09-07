import { render } from "@testing-library/react";
import axe from "axe-core";

import { HeadlessPlanningApp } from "../src/headless/HeadlessPlanningApp";
import type { HeadlessPlanningClient } from "../src/headless/client";
import { LocaleProvider } from "../src/i18n/locale";
import { p8Runtime } from "./p8HeadlessFixtures";

describe("TEST-P8-FRONTEND-DISTRIBUTION-001 accessibility", () => {
  it("has no axe violations in the independently packaged entry surface", async () => {
    const unavailable = async () => {
      throw new Error("not invoked in static accessibility evidence");
    };
    const client: HeadlessPlanningClient = {
      create: unavailable,
      status: unavailable,
      result: unavailable,
      cancel: unavailable,
      retry: unavailable,
    };
    const { container } = render(
      <LocaleProvider initialLocale="zh-CN">
        <HeadlessPlanningApp client={client} runtime={p8Runtime} />
      </LocaleProvider>,
    );
    const result = await axe.run(container, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });
});
