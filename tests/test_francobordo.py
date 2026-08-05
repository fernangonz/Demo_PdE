# -*- coding: utf-8 -*-
"""Verificacion end-to-end de PI falta de francobordo."""

from __future__ import annotations

import unittest

from core.datos import RepositorioDatos
from core.impact_models import (
    MODOS_FALLO_PLANTILLA,
    iteraciones_desde_calculo_activo,
    resumen_activo_desde_calculo_activo,
)
from core.modelos.impacto.calculo_activo import calcular_impactos_puerto
from core.modelos.impacto.vista_resultados import construir_vista_resultados_activo

ACTIVOS_FRANCOBORDO = ("Muelle", "Pantal", "Duque de alba", "Rampa Ro-Ro")
MODO_FB = "PI FALTA DE FRANCOBORDO"


def _activo_coincide(activo_raw: str, patron: str) -> bool:
    return patron.lower() in activo_raw.lower()


class TestFrancobordo(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo = RepositorioDatos.cargar()
        cls.resultado_puerto = calcular_impactos_puerto(cls.repo)

    def test_modo_en_plantilla_resumen(self) -> None:
        self.assertIn(MODO_FB, MODOS_FALLO_PLANTILLA)

    def test_cuatro_activos_con_resultado_francobordo(self) -> None:
        for patron in ACTIVOS_FRANCOBORDO:
            with self.subTest(activo=patron):
                r = next(
                    (
                        x
                        for x in self.resultado_puerto.resultados_por_activo
                        if _activo_coincide(x.activo_raw, patron)
                    ),
                    None,
                )
                self.assertIsNotNone(r, f"No se encontro activo {patron}")
                assert r is not None
                self.assertTrue(r.ok, f"{patron}: calculo no ok")
                fb = r.resultado_francobordo
                self.assertIsNotNone(fb, f"{patron}: sin resultado_francobordo")
                assert fb is not None
                self.assertTrue(fb.ok, f"{patron}: francobordo.ok=False: {fb.error}")
                self.assertEqual(len(fb.iteraciones), 1, f"{patron}: sin iteraciones FB")

    def test_francobordo_en_iteraciones_y_resumen_ui(self) -> None:
        for patron in ACTIVOS_FRANCOBORDO:
            with self.subTest(activo=patron):
                r = next(
                    x
                    for x in self.resultado_puerto.resultados_por_activo
                    if _activo_coincide(x.activo_raw, patron)
                )
                iters = iteraciones_desde_calculo_activo(r)
                fb_iters = [i for i in iters if "francobordo" in i.modo_fallo.lower()]
                self.assertEqual(len(fb_iters), 1, f"{patron}: falta iteracion FB en UI")

                resumen = resumen_activo_desde_calculo_activo(r)
                self.assertIsNotNone(resumen)
                assert resumen is not None
                self.assertIn(
                    MODO_FB,
                    resumen.modos_fallo,
                    f"{patron}: {MODO_FB} no esta en resumen consolidado",
                )
                fila_futuro = next(
                    f for f in resumen.filas if f["Escenarios"] == "SSP2-4.5"
                )
                datos_fb = fila_futuro["modos"][MODO_FB]
                self.assertTrue(
                    bool(
                        datos_fb.get("Cambio respecto al hist\u00f3rico", "")
                        or datos_fb.get("Cambio respecto al historico", "")
                    ),
                    f"{patron}: resumen FB sin datos en escenario futuro",
                )

                vista = construir_vista_resultados_activo(
                    r,
                    iteraciones=iters,
                    resumen_activo=resumen,
                    cp_numero=r.cp_numero,
                    cp_total=self.resultado_puerto.cp_total,
                )
                self.assertIsNotNone(vista)
                assert vista is not None
                fb_modos = [g for g in vista.modos if "francobordo" in g.modo_fallo.lower()]
                self.assertEqual(len(fb_modos), 1, f"{patron}: falta grupo IM FB en vista")


if __name__ == "__main__":
    unittest.main()
