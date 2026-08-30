import frontendPackage from "../../../package.json";
import { appConfig } from "../../app/config";
import { CURRENT_RELEASE } from "./releaseHistory";

function cleanVersion(value: string) {
  return value.replace(/^[^0-9]*/, "");
}

export const ABOUT_SYSTEM = {
  name: appConfig.appName,
  description: "Sistema de Gestión de Calidad y Anomalías",
  version: CURRENT_RELEASE.version,
  versionStatus: CURRENT_RELEASE.statusLabel,
  technicalVersion: frontendPackage.version,
  buildDate: __APP_VERSION__,
  commit: __APP_BUILD_INFO__.shortCommit,
  branch: __APP_BUILD_INFO__.branch,
  deploymentEnvironment: __APP_BUILD_INFO__.environment,
  hasUncommittedChanges: __APP_BUILD_INFO__.dirty,
  createdBy: "Marcelo",
  technologies: [
    `React ${cleanVersion(frontendPackage.dependencies.react)}`,
    `TypeScript ${cleanVersion(frontendPackage.devDependencies.typescript)}`,
    `Vite ${cleanVersion(frontendPackage.devDependencies.vite)}`,
    `React Router ${cleanVersion(frontendPackage.dependencies["react-router-dom"])}`,
    "Python 3.14",
    "Django 5.2",
    "Django REST Framework 3.15",
    "PostgreSQL 17",
    "Gunicorn 23",
    "Nginx 1.27",
    "Docker Compose",
  ],
} as const;
