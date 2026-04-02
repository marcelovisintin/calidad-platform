ROLE_OPERARIO = "OPERARIO"
ROLE_SUPERVISOR = "SUPERVISOR"
ROLE_CALIDAD = "CALIDAD"
ROLE_INGENIERIA = "INGENIERIA"
ROLE_ADMINISTRADOR = "ADMINISTRADOR"

ROLE_DEFINITIONS = {
    ROLE_OPERARIO: {
        "name": "Operario",
        "description": "Reporta anomalias y ejecuta acciones asignadas dentro de su sector.",
    },
    ROLE_SUPERVISOR: {
        "name": "Supervisor",
        "description": "Coordina anomalias de su sector y asigna acciones operativas.",
    },
    ROLE_CALIDAD: {
        "name": "Calidad",
        "description": "Clasifica, verifica eficacia y formaliza cierres del modulo.",
    },
    ROLE_INGENIERIA: {
        "name": "Ingenieria",
        "description": "Analiza causas y define acciones tecnicas y de mejora.",
    },
    ROLE_ADMINISTRADOR: {
        "name": "Administrador",
        "description": "Administra seguridad, usuarios y configuracion transversal.",
    },
}

PERMISSION_ADD_USER = "accounts.add_user"
PERMISSION_CHANGE_USER = "accounts.change_user"
PERMISSION_DELETE_USER = "accounts.delete_user"
PERMISSION_VIEW_USER = "accounts.view_user"

PERMISSION_CREATE_ANOMALY = "anomalies.add_anomaly"
PERMISSION_EDIT_ANOMALY = "anomalies.change_anomaly"
PERMISSION_VIEW_ANOMALY = "anomalies.view_anomaly"
PERMISSION_CLASSIFY_ANOMALY = "anomalies.classify_anomaly"
PERMISSION_ANALYZE_ANOMALY = "anomalies.analyze_anomaly"
PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY = "anomalies.verify_effectiveness_anomaly"
PERMISSION_CLOSE_ANOMALY = "anomalies.close_anomaly"
PERMISSION_CANCEL_ANOMALY = "anomalies.cancel_anomaly"
PERMISSION_REOPEN_ANOMALY = "anomalies.reopen_anomaly"
PERMISSION_VIEW_ALL_ANOMALY = "anomalies.view_all_anomaly"
PERMISSION_VIEW_SECTOR_ANOMALY = "anomalies.view_sector_anomaly"

PERMISSION_VIEW_ACTION_PLAN = "actions.view_actionplan"
PERMISSION_VIEW_ACTION_ITEM = "actions.view_actionitem"
PERMISSION_ASSIGN_ACTION = "actions.assign_action"
PERMISSION_EXECUTE_ACTION = "actions.execute_action"
PERMISSION_VERIFY_ACTION_EFFECTIVENESS = "actions.verify_action_effectiveness"

PERMISSION_VIEW_AUDIT = "audit.view_auditevent"

PERMISSION_DEFINITIONS = {
    PERMISSION_ADD_USER: {
        "app_label": "accounts",
        "model": "user",
        "codename": "add_user",
        "name": "Puede crear usuarios",
    },
    PERMISSION_CHANGE_USER: {
        "app_label": "accounts",
        "model": "user",
        "codename": "change_user",
        "name": "Puede editar usuarios",
    },
    PERMISSION_DELETE_USER: {
        "app_label": "accounts",
        "model": "user",
        "codename": "delete_user",
        "name": "Puede eliminar usuarios",
    },
    PERMISSION_VIEW_USER: {
        "app_label": "accounts",
        "model": "user",
        "codename": "view_user",
        "name": "Puede ver usuarios",
    },
    PERMISSION_CREATE_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "add_anomaly",
        "name": "Puede crear anomalias",
    },
    PERMISSION_EDIT_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "change_anomaly",
        "name": "Puede editar anomalias",
    },
    PERMISSION_VIEW_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "view_anomaly",
        "name": "Puede ver anomalias",
    },
    PERMISSION_CLASSIFY_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "classify_anomaly",
        "name": "Puede clasificar anomalias",
    },
    PERMISSION_ANALYZE_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "analyze_anomaly",
        "name": "Puede analizar anomalias",
    },
    PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "verify_effectiveness_anomaly",
        "name": "Puede verificar eficacia de anomalias",
    },
    PERMISSION_CLOSE_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "close_anomaly",
        "name": "Puede cerrar anomalias",
    },
    PERMISSION_CANCEL_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "cancel_anomaly",
        "name": "Puede anular anomalias",
    },
    PERMISSION_REOPEN_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "reopen_anomaly",
        "name": "Puede reabrir anomalias",
    },
    PERMISSION_VIEW_ALL_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "view_all_anomaly",
        "name": "Puede ver anomalias fuera de su sector segun alcance",
    },
    PERMISSION_VIEW_SECTOR_ANOMALY: {
        "app_label": "anomalies",
        "model": "anomaly",
        "codename": "view_sector_anomaly",
        "name": "Puede ver anomalias solo de su sector",
    },
    PERMISSION_VIEW_ACTION_PLAN: {
        "app_label": "actions",
        "model": "actionplan",
        "codename": "view_actionplan",
        "name": "Puede ver planes de accion",
    },
    PERMISSION_VIEW_ACTION_ITEM: {
        "app_label": "actions",
        "model": "actionitem",
        "codename": "view_actionitem",
        "name": "Puede ver acciones",
    },
    PERMISSION_ASSIGN_ACTION: {
        "app_label": "actions",
        "model": "actionitem",
        "codename": "assign_action",
        "name": "Puede asignar acciones",
    },
    PERMISSION_EXECUTE_ACTION: {
        "app_label": "actions",
        "model": "actionitem",
        "codename": "execute_action",
        "name": "Puede ejecutar acciones",
    },
    PERMISSION_VERIFY_ACTION_EFFECTIVENESS: {
        "app_label": "actions",
        "model": "actionitem",
        "codename": "verify_action_effectiveness",
        "name": "Puede verificar eficacia de acciones",
    },
    PERMISSION_VIEW_AUDIT: {
        "app_label": "audit",
        "model": "auditevent",
        "codename": "view_auditevent",
        "name": "Puede ver auditoria transversal",
    },
}

ROLE_PERMISSION_MATRIX = {
    ROLE_OPERARIO: [
        PERMISSION_CREATE_ANOMALY,
        PERMISSION_VIEW_ANOMALY,
        PERMISSION_VIEW_SECTOR_ANOMALY,
        PERMISSION_VIEW_ACTION_ITEM,
        PERMISSION_EXECUTE_ACTION,
    ],
    ROLE_SUPERVISOR: [
        PERMISSION_CREATE_ANOMALY,
        PERMISSION_EDIT_ANOMALY,
        PERMISSION_VIEW_ANOMALY,
        PERMISSION_VIEW_SECTOR_ANOMALY,
        PERMISSION_ANALYZE_ANOMALY,
        PERMISSION_VIEW_ACTION_PLAN,
        PERMISSION_VIEW_ACTION_ITEM,
        PERMISSION_ASSIGN_ACTION,
        PERMISSION_EXECUTE_ACTION,
        PERMISSION_VIEW_USER,
    ],
    ROLE_CALIDAD: [
        PERMISSION_CREATE_ANOMALY,
        PERMISSION_EDIT_ANOMALY,
        PERMISSION_VIEW_ANOMALY,
        PERMISSION_CLASSIFY_ANOMALY,
        PERMISSION_ANALYZE_ANOMALY,
        PERMISSION_VERIFY_EFFECTIVENESS_ANOMALY,
        PERMISSION_VIEW_ALL_ANOMALY,
        PERMISSION_CLOSE_ANOMALY,
        PERMISSION_CANCEL_ANOMALY,
        PERMISSION_REOPEN_ANOMALY,
        PERMISSION_VIEW_ACTION_PLAN,
        PERMISSION_VIEW_ACTION_ITEM,
        PERMISSION_ASSIGN_ACTION,
        PERMISSION_VERIFY_ACTION_EFFECTIVENESS,
        PERMISSION_VIEW_USER,
        PERMISSION_VIEW_AUDIT,
    ],
    ROLE_INGENIERIA: [
        PERMISSION_CREATE_ANOMALY,
        PERMISSION_EDIT_ANOMALY,
        PERMISSION_VIEW_ANOMALY,
        PERMISSION_ANALYZE_ANOMALY,
        PERMISSION_VIEW_ALL_ANOMALY,
        PERMISSION_VIEW_ACTION_PLAN,
        PERMISSION_VIEW_ACTION_ITEM,
        PERMISSION_ASSIGN_ACTION,
        PERMISSION_EXECUTE_ACTION,
        PERMISSION_VIEW_USER,
    ],
    ROLE_ADMINISTRADOR: sorted(PERMISSION_DEFINITIONS.keys()),
}
