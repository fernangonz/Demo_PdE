# -*- coding: utf-8 -*-
"""Verificacion de Exceso de precipitacion (ELO) — motor PI_PRECIPITACION."""

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
    COL_ANALISIS_1,
    COL_ANALISIS_2,
    COL_INCREMENTO_1,
    COL_INCREMENTO_2,
)
from core.modelos.impacto.pi_precipitacion.utilidades import (
    analisis_incremento,
    es_modo_exceso_precipitacion,
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

    def test_analisis_incremento(self) -> None:
        self.assertEqual(analisis_incremento(1), "INCREMENTA")
        self.assertEqual(analisis_incremento(0), "NO")
        self.assertEqual(analisis_incremento(-3), "NO")

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
        for col in (COL_INCREMENTO_1, COL_ANALISIS_1, COL_INCREMENTO_2, COL_ANALISIS_2):
            self.assertIn(col, tabla.columns, list(tabla.columns))
        self.assertFalse(tabla.empty)

        futuros = tabla[tabla["Escenario"].astype(str) != "Hist\u00f3rico"]
        self.assertFalse(futuros.empty)
        for _, row in futuros.iterrows():
            for col_inc, col_an in (
                (COL_INCREMENTO_1, COL_ANALISIS_1),
                (COL_INCREMENTO_2, COL_ANALISIS_2),
            ):
                delta = row[col_inc]
                esperado = "INCREMENTA" if pd.notna(delta) and float(delta) > 0 else "NO"
                self.assertEqual(row[col_an], esperado)

        iters_ui = iteraciones_desde_calculo_activo(r)
        self.assertTrue(any("precipit" in i.modo_fallo.lower() for i in iters_ui))


if __name__ == "__main__":
    unittest.main()
