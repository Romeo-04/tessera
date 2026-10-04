import { defineConfig } from "vitest/config";

// The domain layer in src/lib is plain TypeScript and is tested in Node.
// Screens are React Native and are verified by running the app.
export default defineConfig({
  test: { include: ["src/lib/**/*.test.ts"], environment: "node" },
});
