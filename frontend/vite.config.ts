import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// `npm run dev` serves the desk on http://localhost:5173 and opens it in the browser.
// The dashboard calls the FastAPI backend at http://localhost:8000 (set VITE_API_URL to change it).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    open: true,
  },
});
