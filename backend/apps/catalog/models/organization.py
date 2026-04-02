from django.db import models

from apps.core.models import ActiveCatalogModel


class Site(ActiveCatalogModel):
    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Sitio"
        verbose_name_plural = "Sitios"
        constraints = [models.UniqueConstraint(fields=["code"], name="catalog_unique_site_code")]


class Area(ActiveCatalogModel):
    site = models.ForeignKey("catalog.Site", on_delete=models.PROTECT, related_name="areas")

    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Area"
        verbose_name_plural = "Areas"
        constraints = [models.UniqueConstraint(fields=["site", "code"], name="cat_area_code_site_uq")]


class Line(ActiveCatalogModel):
    area = models.ForeignKey("catalog.Area", on_delete=models.PROTECT, related_name="lines")

    class Meta(ActiveCatalogModel.Meta):
        verbose_name = "Linea"
        verbose_name_plural = "Lineas"
        constraints = [models.UniqueConstraint(fields=["area", "code"], name="cat_line_code_area_uq")]
