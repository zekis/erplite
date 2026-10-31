import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  base: "/assets/erplite/workz/",
  build: {
    outDir: "../erplite/public/workz",
    emptyOutDir: true,
    rollupOptions: {
      output: { entryFileNames: "app.js", assetFileNames: "[name][extname]" },
    },
  },
});
