# -*- coding: utf-8 -*-
"""Verificacion de Exceso de precipitacion (ELO) - motor PI_PRECIPITACION."""

from __future__ import annotations

import unittest

import pandas as pd

from core.config_indicadores import MODO_PREDEFINIDO, ReglaIndicador
from core.datos import RepositorioDatos
from core.impact_models import (
    MODOS_FALLO_PLANTILLA,
    _es_tabla_precipitacion,
    _subcols_precip_desde_tabla,
    iteraciones_desde_calculo_activo,
)
from core.modelos.catalogo_impactos import MOTOR_PI_PRECIPITACION, entrada_catalogo
from core.modelos.flujos import tiene_diagrama
from core.modelos.impacto.auditoria import fila_tiene_modelo_implementado
from core.modelos.impacto.calculo_activo import calcular_impactos_activo
from core.modelos.impacto.pi_agitacion import ParametrosEntrada
from core.modelos.impacto.pi_agitacion.utilidades import ColumnaEscenario
from core.modelos.impacto.pi_precipitacion.schemas import (
    INTERP_MEJORA,
    INTERP_NO_MEJORA,
    INTERP_SIN_CAMBIOS,
    NUM_INDICADORES_MAX,
    NUM_INDICADORES_MIN,
    PREF_CAMBIO,
    PREF_INTERP,
    columnas_pares_indicadores,
    umbral_mm_desde_indicador,
)
from core.modelos.impacto.pi_precipitacion.utilidades import (
    es_modo_exceso_precipitacion,
    indicadores_predefinidos_precipitacion,
    interpretar_delta_precip,
    tabla_resultado_indicadores,
)
from core.modelos.metodologias import resolver_motor_fila
from core.modelos.registro import MODELOS_IMPACTO
from core.relacion_modelos import IndicadorRelacion, ORIGEN_EXCEL, ReglaModeloActivo

ACTIVO = "Manipulaci\u00f3n de mercanc\u00eda"
MODO = "Exceso de precipitaci\u00f3n"
VARIABLE = "Precipitaci\u00f3n"
TITULO = "PI Exceso de precipitaci\u00f3n"

_ATTR_PESTANA = "pesta" + "\u00f1" + "a"


def _regla_con_indicadores(*nombres: str) -> ReglaModeloActivo:
    inds = tuple(
        IndicadorRelacion(**{
            _ATTR_PESTANA: "Precipitaci\u00f3n",
            "indicador": n,
            "etiqueta": n,
        })
        for n in nombres
    )
    primer = nombres[0] if nombres else "x"
    return ReglaModeloActivo(
        percentil="P50",
        regla_indicador=ReglaIndicador(
            modo_seleccion=MODO_PREDEFINIDO,
            indicador=primer,
            etiqueta=primer,
        ),
        origen=ORIGEN_EXCEL,
        fila=1,
        num_indicadores=len(inds),
        indicadores=inds,
    )


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

    def test_ficha_word_emparejada(self) -> None:
        import unicodedata

        from core.modelos.fichas_word import (
            emparejar_nombre_ficha,
            ficha_word_por_entrada,
        )
        from core.modelos.flujos import buscar_diagrama_pdf

        entrada = entrada_catalogo(
            modo_fallo=MODO,
            variable=VARIABLE,
            tipo_impacto="ELO",
        )
        self.assertIsNotNone(entrada)
        assert entrada is not None
        self.assertEqual(
            emparejar_nombre_ficha("PI EXCESO DE PRECIPITACION.docx"),
            entrada.id,
        )
        ficha = ficha_word_por_entrada(entrada)
        self.assertIsNotNone(ficha)
        assert ficha is not None
        stem = (
            unicodedata.normalize("NFKD", ficha.archivo)
            .encode("ascii", "ignore")
            .decode("ascii")
            .upper()
        )
        self.assertIn("PRECIPITACION", stem)
        self.assertTrue((ficha.html or "").strip())
        self.assertIn("<table", (ficha.html or "").lower())
        self.assertIsNotNone(buscar_diagrama_pdf(MOTOR_PI_PRECIPITACION))

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

    def test_umbral_mm_y_columnas_dos_indicadores(self) -> None:
        self.assertEqual(umbral_mm_desde_indicador("\u2265 1 mm"), "1 mm")
        self.assertEqual(umbral_mm_desde_indicador("dias >= 20 mm"), "20 mm")
        cols = columnas_pares_indicadores("\u2265 1 mm", "\u2265 20 mm")
        self.assertEqual(len(cols), 4)
        self.assertEqual(cols[0], f"{PREF_CAMBIO} (1 mm)")
        self.assertEqual(cols[1], f"{PREF_INTERP} (1 mm)")
        self.assertEqual(cols[2], f"{PREF_CAMBIO} (20 mm)")
        self.assertEqual(cols[3], f"{PREF_INTERP} (20 mm)")

    def test_columnas_un_indicador(self) -> None:
        cols = columnas_pares_indicadores("\u2265 1 mm")
        self.assertEqual(len(cols), 2)
        self.assertEqual(cols[0], f"{PREF_CAMBIO} (1 mm)")
        self.assertEqual(cols[1], f"{PREF_INTERP} (1 mm)")

    def test_limites_indicadores_excel4(self) -> None:
        self.assertEqual(NUM_INDICADORES_MIN, 1)
        self.assertEqual(NUM_INDICADORES_MAX, 2)

        cero, err0 = indicadores_predefinidos_precipitacion(_regla_con_indicadores())
        self.assertEqual(cero, ())
        self.assertIsNotNone(err0)

        uno, err1 = indicadores_predefinidos_precipitacion(
            _regla_con_indicadores("\u2265 1 mm")
        )
        self.assertIsNone(err1)
        self.assertEqual(len(uno), 1)
        self.assertEqual(uno[0].indicador, "\u2265 1 mm")

        dos, err2 = indicadores_predefinidos_precipitacion(
            _regla_con_indicadores("\u2265 1 mm", "\u2265 20 mm")
        )
        self.assertIsNone(err2)
        self.assertEqual(len(dos), 2)

        tres, err3 = indicadores_predefinidos_precipitacion(
            _regla_con_indicadores("a", "b", "c")
        )
        self.assertIsNone(err3)
        self.assertEqual(len(tres), 2)
        self.assertEqual([i.indicador for i in tres], ["a", "b"])

    def test_tabla_resultado_un_indicador(self) -> None:
        fila = pd.Series({
            "Indicador": "\u2265 1 mm",
            "Hist": 10,
            "Fut": 7,
        })
        col_hist = ColumnaEscenario(
            etiqueta="Hist\u00f3rico", escenario="Hist\u00f3rico", anio=1995,
            columna="Hist", es_historico=True,
        )
        col_fut = ColumnaEscenario(
            etiqueta="SSP2-4.5 2040", escenario="SSP2-4.5", anio=2040, columna="Fut",
        )
        tabla = tabla_resultado_indicadores(
            [fila], col_hist, [col_fut], nombres_indicadores=["\u2265 1 mm"],
        )
        cols = list(tabla.columns)
        self.assertEqual(cols, [
            "Escenario",
            f"{PREF_CAMBIO} (1 mm)",
            f"{PREF_INTERP} (1 mm)",
        ])
        self.assertFalse(any("20 mm" in c for c in cols))
        self.assertTrue(_es_tabla_precipitacion(tabla))
        sub = _subcols_precip_desde_tabla(tabla)
        self.assertEqual(len(sub), 2)
        futuros = tabla[tabla["Escenario"].astype(str) != "Hist\u00f3rico"]
        self.assertEqual(int(futuros.iloc[0][f"{PREF_CAMBIO} (1 mm)"]), -3)
        self.assertEqual(futuros.iloc[0][f"{PREF_INTERP} (1 mm)"], INTERP_MEJORA)

    def test_tabla_resultado_dos_indicadores(self) -> None:
        f1 = pd.Series({"Indicador": "\u2265 1 mm", "Hist": 10, "Fut": 12})
        f2 = pd.Series({"Indicador": "\u2265 20 mm", "Hist": 5, "Fut": 5})
        col_hist = ColumnaEscenario(
            etiqueta="Hist\u00f3rico", escenario="Hist\u00f3rico", anio=1995,
            columna="Hist", es_historico=True,
        )
        col_fut = ColumnaEscenario(
            etiqueta="SSP2-4.5 2040", escenario="SSP2-4.5", anio=2040, columna="Fut",
        )
        tabla = tabla_resultado_indicadores(
            [f1, f2],
            col_hist,
            [col_fut],
            nombres_indicadores=["\u2265 1 mm", "\u2265 20 mm"],
        )
        cols = list(tabla.columns)
        self.assertEqual(len(cols), 5)
        self.assertIn(f"{PREF_CAMBIO} (1 mm)", cols)
        self.assertIn(f"{PREF_CAMBIO} (20 mm)", cols)
        self.assertTrue(_es_tabla_precipitacion(tabla))
        self.assertEqual(len(_subcols_precip_desde_tabla(tabla)), 4)

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
