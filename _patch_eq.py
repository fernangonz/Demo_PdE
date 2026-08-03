# -*- coding: utf-8 -*-
from pathlib import Path

path = Path("core/modelos/fichas_excel.py")
text = path.read_text(encoding="utf-8")
start = text.index("def _limpiar_texto_ecuacion")
end = text.index("def _extraer_textos_dibujo_hoja")
new = r'''def _limpiar_texto_ecuacion(texto: str) -> str:
    t = texto or ""
    t = t.replace("\u3016", "").replace("\u3017", "")
    t = re.sub(r"[\u200b\u200c\u200d\ufeff\u2061]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    trans = str.maketrans(
        {
            "\U0001d71f": "\u0394",
            "\U0001d6e5": "\u0394",
            "\U0001d479": "R",
            "\U0001d47a": "S",
            "\U0001d47b": "T",
            "\U0001d46a": "C",
            "\U0001d475": "H",
            "\U0001d473": "F",
            "\U0001d426": "m",
            "\U0001d41a": "a",
            "\U0001d431": "x",
            "\U0001d7ce": "0",
            "\U0001d7d0": "2",
            "\U0001d7d1": "3",
            "\U0001d7d2": "4",
            "\U0001d7d3": "5",
            "\U0001d7d4": "6",
            "\U0001d491": "p",
            "\U0001d490": "o",
            "\U0001d493": "r",
            "\U0001d495": "t",
            "\U0001d484": "c",
            "\U0001d48f": "n",
            "\U0001d460": "s",
            "\U0001d482": "s",
            "\U0001d455": "h",
            "\U0001d456": "i",
            "\U0001d45d": "p",
            "\U0001d45c": "o",
            "\U0001d45f": "r",
            "\U0001d461": "t",
            "\U0001d450": "c",
            "\U0001d45b": "n",
            "\u22c5": "\u00b7",
            "\u2212": "-",
        }
    )
    t = t.translate(trans)
    t = re.sub(r"^\u0394R[_]?S\s*=", "\u0394Rs =", t)
    t = re.sub(r"^\u0394RS\s*=", "\u0394Rs =", t)
    t = re.sub(r"^\u0394Rs\s*=", "\u0394Rs =", t)
    return t.strip()


def _texto_desde_omml(fragment: str) -> str:
    """Une texto OMML; prioriza fallback legible de mc:Fallback."""
    fb_block = re.search(r"<mc:Fallback>(.*?)</mc:Fallback>", fragment, flags=re.S)
    if fb_block:
        texts = re.findall(r"<a:t[^>]*>(.*?)</a:t>", fb_block.group(1))
        if texts:
            joined = "".join(html_lib.unescape(x) for x in texts)
            limpio = _limpiar_texto_ecuacion(joined)
            if limpio and (
                "max" in limpio.lower() or "\u0394" in limpio or "=" in limpio
            ):
                return limpio

    texts = re.findall(r"<m:t[^>]*>(.*?)</m:t>", fragment)
    if texts:
        return _limpiar_texto_ecuacion("".join(html_lib.unescape(x) for x in texts))

    texts_a = re.findall(r"<a:t[^>]*>(.*?)</a:t>", fragment)
    if texts_a:
        joined = "".join(html_lib.unescape(x) for x in texts_a if "<" not in x)
        return _limpiar_texto_ecuacion(joined)
    return ""


'''
path.write_text(text[:start] + new + text[end:], encoding="utf-8")
print("patched ok")
