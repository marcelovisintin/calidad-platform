import { apiRequest } from "./http";
import type {
  AnomalyAttachmentSummary,
  AnomalyCodeReservation,
  AnomalyCreatePayload,
  AnomalyDetail,
  AnomalyListItem,
  AnomalyRepetitionStudyResponse,
  ImmediateActionPayload,
  ObservationActionPayload,
  ObservationLoadPayload,
  ObservationVerificationPayload,
  PagedResponse,
  WorkflowMetadata,
} from "./types";

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
