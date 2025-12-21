import { defineConfig } from "eslint/config";
import json from "@eslint/json";

const ignores = [
  "BMAD-METHOD/**",
  "quint-code/**",
  "node_modules/**",
  "runs/**",
  ".pytest_cache/**",
  "coverage/**",
  "package-lock.json",
];

export default defineConfig([
  {
    plugins: {
      json,
    },
  },
  {
    files: ["**/*.json"],
    ignores,
    language: "json/json",
    rules: {
      "json/no-duplicate-keys": "error",
    },
  },
  {
    files: ["**/*.jsonc"],
    ignores,
    language: "json/jsonc",
    rules: {
      "json/no-duplicate-keys": "error",
    },
  },
]);
