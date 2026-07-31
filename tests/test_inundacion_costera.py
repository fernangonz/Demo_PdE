# -*- coding: utf-8 -*-
"""Verificacion de Inundacion costera (ELO) bajo PI superacion de umbral."""

from __future__ import annotations

import unittest

from core.datos import RepositorioDatos
from core.impact_models import (
    MODOS_FALLO_PLANTILLA,
    iteraciones_desde_calculo_activo,
)
from core.modelos.catalogo_impactos import entrada_catalogo
from core.modelos.impacto.calculo_activo import calcular_impactos_activo
from core.modelos.impacto.pi_agitacion import ParametrosEntrada
from core.modelos.impacto.pi_agitacion.pasos import construir_pasos_modo_fallo
from core.modelos.impacto.pi_agitacion.utilidades import (
    es_modo_inundacion_costera,
    es_modo_superacion_umbral,
)
from core.modelos.impacto.pi_francobordo.utilidades import es_modo_falta_francobordo

MODO = "Inundaci\u00f3n costera"
MODO_CORTO = "Inundaci\u00f3n"
TITULO = "PI Inundaci\u00f3n costera"


class TestInundacionCostera(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = RepositorioDatos.cargar()

    def test_pasos_acepta_seleccion_especial(self) -> None:
        import inspect

        params = inspect.signature(construir_pasos_modo_fallo).parameters
        self.assertIn("seleccion_especial", params)
        self.assertIn("nota_paso6", params)

    def test_catalogo_y_plantilla(self) -> None:
        entrada = entrada_catalogo(
            modo_fallo=MODO,
            variable=MODO,
            tipo_impacto="ELO",
        )
        self.assertIsNotNone(entrada)
        assert entrada is not None
        self.assertEqual(entrada.motor_id, "PI_AGITACION")
        self.assertIn(TITULO, MODOS_FALLO_PLANTILLA)

    def test_matcher_no_confundir_con_francobordo(self) -> None:
        self.assertTrue(es_modo_inundacion_costera(MODO, MODO, "ELO"))
        self.assertTrue(es_modo_superacion_umbral(MODO_CORTO, MODO, "ELO"))
        self.assertFalse(es_modo_falta_francobordo(MODO, MODO, "ELO"))
        self.assertFalse(
            es_modo_inundacion_costera("Falta de francobordo", "Nivel del mar", "ELO")
        )

    def test_superficies_usa_agitacion_con_fb(self) -> None:
        r = calcular_impactos_activo(
            self.repo,
            params_agitacion=ParametrosEntrada(activo="Superficies"),
            incluir_francobordo=False,
            incluir_calado=False,
        )
        self.assertTrue(r.ok, r.advertencias)
        self.assertIsNotNone(r.resultado_agitacion)
        assert r.resultado_agitacion is not None
        self.assertTrue(r.resultado_agitacion.ok, r.resultado_agitacion.error)
        inund = [
            it
            for it in r.resultado_agitacion.iteraciones
            if "inund" in it.modo_fallo.lower()
        ]
        self.assertGreaterEqual(len(inund), 1)
        self.assertIsNone(r.resultado_francobordo)
        self.assertIn("0.6", inund[0].indicador_seleccionado.replace(",", "."))
        self.assertTrue(str(inund[0].umbral).startswith("Fb"))
        iters_ui = iteraciones_desde_calculo_activo(r)
        self.assertTrue(any("inund" in i.modo_fallo.lower() for i in iters_ui))


if __name__ == "__main__":
    unittest.main()
