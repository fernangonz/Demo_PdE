"""Extrae pasos de falta de calado Bocana (OK) y Muelle (ERROR) para guia Excel."""
from __future__ import annotations

import json
from pathlib import Path

from core.datos.repositorio import RepositorioDatos
from core.modelos.impacto.calculo_activo import calcular_impactos_puerto


def _tabla_resumen(tablas) -> dict:
    out = {}
    for t in tablas or []:
        titulo = str(getattr(t, "titulo", "") or "")
        filas = getattr(t, "filas", None) or []
        # compactar filas a dicts serializables
        compact = []
        for f in filas[:8]:
            if isinstance(f, dict):
                compact.append({str(k): ("" if v is None else str(v)) for k, v in f.items()})
            else:
                compact.append(str(f))
        out[titulo] = compact
    return out


def _pasos_list(resultado) -> list:
    if resultado is None:
        return []
    rpp = getattr(resultado, "resultados_por_pasos", None)
    if rpp is None:
        rpp = getattr(resultado, "pasos", None)
    if rpp is None:
        return []
    if hasattr(rpp, "pasos"):
        return list(rpp.pasos or [])
    if isinstance(rpp, list):
        return rpp
    return []


def _dump_resultado(label: str, resultado) -> dict:
    if resultado is None:
        return {"label": label, "existe": False}
    pasos = []
    for p in _pasos_list(resultado):
        pasos.append({
            "numero": getattr(p, "numero", None),
            "nombre": getattr(p, "nombre", None),
            "excel": getattr(p, "excel", None),
            "procedimiento": getattr(p, "procedimiento", None),
            "error_code": getattr(p, "error_code", None) or getattr(p, "codigo_error", None),
            "ok": getattr(p, "ok", None),
            "motivo": getattr(p, "motivo", None) or getattr(p, "mensaje", None),
            "tablas": _tabla_resumen(getattr(p, "tablas", None)),
        })
    # atributos utiles del resultado
    attrs = {}
    for a in (
        "ok", "error_code", "motivo", "mensaje", "calado_buque", "umbral_m",
        "umbral_txt", "activo", "tipo_impacto", "nombre_modelo", "modo_fallo",
    ):
        if hasattr(resultado, a):
            attrs[a] = getattr(resultado, a)
    # iteraciones
    iters = []
    for it in getattr(resultado, "iteraciones", None) or []:
        iters.append({
            k: getattr(it, k, None)
            for k in (
                "modo_fallo", "ok", "error_code", "motivo", "umbral_m",
                "calado_buque", "percentil", "etiqueta_im",
            )
            if hasattr(it, k)
        })
    return {
        "label": label,
        "existe": True,
        "attrs": {k: (None if v is None else (v if isinstance(v, (int, float, bool)) else str(v))) for k, v in attrs.items()},
        "iteraciones": iters,
        "pasos": pasos,
        "resultado_attrs": [a for a in dir(resultado) if not a.startswith("_")],
    }


def main() -> None:
    d = RepositorioDatos.cargar()
    r = calcular_impactos_puerto(d)
    payload = {"activos": {}}
    for res in r.resultados_por_activo:
        nombre = str(res.activo)
        if nombre not in ("Bocana", "Muelle"):
            continue
        payload["activos"][nombre] = {
            "PI": _dump_resultado("PI", res.resultado_calado_pi),
            "OPEX": _dump_resultado("OPEX", res.resultado_calado_opex),
            "CAPEX": _dump_resultado("CAPEX", res.resultado_calado_capex),
            "advertencias": [str(a) for a in (getattr(res, "advertencias", None) or [])][:20],
        }
    out = Path(__file__).with_name("_guia_calado_dump.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WROTE", out)
    for act, block in payload["activos"].items():
        print("===", act, "===")
        for lab in ("PI", "OPEX", "CAPEX"):
            b = block[lab]
            print(lab, "existe", b["existe"], "n_pasos", len(b.get("pasos") or []), "attrs", b.get("attrs"))


if __name__ == "__main__":
    main()
