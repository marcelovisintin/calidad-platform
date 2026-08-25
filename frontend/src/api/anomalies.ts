import { apiRequest } from "./http";
import type {
  AnomalyAttachmentSummary,
  AnomalyCodeReservation,
  AnomalyCreatePayload,
  AnomalyDetail,
  AnomalyListItem,
  AnomalyRepetitionStudyResponse,
  AffectedOrderListResponse,
  ImmediateActionPayload,
  ObservationActionPayload,
  ObservationLoadPayload,
  ObservationVerificationPayload,
  PagedResponse,
  WorkflowMetadata,
} from "./types";

export type AffectedOrderFilters = {
  search?: string;
  orderType?: string;
  number?: string;
  anomaly?: string;
  area?: string;
  status?: string;
  quantityMin?: string;
  quantityMax?: string;
  dateFrom?: string;
  dateTo?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
};

function affectedOrderParams(filters: AffectedOrderFilters) {
  const params = new URLSearchParams();
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 20));
  const values: Array<[string, string | undefined]> = [
    ["search", filters.search],
    ["order_type", filters.orderType],
    ["number", filters.number],
    ["anomaly", filters.anomaly],
    ["area", filters.area],
    ["status", filters.status],
    ["quantity_min", filters.quantityMin],
    ["quantity_max", filters.quantityMax],
    ["date_from", filters.dateFrom],
    ["date_to", filters.dateTo],
    ["ordering", filters.ordering],
  ];
  values.forEach(([key, value]) => {
    if (value?.trim()) {
      params.set(key, value.trim());
    }
  });
  return params;
}

export function fetchWorkflowMetadata() {
  return apiRequest<WorkflowMetadata>("/anomalies/workflow-metadata/");
}

export function fetchMyAnomalies(reporterId?: string, search = "", page = 1) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", "10");

  if (reporterId) {
    params.set("reporter", reporterId);
  }
  if (search.trim()) {
    params.set("search", search.trim());
  }

  return apiRequest<PagedResponse<AnomalyListItem>>(`/anomalies/?${params.toString()}`);
}

export function fetchImmediateActionAnomalies(search = "", page = 1, includeClosed = false) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("page_size", "10");

  if (search.trim()) {
    params.set("search", search.trim());
  }
  if (includeClosed) {
    params.set("include_closed", "true");
  }

  return apiRequest<PagedResponse<AnomalyListItem>>(`/anomalies/immediate-actions/?${params.toString()}`);
}

export function fetchAnomalyDetail(anomalyId: string) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/`);
}

export function fetchAnomalyRepetitionStudy(dateFrom: string) {
  const params = new URLSearchParams();
  params.set("date_from", dateFrom);
  return apiRequest<AnomalyRepetitionStudyResponse>(`/anomalies/repetition-study/?${params.toString()}`);
}

export function fetchAffectedOrders(filters: AffectedOrderFilters) {
  return apiRequest<AffectedOrderListResponse>(`/anomalies/affected-orders/?${affectedOrderParams(filters).toString()}`);
}

export async function downloadAffectedOrdersCsv(filters: AffectedOrderFilters) {
  const params = affectedOrderParams({ ...filters, page: 1, pageSize: 100 });
  params.set("export", "csv");
  const content = await apiRequest<string>(`/anomalies/affected-orders/?${params.toString()}`);
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "ordenes-afectadas.csv";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function reserveAnomalyCode() {
  return apiRequest<AnomalyCodeReservation>("/anomalies/reserve-code/", {
    method: "POST",
  });
}

export function createAnomaly(payload: AnomalyCreatePayload) {
  return apiRequest<AnomalyDetail>("/anomalies/", {
    method: "POST",
    body: payload,
  });
}

export function saveImmediateAction(anomalyId: string, payload: ImmediateActionPayload) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/immediate-action/`, {
    method: "POST",
    body: payload,
  });
}

export function saveObservationLoad(anomalyId: string, payload: ObservationLoadPayload) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/observation/load/`, {
    method: "POST",
    body: payload,
  });
}

export function saveObservationActionTaken(anomalyId: string, payload: ObservationActionPayload) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/observation/actions-taken/`, {
    method: "POST",
    body: payload,
  });
}

export function verifyObservationEffectiveness(anomalyId: string, payload: ObservationVerificationPayload) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/observation/effectiveness/`, {
    method: "POST",
    body: payload,
  });
}

export function uploadAnomalyAttachment(
  anomalyId: string,
  payload: {
    file: File;
    originalName?: string;
  },
) {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.originalName?.trim()) {
    formData.append("original_name", payload.originalName.trim());
  }
  return apiRequest<AnomalyAttachmentSummary>(`/anomalies/${anomalyId}/attachments/`, {
    method: "POST",
    body: formData,
  });
}

export function classifyAnomalyBySeverity(
  anomalyId: string,
  payload: {
    severity: string;
    classification_responsible?: string;
    classification_reason?: string;
  },
) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function unlockAnomalyClassificationChange(anomalyId: string) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/classification/unlock/`, {
    method: "POST",
  });
}
