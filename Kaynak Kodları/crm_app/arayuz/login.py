from __future__ import annotations

import math
import random

from PyQt5.QtCore import (
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    QTimer,
    Qt,
)
from PyQt5.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..veritabani import DatabaseManager

from .styles import COLORS

# Bu dosya uygulamanın giriş ekranını ve sol taraftaki animasyonlu tanıtım panelini içerir.
# Başarılı kimlik doğrulama sonrası authenticated_user alanı ana pencereye aktarılır.


# Giriş ekranındaki animasyonlu arka plan parçacığının veri modeli.
# ---------------------------------------------------------------------------
#  Floating particle for the showcase panel
# ---------------------------------------------------------------------------
class _Particle:
    __slots__ = ("x", "y", "radius", "speed", "opacity", "angle", "drift")

    def __init__(self, width: float, height: float) -> None:
        self.x = random.uniform(0, width)
        self.y = random.uniform(0, height)
        self.radius = random.uniform(2.5, 7)
        self.speed = random.uniform(0.15, 0.55)
        self.opacity = random.uniform(0.08, 0.30)
        self.angle = random.uniform(0, 2 * math.pi)
        self.drift = random.uniform(0.002, 0.008)

    def tick(self, height: float) -> None:
        # Parçacığı yukarı doğru hareket ettirir, ekrandan çıkınca alta alır.
        self.y -= self.speed
        self.x += math.sin(self.angle) * 0.35
        self.angle += self.drift
        if self.y < -self.radius:
            self.y = height + self.radius
            self.x = random.uniform(0, height)


# Login ekranının sol tarafındaki tanıtım/animasyon paneli.
# ---------------------------------------------------------------------------
#  Animated showcase panel (left side)
# ---------------------------------------------------------------------------
class _ShowcasePanel(QWidget):
    """Full‑height left panel with gradient background, floating particles
    and decorative geometric shapes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._particles: list[_Particle] = []
        self._phase: float = 0.0
        self._glow_phase: float = 0.0

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)

    def _ensure_particles(self) -> None:
        # Panel boyutuna göre yeterli sayıda arka plan parçacığı oluşturulur.
        target = 45
        w, h = self.width(), self.height()
        while len(self._particles) < target:
            self._particles.append(_Particle(w, h))

    def _tick(self) -> None:
        # Timer her çalıştığında animasyon fazları ve parçacık konumları yenilenir.
        self._phase += 0.012
        self._glow_phase += 0.025
        h = self.height()
        for p in self._particles:
            p.tick(h)
        self.update()

    # -- paint ---------------------------------------------------------------
    def paintEvent(self, event) -> None:  # type: ignore[override]
        # Gradient, ışık halkaları, parçacıklar ve tanıtım metni elle çizilir.
        self._ensure_particles()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())

        # ── Background gradient ──
        bg = QLinearGradient(0, 0, rect.width(), rect.height())
        bg.setColorAt(0.0, QColor("#0a0520"))
        bg.setColorAt(0.35, QColor("#110d35"))
        bg.setColorAt(0.7, QColor("#1a1450"))
        bg.setColorAt(1.0, QColor("#0f0a2a"))
        painter.fillRect(rect, bg)

        # ── Soft radial glow that breathes ──
        glow_alpha = int(25 + 12 * math.sin(self._glow_phase))
        glow = QRadialGradient(rect.width() * 0.35, rect.height() * 0.35, rect.width() * 0.7)
        glow.setColorAt(0.0, QColor(99, 102, 241, glow_alpha + 20))
        glow.setColorAt(0.5, QColor(99, 102, 241, glow_alpha))
        glow.setColorAt(1.0, QColor(99, 102, 241, 0))
        painter.fillRect(rect, glow)

        # Secondary glow
        glow2 = QRadialGradient(rect.width() * 0.75, rect.height() * 0.7, rect.width() * 0.5)
        glow2.setColorAt(0.0, QColor(139, 92, 246, int(glow_alpha * 0.6)))
        glow2.setColorAt(1.0, QColor(139, 92, 246, 0))
        painter.fillRect(rect, glow2)

        # ── Decorative ring ──
        ring_cx = rect.width() * 0.5
        ring_cy = rect.height() * 0.42
        ring_r = min(rect.width(), rect.height()) * 0.28
        ring_pen = QPen(QColor(255, 255, 255, 12), 1.5)
        painter.setPen(ring_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(ring_cx, ring_cy), ring_r, ring_r)
        painter.drawEllipse(QPointF(ring_cx, ring_cy), ring_r * 0.72, ring_r * 0.72)

        # ── Rotating dashed arc ──
        arc_pen = QPen(QColor(99, 102, 241, 55), 2, Qt.DashLine)
        painter.setPen(arc_pen)
        painter.save()
        painter.translate(ring_cx, ring_cy)
        painter.rotate(self._phase * 60 % 360)
        arc_rect = QRectF(-ring_r * 0.9, -ring_r * 0.9, ring_r * 1.8, ring_r * 1.8)
        painter.drawArc(arc_rect, 0, 120 * 16)
        painter.restore()

        # ── Particles ──
        for p in self._particles:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(p.opacity * 255)))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # ── Connecting lines between close particles ──
        painter.setPen(Qt.NoPen)
        for i, a in enumerate(self._particles):
            for b in self._particles[i + 1 :]:
                dx = a.x - b.x
                dy = a.y - b.y
                dist = math.hypot(dx, dy)
                if dist < 90:
                    alpha = int((1 - dist / 90) * 28)
                    painter.setPen(QPen(QColor(255, 255, 255, alpha), 0.5))
                    painter.drawLine(QPointF(a.x, a.y), QPointF(b.x, b.y))
                    painter.setPen(Qt.NoPen)

        # ── Text content ──
        painter.setPen(Qt.NoPen)

        # Big title
        title_y = rect.height() * 0.62
        painter.setPen(QColor(255, 255, 255, 240))
        painter.setFont(QFont("Segoe UI", 38, QFont.Bold))
        painter.drawText(
            QRectF(40, title_y, rect.width() - 80, 52),
            Qt.AlignLeft | Qt.AlignVCenter,
            "NexCRM",
        )

        # Subtitle
        painter.setPen(QColor(255, 255, 255, 130))
        painter.setFont(QFont("Segoe UI", 13))
        painter.drawText(
            QRectF(42, title_y + 56, rect.width() - 80, 72),
            Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
            "Müşteri ilişkilerinizi yönetmenin en akıllı yolu.",
        )

        # Feature pills
        pill_y = title_y + 126
        pills = ["⚡ AI Destekli", "📊 Anlık Analiz", "🔒 Güvenli"]
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        pill_x = 42.0
        for pill_text in pills:
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(pill_text) + 24
            pill_rect = QRectF(pill_x, pill_y, tw, 32)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 16))
            painter.drawRoundedRect(pill_rect, 16, 16)
            painter.setPen(QColor(255, 255, 255, 170))
            painter.drawText(pill_rect, Qt.AlignCenter, pill_text)
            pill_x += tw + 10

        # Bottom copyright
        painter.setPen(QColor(255, 255, 255, 50))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(40, rect.height() - 44, rect.width() - 80, 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            "© 2026 NexCRM Pro  ·  Tüm hakları saklıdır",
        )


# Label + input alanını tek küçük bileşende toplayan form parçası.
# ---------------------------------------------------------------------------
#  Login form input with built‑in label
# ---------------------------------------------------------------------------
class _FormInput(QWidget):
    """Custom input field with floating label above."""

    def __init__(self, label: str, placeholder: str = "", is_password: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel(label)
        self._label.setStyleSheet(
            f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800; "
            "letter-spacing: 0.5px; text-transform: uppercase; background: transparent;"
        )
        layout.addWidget(self._label)

        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        if is_password:
            self.input.setEchoMode(QLineEdit.Password)
        self.input.setMinimumHeight(50)
        self.input.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(243, 237, 228, 180);
                color: {COLORS['slate_900']};
                border: 2px solid transparent;
                border-radius: 16px;
                padding: 12px 16px;
                font-size: 14px;
                font-weight: 500;
            }}
            QLineEdit:focus {{
                background: white;
                border: 2px solid {COLORS['accent']};
            }}
            QLineEdit::placeholder {{
                color: {COLORS['slate_400']};
            }}
        """)
        layout.addWidget(self.input)


# Yeni şirket kayıt akışının şimdilik veritabanına dokunmayan görsel önizlemesi.
class CompanyRegistrationPreviewDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Şirket Kaydı Önizleme")
        self.resize(760, 720)
        self.setMinimumSize(680, 620)
        self.setModal(True)
        self.setStyleSheet(f"""
            QDialog {{
                background: #f8fafc;
            }}
            QComboBox {{
                background: white;
                color: {COLORS['slate_900']};
                border: 2px solid transparent;
                border-radius: 16px;
                padding: 10px 14px;
                font-size: 13px;
                min-height: 28px;
            }}
            QComboBox:focus {{
                border: 2px solid {COLORS['accent']};
            }}
            QTextEdit {{
                background: white;
                color: {COLORS['slate_900']};
                border: 2px solid transparent;
                border-radius: 16px;
                padding: 12px 14px;
                font-size: 13px;
            }}
            QTextEdit:focus {{
                border: 2px solid {COLORS['accent']};
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 #8b5cf6
                );
                border: none;
            }}
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(28, 24, 28, 24)
        header_layout.setSpacing(8)

        badge = QLabel("KURULUM ÖNİZLEMESİ")
        badge.setStyleSheet("color: rgba(255,255,255,190); font-size: 11px; font-weight: 900; letter-spacing: 1px;")
        title = QLabel("Şirketinin kaydını tamamla")
        title.setStyleSheet("color: white; font-size: 26px; font-weight: 900; background: transparent;")
        subtitle = QLabel("Bu ekran şu an sadece tasarım önizlemesidir; kayıt butonu veritabanına kayıt oluşturmaz.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: rgba(255,255,255,210); font-size: 13px; font-weight: 600; background: transparent;")
        header_layout.addWidget(badge)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(26, 24, 26, 24)
        body_layout.setSpacing(18)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        body_layout.addWidget(self._section_title("1. Şirket Bilgileri", "CRM çalışma alanının temel kimliği."))
        body_layout.addWidget(self._company_card())
        body_layout.addWidget(self._section_title("2. Adres ve Fatura", "Fatura ve resmi iletişim bilgileri için ön hazırlık."))
        body_layout.addWidget(self._billing_card())
        body_layout.addWidget(self._section_title("3. İlk Süper Admin", "Şirket hesabını yönetecek ilk kullanıcı bilgileri."))
        body_layout.addWidget(self._admin_card())
        body_layout.addWidget(self._section_title("4. Paket ve Notlar", "İleride lisans/aktivasyon yapısına bağlanabilecek alanlar."))
        body_layout.addWidget(self._plan_card())
        body_layout.addWidget(self._info_card())
        body_layout.addStretch(1)

        footer = QFrame()
        footer.setStyleSheet("background: white; border-top: 1px solid rgba(15, 23, 42, 18);")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

        preview_note = QLabel("Önizleme modu: hiçbir bilgi kaydedilmez.")
        preview_note.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; font-weight: 700; background: transparent;")
        footer_layout.addWidget(preview_note, 1)

        close_button = QPushButton("Kapat")
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setMinimumHeight(44)
        close_button.setStyleSheet(self._button_style("ghost"))
        close_button.clicked.connect(self.reject)

        register_button = QPushButton("Kayıt Ol")
        register_button.setCursor(Qt.PointingHandCursor)
        register_button.setMinimumHeight(44)
        register_button.setToolTip("Şimdilik pasif: veritabanı kaydı oluşturmaz.")
        register_button.setStyleSheet(self._button_style("primary"))
        register_button.clicked.connect(lambda: None)

        footer_layout.addWidget(close_button)
        footer_layout.addWidget(register_button)
        root.addWidget(footer)

    def _button_style(self, variant: str) -> str:
        if variant == "primary":
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['accent']}, stop:1 #8b5cf6);
                    color: white;
                    border: none;
                    border-radius: 14px;
                    padding: 0 22px;
                    font-size: 13px;
                    font-weight: 900;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 {COLORS['accent_dark']}, stop:1 #7c3aed);
                }}
            """
        return f"""
            QPushButton {{
                background: {COLORS['slate_100']};
                color: {COLORS['slate_700']};
                border: none;
                border-radius: 14px;
                padding: 0 20px;
                font-size: 13px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_light']};
                color: {COLORS['accent_dark']};
            }}
        """

    def _section_title(self, title: str, subtitle: str) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 16px; font-weight: 900;")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; font-weight: 600;")
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return wrap

    def _card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: white;
                border: none;
                border-radius: 22px;
            }
        """)
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(15, 23, 42, 18))
        card.setGraphicsEffect(shadow)
        return card

    def _combo(self, items: list[str]) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setCursor(Qt.PointingHandCursor)
        return combo

    def _company_card(self) -> QFrame:
        card = self._card()
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)

        grid.addWidget(_FormInput("Şirket adı", "Örn. ABC Teknoloji A.Ş."), 0, 0)
        grid.addWidget(_FormInput("Yetkili kişi", "Ad Soyad"), 0, 1)
        grid.addWidget(_FormInput("Kurumsal e-posta", "info@sirket.com"), 1, 0)
        grid.addWidget(_FormInput("Telefon", "05xx xxx xx xx"), 1, 1)
        grid.addWidget(_FormInput("Vergi no", "Opsiyonel"), 2, 0)
        grid.addWidget(_FormInput("Web sitesi", "https://"), 2, 1)
        grid.addWidget(self._labeled_combo("Sektör", ["Teknoloji", "Perakende", "Finans", "Sağlık", "Eğitim", "Diğer"]), 3, 0)
        grid.addWidget(self._labeled_combo("Ekip büyüklüğü", ["1-5", "6-20", "21-50", "51-200", "200+"]), 3, 1)
        return card

    def _billing_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(_FormInput("Şehir", "İstanbul"))
        row.addWidget(_FormInput("Ülke", "Türkiye"))
        layout.addLayout(row)
        address_label = QLabel("Açık adres")
        address_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        address = QTextEdit()
        address.setPlaceholderText("Mahalle, cadde, bina no, ilçe...")
        address.setMinimumHeight(92)
        layout.addWidget(address_label)
        layout.addWidget(address)
        return card

    def _admin_card(self) -> QFrame:
        card = self._card()
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        grid.addWidget(_FormInput("Ad soyad", "İlk yönetici"), 0, 0)
        grid.addWidget(_FormInput("E-posta", "admin@sirket.com"), 0, 1)
        grid.addWidget(_FormInput("Telefon", "05xx xxx xx xx"), 1, 0)
        grid.addWidget(_FormInput("Rol", "Süper Admin"), 1, 1)
        grid.addWidget(_FormInput("Şifre", "En az 8 karakter", is_password=True), 2, 0)
        grid.addWidget(_FormInput("Şifre tekrar", "Tekrar girin", is_password=True), 2, 1)
        return card

    def _plan_card(self) -> QFrame:
        card = self._card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(self._labeled_combo("Paket", ["Pro Deneme", "Pro", "Enterprise", "Özel Kurulum"]))
        row.addWidget(self._labeled_combo("Veri başlangıcı", ["Boş CRM", "Demo verilerle başlat", "Excel aktarımı planla"]))
        layout.addLayout(row)
        note_label = QLabel("Kurulum notu")
        note_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        note = QTextEdit()
        note.setPlaceholderText("Satış ekibi, destek ekibi, özel alan ihtiyacı veya lisans notları...")
        note.setMinimumHeight(92)
        layout.addWidget(note_label)
        layout.addWidget(note)
        return card

    def _labeled_combo(self, label: str, items: list[str]) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800; letter-spacing: 0.5px;")
        layout.addWidget(label_widget)
        layout.addWidget(self._combo(items))
        return wrap

    def _info_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['accent_light']};
                border: none;
                border-radius: 18px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(5)
        title = QLabel("Sonraki fazda bağlanabilecek akış")
        title.setStyleSheet(f"color: {COLORS['accent_dark']}; font-size: 13px; font-weight: 900; background: transparent;")
        text = QLabel("Bu ekran ileride şirket tablosu, ilk Süper Admin oluşturma, aktivasyon kodu ve lisans kontrolüne bağlanabilir.")
        text.setWordWrap(True)
        text.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px; font-weight: 600; background: transparent;")
        layout.addWidget(title)
        layout.addWidget(text)
        return card


# Kullanıcı kimlik doğrulamasını yapan modern giriş penceresi.
# ---------------------------------------------------------------------------
#  Main login dialog
# ---------------------------------------------------------------------------
class LoginDialog(QDialog):
    def __init__(self, db: DatabaseManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.authenticated_user = None
        self.setWindowTitle("NexCRM Pro — Giriş")
        self.resize(980, 680)
        self.setMinimumSize(880, 620)
        self.setModal(True)

        # Window‑level style
        self.setStyleSheet(f"""
            QDialog {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #f0f0ff, stop:0.5 #f5f3ff, stop:1 #eef2ff
                );
            }}
            QCheckBox {{
                spacing: 8px;
                color: {COLORS['slate_500']};
                font-size: 12px;
                background: transparent;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 6px;
                border: 2px solid {COLORS['slate_300']};
                background: white;
            }}
            QCheckBox::indicator:checked {{
                background: {COLORS['accent']};
                border-color: {COLORS['accent']};
            }}
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Left: Showcase ──
        showcase_wrapper = QFrame()
        showcase_wrapper.setStyleSheet("background: transparent; border: none;")
        sw_layout = QVBoxLayout(showcase_wrapper)
        sw_layout.setContentsMargins(16, 16, 0, 16)

        showcase_frame = QFrame()
        showcase_frame.setStyleSheet("border-radius: 28px; background: transparent;")
        sf_layout = QVBoxLayout(showcase_frame)
        sf_layout.setContentsMargins(0, 0, 0, 0)

        self._showcase = _ShowcasePanel()
        self._showcase.setStyleSheet("border-radius: 28px;")
        sf_layout.addWidget(self._showcase)

        sw_layout.addWidget(showcase_frame)
        root.addWidget(showcase_wrapper, 5)

        # ── Right: Form ──
        form_wrapper = QWidget()
        form_wrapper.setStyleSheet("background: transparent;")
        form_outer = QHBoxLayout(form_wrapper)
        form_outer.setContentsMargins(40, 40, 40, 40)

        form_container = QVBoxLayout()
        form_container.addStretch(1)

        # Logo icon
        logo = QLabel("✦")
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        logo.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {COLORS['accent']}, stop:1 #8b5cf6);
                color: white;
                border-radius: 18px;
                font-size: 22px;
                font-weight: bold;
            }}
        """)
        logo_shadow = QGraphicsDropShadowEffect(logo)
        logo_shadow.setBlurRadius(28)
        logo_shadow.setOffset(0, 6)
        logo_shadow.setColor(QColor(99, 102, 241, 60))
        logo.setGraphicsEffect(logo_shadow)
        form_container.addWidget(logo, alignment=Qt.AlignLeft)
        form_container.addSpacing(20)

        # Welcome text
        welcome = QLabel("Hoş geldiniz")
        welcome.setStyleSheet(
            f"color: {COLORS['slate_900']}; font-size: 28px; font-weight: 800; "
            "background: transparent;"
        )
        form_container.addWidget(welcome)

        subtitle = QLabel("Devam etmek için hesabınıza giriş yapın")
        subtitle.setStyleSheet(
            f"color: {COLORS['slate_400']}; font-size: 13px; font-weight: 500; "
            "background: transparent;"
        )
        form_container.addWidget(subtitle)
        form_container.addSpacing(32)

        # Email
        self._email_field = _FormInput("E-posta", "ornek@nexcrm.com")
        self._email_field.input.setText(
            self.db.get_setting("remembered_email", "admin@nexcrm.com")
        )
        form_container.addWidget(self._email_field)
        form_container.addSpacing(6)

        # Password
        self._password_field = _FormInput("Şifre", "••••••••", is_password=True)
        form_container.addWidget(self._password_field)
        form_container.addSpacing(8)

        # Options row
        options = QHBoxLayout()
        options.setContentsMargins(0, 0, 0, 0)
        self.remember = QCheckBox("Beni hatırla")
        self.remember.setChecked(bool(self._email_field.input.text().strip()))

        self.show_password = QCheckBox("Şifreyi göster")
        self.show_password.toggled.connect(self._toggle_password)

        options.addWidget(self.remember)
        options.addStretch(1)
        options.addWidget(self.show_password)
        form_container.addLayout(options)
        form_container.addSpacing(6)

        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(
            f"color: {COLORS['rose']}; font-size: 12px; font-weight: 700; "
            "background: transparent;"
        )
        self.error_label.setMinimumHeight(18)
        self.error_label.setAlignment(Qt.AlignCenter)
        form_container.addWidget(self.error_label)
        form_container.addSpacing(4)

        # Login button
        self.login_button = QPushButton("  Giriş Yap  →")
        self.login_button.setCursor(Qt.PointingHandCursor)
        self.login_button.setMinimumHeight(52)
        self.login_button.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']}, stop:1 #8b5cf6);
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 15px;
                font-weight: 800;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent_dark']}, stop:1 #7c3aed);
            }}
            QPushButton:pressed {{
                background: {COLORS['accent_dark']};
            }}
        """)
        btn_shadow = QGraphicsDropShadowEffect(self.login_button)
        btn_shadow.setBlurRadius(24)
        btn_shadow.setOffset(0, 8)
        btn_shadow.setColor(QColor(99, 102, 241, 55))
        self.login_button.setGraphicsEffect(btn_shadow)
        self.login_button.clicked.connect(self.try_login)
        form_container.addWidget(self.login_button)
        form_container.addSpacing(10)

        # Demo button
        demo_button = QPushButton("Demo Hesabı ile Dene")
        demo_button.setCursor(Qt.PointingHandCursor)
        demo_button.setMinimumHeight(48)
        demo_button.setStyleSheet(f"""
            QPushButton {{
                background: rgba(243, 237, 228, 200);
                color: {COLORS['slate_600']};
                border: none;
                border-radius: 16px;
                font-size: 13px;
                font-weight: 700;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_light']};
                color: {COLORS['accent_dark']};
            }}
        """)
        demo_button.clicked.connect(self._fill_demo_credentials)
        form_container.addWidget(demo_button)
        form_container.addSpacing(10)

        company_register_button = QPushButton("Şirketinin kaydını tamamla")
        company_register_button.setCursor(Qt.PointingHandCursor)
        company_register_button.setMinimumHeight(48)
        company_register_button.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['accent_dark']};
                border: 2px solid {COLORS['accent_light']};
                border-radius: 16px;
                font-size: 13px;
                font-weight: 800;
                padding: 0 24px;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_light']};
                border-color: {COLORS['accent']};
                color: {COLORS['accent_dark']};
            }}
        """)
        company_register_button.clicked.connect(self.open_company_registration_preview)
        form_container.addWidget(company_register_button)

        form_container.addStretch(1)

        # Version badge at bottom
        version = QLabel("v2.0  ·  Pro Edition")
        version.setStyleSheet(
            f"color: {COLORS['slate_400']}; font-size: 10px; font-weight: 600; "
            "background: transparent;"
        )
        version.setAlignment(Qt.AlignCenter)
        form_container.addWidget(version)

        form_outer.addLayout(form_container)
        root.addWidget(form_wrapper, 4)

        # Shortcut references for convenience
        self.email = self._email_field.input
        self.password = self._password_field.input

        self.password.returnPressed.connect(self.try_login)
        self.email.returnPressed.connect(lambda: self.password.setFocus())

    # -- helpers -------------------------------------------------------------
    def _fill_demo_credentials(self) -> None:
        # Demo butonu için varsayılan yönetici hesabını forma doldurur.
        self.email.setText("admin@nexcrm.com")
        self.password.setText("Admin123!")
        self.remember.setChecked(True)
        self.password.setFocus()
        self.password.selectAll()

    def _toggle_password(self, checked: bool) -> None:
        # Kullanıcı isterse şifreyi düz metin olarak görür.
        self.password.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def open_company_registration_preview(self) -> None:
        # Şimdilik sadece görsel şirket kayıt penceresini açar; veritabanına kayıt yapmaz.
        dialog = CompanyRegistrationPreviewDialog(self)
        dialog.exec_()

    def try_login(self) -> None:
        # Form değerlerini doğrular ve veritabanı login kontrolünü çağırır.
        email = self.email.text().strip()
        password = self.password.text().strip()
        if not email or not password:
            self.error_label.setText("⚠  E-posta ve şifre zorunlu.")
            return
        user, message = self.db.authenticate_user(
            email, password, self.remember.isChecked()
        )
        if not user:
            self.error_label.setText(f"⚠  {message}")
            self.password.selectAll()
            self.password.setFocus()
            return
        self.error_label.setText("")
        self.authenticated_user = user
        self.accept()

    @staticmethod
    def show_login_failed(parent: QWidget, message: str) -> None:
        # Eski kullanım ihtimali için merkezi hata penceresi yardımcısı.
        QMessageBox.critical(parent, "Giriş başarısız", message)
