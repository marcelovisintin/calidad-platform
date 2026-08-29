import { apiRequest, downloadApiFile } from "./http";
import type { IndicatorCatalogResponse, IndicatorDashboardResponse, IndicatorReportRecipient, IndicatorReportResponse } from "./types";

export type IndicatorDashboardFilters = {
  dateFrom: string;
  dateTo: string;
  area: string;
  groupBy: string;
  page: number;
  pageSize?: number;
};


export function fetchIndicatorCatalog() {
  return apiRequest<IndicatorCatalogResponse>("/indicators/");
}

export function fetchIndicatorDashboard(key: string, filters: IndicatorDashboardFilters) {
  const params = indicatorParams(filters);
  return apiRequest<IndicatorDashboardResponse>(`/indicators/${key}/?${params.toString()}`);
}

function indicatorParams(filters: IndicatorDashboardFilters) {
  const params = new URLSearchParams({
    date_from: filters.dateFrom,
    date_to: filters.dateTo,
    page: String(filters.page),
    page_size: String(filters.pageSize ?? 20),
  });
  if (filters.area) {
    params.set("area", filters.area);
  }
  if (filters.groupBy) {
    params.set("group_by", filters.groupBy);
  }
  return params;
}

export function downloadIndicatorCsv(key: string, filters: IndicatorDashboardFilters) {
  return downloadApiFile(`/indicators/${key}/csv/?${indicatorParams(filters).toString()}`);
}

export function fetchIndicatorReportRecipients() {
  return apiRequest<IndicatorReportRecipient[]>("/indicators/report-recipients/");
}

export function createIndicatorReport(key: string, filters: IndicatorDashboardFilters, recipientIds: string[]) {
  return apiRequest<IndicatorReportResponse>(`/indicators/${key}/reports/`, {
    method: "POST",
    body: {
      date_from: filters.dateFrom,
      date_to: filters.dateTo,
      area: filters.area || null,
      group_by: filters.groupBy,
      recipient_ids: recipientIds,
    },
  });
}

export function fetchIndicatorReport(reportId: string) {
  return apiRequest<IndicatorReportResponse>(`/indicators/reports/${reportId}/`);
}
