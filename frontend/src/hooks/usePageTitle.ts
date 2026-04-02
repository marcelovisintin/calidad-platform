import { useEffect } from "react";
import { appConfig } from "../app/config";

export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} | ${appConfig.appName}`;
  }, [title]);
}
