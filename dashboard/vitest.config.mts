import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// "server-only" só existe para impedir import em componentes cliente; nos testes vira módulo vazio.
export default defineConfig({
  resolve: {
    alias: {
      "server-only": fileURLToPath(new URL("./test/server-only.ts", import.meta.url)),
      "@": fileURLToPath(new URL("./", import.meta.url)),
    },
  },
  test: { include: ["**/__tests__/**/*.test.ts"] },
});
