import {
  excludedP313RouteFragments,
  p3WorkspaceRoutes,
  p4WorkspaceRoutes,
  workspaceRoutes,
} from "../src/app/routeInventory";

describe("P3-13 route inventory", () => {
  it("preserves the 18 authorized workspace routes", () => {
    expect(p3WorkspaceRoutes).toHaveLength(18);
    expect(new Set(p3WorkspaceRoutes.map((route) => route.path)).size).toBe(18);
    expect(p3WorkspaceRoutes.map((route) => route.path)).toEqual(
      expect.arrayContaining([
        "/planning/versions/:schedule_version_id/gantt/factory",
        "/planning/versions/:schedule_version_id/gantt/workshops",
        "/planning/versions/:schedule_version_id/gantt/machines",
        "/resource-load",
        "/compare",
      ]),
    );
  });

  it("keeps P4 and Production publication routes outside the frozen P3 subset", () => {
    const paths = p3WorkspaceRoutes.map((route) => route.path.toLowerCase()).join("\n");
    for (const fragment of excludedP313RouteFragments) {
      expect(paths).not.toContain(fragment);
    }
    expect(paths).not.toContain("mes");
  });

  it("adds exactly one bounded P4 dynamic-replanning route", () => {
    expect(p4WorkspaceRoutes.map((route) => route.path)).toEqual([
      "/planning/replanning",
    ]);
    expect(workspaceRoutes).toHaveLength(19);
    expect(new Set(workspaceRoutes.map((route) => route.path)).size).toBe(19);
    expect(workspaceRoutes.map((route) => route.path).join("\n")).not.toContain(
      "production-publish",
    );
  });
});
