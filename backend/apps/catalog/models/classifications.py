from django.db import models

from apps.core.models import ActiveCatalogModel


class AnomalyType(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Tipo de desvio"
        verbose_name_plural = "Tipos de desvio"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_anomaly_type_code")]


class AnomalyOrigin(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Imputacion de anomalia"
        verbose_name_plural = "Imputaciones de anomalia"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_anomaly_origin_code")]


class Severity(ActiveCatalogModel):
    requires_classification_responsible = models.BooleanField(default=True)
    closes_anomaly_as_invalid = models.BooleanField(default=False)

    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Severidad"
        verbose_name_plural = "Severidades"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_severity_code")]


class Priority(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Orden operativo"
        verbose_name_plural = "Orden operativo"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_priority_code")]


class ActionType(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Tipo de accion"
        verbose_name_plural = "Tipos de accion"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_action_type_code")]


class OrderType(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Tipo de orden afectada"
        verbose_name_plural = "Tipos de ordenes afectadas"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_order_type_code")]
