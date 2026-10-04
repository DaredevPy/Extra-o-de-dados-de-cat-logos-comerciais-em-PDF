"""
Gerador de Catálogo Comercial em PDF para testes e demonstração.
Cria um PDF realista com produtos, códigos, descrições e preços em formato de tabela e blocos de texto.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Registrar fontes com suporte completo a UTF-8 se disponíveis no Windows
font_family = "Helvetica"
font_family_bold = "Helvetica-Bold"

if os.path.exists("C:/Windows/Fonts/arial.ttf"):
    try:
        pdfmetrics.registerFont(TTFont("ArialCustom", "C:/Windows/Fonts/arial.ttf"))
        font_family = "ArialCustom"
        if os.path.exists("C:/Windows/Fonts/arialbd.ttf"):
            pdfmetrics.registerFont(TTFont("ArialBoldCustom", "C:/Windows/Fonts/arialbd.ttf"))
            font_family_bold = "ArialBoldCustom"
        else:
            font_family_bold = "ArialCustom"
    except Exception:
        pass

def generate_sample_catalog(output_path: str = "catalogo_exemplo.pdf") -> str:
    """Gera um PDF de catálogo comercial fictício com 3 páginas."""
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CatalogTitle',
        parent=styles['Heading1'],
        fontName=font_family_bold,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1 # Center
    )
    
    subtitle_style = ParagraphStyle(
        'CatalogSubtitle',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563'),
        alignment=1
    )
    
    section_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontName=font_family_bold,
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1F2937'),
        spaceBefore=12,
        spaceAfter=6
    )
    
    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=9,
        leading=12
    )
    
    cell_bold = ParagraphStyle(
        'CellBold',
        parent=cell_style,
        fontName=font_family_bold
    )
    
    story = []

    # --- PÁGINA 1: Informática e Escritório (Tabela Estruturada) ---
    story.append(Paragraph("CATÁLOGO DE PRODUTOS 2026 - MEGA DISTRIBUIDORA", title_style))
    story.append(Paragraph("Setor: Informática, Automação e Escritório", subtitle_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("Tabela de Produtos - Hardware & Periféricos", section_style))

    table_data_p1 = [
        [Paragraph("Código", cell_bold), Paragraph("Descrição / Nome do Produto", cell_bold), Paragraph("Preço Unitário", cell_bold)]
    ]
    
    products_p1 = [
        ("INF-1001", "Monitor LED 27 Pol. Full HD 100Hz HDMI/VGA", "R$ 789,90"),
        ("INF-1002", "Teclado Mecânico Gamer Switch Blue RGB ABNT2", "R$ 189,50"),
        ("INF-1003", "Mouse Óptico Sem Fio Ergonômico 2400 DPI", "R$ 69,90"),
        ("INF-1004", "Headset Gamer Som Surround 7.1 Microfone Noise Cancelling", "R$ 219,00"),
        ("INF-1005", "SSD NVMe M.2 1TB Leitura 3500MB/s Gravação 3000MB/s", "R$ 389,00"),
        ("INF-1006", "Cabo HDMI 2.1 Ultra High Speed 8K 60Hz 2 Metros", "R$ 39,90"),
        ("INF-1007", "Nobreak 1200VA Bivolt Automático com 6 Tomadas", "R$ 649,00"),
        ("INF-1008", "Cadeira Ergonômica de Escritório com Apoio Lombar", "R$ 899,00"),
        ("INF-1009", "Webcam Full HD 1080p 60FPS com Autofoco e Microfone Duplo", "R$ 279,90"),
        ("INF-1010", "Hub USB-C 7 em 1 com Saída HDMI 4K e Leitor SD", "R$ 159,90")
    ]

    for cod, desc, preco in products_p1:
        table_data_p1.append([
            Paragraph(cod, cell_bold),
            Paragraph(desc, cell_style),
            Paragraph(preco, cell_bold)
        ])

    t1 = Table(table_data_p1, colWidths=[1.3 * inch, 4.3 * inch, 1.6 * inch])
    t1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#DBEAFE')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)
    
    # --- PÁGINA 2: Ferramentas e Elétrica (Formato Misto: Tabela compacta) ---
    story.append(PageBreak())
    story.append(Paragraph("CATÁLOGO DE PRODUTOS 2026 - MEGA DISTRIBUIDORA", title_style))
    story.append(Paragraph("Setor: Ferramentas, Máquinas e Materiais Elétricos", subtitle_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("Ferramentas Profissionais & Elétrica", section_style))

    table_data_p2 = [
        [Paragraph("Ref.", cell_bold), Paragraph("Especificação do Produto", cell_bold), Paragraph("Valor (R$)", cell_bold)]
    ]
    
    products_p2 = [
        ("FER-2001", "Parafusadeira e Furadeira de Impacto a Bateria 20V", "R$ 459,90"),
        ("FER-2002", "Jogo de Ferramentas Manuais 110 Peças com Maleta", "R$ 299,00"),
        ("FER-2003", "Esmerilhadeira Angular 4.1/2 Polegadas 850W 110V", "R$ 249,50"),
        ("FER-2004", "Multímetro Digital Automático com Teste de Tensão e Diodo", "R$ 89,90"),
        ("FER-2005", "Alicate Decapador e Crimpador de Fios Automático", "R$ 65,00"),
        ("FER-2006", "Rolo de Fita Isolante Antichama 19mm x 20m (Kit c/ 10 un)", "R$ 48,00"),
        ("FER-2007", "Serra Mármore 1400W 12000 RPM com Disco Diamantado", "R$ 389,90"),
        ("FER-2008", "Trena Laser Digital de Precisão Alcance 40 Metros", "R$ 139,00"),
        ("FER-2009", "Extensão Elétrica Profissional Carretel 20 Metros 20A", "R$ 185,00"),
        ("FER-2010", "Compressor de Ar Portátil 12V 150 PSI Digital para Pneus", "R$ 129,90")
    ]

    for cod, desc, preco in products_p2:
        table_data_p2.append([
            Paragraph(cod, cell_bold),
            Paragraph(desc, cell_style),
            Paragraph(preco, cell_bold)
        ])

    t2 = Table(table_data_p2, colWidths=[1.3 * inch, 4.3 * inch, 1.6 * inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#FEF3C7')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#92400E')),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E5E7EB')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFFBEB')]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)

    # --- PÁGINA 3: Linhas de Texto Formatadas (Padrão Catálogo de Linhas / Balcão) ---
    story.append(PageBreak())
    story.append(Paragraph("CATÁLOGO DE PRODUTOS 2026 - MEGA DISTRIBUIDORA", title_style))
    story.append(Paragraph("Setor: Papelaria, Suprimentos e Utilidades", subtitle_style))
    story.append(Spacer(1, 15))
    story.append(Paragraph("Lista Rápida de Suprimentos (Formato Linhas)", section_style))

    p3_items = [
        "Cód. SUP-3001 - Caixa de Papel Sulfite A4 75g com 5000 Folhas - R$ 245,00",
        "Cód. SUP-3002 - Toner Compatível Preto HP 85A CE285A 1.6k - R$ 42,90",
        "Cód. SUP-3003 - Fita Adesiva Transparente 45mm x 100m Pacote c/ 6 rolos - R$ 38,50",
        "Cód. SUP-3004 - Grampeador de Mesa Médio Metal para até 40 Folhas - R$ 28,00",
        "Cód. SUP-3005 - Caneta Esferográfica Azul 1.0mm Caixa c/ 50 unidades - R$ 39,90",
        "Cód. SUP-3006 - Bobina Térmica 80x40 para Cupom Fiscal Caixa c/ 30 rolos - R$ 74,90",
        "Cód. SUP-3007 - Caixa de Arquivo Morto Polionda Plástico Azul c/ 10 un - R$ 52,00",
        "Cód. SUP-3008 - Suporte Articulado para Notebook em Alumínio Premium - R$ 99,90",
        "Cód. SUP-3009 - Luminária de Mesa LED Articulada com Controle de Brilho - R$ 79,00",
        "Cód. SUP-3010 - Filtro de Linha 6 Tomadas Bivolt com Chave Disjuntor - R$ 45,90"
    ]

    item_style = ParagraphStyle(
        'TextItem',
        parent=styles['Normal'],
        fontName=font_family,
        fontSize=10,
        leading=16,
        textColor=colors.HexColor('#111827'),
        spaceAfter=6
    )

    for item in p3_items:
        story.append(Paragraph(item, item_style))

    doc.build(story)
    return os.path.abspath(output_path)

if __name__ == "__main__":
    path = generate_sample_catalog("catalogo_exemplo.pdf")
    print(f"Catálogo de exemplo gerado com sucesso em: {path}")
