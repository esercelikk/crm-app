from __future__ import annotations

from typing import List, Sequence

from PyQt5.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .styles import COLORS, COLORS_LIGHT

# Bu dosya uygulama genelinde tekrar kullanılan özel PyQt widgetlarını içerir.
# Kartlar, rozetler, grafikler ve yıldız puanlama bileşenleri burada toplanır.


# Renk string'ini alpha kanallı QColor nesnesine çevirir.
def with_alpha(color: str, alpha: int) -> QColor:
    qcolor = QColor(color)
    qcolor.setAlpha(alpha)
    return qcolor


# Qt stylesheet içinde kullanılacak rgba(...) metnini üretir.
def rgba_string(color: str, alpha: int) -> str:
    qcolor = with_alpha(color, alpha)
    return f"rgba({qcolor.red()}, {qcolor.green()}, {qcolor.blue()}, {qcolor.alpha()})"


# Grafik eksenlerinde para değerlerini TL formatında gösterir.
def format_chart_value(value: float) -> str:
    return f"₺{value:,.0f}".replace(",", ".")


# Kart ve panel gibi bileşenlere ortak gölge efekti verir.
def apply_shadow(widget: QWidget, blur: int = 26, y_offset: int = 8) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(with_alpha(COLORS["slate_900"], 34))
    widget.setGraphicsEffect(effect)


# Uygulamadaki standart cam/kart yüzey bileşeni.
class CardFrame(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.shadow_val = 8
        self._effect = QGraphicsDropShadowEffect(self)
        self._effect.setBlurRadius(26)
        self._effect.setOffset(0, self.shadow_val)
        self._effect.setColor(with_alpha(COLORS["slate_900"], 34))
        self.setGraphicsEffect(self._effect)
        
        self.anim = QPropertyAnimation(self._effect, b"offset")
        self.anim.setDuration(200)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)

    def enterEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._effect.offset())
        self.anim.setEndValue(QPointF(0, 16))
        self.anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim.stop()
        self.anim.setStartValue(self._effect.offset())
        self.anim.setEndValue(QPointF(0, self.shadow_val))
        self.anim.start()
        super().leaveEvent(event)


# Kullanıcı veya kayıt baş harflerini renkli avatar olarak gösterir.
class AvatarLabel(QLabel):
    def __init__(self, initials: str, color: str = COLORS["accent"], size: int = 38, parent: QWidget | None = None) -> None:
        super().__init__(initials, parent)
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Segoe UI", max(10, int(size * 0.28)), QFont.Bold))
        self.color_key = color
        self._apply_style()

    def _apply_style(self):
        c = COLORS.get(self.color_key, self.color_key) if self.color_key in COLORS else self.color_key
        # fallback is just using the string itself if not found
        if self.color_key == COLORS_LIGHT["accent"]: # Hack for default arg equality
            c = COLORS["accent"]
            
        self.setStyleSheet(
            f"""
            QLabel {{
                color: white;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {c}, stop:1 {COLORS['cyan']});
                border-radius: {self.width() // 2}px;
            }}
            """
        )

    def set_initials(self, initials: str) -> None:
        self.setText(initials)
        self._apply_style()


# Durum, rol, öncelik ve aşama etiketleri için renk eşleştirmeleri.
def get_badge_tones():
    return {
        "Aktif": (COLORS["emerald_light"], COLORS["emerald"]),
        "Beklemede": (COLORS["amber_light"], COLORS["amber"]),
        "Riskli": (COLORS["rose_light"], COLORS["rose"]),
        "Pasif": (COLORS["slate_100"], COLORS["slate_500"]),
        "Süper Admin": (COLORS["violet_light"], COLORS["violet"]),
        "Yönetici": (COLORS["accent_light"], COLORS["accent"]),
        "Satış Müdürü": (COLORS["amber_light"], COLORS["amber"]),
        "Satış Temsilcisi": (COLORS["cyan_light"], COLORS["cyan"]),
        "Destek": (COLORS["emerald_light"], COLORS["emerald"]),
        "Finans": (COLORS["rose_light"], COLORS["rose"]),
        "Başarı": (COLORS["emerald_light"], COLORS["emerald"]),
        "Bilgi": (COLORS["accent_light"], COLORS["accent"]),
        "Kritik": (COLORS["rose_light"], COLORS["rose"]),
        "Uyarı": (COLORS["amber_light"], COLORS["amber"]),
        "VIP": (COLORS["amber_light"], COLORS["amber"]),
        "Enterprise": (COLORS["violet_light"], COLORS["violet"]),
        "Potansiyel": (COLORS["accent_light"], COLORS["accent"]),
        "Sıcak": (COLORS["rose_light"], COLORS["rose"]),
        "Soğuk": (COLORS["slate_100"], COLORS["slate_500"]),
        "Önemli": (COLORS["amber_light"], COLORS["amber"]),
        "Takip": (COLORS["accent_light"], COLORS["accent"]),
        "Öncelikli": (COLORS["amber_light"], COLORS["amber"]),
        "Kurumsal": (COLORS["violet_light"], COLORS["violet"]),
        "Yeni": (COLORS["emerald_light"], COLORS["emerald"]),
        "Takipte": (COLORS["cyan_light"], COLORS["cyan"]),
        "Yüksek": (COLORS["rose_light"], COLORS["rose"]),
        "Orta": (COLORS["amber_light"], COLORS["amber"]),
        "Düşük": (COLORS["slate_100"], COLORS["slate_500"]),
        "Tamamlandı": (COLORS["emerald_light"], COLORS["emerald"]),
        "Gecikti": (COLORS["rose_light"], COLORS["rose"]),
        "Bugün": (COLORS["amber_light"], COLORS["amber"]),
        "Planlandı": (COLORS["accent_light"], COLORS["accent"]),
        "Bekliyor": (COLORS["slate_100"], COLORS["slate_500"]),
        "Telefon": (COLORS["violet_light"], COLORS["violet"]),
        "Toplantı": (COLORS["accent_light"], COLORS["accent"]),
        "Email": (COLORS["cyan_light"], COLORS["cyan"]),
        "Olumlu": (COLORS["emerald_light"], COLORS["emerald"]),
        "Olumsuz": (COLORS["rose_light"], COLORS["rose"]),
        "Gönderildi": (COLORS["emerald_light"], COLORS["emerald"]),
        "Alındı": (COLORS["accent_light"], COLORS["accent"]),
    }

# Tek satırlık renkli durum/etiket rozeti.
class BadgeLabel(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.apply_tone(text)

    def apply_tone(self, text: str) -> None:
        bg, fg = get_badge_tones().get(text, (COLORS["slate_100"], COLORS["slate_700"]))
        self.setText(text)
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {bg};
                color: {fg};
                border-radius: 14px;
                padding: 5px 11px;
                font-size: 11px;
                font-weight: 800;
            }}
            """
        )


# Dashboard'da kullanılan temel metrik kartı.
class StatCard(CardFrame):
    def __init__(self, title: str, value: str, meta: str, tone: str = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tone = tone if tone else COLORS["accent"]
        self.setMinimumHeight(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.pill = QLabel()
        self.pill.setFixedSize(46, 46)
        self.pill.setStyleSheet(
            f"background: {rgba_string(self.tone, 26)}; border-radius: 15px;"
        )
        top.addWidget(self.pill)
        top.addStretch(1)
        layout.addLayout(top)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800;")
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 30px; font-weight: 800;")
        self.meta_label = QLabel(meta)
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.meta_label)

    def set_data(self, title: str, value: str, meta: str) -> None:
        self.title_label.setText(title)
        self.value_label.setText(value)
        self.meta_label.setText(meta)


# Tıklanınca detay satırlarını açıp kapatan metrik kartı.
class ExpandableStatCard(CardFrame):
    def __init__(
        self,
        title: str,
        value: str,
        meta: str,
        details: Sequence[tuple[str, str]],
        tone: str = COLORS["accent"],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.tone = tone
        self.expanded = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(186)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        self.pill = QLabel()
        self.pill.setFixedSize(46, 46)
        self.pill.setStyleSheet(
            f"background: {rgba_string(self.tone, 26)}; border-radius: 15px;"
        )
        self.pill.setAttribute(Qt.WA_TransparentForMouseEvents)
        top.addWidget(self.pill)

        top.addStretch(1)
        self.state_label = QLabel("Detay")
        self.state_label.setStyleSheet(
            f"""
            QLabel {{
                background: {rgba_string(self.tone, 24)};
                color: {self.tone};
                border-radius: 14px;
                padding: 6px 11px;
                font-size: 11px;
                font-weight: 800;
            }}
            """
        )
        self.state_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        top.addWidget(self.state_label)
        root.addLayout(top)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800;")
        self.title_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 32px; font-weight: 800;")
        self.value_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.meta_label = QLabel(meta)
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
        self.meta_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        root.addWidget(self.title_label)
        root.addWidget(self.value_label)
        root.addWidget(self.meta_label)

        self.details_frame = QFrame()
        self.details_frame.setMaximumHeight(0)
        self.details_frame.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.details_frame.setStyleSheet(
            f"""
            QFrame {{
                background: {rgba_string(self.tone, 10)};
                border-radius: 20px;
            }}
            QLabel {{
                background: transparent;
            }}
            """
        )
        details_layout = QVBoxLayout(self.details_frame)
        details_layout.setContentsMargins(14, 12, 14, 12)
        details_layout.setSpacing(10)

        for label, detail in details:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            left = QLabel(label)
            left.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 700;")
            left.setAttribute(Qt.WA_TransparentForMouseEvents)
            right = QLabel(detail)
            right.setWordWrap(True)
            right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            right.setStyleSheet(f"color: {COLORS['slate_800']}; font-size: 11px; font-weight: 700;")
            right.setAttribute(Qt.WA_TransparentForMouseEvents)
            row.addWidget(left)
            row.addStretch(1)
            row.addWidget(right, 1)
            details_layout.addLayout(row)

        root.addWidget(self.details_frame)

        self.animation = QPropertyAnimation(self.details_frame, b"maximumHeight", self)
        self.animation.setDuration(240)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.toggle()
        super().mousePressEvent(event)

    def toggle(self, expanded: bool | None = None) -> None:
        if expanded is None:
            expanded = not self.expanded
        self.expanded = expanded
        self.state_label.setText("Kapat" if expanded else "Detay")
        self.animation.stop()
        self.animation.setStartValue(self.details_frame.maximumHeight())
        self.animation.setEndValue(self.details_frame.sizeHint().height() if expanded else 0)
        self.animation.start()


# Yüzde ilerlemesini başlık + progress bar olarak gösterir.
class ProgressRow(QWidget):
    def __init__(self, title: str, value: int = 0, color: str = COLORS["accent"], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px; font-weight: 700;")
        self.value_label = QLabel(f"%{value}")
        self.value_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; font-weight: 800;")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.value_label)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(value)
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                background: {COLORS['slate_100']};
                border: none;
                border-radius: 9px;
                height: 12px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 9px;
            }}
            """
        )
        layout.addLayout(header)
        layout.addWidget(self.progress)

    def set_value(self, value: int) -> None:
        self.progress.setValue(value)
        self.value_label.setText(f"%{value}")


# Satış trendi gibi zaman serilerini çizmek için özel çizim widget'ı.
class LineChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: List[float] = []
        self.labels: List[str] = []
        self.series_name = "Satış"
        self.line_color = QColor(COLORS["accent"])
        self.fill_color = with_alpha(COLORS["accent"], 40)
        self.hover_index = -1
        self.selected_index = -1
        self.setMinimumHeight(192)
        self.setMouseTracking(True)

    def set_series(self, labels: List[str], values: List[float], series_name: str = "Satış") -> None:
        self.labels = labels
        self.values = values
        self.series_name = series_name
        self.hover_index = -1
        self.selected_index = -1
        self.update()

    def _chart_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(56, 12, -22, -28)

    def _points(self, rect: QRectF) -> List[QPointF]:
        if not self.values:
            return []
        max_value = max(self.values) or 1
        min_value = min(self.values)
        spread = max(max_value - min_value, 1)
        points: List[QPointF] = []
        for index, value in enumerate(self.values):
            x = rect.left() + (rect.width() * index / max(len(self.values) - 1, 1))
            y = rect.bottom() - ((value - min_value) / spread) * rect.height()
            points.append(QPointF(x, y))
        return points

    def _active_index(self) -> int:
        return self.hover_index if self.hover_index >= 0 else self.selected_index

    def _nearest_index(self, x_pos: float) -> int:
        points = self._points(self._chart_rect())
        if not points:
            return -1
        distances = [abs(point.x() - x_pos) for point in points]
        nearest = min(range(len(distances)), key=distances.__getitem__)
        return nearest if distances[nearest] <= 24 else -1

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        self.hover_index = self._nearest_index(event.pos().x())
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self.hover_index = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        nearest = self._nearest_index(event.pos().x())
        self.selected_index = -1 if nearest == self.selected_index else nearest
        self.update()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.line_color = QColor(COLORS["accent"])
        self.fill_color = with_alpha(COLORS["accent"], 40)
        rect = self._chart_rect()
        painter.fillRect(self.rect(), Qt.transparent)

        if not self.values:
            painter.setPen(QColor(COLORS["slate_400"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "Grafik verisi yok")
            return

        max_value = max(self.values) or 1
        min_value = min(self.values)
        spread = max(max_value - min_value, 1)
        points = self._points(rect)
        active_index = self._active_index()

        guide_pen = QPen(with_alpha(COLORS["slate_500"], 44), 1, Qt.DotLine)
        painter.setPen(guide_pen)
        for row in range(5):
            y = int(rect.top() + row * rect.height() / 4)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)

        if active_index >= 0:
            painter.setPen(QPen(with_alpha(COLORS["accent"], 90), 1, Qt.DashLine))
            painter.drawLine(QPointF(points[active_index].x(), rect.top()), QPointF(points[active_index].x(), rect.bottom()))

        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)

        fill_path = QPainterPath(path)
        fill_path.lineTo(points[-1].x(), rect.bottom())
        fill_path.lineTo(points[0].x(), rect.bottom())
        fill_path.closeSubpath()

        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0, with_alpha(COLORS["accent"], 70))
        gradient.setColorAt(1, with_alpha(COLORS["accent"], 12))
        painter.fillPath(fill_path, gradient)

        painter.setPen(QPen(self.line_color, 3))
        painter.drawPath(path)

        for index, point in enumerate(points):
            if index == active_index:
                painter.setBrush(with_alpha(COLORS["accent"], 40))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(point, 12, 12)
            radius = 6 if index == active_index else 4
            painter.setBrush(with_alpha(COLORS["surface"], 244))
            painter.setPen(QPen(self.line_color, 2))
            painter.drawEllipse(point, radius, radius)

        painter.setPen(QColor(COLORS["slate_500"]))
        painter.setFont(QFont("Segoe UI", 9))
        for index, label in enumerate(self.labels):
            x = rect.left() + (rect.width() * index / max(len(self.labels) - 1, 1))
            painter.drawText(QRectF(x - 18, rect.bottom() + 10, 36, 18), Qt.AlignCenter, label)

        painter.setPen(QColor(COLORS["slate_400"]))
        painter.setFont(QFont("Segoe UI", 9))
        for step in range(4):
            value = max_value - (spread * step / 3)
            y = rect.top() + step * rect.height() / 3
            painter.drawText(QRectF(8, y - 10, rect.left() - 16, 18), Qt.AlignRight | Qt.AlignVCenter, format_chart_value(value))

        if active_index >= 0:
            point = points[active_index]
            bubble = QRectF(point.x() - 64, point.y() - 58, 128, 44)
            if bubble.left() < rect.left():
                bubble.moveLeft(rect.left())
            if bubble.right() > rect.right():
                bubble.moveRight(rect.right())
            if bubble.top() < 4:
                bubble.moveTop(point.y() + 14)

            painter.setPen(QPen(with_alpha(COLORS["slate_500"], 34), 1))
            painter.setBrush(with_alpha(COLORS["surface"], 236))
            painter.drawRoundedRect(bubble, 14, 14)
            painter.setPen(QColor(COLORS["slate_500"]))
            painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
            painter.drawText(QRectF(bubble.left(), bubble.top() + 8, bubble.width(), 12), Qt.AlignCenter, self.labels[active_index])
            painter.setPen(QColor(COLORS["slate_900"]))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(QRectF(bubble.left(), bubble.top() + 20, bubble.width(), 16), Qt.AlignCenter, format_chart_value(self.values[active_index]))


# Basit bar grafik çizimi yapan yardımcı widget.
class BarChartWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values: List[float] = []
        self.labels: List[str] = []
        self.setMinimumHeight(208)

    def set_series(self, labels: List[str], values: List[float]) -> None:
        self.labels = labels
        self.values = values
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(16, 12, -16, -28)
        if not self.values:
            painter.setPen(QColor(COLORS["slate_400"]))
            painter.drawText(self.rect(), Qt.AlignCenter, "Grafik verisi yok")
            return

        max_value = max(self.values) or 1
        bar_width = rect.width() / max(len(self.values) * 1.5, 1)

        painter.setPen(QPen(with_alpha(COLORS["slate_500"], 36), 1, Qt.DotLine))
        for row in range(5):
            y = rect.top() + row * rect.height() / 4
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))

        for index, value in enumerate(self.values):
            x = rect.left() + index * bar_width * 1.5 + 4
            height = (value / max_value) * (rect.height() - 10)
            bar_rect = QRectF(x, rect.bottom() - height, bar_width, height)
            painter.setBrush(QColor(COLORS["accent"]))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bar_rect, 7, 7)
            painter.setPen(QColor(COLORS["slate_500"]))
            painter.drawText(QRectF(x - 4, rect.bottom() + 5, bar_width + 8, 18), Qt.AlignCenter, self.labels[index])


# 0-100 arası skoru halka grafik olarak gösterir.
class DonutScoreWidget(QWidget):
    def __init__(self, score: int = 0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.score = score
        self.setMinimumSize(162, 162)

    def set_score(self, score: int) -> None:
        self.score = max(0, min(score, 100))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(18, 18, -18, -18)

        track_pen = QPen(with_alpha(COLORS["slate_500"], 26), 12)
        value_pen = QPen(QColor(COLORS["emerald"]), 12)
        value_pen.setCapStyle(Qt.RoundCap)

        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(value_pen)
        painter.drawArc(rect, 90 * 16, int(-360 * 16 * self.score / 100))

        painter.setPen(QColor(COLORS["slate_900"]))
        painter.setFont(QFont("Segoe UI", 24, QFont.Bold))
        painter.drawText(self.rect(), Qt.AlignCenter, str(self.score))


# Müşteri AI skorunu okunur 1-5 yıldız görünümüne çevirir.
class StarRatingWidget(QWidget):
    """1-5 yıldız gösteren read-only widget. ai_score (0-100) → yıldız."""

    STAR_FILLED = "★"
    STAR_EMPTY = "☆"

    def __init__(self, score: int = 0, size: int = 16, parent=None):
        super().__init__(parent)
        self._stars = self.score_to_stars(score)
        self._size = size
        self._setup()

    @staticmethod
    def score_to_stars(score: int) -> int:
        if score >= 85:
            return 5
        elif score >= 68:
            return 4
        elif score >= 50:
            return 3
        elif score >= 30:
            return 2
        else:
            return 1

    def _setup(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        for i in range(5):
            star = QLabel(self.STAR_FILLED if i < self._stars else self.STAR_EMPTY)
            color = "#f59e0b" if i < self._stars else COLORS["slate_300"]
            star.setStyleSheet(f"color: {color}; font-size: {self._size}px;")
            star.setFixedWidth(self._size + 4)
            layout.addWidget(star)

    def set_score(self, score: int):
        self._stars = self.score_to_stars(score)
        # Clear and rebuild
        while self.layout().count():
            item = self.layout().takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(5):
            star = QLabel(self.STAR_FILLED if i < self._stars else self.STAR_EMPTY)
            color = "#f59e0b" if i < self._stars else COLORS["slate_300"]
            star.setStyleSheet(f"color: {color}; font-size: {self._size}px;")
            star.setFixedWidth(self._size + 4)
            self.layout().addWidget(star)


# Formlarda kullanıcıdan 1-5 yıldız puanı almak için kullanılır.
class StarRatingInput(QWidget):
    """Tıklanabilir 1-5 yıldız input widget'ı (formlar için)."""

    def __init__(self, initial: int = 3, size: int = 24, parent=None):
        super().__init__(parent)
        self._value = initial
        self._size = size
        self._buttons = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        from PyQt5.QtWidgets import QPushButton
        for i in range(5):
            btn = QPushButton("★")
            btn.setFixedSize(size + 10, size + 10)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, idx=i: self._set_value(idx + 1))
            layout.addWidget(btn)
            self._buttons.append(btn)
        self._update_display()

    def _set_value(self, val: int):
        self._value = val
        self._update_display()

    def _update_display(self):
        for i, btn in enumerate(self._buttons):
            if i < self._value:
                btn.setStyleSheet(f"""
                    QPushButton {{ background: transparent; border: none; color: #f59e0b;
                    font-size: {self._size}px; font-weight: bold; }}
                    QPushButton:hover {{ color: #d97706; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background: transparent; border: none; color: {COLORS['slate_300']};
                    font-size: {self._size}px; }}
                    QPushButton:hover {{ color: #f59e0b; }}
                """)

    def value(self) -> int:
        return self._value

    @staticmethod
    def stars_to_score(stars: int) -> int:
        mapping = {1: 15, 2: 35, 3: 55, 4: 75, 5: 92}
        return mapping.get(stars, 55)

