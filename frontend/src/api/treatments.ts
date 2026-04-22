import { apiRequest } from "./http";
import type {
  PagedResponse,
  TreatmentCandidate,
  TreatmentDetail,
  TreatmentEvidence,
  TreatmentParticipant,
  TreatmentRootCause,
  TreatmentSummary,
  TreatmentTask,
  TreatmentTaskEvidence,
  TreatmentTaskHistory,
  TreatmentUpdatePayload,
  TreatmentWritePayload,
} from "./types";

export function fetchTreatments(page = 1, search = "") {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (search.trim()) {
    params.set("search", search.trim());
  }
  return apiRequest<PagedResponse<TreatmentSummary>>(`/actions/treatments/?${params.toString()}`);
}

export function fetchTreatmentTasksHistory(filters: {
  page?: number;
  q?: string;
  anomaly?: string;
  treatment?: string;
  completedOn?: string;
  performedBy?: string;
  status?: string;
} = {}) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: "10",
  });

  if (filters.q?.trim()) {
    params.set("q", filters.q.trim());
  }
  if (filters.anomaly?.trim()) {
    params.set("anomaly", filters.anomaly.trim());
  }
  if (filters.treatment?.trim()) {
    params.set("treatment", filters.treatment.trim());
  }
  if (filters.completedOn?.trim()) {
    params.set("completed_on", filters.completedOn.trim());
  }
  if (filters.performedBy?.trim()) {
    params.set("performed_by", filters.performedBy.trim());
  }
  if (filters.status?.trim()) {
    params.set("status", filters.status.trim());
  }

  return apiRequest<PagedResponse<TreatmentTaskHistory>>(`/actions/treatments/tasks-history/?${params.toString()}`);
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

export function fetchTreatmentCandidates(filters: {
  page?: number;
  pageSize?: number;
  treatmentId?: string;
  anomaly?: string;
  sector?: string;
  area?: string;
  user?: string;
  dateFrom?: string;
  dateTo?: string;
} = {}) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: String(filters.pageSize ?? 100),
  });

  if (filters.treatmentId?.trim()) {
    params.set("treatment", filters.treatmentId.trim());
  }
  if (filters.anomaly?.trim()) {
    params.set("anomaly", filters.anomaly.trim());
  }
  if (filters.sector?.trim()) {
    params.set("sector", filters.sector.trim());
  }
  if (filters.area?.trim()) {
    params.set("area", filters.area.trim());
  }
  if (filters.user?.trim()) {
    params.set("user", filters.user.trim());
  }
  if (filters.dateFrom?.trim()) {
    params.set("date_from", filters.dateFrom.trim());
  }
  if (filters.dateTo?.trim()) {
    params.set("date_to", filters.dateTo.trim());
  }

  return apiRequest<PagedResponse<TreatmentCandidate>>(`/actions/treatments/candidates/?${params.toString()}`);
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

export function addTreatmentEvidence(
  treatmentId: string,
  payload: {
    file: File;
    note?: string;
  },
) {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.note?.trim()) {
    formData.append("note", payload.note.trim());
  }
  return apiRequest<TreatmentEvidence>(`/actions/treatments/${treatmentId}/evidences/`, {
    method: "POST",
    body: formData,
  });
}

export function addTreatmentTaskEvidence(
  treatmentId: string,
  taskId: string,
  payload: {
    file: File;
    note?: string;
  },
) {
  const formData = new FormData();
  formData.append("file", payload.file);
  if (payload.note?.trim()) {
    formData.append("note", payload.note.trim());
  }
  return apiRequest<TreatmentTaskEvidence>(`/actions/treatments/${treatmentId}/tasks/${taskId}/evidences/`, {
    method: "POST",
    body: formData,
  });
}
