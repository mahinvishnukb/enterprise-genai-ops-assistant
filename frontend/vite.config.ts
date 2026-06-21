import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxies /api/* to the FastAPI backend during local dev so the React app
// can call relative paths ("/api/chat") without hardcoding a host, and
// without the backend needing permissive CORS in dev.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
