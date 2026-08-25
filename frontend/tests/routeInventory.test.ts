import { excludedP312RouteFragments, workspaceRoutes } from "../src/app/routeInventory";

describe("P3-12 route inventory", () => {
  it("contains the 18 authorized read-only routes", () => {
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

  it("does not allocate P3-13 control or later-phase routes", () => {
    const paths = workspaceRoutes.map((route) => route.path.toLowerCase()).join("\n");
    for (const fragment of excludedP312RouteFragments) {
      expect(paths).not.toContain(fragment);
    }
    expect(paths).not.toContain("simulation");
  });
});
