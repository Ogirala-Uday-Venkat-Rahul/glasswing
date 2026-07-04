import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on 5173. The backend runs separately on 8000; the frontend talks to
// it directly using VITE_API_BASE_URL (see src/api.js), and the backend already
// allows cross-origin calls, so no proxy is needed here.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
