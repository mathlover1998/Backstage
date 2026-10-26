import os

# Phai set TRUOC khi PySide6 khoi tao platform plugin. Nho vay test UI chay
# duoc tren CI runner khong co display, va khong bat cua so len man hinh khi
# chay test o local.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
