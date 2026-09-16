import { apiRequest } from "./http";
import type {
  PagedResponse,
  TreatmentDetail,
  TreatmentEvidence,
  TreatmentLearnedLessonPayload,
  TreatmentParticipant,
  TreatmentParticipantOption,
  TreatmentRootCause,
  TreatmentSummary,
  TreatmentTask,
  TreatmentTaskEvidence,
  TreatmentTaskHistory,
  TreatmentUpdatePayload,
  TreatmentValidationPayload,
  TreatmentWritePayload,
} from "./types";

export function fetchTreatments(page = 1, search = "", options: { validationReady?: boolean } = {}) {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (search.trim()) {
    params.set("search", search.trim());
  }
  if (options.validationReady) {
    params.set("validation_ready", "1");
  }
  return apiRequest<PagedResponse<TreatmentSummary>>(`/actions/treatments/?${params.toString()}`);
}

export function fetchTreatmentTracking(filters: {
  page?: number;
  code?: string;
  user?: string;
  process?: string;
} = {}) {
  const params = new URLSearchParams({
    page: String(filters.page ?? 1),
    page_size: "10",
  });
  if (filters.code?.trim()) {
    params.set("code", filters.code.trim());
  }
  if (filters.user?.trim()) {
    params.set("user", filters.user.trim());
  }
  if (filters.process?.trim()) {
    params.set("process", filters.process.trim());
  }
  return apiRequest<PagedResponse<TreatmentSummary>>(`/actions/treatment-tracking/?${params.toString()}`);
}

export function fetchTreatmentTrackingDetail(treatmentId: string) {
  return apiRequest<TreatmentDetail>(`/actions/treatment-tracking/${treatmentId}/`);
}

export function fetchLearnedLessons(page = 1, search = "") {
  const params = new URLSearchParams({ page: String(page), page_size: "10" });
  if (search.trim()) {
    params.set("search", search.trim());
  }
  return apiRequest<PagedResponse<TreatmentSummary>>(`/actions/learned-lessons/?${params.toString()}`);
}

export function saveTreatmentLearnedLesson(treatmentId: string, payload: TreatmentLearnedLessonPayload) {
  const formData = new FormData();
  formData.append("has_learning", String(payload.has_learning));
  formData.append("learned_text", payload.learned_text ?? "");
  formData.append("no_learning_reason", payload.no_learning_reason ?? "");
  formData.append("procedure_modified", String(payload.procedure_modified));
  formData.append("procedure_modification_notes", payload.procedure_modification_notes ?? "");
  formData.append("confirm_modification", String(payload.confirm_modification ?? false));
  (payload.evidences ?? []).forEach((file) => {
    formData.append("evidences", file);
  });
  return apiRequest<TreatmentSummary>(`/actions/learned-lessons/${treatmentId}/`, {
    method: "PATCH",
    body: formData,
  });
}

export function sendTreatmentLessonForPublication(treatmentId: string) {
  return apiRequest<TreatmentSummary>(`/actions/learned-lessons/${treatmentId}/send-for-publication/`, { method: "POST" });
}

export function publishTreatmentLesson(treatmentId: string) {
  return apiRequest<TreatmentSummary>(`/actions/learned-lessons/${treatmentId}/publish/`, { method: "POST" });
}

export function createLessonDerivedAction(treatmentId: string, payload: {
  title: string; description: string; responsible: string; execution_date: string;
}) {
  return apiRequest<TreatmentSummary>(`/actions/learned-lessons/${treatmentId}/derived-actions/`, {
    method: "POST", body: payload,
  });
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

export function deleteEmptyTreatment(code: string) {
  return apiRequest<{ code: string }>("/actions/treatments/delete-empty/", {
    method: "POST",
    body: { code },
  });
}

export function confirmTreatmentConvocation(
  treatmentId: string,
  payload: { scheduled_for: string; treatment_location?: string },
) {
  return apiRequest<TreatmentDetail>(`/actions/treatments/${treatmentId}/confirm-convocation/`, {
    method: "POST",
    body: payload,
  });
}

export function fetchTreatmentParticipantOptions(treatmentId: string) {
  return apiRequest<TreatmentParticipantOption[]>(`/actions/treatments/${treatmentId}/participant-options/`);
}

export function validateTreatmentEffectiveness(treatmentId: string, payload: TreatmentValidationPayload) {
  return apiRequest<TreatmentDetail>(`/actions/treatments/${treatmentId}/validation/`, {
    method: "POST",
    body: payload,
  });
}

export function fetchOpenTreatmentOptions(anomalyId: string) {
  const params = new URLSearchParams({ anomaly: anomalyId });
  return apiRequest<TreatmentSummary[]>(`/actions/treatments/open-options/?${params.toString()}`);
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

export function removeTreatmentParticipant(treatmentId: string, participantId: string) {
  return apiRequest<void>(`/actions/treatments/${treatmentId}/participants/${participantId}/remove/`, {
    method: "POST",
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
    root_cause_ids?: string[];
    responsible?: string | null;
    execution_date?: string | null;
    status?: string;
    evidence_note?: string;
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
    root_cause_ids?: string[];
    responsible?: string | null;
    execution_date?: string | null;
    status?: string;
    evidence_note?: string;
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
