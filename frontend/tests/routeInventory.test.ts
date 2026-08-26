import { excludedP313RouteFragments, workspaceRoutes } from "../src/app/routeInventory";

describe("P3-13 route inventory", () => {
  it("preserves the 18 authorized workspace routes", () => {
    expect(workspaceRoutes).toHaveLength(18);
    expect(new Set(workspaceRoutes.map((route) => route.path)).size).toBe(18);
    expect(workspaceRoutes.map((route) => route.path)).toEqual(
      expect.arrayContaining([
        "/planning/versions/:schedule_version_id/gantt/factory",
        "/planning/versions/:schedule_version_id/gantt/workshops",
        "/planning/versions/:schedule_version_id/gantt/machines",
        "/resource-load",
        "/compare",
      ]),
    );
  });

  it("does not allocate P4 or Production publication routes", () => {
    const paths = workspaceRoutes.map((route) => route.path.toLowerCase()).join("\n");
    for (const fragment of excludedP313RouteFragments) {
      expect(paths).not.toContain(fragment);
    }
    expect(paths).not.toContain("mes");
  });
});
