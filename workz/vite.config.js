import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
export default defineConfig({
  plugins: [
    react(),
    {
      name: "workz-cache-version",
      closeBundle() {
        // The authenticated Frappe page has fixed asset names. Version them on
        // every build so a returning user receives the new calendar immediately.
        const page = new URL("../erplite/www/workz.html", import.meta.url);
        let html = readFileSync(page, "utf8");
        for (const name of ["app.js", "index.css"]) {
          const hash = createHash("sha256")
            .update(
              readFileSync(
                new URL(`../erplite/public/workz/${name}`, import.meta.url),
              ),
            )
            .digest("hex")
            .slice(0, 12);
          html = html.replace(
            new RegExp(
              `/assets/erplite/workz/${name.replaceAll(".", "\\.")}(?:\\?v=[a-f0-9]+)?`,
              "g",
            ),
            `/assets/erplite/workz/${name}?v=${hash}`,
          );
        }
        writeFileSync(page, html);
      },
    },
  ],
  base: "/assets/erplite/workz/",
  build: {
    outDir: "../erplite/public/workz",
    emptyOutDir: true,
    rollupOptions: {
      output: { entryFileNames: "app.js", assetFileNames: "[name][extname]" },
    },
  },
});
