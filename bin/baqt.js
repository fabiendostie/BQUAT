#!/usr/bin/env node
/**
 * BAQT CLI wrapper for npx support.
 *
 * This script invokes the Python installer CLI, enabling usage like:
 *   npx baqt install
 *   npx baqt verify
 *   npx baqt status
 */

const { spawn } = require("child_process");
const path = require("path");

const args = process.argv.slice(2);

// Try to find Python executable
const pythonCandidates = ["python3", "python", "py"];

function tryPython(candidates, index = 0) {
  if (index >= candidates.length) {
    console.error("Error: Python 3.11+ not found.");
    console.error("Please install Python 3.11 or later and ensure it is in your PATH.");
    process.exit(1);
  }

  const pythonCmd = candidates[index];
  const installerPath = path.join(__dirname, "..", "installer", "cli.py");

  const child = spawn(pythonCmd, ["-m", "installer.cli", ...args], {
    cwd: path.join(__dirname, ".."),
    stdio: "inherit",
    shell: true,
  });

  child.on("error", () => {
    // Try next Python candidate
    tryPython(candidates, index + 1);
  });

  child.on("exit", (code) => {
    process.exit(code || 0);
  });
}

tryPython(pythonCandidates);
