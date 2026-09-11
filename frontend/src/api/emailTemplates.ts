import { apiRequest } from "./http";
import type { EmailTemplateDefinition, EmailTemplateUpdatePayload } from "./types";

const BASE_PATH = "/notifications/email-templates/";

export function fetchEmailTemplates() {
  return apiRequest<EmailTemplateDefinition[]>(BASE_PATH);
}

export function updateEmailTemplate(code: string, payload: EmailTemplateUpdatePayload) {
  return apiRequest<EmailTemplateDefinition>(`${BASE_PATH}${encodeURIComponent(code)}/`, {
    method: "PATCH",
    body: payload,
  });
}

export function resetEmailTemplate(code: string) {
  return apiRequest<EmailTemplateDefinition>(`${BASE_PATH}${encodeURIComponent(code)}/`, {
    method: "DELETE",
  });
}
