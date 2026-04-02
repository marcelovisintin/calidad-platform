export type UUID = string;

export interface SiteSummary {
  id: UUID;
  code: string;
  name: string;
}

export interface AreaSummary {
  id: UUID;
  code: string;
  name: string;
  site?: SiteSummary;
}

export interface CatalogSummary {
  id: UUID;
  code: string;
  name: string;
}

export type CatalogEntity =
  | "sites"
  | "areas"
  | "lines"
  | "anomaly-types"
  | "anomaly-origins"
  | "severities"
  | "priorities"
  | "action-types";

export interface CatalogManagementItem extends CatalogSummary {
  is_active: boolean;
  display_order: number;
  created_at: string;
  updated_at: string;
  row_version: number;
  site?: SiteSummary | null;
  site_id?: UUID | null;
  area?: AreaSummary | null;
  area_id?: UUID | null;
}

export interface UserSummary {
  id: UUID;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
}

export interface CurrentUser extends UserSummary {
  employee_code?: string;
  access_level: "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";
  must_change_password: boolean;
  password_changed_at?: string | null;
  sector?: AreaSummary | null;
  is_active: boolean;
  date_joined: string;
  last_login?: string | null;
  last_activity_at?: string | null;
  role_codes: string[];
  role_scopes: Array<{
    id: UUID;
    role: CatalogSummary;
    site?: SiteSummary | null;
    area?: AreaSummary | null;
  }>;
  permissions: string[];
}


export interface UserDirectoryItem {
  id: UUID;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  employee_code?: string;
  phone?: string;
  access_level: "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";
  must_change_password: boolean;
  password_changed_at?: string | null;
  sector?: AreaSummary | null;
  primary_sector_id?: UUID | null;
  is_active: boolean;
  is_staff: boolean;
  date_joined: string;
  last_login?: string | null;
  last_activity_at?: string | null;
  role_codes: string[];
}

export interface UserWritePayload {
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  employee_code?: string;
  phone?: string;
  access_level?: "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";
  primary_sector?: UUID | null;
  is_active?: boolean;
  password?: string;
}
export interface LoginResponse {
  access: string;
  refresh: string;
  user: CurrentUser;
}

export interface ApiRootResponse {
  service: string;
  version: string;
  status: string;
  endpoints: Record<string, string>;
}

export interface PagedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface WorkflowMetadata {
  statuses: Record<string, string>;
  stages: Record<string, string>;
  analysis_methods: Record<string, string>;
  participant_roles: Record<string, string>;
  comment_types: Record<string, string>;
}

export interface ActionItemSummary {
  id: UUID;
  code?: string;
  title: string;
  description: string;
  status: string;
  effective_status?: string;
  is_overdue?: boolean;
  due_date?: string | null;
  completed_at?: string | null;
  is_mandatory: boolean;
  sequence: number;
  expected_evidence?: string;
  closure_comment?: string;
  action_type?: CatalogSummary;
  priority?: CatalogSummary | null;
  assigned_to?: UserSummary | null;
  created_at?: string;
  updated_at?: string;
  row_version?: number;
}

export interface ActionEvidence {
  id: UUID;
  evidence_type?: string;
  note?: string;
  file_url?: string;
  created_at: string;
}

export interface ActionItemHistory {
  id: UUID;
  event_type: string;
  from_status?: string | null;
  to_status?: string | null;
  comment: string;
  changed_at: string;
  changed_by?: UserSummary | null;
  snapshot_data?: Record<string, unknown>;
}

export interface ActionItemDetail extends ActionItemSummary {
  evidences: ActionEvidence[];
  history: ActionItemHistory[];
}

export interface ActionPlanSummary {
  id: UUID;
  anomaly?: {
    id: UUID;
    code: string;
    title: string;
    current_status: string;
    current_stage: string;
  };
  owner?: UserSummary | null;
  status: string;
  approved_at?: string | null;
  items_count?: number;
  pending_items_count?: number;
  overdue_items_count?: number;
  items?: ActionItemSummary[];
  created_at?: string;
  updated_at?: string;
  row_version?: number;
}


export interface TreatmentAnomalySummary {
  id: UUID;
  code: string;
  title: string;
  description: string;
  current_status: string;
  current_stage: string;
  reporter?: UserSummary | null;
  area?: CatalogSummary | null;
  anomaly_origin?: CatalogSummary | null;
  detected_at?: string;
}

export interface TreatmentParticipant {
  id: UUID;
  user?: UserSummary | null;
  role: string;
  note?: string;
  created_at: string;
  updated_at: string;
}

export interface TreatmentAnomalyLink {
  id: UUID;
  anomaly: TreatmentAnomalySummary;
  is_primary: boolean;
  created_at: string;
}

export interface TreatmentTaskAnomalyLink {
  id: UUID;
  anomaly: TreatmentAnomalySummary;
}

export interface TreatmentTask {
  id: UUID;
  code: string;
  title: string;
  description: string;
  status: string;
  execution_date?: string | null;
  responsible?: UserSummary | null;
  root_cause?: UUID | null;
  is_overdue?: boolean;
  anomaly_links: TreatmentTaskAnomalyLink[];
  created_at: string;
  updated_at: string;
}

export interface TreatmentRootCause {
  id: UUID;
  sequence: number;
  description: string;
  tasks: TreatmentTask[];
  created_at: string;
  updated_at: string;
}

export interface TreatmentSummary {
  id: UUID;
  code: string;
  status: string;
  scheduled_for?: string | null;
  method_used?: string;
  observations?: string;
  primary_anomaly: TreatmentAnomalySummary;
  created_at: string;
  updated_at: string;
}

export interface TreatmentDetail extends TreatmentSummary {
  participants: TreatmentParticipant[];
  anomaly_links: TreatmentAnomalyLink[];
  root_causes: TreatmentRootCause[];
  tasks: TreatmentTask[];
  row_version: number;
}

export interface TreatmentCandidate extends TreatmentAnomalySummary {}

export interface TreatmentWritePayload {
  primary_anomaly: UUID;
  scheduled_for?: string | null;
  status?: "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";
  method_used?: "" | "five_whys" | "6m" | "ishikawa" | "a3" | "8d" | "other";
  observations?: string;
}

export interface TreatmentUpdatePayload {
  scheduled_for?: string | null;
  status?: "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";
  method_used?: "" | "five_whys" | "6m" | "ishikawa" | "a3" | "8d" | "other";
  observations?: string;
}

export interface NotificationInboxItem {
  id: UUID;
  title: string;
  body: string;
  category: string;
  is_task: boolean;
  task_type?: string;
  action_url?: string;
  due_at?: string | null;
  delivery_status: string;
  read_at?: string | null;
  task_status?: string | null;
  assigned_at?: string | null;
  resolved_at?: string | null;
  source_type?: string;
  source_id?: UUID;
  context_data?: Record<string, unknown>;
  created_at: string;
}

export interface NotificationInboxSummary {
  total: number;
  unread: number;
  tasks_total: number;
  tasks_pending: number;
  tasks_in_progress: number;
  tasks_overdue: number;
}

export interface AnomalyListItem {
  id: UUID;
  code: string;
  title: string;
  current_status: string;
  current_stage: string;
  detected_at: string;
  site?: SiteSummary;
  area?: AreaSummary;
  line?: CatalogSummary | null;
  reporter?: UserSummary | null;
  owner?: UserSummary | null;
  current_responsible?: UserSummary | null;
  anomaly_type?: CatalogSummary;
  anomaly_origin?: CatalogSummary;
  severity?: CatalogSummary;
  priority?: CatalogSummary;
  manufacturing_order_number?: string;
  affected_quantity?: number | null;
  affected_process?: string;
  due_at?: string | null;
  closed_at?: string | null;
  reopened_count?: number;
}

export interface AnomalyStatusHistory {
  id: UUID;
  from_status: string;
  to_status: string;
  from_stage: string;
  to_stage: string;
  comment: string;
  changed_at: string;
  changed_by?: UserSummary | null;
}

export interface AnomalyComment {
  id: UUID;
  body: string;
  comment_type: string;
  author?: UserSummary | null;
  created_at: string;
}

export interface AnomalyProposal {
  id: UUID;
  title: string;
  description: string;
  proposed_by?: UserSummary | null;
  proposed_at: string;
  is_selected: boolean;
  sequence: number;
}

export interface AnomalyInitialVerification {
  id: UUID;
  verified_by?: UserSummary | null;
  verified_at: string;
  material_checked: boolean;
  machine_checked: boolean;
  method_checked: boolean;
  manpower_checked: boolean;
  milieu_checked: boolean;
  measurement_checked: boolean;
  material_notes?: string;
  machine_notes?: string;
  method_notes?: string;
  manpower_notes?: string;
  milieu_notes?: string;
  measurement_notes?: string;
  summary?: string;
}

export interface AnomalyClassification {
  id: UUID;
  classified_by?: UserSummary | null;
  classified_at: string;
  containment_required: boolean;
  requires_action_plan: boolean;
  requires_effectiveness_verification: boolean;
  impact_scope?: string;
  summary?: string;
}

export interface AnomalyCauseAnalysis {
  id: UUID;
  analyzed_by?: UserSummary | null;
  analyzed_at: string;
  method_used: string;
  immediate_cause?: string;
  root_cause?: string;
  summary?: string;
}

export interface AnomalyEffectivenessCheck {
  id: UUID;
  verified_by?: UserSummary | null;
  verified_at: string;
  is_effective: boolean;
  evidence_summary?: string;
  comment?: string;
  recommended_stage?: string;
}

export interface AnomalyLearning {
  id: UUID;
  recorded_by?: UserSummary | null;
  recorded_at: string;
  standardization_actions?: string;
  lessons_learned?: string;
  document_changes?: string;
  shared_with?: string;
  shared_at?: string | null;
}

export interface AnomalyDetail extends AnomalyListItem {
  description: string;
  duplicate_of?: AnomalyListItem | null;
  last_transition_at?: string | null;
  containment_summary?: string;
  classification_summary?: string;
  root_cause_summary?: string;
  resolution_summary?: string;
  result_summary?: string;
  effectiveness_summary?: string;
  closure_comment?: string;
  cancellation_reason?: string;
  comments: AnomalyComment[];
  attachments: Array<{
    id: UUID;
    original_name: string;
    content_type: string;
    file_url: string;
    uploaded_by?: UserSummary | null;
    created_at: string;
  }>;
  participants: Array<{
    id: UUID;
    user?: UserSummary | null;
    role: string;
    note?: string;
    created_at: string;
    updated_at: string;
  }>;
  proposals: AnomalyProposal[];
  effectiveness_checks: AnomalyEffectivenessCheck[];
  status_history: AnomalyStatusHistory[];
  initial_verification?: AnomalyInitialVerification | null;
  classification?: AnomalyClassification | null;
  cause_analysis?: AnomalyCauseAnalysis | null;
  learning?: AnomalyLearning | null;
  action_plans: ActionPlanSummary[];
  created_at: string;
  updated_at: string;
  row_version: number;
}

export interface AnomalyCreatePayload {
  title: string;
  description: string;
  site: UUID;
  area: UUID;
  anomaly_type: UUID;
  anomaly_origin: UUID;
  priority: UUID;
  detected_at: string;
  manufacturing_order_number?: string;
  affected_quantity?: number;
  affected_process?: string;
}

export interface CatalogBootstrap {
  source?: string;
  generatedAt?: string | null;
  sites: SiteSummary[];
  areas: AreaSummary[];
  anomalyTypes: CatalogSummary[];
  anomalyOrigins: CatalogSummary[];
  severities: CatalogSummary[];
  priorities: CatalogSummary[];
  actionTypes: CatalogSummary[];
}








