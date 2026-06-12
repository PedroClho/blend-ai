import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev: o backend FastAPI roda em :8000 (container torch20); o proxy evita CORS.
// Build: `npm run build` gera web/dist, servido estático pelo próprio FastAPI.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
