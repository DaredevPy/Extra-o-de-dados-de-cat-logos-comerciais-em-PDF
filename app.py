"""
Ponto de entrada da aplicação Desktop de Extração de Catálogos Comerciais em PDF.
"""

import sys
from gui.main_window import MainWindow

def main():
    try:
        app = MainWindow()
        app.mainloop()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Erro fatal ao executar aplicação: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
