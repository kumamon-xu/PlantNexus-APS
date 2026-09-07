import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  base: "./",
  plugins: [react()],
  build: {
    emptyOutDir: true,
    manifest: true,
    outDir: "dist/headless",
    rollupOptions: {
      input: resolve(process.cwd(), "headless.html"),
    },
    sourcemap: false,
    target: "es2022",
  },
});
