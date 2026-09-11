from datetime import datetime

import arabic_reshaper
from bidi.algorithm import get_display
from fpdf import FPDF

ARABIC_RANGES = (
    (0x0600, 0x06FF),
    (0x0750, 0x077F),
    (0x08A0, 0x08FF),
    (0xFB50, 0xFDFF),
    (0xFE70, 0xFEFF),
)

# Polices Windows couvrant à la fois le latin (français/anglais) et l'arabe.
PDF_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
    (r"C:\Windows\Fonts\arialuni.ttf", r"C:\Windows\Fonts\arialuni.ttf"),
]


def contains_arabic(text: str) -> bool:
    return any(any(lo <= ord(ch) <= hi for lo, hi in ARABIC_RANGES) for ch in text)


def _shape_line(line: str) -> str:
    if not line.strip():
        return ""
    # Le PDF ne gère pas nativement l'arabe (lettres liées + sens droite-à-gauche) :
    # on relie les lettres puis on réordonne la ligne avant de l'écrire.
    if contains_arabic(line):
        return get_display(arabic_reshaper.reshape(line))
    return line


def _register_pdf_font(pdf: FPDF) -> str:
    for regular, bold in PDF_FONT_CANDIDATES:
        try:
            pdf.add_font("ExportFont", "", regular)
            pdf.add_font("ExportFont", "B", bold)
            return "ExportFont"
        except (RuntimeError, FileNotFoundError):
            continue
    return "helvetica"


def _write_line(pdf: FPDF, h: float, text: str, align: str = "L") -> None:
    # new_x/new_y ramènent le curseur en marge gauche : par défaut fpdf2 le laisse
    # à droite après un multi_cell, ce qui épuise la largeur disponible ligne après ligne.
    pdf.multi_cell(0, h, text, align=align, new_x="LMARGIN", new_y="NEXT")


def build_pdf(pdf_url: str, messages: list[dict]) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    font = _register_pdf_font(pdf)

    pdf.set_font(font, "B", 16)
    _write_line(pdf, 10, "Analyse PDF IA - Export de la conversation", align="C")
    pdf.ln(2)

    pdf.set_font(font, "", 9)
    _write_line(pdf, 6, f"Exporté le {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    _write_line(pdf, 6, f"Document source : {pdf_url}")
    pdf.ln(4)

    for msg in messages:
        label = "Question" if msg["role"] == "user" else "Réponse"
        pdf.set_font(font, "B", 11)
        _write_line(pdf, 7, _shape_line(f"{label} :"))
        pdf.set_font(font, "", 11)
        for line in msg["content"].split("\n"):
            _write_line(pdf, 7, _shape_line(line))
        pdf.ln(3)

    return bytes(pdf.output())
