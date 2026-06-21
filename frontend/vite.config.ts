import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Proxies /api/* to the FastAPI backend during local dev so the React app
// can call relative paths ("/api/chat") without hardcoding a host, and
// without the backend needing permissive CORS in dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
