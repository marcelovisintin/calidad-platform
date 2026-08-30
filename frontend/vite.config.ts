import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const backendTarget = "http://127.0.0.1:8000";
const buildVersion = new Date().toISOString();
const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

type GitHistoryItem = {
  commit: string;
  shortCommit: string;
  date: string;
  author: string;
  subject: string;
  decorations: string;
};

function runGit(args: string[]) {
  try {
    return execFileSync("git", ["-C", repositoryRoot, ...args], { encoding: "utf8" }).trim();
  } catch {
    return "";
  }
}

function parseGitHistory(raw: string): GitHistoryItem[] {
  return raw
    .split(/\r?\n/)
    .map((line) => line.split("\t"))
    .filter((parts) => parts.length >= 5 && Boolean(parts[0]))
    .map(([commit, shortCommit, date, author, subject, decorations = ""]) => ({
      commit,
      shortCommit,
      date,
      author,
      subject,
      decorations,
    }));
}

function readEncodedHistory() {
  const encoded = process.env.APP_GIT_HISTORY_B64?.trim();
  if (!encoded) {
    return "";
  }
  try {
    return Buffer.from(encoded, "base64").toString("utf8");
  } catch {
    return "";
  }
}

const gitLogFormat = "%H%x09%h%x09%aI%x09%an%x09%s%x09%D";
const gitHistory = parseGitHistory(
  readEncodedHistory() || runGit(["log", "-n", "30", "--date=iso-strict", `--pretty=format:${gitLogFormat}`]),
);
const currentGitEntry = gitHistory[0];
const gitCommit = process.env.APP_GIT_COMMIT?.trim() || currentGitEntry?.commit || "no-disponible";
const shortGitCommit = process.env.APP_GIT_SHORT_COMMIT?.trim() || currentGitEntry?.shortCommit || gitCommit.slice(0, 7);
const gitBranch = process.env.APP_GIT_BRANCH?.trim() || runGit(["branch", "--show-current"]) || "no-disponible";
const gitDirty = process.env.APP_GIT_DIRTY
  ? process.env.APP_GIT_DIRTY.toLowerCase() === "true"
  : Boolean(runGit(["status", "--porcelain"]));
const deploymentEnvironment = process.env.APP_DEPLOYMENT_ENV?.trim() || "local";
const releaseTag = currentGitEntry?.decorations.match(/(?:^|, )tag: (release-[^,]+)/)?.[1] ?? "";
const buildInfo = {
  buildDate: buildVersion,
  commit: gitCommit,
  shortCommit: shortGitCommit,
  branch: gitBranch,
  dirty: gitDirty,
  environment: deploymentEnvironment,
  releaseTag,
  history: gitHistory,
};

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(buildVersion),
    __APP_BUILD_INFO__: JSON.stringify(buildInfo),
  },
  plugins: [
    react(),
    {
      name: "emit-app-version",
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "version.json",
          source: JSON.stringify({
            version: buildVersion,
            commit: gitCommit,
            branch: gitBranch,
            environment: deploymentEnvironment,
          }),
        });
      },
    },
  ],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": {
        target: backendTarget,
        changeOrigin: true,
      },
      "/media": {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
  },
  build: {
    target: "es2020",
    sourcemap: false,
  },
});
