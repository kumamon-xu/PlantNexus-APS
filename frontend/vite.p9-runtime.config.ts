import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

if (!process.env.P9_RUNTIME_URL) throw new Error("P9_RUNTIME_URL is required");
export default defineConfig({ plugins: [react()], server: { proxy: { "/api": { target: process.env.P9_RUNTIME_URL } } } });
