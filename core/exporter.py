import os
from typing import List
import pandas as pd
from core.models import ProductItem

class CatalogExporter:
    """Exporta lista de produtos para Excel ou CSV com suporte completo a caracteres em português."""
    
    @staticmethod
    def export_to_excel(products: List[ProductItem], file_path: str) -> str:
        """Exporta os produtos para planilha Excel (.xlsx)."""
        data = [p.to_dict() for p in products]
        df = pd.DataFrame(data)
        
        # Garante a extensão correta
        if not file_path.lower().endswith(".xlsx"):
            file_path += ".xlsx"
            
        # Cria o arquivo com estilo amigável
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Produtos")
            
            # Ajusta a largura das colunas automaticamente
            worksheet = writer.sheets["Produtos"]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 10)
                
        return file_path

    @staticmethod
    def export_to_csv(products: List[ProductItem], file_path: str) -> str:
        """Exporta os produtos para arquivo CSV com codificação UTF-8-SIG (compatível com Excel no Windows)."""
        data = [p.to_dict() for p in products]
        df = pd.DataFrame(data)
        
        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"
            
        df.to_csv(file_path, index=False, sep=";", encoding="utf-8-sig")
        return file_path
