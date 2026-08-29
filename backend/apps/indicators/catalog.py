from __future__ import annotations


INDICATOR_DEFINITIONS = (
    {
        "key": "anomalies-treated",
        "sequence": 1,
        "title": "Anomalias generadas y tratadas",
        "description": "Compara altas, resoluciones, pendientes y porcentaje de tratamiento por periodo.",
        "primary_date": "detected_at",
    },
    {
        "key": "treatments",
        "sequence": 2,
        "title": "Tratamientos",
        "description": "Mide tratamientos creados, completados, abiertos y su evolucion.",
        "primary_date": "created_at",
    },
    {
        "key": "anomalies-by-process",
        "sequence": 3,
        "title": "Anomalias por proceso",
        "description": "Distribuye cantidades y porcentajes por proceso con evolucion y Pareto.",
        "primary_date": "detected_at",
    },
    {
        "key": "finding-classification",
        "sequence": 4,
        "title": "Clasificacion de hallazgos",
        "description": "Analiza no conformidades, observaciones, OBS-TRT, mejoras e invalidas.",
        "primary_date": "classified_at",
    },
    {
        "key": "repetition-pareto",
        "sequence": 5,
        "title": "Repetitividad y Pareto",
        "description": "Identifica concentraciones por tipo, proceso, origen y orden afectada.",
        "primary_date": "detected_at",
    },
    {
        "key": "actions",
        "sequence": 6,
        "title": "Acciones",
        "description": "Controla estados, vencimientos y cumplimiento por responsable y proceso.",
        "primary_date": "created_at",
    },
    {
        "key": "effectiveness",
        "sequence": 7,
        "title": "Eficacia",
        "description": "Mide verificaciones eficaces, no eficaces, pendientes, vencidas y reaperturas.",
        "primary_date": "validated_at",
    },
    {
        "key": "affected-orders",
        "sequence": 8,
        "title": "Ordenes afectadas",
        "description": "Consolida ordenes, cantidades, procesos, evolucion y concentracion de afectaciones.",
        "primary_date": "detected_at",
    },
    {
        "key": "learned-lessons",
        "sequence": 9,
        "title": "Lecciones aprendidas",
        "description": "Mide cobertura de aprendizaje y modificaciones de procedimientos.",
        "primary_date": "saved_at",
    },
)


def indicator_catalog() -> list[dict]:
    return [dict(item) for item in INDICATOR_DEFINITIONS]


def indicator_definition(key: str) -> dict | None:
    return next((dict(item) for item in INDICATOR_DEFINITIONS if item["key"] == key), None)
