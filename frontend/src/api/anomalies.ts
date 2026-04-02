import { apiRequest } from "./http";
import type {
  AnomalyCreatePayload,
  AnomalyDetail,
  AnomalyListItem,
  PagedResponse,
  WorkflowMetadata,
} from "./types";

export function fetchWorkflowMetadata() {
  return apiRequest<WorkflowMetadata>("/anomalies/workflow-metadata/");
}

export function fetchMyAnomalies(reporterId?: string, search = "") {
  const params = new URLSearchParams();
  if (reporterId) {
    params.set("reporter", reporterId);
  }
  if (search.trim()) {
    params.set("search", search.trim());
  }
  const query = params.toString();
  return apiRequest<PagedResponse<AnomalyListItem>>(query ? `/anomalies/?${query}` : "/anomalies/");
}

export function fetchAnomalyDetail(anomalyId: string) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/`);
}

export function createAnomaly(payload: AnomalyCreatePayload) {
  return apiRequest<AnomalyDetail>("/anomalies/", {
    method: "POST",
    body: payload,
  });
}

export function classifyAnomalyBySeverity(anomalyId: string, severityId: string) {
  return apiRequest<AnomalyDetail>(`/anomalies/${anomalyId}/`, {
    method: "PATCH",
    body: {
      severity: severityId,
    },
  });
}
