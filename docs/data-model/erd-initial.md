# ERD Inicial y Modelo de Datos Base

## Objetivo

Definir un modelo de datos inicial consistente con:

- sistema multiusuario
- operacion multi-sitio y multi-area
- workflow de anomalias
- acciones correctivas
- trazabilidad y auditoria

## Convenciones generales

- Todas las entidades transaccionales incluyen `created_at`, `created_by`, `updated_at`, `updated_by`.
- No se realiza hard delete sobre entidades de negocio.
- Los catalogos se inactivan mediante `is_active`.
- El usuario debe ser `CustomUser` desde el inicio.
- Las entidades criticas deben considerar control de concurrencia optimista con `row_version`.

## ERD conceptual inicial

```mermaid
erDiagram
    User ||--o{ UserRoleScope : has
    Role ||--o{ UserRoleScope : grants

    Site ||--o{ Area : contains
    Area ||--o{ Line : contains

    Site ||--o{ Anomaly : scopes
    Area ||--o{ Anomaly : owns
    Line o|--o{ Anomaly : locates
    User ||--o{ Anomaly : reports
    User ||--o{ Anomaly : owns
    AnomalyType ||--o{ Anomaly : classifies
    AnomalyOrigin ||--o{ Anomaly : originates
    Severity ||--o{ Anomaly : qualifies
    Priority ||--o{ Anomaly : prioritizes

    Anomaly ||--o{ AnomalyStatusHistory : tracks
    Anomaly ||--o{ AnomalyComment : logs
    Anomaly ||--o{ AnomalyAttachment : stores
    Anomaly ||--o| ActionPlan : has_active_plan

    ActionPlan ||--o{ ActionItem : contains
    ActionItem ||--o{ ActionEvidence : proves
    User ||--o{ ActionItem : assigned
    ActionType ||--o{ ActionItem : categorizes

    Notification ||--o{ NotificationRecipient : targets
    User ||--o{ NotificationRecipient : receives

    Anomaly ||--o{ AuditEvent : generates
    ActionItem ||--o{ AuditEvent : generates
    User ||--o{ AuditEvent : performs

    User {
        uuid id
        string username
        string email
        boolean is_active
    }

    Role {
        uuid id
        string code
        string name
    }

    UserRoleScope {
        uuid id
        uuid user_id
        uuid role_id
        uuid site_id
        uuid area_id
    }

    Site {
        uuid id
        string code
        string name
        boolean is_active
    }

    Area {
        uuid id
        uuid site_id
        string code
        string name
        boolean is_active
    }

    Line {
        uuid id
        uuid area_id
        string code
        string name
        boolean is_active
    }

    Anomaly {
        uuid id
        string code
        uuid site_id
        uuid area_id
        uuid line_id
        uuid reporter_id
        uuid owner_id
        uuid anomaly_type_id
        uuid anomaly_origin_id
        uuid severity_id
        uuid priority_id
        string current_status
        datetime detected_at
        datetime due_at
        datetime closed_at
    }

    AnomalyStatusHistory {
        uuid id
        uuid anomaly_id
        string from_status
        string to_status
        text reason
        uuid changed_by_id
        datetime changed_at
    }

    AnomalyComment {
        uuid id
        uuid anomaly_id
        text body
        uuid author_id
        datetime created_at
    }

    AnomalyAttachment {
        uuid id
        uuid anomaly_id
        string file_name
        string storage_path
        uuid uploaded_by_id
        datetime uploaded_at
    }

    ActionPlan {
        uuid id
        uuid anomaly_id
        string status
        uuid owner_id
        datetime approved_at
    }

    ActionItem {
        uuid id
        uuid action_plan_id
        uuid action_type_id
        uuid assigned_to_id
        string status
        date due_date
        datetime completed_at
    }

    ActionEvidence {
        uuid id
        uuid action_item_id
        string evidence_type
        string storage_path
        uuid created_by_id
        datetime created_at
    }

    Notification {
        uuid id
        string source_type
        uuid source_id
        string template_code
        string status
    }

    NotificationRecipient {
        uuid id
        uuid notification_id
        uuid user_id
        string channel
        string delivery_status
        datetime read_at
    }

    AuditEvent {
        uuid id
        string entity_type
        uuid entity_id
        string action
        uuid actor_id
        string request_id
        jsonb before_data
        jsonb after_data
        datetime created_at
    }

    AnomalyType {
        uuid id
        string code
        string name
    }

    AnomalyOrigin {
        uuid id
        string code
        string name
    }

    Severity {
        uuid id
        string code
        string name
    }

    Priority {
        uuid id
        string code
        string name
    }

    ActionType {
        uuid id
        string code
        string name
    }
```

## Restricciones recomendadas

### Unicidad

- `Site.code` unico
- `Area.code` unico por `site`
- `Line.code` unico por `area`
- `Role.code` unico
- `Anomaly.code` unico global
- `UserRoleScope` unico por `user + role + site + area`
- `NotificationRecipient` unico por `notification + user + channel`

### Integridad de negocio

- `Anomaly.closed_at` solo puede tener valor cuando `current_status = closed`
- `ActionItem.completed_at` solo puede tener valor cuando `status = completed`
- `ActionPlan` debe tener a lo sumo un plan activo por anomalia
- `AnomalyStatusHistory` es append-only
- `AuditEvent` es append-only

### Indices clave

- `Anomaly(current_status, priority_id, area_id)`
- `Anomaly(code)`
- `Anomaly(detected_at)`
- `ActionItem(status, due_date, assigned_to_id)`
- `AuditEvent(entity_type, entity_id, created_at)`
- `NotificationRecipient(user_id, delivery_status, read_at)`

## Observaciones de diseño

- `Anomaly` es el aggregate root y concentra el identificador funcional del caso.
- `ActionPlan` y `ActionItem` se modelan separados para evitar acoplar el workflow de ejecucion con la entidad principal.
- `AuditEvent` no reemplaza historiales de negocio especializados; los complementa.
- Los adjuntos solo guardan metadata en base; el binario vive en storage.
