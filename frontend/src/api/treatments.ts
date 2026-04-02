import { apiRequest } from "./http";
import type {
  PagedResponse,
  TreatmentCandidate,
  TreatmentDetail,
  TreatmentParticipant,
  TreatmentRootCause,
  TreatmentSummary,
  TreatmentTask,
  TreatmentUpdatePayload,
  TreatmentWritePayload,
} from "./types";

export function fetchTreatments() {
  return apiRequest<PagedResponse<TreatmentSummary>>("/actions/treatments/");
}

export function fetchTreatmentDetail(treatmentId: string) {
  return apiRequest<TreatmentDetail>(`/actions/treatments/${treatmentId}/`);
}

export function createTreatment(payload: TreatmentWritePayload) {
  return apiRequest<TreatmentDetail>("/actions/treatments/", {
    method: "POST",
    body: payload,
  });
}

export function updateTreatment(treatmentId: string, payload: TreatmentUpdatePayload) {
  return apiRequest<TreatmentDetail>(`/actions/treatments/${treatmentId}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function fetchTreatmentCandidates() {
  return apiRequest<PagedResponse<TreatmentCandidate>>("/actions/treatments/candidates/");
}

export function addTreatmentAnomaly(treatmentId: string, anomalyId: string) {
  return apiRequest<TreatmentCandidate>(`/actions/treatments/${treatmentId}/anomalies/`, {
    method: "POST",
    body: { anomaly: anomalyId },
  });
}

export function addTreatmentParticipant(
  treatmentId: string,
  payload: { user: string; role?: string; note?: string },
) {
  return apiRequest<TreatmentParticipant>(`/actions/treatments/${treatmentId}/participants/`, {
    method: "POST",
    body: payload,
  });
}

export function addTreatmentRootCause(treatmentId: string, description: string) {
  return apiRequest<TreatmentRootCause>(`/actions/treatments/${treatmentId}/root-causes/`, {
    method: "POST",
    body: { description },
  });
}

export function addTreatmentTask(
  treatmentId: string,
  payload: {
    title: string;
    description?: string;
    root_cause?: string | null;
    responsible?: string | null;
    execution_date?: string | null;
    status?: string;
    anomaly_ids?: string[];
  },
) {
  return apiRequest<TreatmentTask>(`/actions/treatments/${treatmentId}/tasks/`, {
    method: "POST",
    body: payload,
  });
}

export function updateTreatmentTask(
  treatmentId: string,
  taskId: string,
  payload: {
    title?: string;
    description?: string;
    root_cause?: string | null;
    responsible?: string | null;
    execution_date?: string | null;
    status?: string;
    anomaly_ids?: string[];
  },
) {
  return apiRequest<TreatmentTask>(`/actions/treatments/${treatmentId}/tasks/${taskId}/`, {
    method: "PATCH",
    body: payload,
  });
}
