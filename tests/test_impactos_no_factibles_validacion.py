# -*- coding: utf-8 -*-
"""No factibles + ELO sin metodologia PI Falta de Calado."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

import pandas as pd

from core.modelos.flujos import (
    CODIGO_PROCEDIMIENTO_FLUJO_FALTANTE,
    resolver_motivo_y_codigo_diagrama_indicadores,
    tiene_diagrama,
)
from core.modelos.impacto.auditoria import fila_tiene_modelo_implementado
from core.modelos.impacto.impactos_no_factibles import (
    FiltroImpactosNoFactibles,
    debe_omitir_im,
)
from core.modelos.impacto.validacion_puerto import validar_puerto_antes_calculo

COL_ACTIVO = "Activo f\u00edsico u Operacional"
COL_TIPO = "Tipo de impacto"
COL_DESC = "Descripcion"
COL_MODO = "Modos de fallo / Modos de parada"


def _fila_relacion_elo_calado() -> pd.Series:
    return pd.Series(
        {
            "N\u00ba": 1,
            COL_TIPO: "ELO",
            COL_MODO: "Falta de Calado",
            "Variable": "Nivel del mar",
            COL_ACTIVO: "Muelle",
            "Tipo activo/servicio": "Muelle",
        }
    )


class TestFiltroNoFactiblesMatching(unittest.TestCase):
    def test_ffill_activo_y_tipo_elo_no_descripcion(self) -> None:
        df = pd.DataFrame(
            {
                COL_ACTIVO: ["Muelle", None],
                COL_TIPO: ["ELO", "ELO"],
                COL_DESC: ["Interrupcion operativa", "Interrupcion operativa"],
                COL_MODO: ["Agitacion", "Falta de Calado"],
            }
        )
        filtro = FiltroImpactosNoFactibles.desde_dataframe(df, [False, True])
        self.assertTrue(filtro.es_no_factible("Muelle", "ELO", "Falta de Calado"))
        self.assertFalse(filtro.es_no_factible("Muelle", "ELO", "Agitacion"))
        self.assertFalse(
            filtro.es_no_factible(
                "Muelle", "Interrupcion operativa", "Falta de Calado"
            )
        )

    def test_alias_agitacion_exceso_oleaje(self) -> None:
        """Tabla Agitacion omite IM Exceso de oleaje (y al reves)."""
        agitacion = "Agitaci\u00f3n"
        df_agitacion = pd.DataFrame(
            {
                COL_ACTIVO: ["Muelle"],
                COL_TIPO: ["ELO"],
                COL_DESC: ["Interrupcion operativa"],
                COL_MODO: [agitacion],
            }
        )
        filtro_ag = FiltroImpactosNoFactibles.desde_dataframe(df_agitacion, [True])
        self.assertTrue(filtro_ag.es_no_factible("Muelle", "ELO", "Exceso de oleaje"))
        self.assertTrue(filtro_ag.es_no_factible("Muelle", "ELO", agitacion))
        self.assertTrue(
            debe_omitir_im(
                SimpleNamespace(filtro_impactos_no_factibles=filtro_ag),
                activo="Muelle",
                tipo_impacto="ELO",
                modo_fallo="Exceso de Oleaje",
            )
        )

        df_oleaje = pd.DataFrame(
            {
                COL_ACTIVO: ["Muelle"],
                COL_TIPO: ["ELO"],
                COL_DESC: ["Interrupcion operativa"],
                COL_MODO: ["  Exceso de oleaje  "],
            }
        )
        filtro_ol = FiltroImpactosNoFactibles.desde_dataframe(df_oleaje, [True])
        self.assertTrue(filtro_ol.es_no_factible("Muelle", "ELO", "Agitacion"))
        self.assertFalse(filtro_ol.es_no_factible("Muelle", "ELO", "Falta de Calado"))


class TestEloCaladoSinMetodologia(unittest.TestCase):
    def test_pi_falta_calado_sin_diagrama(self) -> None:
        self.assertFalse(tiene_diagrama("PI_CALADO_ELO"))

    def test_fila_elo_sin_modelo_implementado(self) -> None:
        self.assertFalse(fila_tiene_modelo_implementado(_fila_relacion_elo_calado()))

    def test_no_inventar_nm_h0_si_falta_diagrama(self) -> None:
        motivo, codigo = resolver_motivo_y_codigo_diagrama_indicadores(
            "PI_CALADO_ELO",
            "se requieren 3 indicadores NM, h0 y h sedimentacion",
        )
        self.assertEqual(codigo, CODIGO_PROCEDIMIENTO_FLUJO_FALTANTE)
        self.assertNotIn("NM", motivo)
        self.assertNotIn("h0", motivo)
        self.assertNotIn("sedimentacion", motivo.lower())
        self.assertIn("diagrama", motivo.lower())

    def test_validacion_sin_error_inventado_nm(self) -> None:
        relacion = pd.DataFrame([_fila_relacion_elo_calado().to_dict()])
        config = pd.DataFrame(
            [
                {
                    COL_ACTIVO: "Muelle",
                    "Tipo de UO": "Infraestructura",
                    "Dc": 10.0,
                }
            ]
        )
        datos = SimpleNamespace(
            config_puerto=config,
            relacion_impactos=relacion,
            relacion_modelos=None,
            umbrales_por_hoja=None,
            umbrales_lista_master=None,
            info_clima={},
        )
        resultado = validar_puerto_antes_calculo(datos)
        errores_inventados = [
            a
            for a in resultado.errores
            if "NM" in (a.input_faltante or "")
            or "h0" in (a.input_faltante or "").lower()
            or "sediment" in (a.input_faltante or "").lower()
            or a.codigo == CODIGO_PROCEDIMIENTO_FLUJO_FALTANTE
        ]
        self.assertEqual(errores_inventados, [])
        avisos_sin_met = [
            a
            for a in resultado.avisos
            if a.codigo == "MODO_SIN_METODOLOGIA"
            and "calado" in (a.modo_fallo or "").lower()
            and (a.tipo_impacto or "").upper() == "ELO"
        ]
        self.assertTrue(avisos_sin_met)
        self.assertEqual(avisos_sin_met[0].nivel, "warning")

    def test_marcado_no_factible_omite_aviso(self) -> None:
        relacion = pd.DataFrame([_fila_relacion_elo_calado().to_dict()])
        config = pd.DataFrame(
            [{COL_ACTIVO: "Muelle", "Tipo de UO": "Infraestructura", "Dc": 10.0}]
        )
        filtro = FiltroImpactosNoFactibles.desde_dataframe(
            pd.DataFrame(
                {
                    COL_ACTIVO: ["Muelle"],
                    COL_TIPO: ["ELO"],
                    COL_DESC: ["Interrupcion operativa"],
                    COL_MODO: ["Falta de Calado"],
                }
            ),
            [True],
        )
        self.assertTrue(
            debe_omitir_im(
                SimpleNamespace(filtro_impactos_no_factibles=filtro),
                activo="Muelle",
                tipo_impacto="ELO",
                modo_fallo="Falta de Calado",
            )
        )
        resultado = validar_puerto_antes_calculo(
            SimpleNamespace(
                config_puerto=config,
                relacion_impactos=relacion,
                relacion_modelos=None,
                umbrales_por_hoja=None,
                umbrales_lista_master=None,
                info_clima={},
            ),
            filtro_impactos_no_factibles=filtro,
        )
        avisos_muelle_calado = [
            a
            for a in resultado.avisos
            if "calado" in (a.modo_fallo or "").lower()
            and "muelle" in (a.activo or "").lower()
        ]
        self.assertEqual(avisos_muelle_calado, [])


class TestRecalculoCambiaFiltro(unittest.TestCase):
    def test_filtro_vacio_no_omite(self) -> None:
        filtro = FiltroImpactosNoFactibles.vacio()
        self.assertFalse(
            debe_omitir_im(
                SimpleNamespace(filtro_impactos_no_factibles=filtro),
                activo="Muelle",
                tipo_impacto="ELO",
                modo_fallo="Falta de Calado",
            )
        )

    def test_desde_dataframe_desmarcar_deja_vacio(self) -> None:
        df = pd.DataFrame(
            {
                COL_ACTIVO: ["Muelle"],
                COL_TIPO: ["ELO"],
                COL_DESC: ["Interrupcion operativa"],
                COL_MODO: ["Falta de Calado"],
            }
        )
        marcado = FiltroImpactosNoFactibles.desde_dataframe(df, [True])
        libre = FiltroImpactosNoFactibles.desde_dataframe(df, [False])
        self.assertTrue(marcado.es_no_factible("Muelle", "ELO", "Falta de Calado"))
        self.assertFalse(libre.es_no_factible("Muelle", "ELO", "Falta de Calado"))
        self.assertEqual(libre.marcados, ())


if __name__ == "__main__":
    unittest.main()
