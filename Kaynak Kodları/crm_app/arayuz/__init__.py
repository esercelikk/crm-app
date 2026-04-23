# Arayüz paketinin dışarı açtığı ana sınıflar burada toplanır.
# main.py sadece bu iki sınıfı import ederek login ve ana pencereyi başlatır.
from .login import LoginDialog
from .main_window import CRMMainWindow

# Paket dışından kullanılabilecek resmi arayüz API'si.
__all__ = ["LoginDialog", "CRMMainWindow"]
