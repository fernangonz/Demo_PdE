"""Capa de acceso a datos — independiente de modelos e interfaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from core.data_loader import (
    DATA_DIRS,
    _normalizar,
    cargar_configuracion_puerto,
    cargar_datos_clima,
    cargar_relacion_modelos_activos_indicadores,
    cargar_umbrales_curvas_dano,
    relacion_impactos_desde_lista_master,
)


@dataclass
class RepositorioDatos:
    """Fuente única de datos para modelos y UI.

    Ejemplo::

        repo = RepositorioDatos.cargar()
        clima = repo.info_clima
        config = repo.config_puerto
    """

    info_clima: dict
    config_puerto: pd.DataFrame
    relacion_impactos: pd.DataFrame
    relacion_modelos: pd.DataFrame
    umbrales_por_hoja: dict[str, pd.DataFrame]
    umbrales_lista_master: pd.DataFrame | None = None
    rutas: dict[str, str] = field(default_factory=dict)

    @classmethod
    def cargar(cls, data_dirs: list[Path] | None = None) -> RepositorioDatos:
        dirs = data_dirs or DATA_DIRS
        info_clima = cargar_datos_clima(dirs)
        config_puerto, info_cfg = cargar_configuracion_puerto(dirs)
        relacion_modelos, info_rmod = cargar_relacion_modelos_activos_indicadores(dirs)
        umbrales, info_umb = cargar_umbrales_curvas_dano(dirs)
        lista_master = info_umb.get("lista_impactos_indicador")
        relacion = relacion_impactos_desde_lista_master(lista_master)
        hoja_im = next(
            (
                h
                for h in info_umb.get("hojas_excluidas", [])
                if _normalizar(h).startswith("listrelacion impactos")
            ),
            "ListRelacion impactos-indicador",
        )
        return cls(
            info_clima=info_clima,
            config_puerto=config_puerto,
            relacion_impactos=relacion,
            relacion_modelos=relacion_modelos,
            umbrales_por_hoja=umbrales,
            umbrales_lista_master=lista_master,
            rutas={
                "clima": info_clima.get("ruta", ""),
                "config_puerto": info_cfg.get("ruta", ""),
                "relacion_impactos": info_umb.get("ruta", ""),
                "relacion_impactos_hoja": hoja_im,
                "relacion_modelos": info_rmod.get("ruta", ""),
                "umbrales": info_umb.get("ruta", ""),
            },
        )

    def to_dict_metadatos(self) -> dict:
        """Metadatos de las fuentes cargadas (trazabilidad)."""
        return {
            "fuentes": self.rutas,
            "variables_climaticas": self.info_clima.get("variables", []),
            "filas_config_puerto": len(self.config_puerto),
            "filas_relacion_impactos": len(self.relacion_impactos),
            "filas_relacion_modelos": len(self.relacion_modelos),
            "hojas_umbrales": list(self.umbrales_por_hoja.keys()),
        }
