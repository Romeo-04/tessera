import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The API is optional. Without VITE_API_URL the app runs the seeded demo only,
// which is the deploy that has to survive until judging closes.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000", "/health": "http://127.0.0.1:8000" },
  },
});
