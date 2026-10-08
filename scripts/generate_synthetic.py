# -*- coding: utf-8 -*-
"""Gera PDF sintético de 9 páginas (cenários A–I) + ground truth JSON."""
import json
import os
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.pagesizes import letter
from reportlab.rl_config import defaultPageSize

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "synthetic")
OUT_PDF = os.path.join(BASE, "cenarios_AI.pdf")
OUT_JSON = os.path.join(BASE, "ground_truth.json")

PAGE_W, PAGE_H = defaultPageSize


def _label(c, pag, txt):
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColorRGB(0.45, 0.45, 0.45)
    c.drawString(40, PAGE_H - 24, f"[{txt}] pagina {pag}")


def _prod_card(c, x, code_y, code, desc, price_y, price, v2_y=None, v2=None,
               promo=None):
    """bloco simples estilo Avon: código grande, descrição, preço R$ abreviado."""
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x, code_y, code)
    c.setFont("Helvetica", 11)
    c.drawString(x, code_y - 18, desc)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x, price_y, f"R$ {price}")
    if v2_y and v2:
        c.drawString(x, v2_y, f"R$ {v2}")
    if promo:
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.8, 0.2, 0.2)
        c.drawString(x, promo, "ECONOMIZE")
        c.setFillColorRGB(0, 0, 0)


def build():
    os.makedirs(BASE, exist_ok=True)
    c = pdfcanvas.Canvas(OUT_PDF, pagesize=letter)
    truth = {}

    # ---- A: 1 código / 1 preço ----
    pag = 1
    _label(c, pag, "A")
    _prod_card(c, 150, 600, "123456", "Batom Mate Nude", 480, "39,90")
    truth[pag] = {"A": {"123456": ["39,90"]}}
    c.showPage()

    # ---- B: 2 códigos -> 1 preço (um preço central para a dupla) ----
    pag = 2
    _label(c, pag, "B")
    _prod_card(c, 110, 600, "200001", "Delineador Preto", 480, "49,90")
    _prod_card(c, 330, 600, "200002", "Delineador Marrom", 480, "49,90")
    truth[pag] = {"B": {"200001": ["49,90"], "200002": ["49,90"], "_n_para_1": True}}
    c.showPage()

    # ---- C: 1 código -> 4 preços por quantidade ----
    pag = 3
    _label(c, pag, "C")
    _prod_card(c, 150, 600, "300001", "Mascara de Cilios", 540, None)
    for i, (q, pr) in enumerate([("1", "8,49"), ("2", "6,99"), ("3", "5,99"), ("4", "4,99")]):
        y = 470 - i * 42
        c.setFont("Helvetica", 11)
        c.drawString(150, y, f"{q} un")
        c.drawString(250, y, f"R$ {pr}")
    truth[pag] = {"C": {"300001": [("8,49", 1), ("6,99", 2), ("5,99", 3), ("4,99", 4)]}}
    c.showPage()

    # ---- D: 2 produtos próximos (código/preço próprios) ----
    pag = 4
    _label(c, pag, "D")
    _prod_card(c, 100, 600, "400001", "Perfume Desodorante 50ml", 480, "12,90")
    _prod_card(c, 330, 600, "400002", "Perfume Desodorante 100ml", 480, "19,90")
    truth[pag] = {"D": {"400001": ["12,90"], "400002": ["19,90"]}}
    c.showPage()

    # ---- E: grade 2x2 (2 códigos / 2 preços x 2 linhas) ----
    pag = 5
    _label(c, pag, "E")
    for (x, code, pr) in [(100, "500001", "10,00"), (330, "500002", "21,00"),
                          (100, "500003", "33,00"), (330, "500004", "44,00")]:
        yy = 600 if code in ("500001", "500002") else 460
        _prod_card(c, x, yy, code, f"{code} - Produto Exemplar", yy - 120, pr)
    truth[pag] = {"E": {"500001": ["10,00"], "500002": ["21,00"],
                        "500003": ["33,00"], "500004": ["44,00"]}}
    c.showPage()

    # ---- F: conflito geométrico x textual (footer com outro preço) ----
    pag = 6
    _label(c, pag, "F")
    _prod_card(c, 150, 600, "600001", "Kit Presente Gloss", 480, "39,90")
    # rodapé tipo "índice" com o MESMO código e um preço DIFERENTE
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0.3, 0.3, 0.3)
    c.drawString(60, 80, "600001 - Kit Gloss listado - R$ 5,99")
    c.setFillColorRGB(0, 0, 0)
    truth[pag] = {"F": {"600001": ["39,90"], "_conflito": True}}
    c.showPage()

    # ---- G: código SEM preço ----
    pag = 7
    _label(c, pag, "G")
    _prod_card(c, 150, 600, "700001", "Sombra Compacta", 480, None)
    truth[pag] = {"G": {"700001": [], "_sem_preco": True}}
    c.showPage()

    # ---- H: preço SEM código (não deve gerar produto fantasma) ----
    pag = 8
    _label(c, pag, "H")
    c.setFont("Helvetica-Bold", 13)
    c.drawString(150, 480, "R$ 25,90")
    truth[pag] = {"H": {"_preco_sem_codigo": True}}
    c.showPage()

    # ---- I: promocional + preço anterior (stacked) ----
    pag = 9
    _label(c, pag, "I")
    _prod_card(c, 150, 600, "800001", "Hidratante Corporal 400ml", 440, "39,90",
               v2_y=470, v2="49,90", promo=410)
    truth[pag] = {"I": {"800001": ["39,90", "49,90"], "_promo": True}}
    c.showPage()

    c.save()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=2)
    print(f"OK: {OUT_PDF}\n     {OUT_JSON}")


if __name__ == "__main__":
    build()