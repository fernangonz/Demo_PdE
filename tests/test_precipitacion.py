# -*- coding: utf-8 -*-
"""Verificacion de Exceso de precipitacion (ELO) - motor PI_PRECIPITACION."""

from __future__ import annotations

import unittest

import pandas as pd

from core.datos import RepositorioDatos
from core.impact_models import MODOS_FALLO_PLANTILLA, iteraciones_desde_calculo_activo
from core.modelos.catalogo_impactos import MOTOR_PI_PRECIPITACION, entrada_catalogo
from core.modelos.flujos import tiene_diagrama
from core.modelos.impacto.auditoria import fila_tiene_modelo_implementado
from core.modelos.impacto.calculo_activo import calcular_impactos_activo
from core.modelos.impacto.pi_agitacion import ParametrosEntrada
from core.modelos.impacto.pi_precipitacion.schemas import (
    INTERP_MEJORA,
    INTERP_NO_MEJORA,
    INTERP_SIN_CAMBIOS,
    PREF_CAMBIO,
    PREF_INTERP,
    columnas_pares_indicadores,
    umbral_mm_desde_indicador,
)
from core.modelos.impacto.pi_precipitacion.utilidades import (
    es_modo_exceso_precipitacion,
    interpretar_delta_precip,
)
from core.modelos.metodologias import resolver_motor_fila
from core.modelos.registro import MODELOS_IMPACTO

ACTIVO = "Manipulaci\u00f3n de mercanc\u00eda"
MODO = "Exceso de precipitaci\u00f3n"
VARIABLE = "Precipitaci\u00f3n"
TITULO = "PI Exceso de precipitaci\u00f3n"


class TestPrecipitacion(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = RepositorioDatos.cargar()

    def test_catalogo_motor_y_diagrama(self) -> None:
        entrada = entrada_catalogo(
            modo_fallo=MODO,
            variable=VARIABLE,
            tipo_impacto="ELO",
        )
        self.assertIsNotNone(entrada)
        assert entrada is not None
        self.assertEqual(entrada.motor_id, MOTOR_PI_PRECIPITACION)
        self.assertTrue(entrada.implementado)
        self.assertIn(MOTOR_PI_PRECIPITACION, MODELOS_IMPACTO)
        self.assertTrue(tiene_diagrama(MOTOR_PI_PRECIPITACION))
        self.assertIn(TITULO, MODOS_FALLO_PLANTILLA)

    def test_matcher_y_resolver(self) -> None:
        self.assertTrue(es_modo_exceso_precipitacion(MODO, VARIABLE, "ELO"))
        self.assertFalse(es_modo_exceso_precipitacion("Exceso de Viento", "Viento", "ELO"))
        fila = pd.Series({
            "Modos de fallo / Modos de parada": MODO,
            "Variable": VARIABLE,
            "Tipo de impacto": "ELO",
        })
        motor_id, _entrada = resolver_motor_fila(fila)
        self.assertEqual(motor_id, MOTOR_PI_PRECIPITACION)
        self.assertTrue(fila_tiene_modelo_implementado(fila))

    def test_umbral_mm_y_columnas(self) -> None:
        self.assertEqual(umbral_mm_desde_indicador("\u2265 1 mm"), "1 mm")
        self.assertEqual(umbral_mm_desde_indicador("dias >= 20 mm"), "20 mm")
        c1, i1, c2, i2 = columnas_pares_indicadores("\u2265 1 mm", "\u2265 20 mm")
        self.assertEqual(c1, f"{PREF_CAMBIO} (1 mm)")
        self.assertEqual(i1, f"{PREF_INTERP} (1 mm)")
        self.assertEqual(c2, f"{PREF_CAMBIO} (20 mm)")
        self.assertEqual(i2, f"{PREF_INTERP} (20 mm)")

    def test_interpretacion_polaridad(self) -> None:
        self.assertEqual(interpretar_delta_precip(1), INTERP_NO_MEJORA)
        self.assertEqual(interpretar_delta_precip(-3), INTERP_MEJORA)
        self.assertEqual(interpretar_delta_precip(0), INTERP_SIN_CAMBIOS)
        self.assertEqual(interpretar_delta_precip(0, es_historico=True), "Referencia")

    def test_manipulacion_mercancia_n63_cuatro_columnas(self) -> None:
        r = calcular_impactos_activo(
            self.repo,
            params_agitacion=ParametrosEntrada(activo=ACTIVO),
            incluir_agitacion=False,
            incluir_francobordo=False,
            incluir_calado=False,
            incluir_precipitacion=True,
        )
        self.assertTrue(r.ok, r.advertencias)
        self.assertIsNotNone(r.resultado_precipitacion)
        assert r.resultado_precipitacion is not None
        self.assertTrue(r.resultado_precipitacion.ok, r.resultado_precipitacion.error)

        precip = [
            it
            for it in r.resultado_precipitacion.iteraciones
            if "precipit" in it.modo_fallo.lower()
        ]
        self.assertGreaterEqual(
            len(precip),
            1,
            [it.modo_fallo for it in r.resultado_precipitacion.iteraciones],
        )
        it = precip[0]
        self.assertEqual(it.estado, "ok", it.motivo)
        self.assertIn("Sin umbral", it.umbral)
        tabla = it.tabla_resultado
        cols = list(tabla.columns)
        self.assertIn(f"{PREF_CAMBIO} (1 mm)", cols, cols)
        self.assertIn(f"{PREF_CAMBIO} (20 mm)", cols, cols)
        self.assertIn(f"{PREF_INTERP} (1 mm)", cols, cols)
        self.assertIn(f"{PREF_INTERP} (20 mm)", cols, cols)
        self.assertFalse(tabla.empty)

        futuros = tabla[tabla["Escenario"].astype(str) != "Hist\u00f3rico"]
        self.assertFalse(futuros.empty)
        for _, row in futuros.iterrows():
            for umbral in ("1 mm", "20 mm"):
                delta = row[f"{PREF_CAMBIO} ({umbral})"]
                esperado = interpretar_delta_precip(
                    None if pd.isna(delta) else float(delta)
                )
                self.assertEqual(row[f"{PREF_INTERP} ({umbral})"], esperado)

        iters_ui = iteraciones_desde_calculo_activo(r)
        self.assertTrue(any("precipit" in i.modo_fallo.lower() for i in iters_ui))


if __name__ == "__main__":
    unittest.main()
