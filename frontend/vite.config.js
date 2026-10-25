import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, Vite forwards /api and /admin to Django, so the browser sees ONE
// origin (localhost:5173): cookies stay SameSite=Strict and no CORS is needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/admin": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/static": { target: "http://127.0.0.1:8000", changeOrigin: true },
      "/media": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
