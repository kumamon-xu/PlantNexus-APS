import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { LocaleProvider } from "../src/i18n/locale";
import { HeadlessPlanningApp } from "../src/headless/HeadlessPlanningApp";
import type { HeadlessPlanningClient } from "../src/headless/client";
import {
  parseCanonicalIngressResult,
  parsePlanningRun,
} from "../src/headless/contracts";
import {
  p8AcceptedResult,
  p8CanonicalRequestText,
  p8CompletedRun,
  p8Runtime,
} from "./p8HeadlessFixtures";

describe("TEST-P8-FRONTEND-DISTRIBUTION-001 Headless workflow UI", () => {
  it("creates, refreshes and renders server Runtime/Extension evidence", async () => {
    const accepted = parseCanonicalIngressResult(p8AcceptedResult);
    const completed = parsePlanningRun(p8CompletedRun);
    const client: HeadlessPlanningClient = {
      create: vi.fn(async () => accepted),
      status: vi.fn(async () => completed),
      result: vi.fn(async () => completed),
      cancel: vi.fn(async () => completed),
      retry: vi.fn(async () => completed),
    };
    const user = userEvent.setup();
    render(
      <LocaleProvider initialLocale="en-US">
        <HeadlessPlanningApp client={client} runtime={p8Runtime} />
      </LocaleProvider>,
    );

    fireEvent.change(
      screen.getByRole("textbox", { name: "Canonical JSON request" }),
      { target: { value: p8CanonicalRequestText } },
    );
    await user.click(screen.getByRole("button", { name: "Submit to APS Runtime" }));
    expect(await screen.findByText("PLANNING-RUN-P8-SYNTHETIC-001")).toBeVisible();
    expect(screen.getByText("EXTENSION-SET-NONE-P8-SAMPLE")).toBeVisible();
    expect(
      screen.getByText(
        "sha256:9999999999999999999999999999999999999999999999999999999999999999",
      ),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Refresh status" }));
    expect(await screen.findByText("COMPLETED")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Load terminal result" }));
    expect(client.status).toHaveBeenCalledOnce();
    expect(client.result).toHaveBeenCalledOnce();
  });

  it("shows a structured authorization failure without inventing success", async () => {
    const client: HeadlessPlanningClient = {
      create: vi.fn(async () => {
        const { HeadlessClientError } = await import("../src/headless/client");
        throw new HeadlessClientError(
          "authorization_denied",
          "scope denied",
          403,
          "P8-FORBIDDEN",
          "FORBIDDEN",
        );
      }),
      status: vi.fn(),
      result: vi.fn(),
      cancel: vi.fn(),
      retry: vi.fn(),
    };
    const user = userEvent.setup();
    render(
      <LocaleProvider initialLocale="en-US">
        <HeadlessPlanningApp client={client} runtime={p8Runtime} />
      </LocaleProvider>,
    );
    fireEvent.change(
      screen.getByRole("textbox", { name: "Canonical JSON request" }),
      { target: { value: p8CanonicalRequestText } },
    );
    await user.click(screen.getByRole("button", { name: "Submit to APS Runtime" }));
    expect(await screen.findByText("authorization_denied")).toBeVisible();
    expect(screen.getByText("scope denied")).toBeVisible();
    expect(screen.queryByText("Authoritative PlanningRun")).not.toBeInTheDocument();
  });
});
