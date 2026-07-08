export type UUID = string;
export type ObservationResolutionPath = "OBSERVATION" | "TREATMENT";

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
  requires_classification_responsible?: boolean;
  closes_anomaly_as_invalid?: boolean;
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
  photo_url?: string;
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
  photo_url?: string;
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

export interface AccessLevelOption {
  value: "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";
  label: string;
}

export interface RoleOption {
  id: UUID;
  code: string;
  name: string;
  permissions: string[];
}

export interface UserScopeOption {
  key: string;
  label: string;
  description: string;
  permission_keys: string[];
}

export interface UserAccessOptions {
  access_levels: AccessLevelOption[];
  roles: RoleOption[];
  scope_options: UserScopeOption[];
}

export interface UserAccessProfile {
  id: UUID;
  username: string;
  full_name: string;
  email: string;
  access_level: AccessLevelOption["value"];
  primary_sector?: AreaSummary | null;
  role?: RoleOption | null;
  manual_scope_keys: string[];
  role_permissions: string[];
  effective_permissions: string[];
}

export interface UserAccessProfilePayload {
  access_level: AccessLevelOption["value"];
  role?: UUID | null;
  manual_scope_keys: string[];
}

export interface UserWritePayload {
  username: string;
  email: string;
  first_name?: string;
  last_name?: string;
  employee_code?: string;
  phone?: string;
  photo?: File | null;
  access_level?: "usuario_activo" | "mando_medio_activo" | "administrador" | "desarrollador";
  primary_sector?: UUID | null;
  is_active?: boolean;
    password?: string;
  }

export type UserImportMode = "create_only" | "update_existing" | "upsert";

export interface UserImportItem {
  row_number: number;
  legajo: string;
  nombre?: string;
  apellido?: string;
  email: string;
  usuario?: string;
  celular?: string;
  existing_user_id?: string;
  status: "create" | "update" | "skip" | "error";
  errors: string[];
  warnings: string[];
}

export interface UserImportPreview {
  mode: UserImportMode;
  summary: {
    total: number;
    new_users: number;
    existing_users: number;
    errors: number;
      skipped: number;
      duplicate_emails: number;
      duplicate_legajos: number;
      duplicate_usernames: number;
    };
  items: UserImportItem[];
}

export interface UserImportResult {
  summary: {
    total: number;
    created: number;
    updated: number;
    skipped: number;
    errors: number;
    warnings: number;
  };
  items: UserImportItem[];
  errors: string[];
  warnings: string[];
}
export interface LoginResponse {
  access: string;
  refresh: string;
  user: CurrentUser;
}

export interface DashboardSummaryStatus {
  key: string;
  label: string;
  count: number;
}

export interface DashboardSummaryUserRow {
  user: {
    id: UUID;
    name: string;
    username: string;
  };
  total: number;
  statuses: DashboardSummaryStatus[];
}

export interface DashboardSummaryCard {
  key: "anomalies" | "actions" | "treatments";
  title: string;
  description: string;
  total: number;
  statuses: DashboardSummaryStatus[];
  detail_rows?: DashboardSummaryUserRow[];
}

export interface DashboardSummaryResponse {
  scope: "admin" | "user";
  cards: DashboardSummaryCard[];
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
  anomaly?: {
    id: UUID;
    code: string;
    title: string;
    current_status: string;
    current_stage: string;
  } | null;
  treatments?: Array<{
    id: UUID;
    code: string;
    status: string;
  }>;
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


export interface AnomalyAttachmentSummary {
  id: UUID;
  original_name: string;
  content_type: string;
  file_url: string;
  uploaded_by?: UserSummary | null;
  created_at: string;
}

export interface TreatmentAnomalySummary {
  id: UUID;
  code: string;
  title: string;
  description: string;
  current_status: string;
  current_stage: string;
  affected_process?: string;
  reporter?: UserSummary | null;
  area?: CatalogSummary | null;
  imputed_area?: CatalogSummary | null;
  anomaly_origin?: CatalogSummary | null;
  detected_at?: string;
  attachments: AnomalyAttachmentSummary[];
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

export interface TreatmentEvidence {
  id: UUID;
  original_name: string;
  content_type: string;
  note?: string;
  file_url: string;
  uploaded_by?: UserSummary | null;
  created_at: string;
}

export interface TreatmentLearnedLessonEvidence {
  id: UUID;
  original_name: string;
  content_type: string;
  file_url: string;
  uploaded_by?: UserSummary | null;
  created_at: string;
}

export interface TreatmentLearnedLesson {
  id: UUID;
  has_learning: boolean | null;
  learned_text: string;
  no_learning_reason: string;
  procedure_modified: boolean | null;
  procedure_modification_notes: string;
  saved_by?: UserSummary | null;
  saved_at?: string | null;
  evidences: TreatmentLearnedLessonEvidence[];
  created_at: string;
  updated_at: string;
}

export interface TreatmentLearnedLessonPayload {
  has_learning: boolean;
  learned_text?: string;
  no_learning_reason?: string;
  procedure_modified: boolean;
  procedure_modification_notes?: string;
  evidences?: File[];
}

export interface TreatmentTaskEvidence {
  id: UUID;
  original_name: string;
  content_type: string;
  note?: string;
  file_url: string;
  uploaded_by?: UserSummary | null;
  created_at: string;
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
  root_causes: TreatmentTaskHistoryRootCause[];
  is_overdue?: boolean;
  anomaly_links: TreatmentTaskAnomalyLink[];
  evidences: TreatmentTaskEvidence[];
  created_at: string;
  updated_at: string;
}


export interface TreatmentTaskHistoryRootCause {
  id: UUID;
  sequence: number;
  description: string;
}

export interface TreatmentTaskHistoryTreatment {
  id: UUID;
  code: string;
  status: string;
  primary_anomaly: TreatmentAnomalySummary;
}

export interface TreatmentTaskHistory {
  id: UUID;
  code: string;
  title: string;
  description: string;
  status: string;
  execution_date?: string | null;
  is_overdue?: boolean;
  responsible?: UserSummary | null;
  treatment: TreatmentTaskHistoryTreatment;
  anomalies: TreatmentAnomalySummary[];
  root_cause?: TreatmentTaskHistoryRootCause | null;
  root_causes: TreatmentTaskHistoryRootCause[];
  evidences: TreatmentTaskEvidence[];
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
  treatment_location?: string;
  method_used?: string;
  observations?: string;
  effectiveness_evaluation_date?: string | null;
  effectiveness_responsible?: UserSummary | null;
  effectiveness_validation_result?: "" | "effective" | "not_effective";
  effectiveness_validated_at?: string | null;
  effectiveness_validated_by?: UserSummary | null;
  effectiveness_validation_comment?: string;
  validation_state?: {
    available: boolean;
    blockers: string[];
  };
  is_locked?: boolean;
  learned_lesson?: TreatmentLearnedLesson | null;
  primary_anomaly: TreatmentAnomalySummary;
  created_at: string;
  updated_at: string;
}

export interface TreatmentAuditEvent {
  id: UUID;
  action: string;
  actor?: UserSummary | null;
  created_at: string;
}

export interface TreatmentValidationPayload {
  result: "effective" | "not_effective";
  comment?: string;
}

export interface TreatmentDetail extends TreatmentSummary {
  participants: TreatmentParticipant[];
  anomaly_links: TreatmentAnomalyLink[];
  root_causes: TreatmentRootCause[];
  tasks: TreatmentTask[];
  evidences: TreatmentEvidence[];
  audit_events?: TreatmentAuditEvent[];
  row_version: number;
}

export interface TreatmentCandidate extends TreatmentAnomalySummary {}

export interface TreatmentWritePayload {
  primary_anomaly: UUID;
  force_create_new?: boolean;
  scheduled_for?: string | null;
  treatment_location?: string;
  status?: "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";
  method_used?: "" | "five_whys" | "6m" | "ishikawa" | "a3" | "8d" | "other";
  observations?: string;
}

export interface TreatmentUpdatePayload {
  scheduled_for?: string | null;
  treatment_location?: string;
  status?: "pending" | "scheduled" | "in_progress" | "completed" | "cancelled";
  method_used?: "" | "five_whys" | "6m" | "ishikawa" | "a3" | "8d" | "other";
  observations?: string;
  effectiveness_evaluation_date?: string | null;
  effectiveness_responsible?: UUID | null;
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
  imputed_area?: AreaSummary | null;
  line?: CatalogSummary | null;
  reporter?: UserSummary | null;
  owner?: UserSummary | null;
  current_responsible?: UserSummary | null;
  anomaly_type?: CatalogSummary;
  anomaly_origin?: CatalogSummary;
  severity?: CatalogSummary;
  priority?: CatalogSummary;
  can_modify_classification?: boolean;
  can_unlock_classification?: boolean;
  is_locked_by_effective_treatment?: boolean;
  classification_change_count?: number;
  classification_change_unlocked?: boolean;
  observation_resolution_path?: ObservationResolutionPath | null;
  manufacturing_order_number?: string;
  affected_quantity?: number | null;
  affected_process?: string;
  due_at?: string | null;
  closed_at?: string | null;
  reopened_count?: number;
}

export interface AnomalyRepetitionStudyBucket {
  type_id: UUID;
  type_name: string;
  count: number;
}

export interface AnomalyRepetitionStudySectorBucket extends AnomalyRepetitionStudyBucket {
  sector_id: UUID;
  sector_name: string;
  finding_type_id: UUID | "";
  finding_type_name: string;
}

export interface AnomalyRepetitionStudyItem {
  id: UUID;
  code: string;
  title: string;
  observations: string;
  anomaly_type: {
    id: UUID;
    name: string;
  };
  sector: {
    id: UUID;
    name: string;
  };
  finding_type: {
    id: UUID | "";
    name: string;
  };
  registered_at: string;
}

export interface AnomalyRepetitionStudyResponse {
  date_from: string;
  date_to: string;
  total: number;
  by_type: AnomalyRepetitionStudyBucket[];
  by_type_sector: AnomalyRepetitionStudySectorBucket[];
  anomalies: AnomalyRepetitionStudyItem[];
}

export interface AnomalyStatusHistory {
  id: UUID;
  from_status: string;
  to_status: string;
  from_stage: string;
  to_stage: string;
  comment: string;
  evidence_note?: string;
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

export interface AnomalyImmediateAction {
  id: UUID;
  responsible?: UserSummary | null;
  action_date: string;
  action_completed_at?: string | null;
  effectiveness_due_at?: string | null;
  effectiveness_verified_at?: string | null;
  effectiveness_is_effective?: boolean | null;
  observation: string;
  actions_taken: string;
  effectiveness_comment?: string;
  closure_comment?: string;
}



export interface AnomalyTreatmentTaskSummary {
  id: UUID;
  code?: string;
  title: string;
  description: string;
  status: string;
  execution_date?: string | null;
  is_overdue?: boolean;
  responsible?: UserSummary | null;
  treatment?: {
    id: UUID;
    code: string;
    status: string;
  } | null;
  root_cause_description?: string;
}

export interface AnomalyTreatmentLearnedLessonSummary {
  treatment_id: UUID;
  treatment_code: string;
  saved_by?: UserSummary | null;
  saved_at?: string | null;
  has_learning: boolean | null;
  learned_text: string;
  no_learning_reason: string;
  procedure_modified: boolean | null;
  procedure_modification_notes: string;
  evidences: TreatmentLearnedLessonEvidence[];
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
  attachments: AnomalyAttachmentSummary[];
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
  immediate_action?: AnomalyImmediateAction | null;
  action_plans: ActionPlanSummary[];
  treatment_tasks: AnomalyTreatmentTaskSummary[];
  learned_lessons: AnomalyTreatmentLearnedLessonSummary[];
  created_at: string;
  updated_at: string;
  row_version: number;
}

export interface ImmediateActionPayload {
  responsible: UUID;
  action_date: string;
  observation: string;
  action_completed_at?: string | null;
  effectiveness_due_at?: string | null;
  actions_taken?: string;
  effectiveness_verified_at?: string | null;
  effectiveness_is_effective?: boolean | null;
  effectiveness_comment?: string;
  closure_comment?: string;
}

export interface ObservationLoadPayload {
  responsible: UUID;
  action_date: string;
  observation: string;
}

export interface ObservationActionPayload {
  action_completed_at: string;
  actions_taken: string;
  effectiveness_due_at: string;
}

export interface ObservationVerificationPayload {
  effectiveness_verified_at: string;
  effectiveness_is_effective: boolean;
  effectiveness_comment?: string;
  closure_comment?: string;
}


export interface AnomalyCodeReservation {
  id: UUID;
  code: string;
  year: number;
  sequence: number;
  created_at: string;
  reserved_by?: UserSummary | null;
}
export interface AnomalyCreatePayload {
  title: string;
  description: string;
  site: UUID;
  area: UUID;
  imputed_area?: UUID;
  anomaly_type: UUID;
  anomaly_origin: UUID;
  priority?: UUID;
  detected_at: string;
  manufacturing_order_number?: string;
  affected_quantity?: number;
  affected_process?: string;
  code_reservation_id?: UUID;
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




















