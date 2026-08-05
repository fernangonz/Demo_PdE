"""Resolucion de diagramas PDF en Flujo de modelos/."""

from __future__ import annotations

import unittest

from core.modelos.flujos import (
    CARPETA_FLUJOS,
    RAIZ_PROYECTO,
    buscar_diagrama_pdf,
    buscar_diagrama_texto,
)


class TestFlujosPdf(unittest.TestCase):
    def test_carpeta_flujos_en_raiz_proyecto(self) -> None:
        self.assertTrue(RAIZ_PROYECTO.is_dir())
        self.assertEqual(CARPETA_FLUJOS, RAIZ_PROYECTO / "Flujo de modelos")
        self.assertTrue(
            CARPETA_FLUJOS.is_dir(),
            f"Falta la carpeta de diagramas: {CARPETA_FLUJOS}",
        )

    def test_pi_agitacion_resuelve_pdf(self) -> None:
        diagrama = buscar_diagrama_pdf("PI_AGITACION")
        self.assertIsNotNone(diagrama)
        assert diagrama is not None
        self.assertTrue(diagrama.ruta.is_file())
        self.assertGreater(diagrama.ruta.stat().st_size, 1000)
        self.assertEqual(diagrama.ruta.suffix.lower(), ".pdf")
        self.assertEqual(diagrama.ruta.parent.resolve(), CARPETA_FLUJOS.resolve())

    def test_diagrama_flujo_unico_resuelve_pdf(self) -> None:
        diagrama = buscar_diagrama_pdf("DIAGRAMA_FLUJO_UNICO")
        self.assertIsNotNone(diagrama)
        assert diagrama is not None
        self.assertTrue(diagrama.ruta.is_file())
        stem = diagrama.ruta.stem.upper()
        self.assertTrue("UNICO" in stem or "UNICO" in stem.replace("\u00da", "U"))

    def test_pi_precipitacion_resuelve_pdf_propio(self) -> None:
        diagrama = buscar_diagrama_pdf("PI_PRECIPITACION")
        self.assertIsNotNone(diagrama)
        assert diagrama is not None
        self.assertTrue(diagrama.ruta.is_file())
        self.assertGreater(diagrama.ruta.stat().st_size, 1000)
        stem = diagrama.ruta.stem.upper()
        self.assertIn("PRECIPITACION", stem.replace("Ó", "O").replace("\u00d3", "O"))
        self.assertNotIn("SUPERACION", stem.replace("Ó", "O").replace("\u00d3", "O"))
        txt = buscar_diagrama_texto("PI_PRECIPITACION")
        self.assertIsNotNone(txt)
        assert txt is not None
        self.assertTrue(txt.ruta.is_file())
        self.assertEqual(txt.ruta.suffix.lower(), ".txt")


if __name__ == "__main__":
    unittest.main()
