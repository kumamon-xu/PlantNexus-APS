import { excludedP311RouteFragments, workspaceRoutes } from "../src/app/routeInventory";

describe("P3-11 route inventory", () => {
  it("contains the 13 authorized read-only routes", () => {
    expect(workspaceRoutes).toHaveLength(13);
    expect(new Set(workspaceRoutes.map((route) => route.path)).size).toBe(13);
  });

  it("does not allocate P3-12 or P3-13 capability routes", () => {
    const paths = workspaceRoutes.map((route) => route.path.toLowerCase()).join("\n");
    for (const fragment of excludedP311RouteFragments) {
      expect(paths).not.toContain(fragment);
    }
    expect(paths).not.toContain("simulation");
  });
});
