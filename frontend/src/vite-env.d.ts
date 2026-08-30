/// <reference types="vite/client" />

declare const __APP_VERSION__: string;

type AppGitHistoryItem = {
  commit: string;
  shortCommit: string;
  date: string;
  author: string;
  subject: string;
  decorations: string;
};

type AppBuildInfo = {
  buildDate: string;
  commit: string;
  shortCommit: string;
  branch: string;
  dirty: boolean;
  environment: string;
  releaseTag: string;
  history: AppGitHistoryItem[];
};

declare const __APP_BUILD_INFO__: AppBuildInfo;
