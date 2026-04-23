from __future__ import annotations

import shutil
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import (
    QDate, QMimeData, QObject, QPoint, QParallelAnimationGroup, QPropertyAnimation, QEasingCurve,
    QRect, QRectF, QSize, QSizeF, Qt, QThread, QTimer, QUrl, pyqtSignal,
)
from PyQt5.QtGui import (
    QColor, QCursor, QDesktopServices, QDrag, QFont, QLinearGradient, QPalette,
    QPainter, QPdfWriter, QPen, QPixmap, QTextCursor,
)
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QGraphicsOpacityEffect,
)

from ..ai import AIEngine
from ..veritabani import DatabaseManager
from ..veritabani.db import PRIORITY_OPTIONS, STATUS_OPTIONS, TAG_OPTIONS, parse_iso
from ..yetki import ROLE_OPTIONS, user_can, user_can_view, visible_views_for_role

from .dialogs import (
    CallDialog,
    ContactDialog,
    EmailDialog,
    NoteDialog,
    OpportunityDialog,
    SettingsDialog,
    TaskDialog,
    UserDialog,
)
from .styles import COLORS, apply_theme, get_app_style
from .widgets import (
    AvatarLabel, BadgeLabel, BarChartWidget, CardFrame, DonutScoreWidget,
    ExpandableStatCard, LineChartWidget, ProgressRow, StarRatingWidget, StatCard,
    apply_shadow, get_badge_tones, rgba_string, with_alpha,
)

# Bu dosya ana pencereyi ve uygulamadaki tüm ana sayfa widgetlarını içerir.
# Veri işlemleri DatabaseManager üzerinden, AI yanıtları ise AIEngine üzerinden çağrılır.

MONTH_NAMES = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]
MONTH_NAMES_SHORT = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
PAGE_MARGIN = 20
SECTION_SPACING = 14
CARD_PADDING = 20


# Para değerlerini arayüzde TL formatına çevirir.
def format_currency(value: float) -> str:
    return f"₺{value:,.0f}".replace(",", ".")


# Ad soyaddan avatar için iki harflik kısaltma üretir.
def initials(name: str) -> str:
    parts = [item for item in name.split() if item]
    if not parts:
        return "NA"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return f"{parts[0][0]}{parts[1][0]}".upper()


# ISO tarih metnini kısa Türkçe tarih/saat görünümüne çevirir.
def format_datetime(value: Optional[str], with_time: bool = True) -> str:
    dt = parse_iso(value)
    if not dt:
        return "-"
    month = MONTH_NAMES_SHORT[dt.month - 1]
    if with_time:
        return f"{dt.day:02d} {month} {dt.year} {dt.hour:02d}:{dt.minute:02d}"
    return f"{dt.day:02d} {month} {dt.year}"


# Takvim başlıklarında kullanılan tam tarih formatı.
def format_full_date(value: date) -> str:
    return f"{value.day:02d} {MONTH_NAMES[value.month - 1]} {value.year}"


# Son temas gibi alanları "Bugün", "Dün", "3 gün önce" şeklinde gösterir.
def format_relative_moment(value: Optional[str]) -> str:
    dt = parse_iso(value)
    if not dt:
        return "Henüz temas yok"
    day_delta = (datetime.now().date() - dt.date()).days
    if day_delta <= 0:
        return "Bugün"
    if day_delta == 1:
        return "Dün"
    if day_delta < 7:
        return f"{day_delta} gün önce"
    if day_delta < 30:
        return f"{max(1, day_delta // 7)} hafta önce"
    return format_datetime(value, with_time=False)


# Dosya boyutunu B, KB veya MB olarak okunur hale getirir.
def format_file_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


# Dinamik yenilenen layout'ların içindeki eski widgetları temizler.
def clear_layout(layout) -> None:
    if layout is None:
        return
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        else:
            child_layout = item.layout()
            if child_layout is not None:
                clear_layout(child_layout)
                child_layout.deleteLater()


# Butonlara uygulamadaki ortak stil varyantlarını atar.
def style_button(button, variant: str = "ghost") -> None:
    is_tool_button = isinstance(button, QToolButton)
    mapping = {
        "primary": "PrimaryAction" if is_tool_button else "PrimaryButton",
        "ghost": "GhostAction" if is_tool_button else "GhostButton",
        "danger": "DangerButton",
        "success": "SuccessButton",
        "header": "HeaderIcon",
        "segment": "SegmentButton",
    }
    button.setObjectName(mapping.get(variant, "GhostButton"))


# Tek satırda stil verilmiş, callback bağlanmış QPushButton oluşturur.
def make_button(text: str, callback, variant: str = "ghost", flat: bool = False) -> QPushButton:
    button = QPushButton(text)
    style_button(button, variant)
    button.setCursor(Qt.PointingHandCursor)
    button.clicked.connect(callback)
    if flat:
        button.setFixedHeight(34)
    return button


# Tablo widgetlarında ortak kolon, seçim ve görünüm ayarlarını yapar.
def configure_table(table: QTableWidget, headers: List[str], stretch_last: bool = True) -> None:
    table.setObjectName("DataTable")
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(52)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setFocusPolicy(Qt.NoFocus)
    table.setShowGrid(False)
    table.setSortingEnabled(False)
    table.setWordWrap(True)
    table.setTextElideMode(Qt.ElideRight)
    table.verticalHeader().setDefaultSectionSize(64)
    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    header.setSectionResizeMode(QHeaderView.ResizeToContents)
    if stretch_last:
        header.setStretchLastSection(True)


# QTableWidget içine hizalı ve isteğe bağlı kalın metin yerleştirir.
def set_table_item(table: QTableWidget, row: int, column: int, text: str, align=Qt.AlignLeft | Qt.AlignVCenter, bold: bool = False) -> None:
    item = QTableWidgetItem(text)
    item.setTextAlignment(int(align))
    if bold:
        font = item.font()
        font.setBold(True)
        item.setFont(font)
    table.setItem(row, column, item)


# Görev tarih ve tamamlanma durumundan kullanıcıya görünen durumu hesaplar.
def resolve_task_status(task: Dict[str, Any]) -> str:
    if task.get("is_done"):
        return "Tamamlandı"
    due_at = parse_iso(task.get("due_at"))
    if not due_at:
        return "Bekliyor"
    now = datetime.now()
    if due_at < now:
        return "Gecikti"
    if due_at.date() == now.date():
        return "Bugün"
    return "Planlandı"


# Kart başlığı, alt başlığı ve gövde layout'u ile standart panel oluşturur.
def create_card(title: str, subtitle: str = "") -> tuple:
    card = CardFrame()
    outer = QVBoxLayout(card)
    outer.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
    outer.setSpacing(16)
    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(10)
    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)
    title_label = QLabel(title)
    title_label.setObjectName("CardTitle")
    text_col.addWidget(title_label)
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("CardSubtitle")
        subtitle_label.setWordWrap(True)
        text_col.addWidget(subtitle_label)
    header.addLayout(text_col)
    header.addStretch(1)
    outer.addLayout(header)
    body = QVBoxLayout()
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(12)
    outer.addLayout(body)
    return card, body, header


def role_accent_color(role: str) -> str:
    mapping = {
        "Süper Admin": COLORS["violet"],
        "Yönetici": COLORS["accent"],
        "Satış Müdürü": COLORS["amber"],
        "Satış Temsilcisi": COLORS["cyan"],
        "Destek": COLORS["emerald"],
        "Finans": COLORS["rose"],
    }
    return mapping.get(role, COLORS["accent"])


# ─────────────────────────────────────────────────────────
# SEARCH RESULTS & NOTIFICATIONS DIALOGS
# ─────────────────────────────────────────────────────────
# Header aramasından gelen sonuçları gruplu ağaç görünümünde gösterir.
class SearchResultsDialog(QDialog):
    def __init__(self, results: Dict[str, List[Dict[str, Any]]], parent=None):
        super().__init__(parent)
        self.selected_result: Optional[Dict[str, Any]] = None
        self.setWindowTitle("Arama Sonuçları")
        self.resize(580, 480)
        layout = QVBoxLayout(self)
        title = QLabel("Global Arama Sonuçları")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Başlık", "Detay"])
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(True)
        for section_name, items in results.items():
            root = QTreeWidgetItem([section_name.capitalize(), f"{len(items)} sonuç"])
            root.setFirstColumnSpanned(True)
            tree.addTopLevelItem(root)
            for item in items:
                label = item.get("full_name") or item.get("title") or "Kayıt"
                detail = item.get("company") or ""
                child = QTreeWidgetItem([label, detail])
                child.setData(0, Qt.UserRole, item)
                root.addChild(child)
        tree.expandAll()
        layout.addWidget(tree, 1)
        tree.itemDoubleClicked.connect(self._accept_item)
        self.tree = tree

    def _accept_item(self, item, _column):
        payload = item.data(0, Qt.UserRole)
        if payload:
            self.selected_result = payload
            self.accept()


# Tek bir bildirimi kart/tile olarak gösteren tıklanabilir bileşen.
class NotificationTile(QFrame):
    clicked = pyqtSignal(dict)

    def __init__(self, notification: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.notification = notification
        self.selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("NotificationTile")
        self.setAttribute(Qt.WA_StyledBackground, True)
        apply_shadow(self, blur=18, y_offset=4)

        tone = {
            "Başarı": (COLORS["emerald_light"], COLORS["emerald"]),
            "Bilgi": (COLORS["accent_light"], COLORS["accent"]),
            "Kritik": (COLORS["rose_light"], COLORS["rose"]),
            "Uyarı": (COLORS["amber_light"], COLORS["amber"]),
        }
        self.tone_bg, self.tone_fg = tone.get(notification.get("severity"), (COLORS["slate_100"], COLORS["slate_700"]))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.avatar = AvatarLabel(initials(notification["title"]), self.tone_fg, 42)
        layout.addWidget(self.avatar, 0, Qt.AlignTop)

        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.title_label = QLabel(notification["title"])
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 14px; font-weight: 800;")
        top.addWidget(self.title_label, 1)
        top.addWidget(BadgeLabel(notification.get("severity", "Bilgi")))
        if not notification.get("is_read"):
            unread = QLabel("Yeni")
            unread.setStyleSheet(
                f"""
                QLabel {{
                    background: {rgba_string(COLORS['accent'], 18)};
                    color: {COLORS['accent']};
                    border-radius: 12px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 800;
                }}
                """
            )
            top.addWidget(unread)
        body.addLayout(top)

        self.message_label = QLabel(notification["message"])
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px; line-height: 1.45;")
        body.addWidget(self.message_label)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(8)
        route = notification.get("action_view")
        route_label = QLabel("İlgili ekran açılır" if route else "Bilgilendirme kaydı")
        route_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 700;")
        time_label = QLabel(format_datetime(notification.get("created_at")))
        time_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 700;")
        footer.addWidget(route_label)
        footer.addStretch(1)
        footer.addWidget(time_label)
        body.addLayout(footer)

        layout.addLayout(body, 1)
        self._sync_style()

    def _sync_style(self) -> None:
        background = "#ffffff" if not self.selected else rgba_string(self.tone_fg, 15)
        self.setStyleSheet(
            f"""
            QFrame#NotificationTile {{
                background: {background};
                border-radius: 24px;
            }}
            """
        )

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        self._sync_style()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        self.clicked.emit(self.notification)
        super().mousePressEvent(event)


# Bildirimleri özet ve liste halinde gösteren modal pencere.
class NotificationDialog(QDialog):
    def __init__(self, notifications: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.notifications = notifications
        self.selected_notification: Optional[Dict[str, Any]] = None
        self.tiles: List[NotificationTile] = []
        self.setWindowTitle("Bildirim Merkezi")
        self.resize(620, 620)
        layout = QVBoxLayout(self)

        title = QLabel("Bildirim Merkezi")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Son aksiyonları tek bakışta gör, istediğin kaydı seçip ilgili ekrana geç.")
        subtitle.setObjectName("SectionSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        unread_count = len([item for item in notifications if not item.get("is_read")])
        summary = QFrame()
        summary.setStyleSheet(
            f"""
            QFrame {{
                background: {COLORS['surface_alt']};
                border-radius: 20px;
            }}
            """
        )
        summary_layout = QHBoxLayout(summary)
        summary_layout.setContentsMargins(16, 14, 16, 14)
        summary_layout.setSpacing(12)
        summary_layout.addWidget(self._make_summary_metric("Toplam", str(len(notifications)), COLORS["accent"]))
        summary_layout.addWidget(self._make_summary_metric("Okunmamış", str(unread_count), COLORS["amber"]))
        summary_layout.addWidget(self._make_summary_metric("Kritik", str(len([item for item in notifications if item.get("severity") == "Kritik"])), COLORS["rose"]))
        summary_layout.addStretch(1)
        layout.addWidget(summary)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.feed_layout = QVBoxLayout(body)
        self.feed_layout.setContentsMargins(2, 6, 2, 6)
        self.feed_layout.setSpacing(12)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        self.selection_hint = QLabel("Bir bildirim seçtiğinde ilgili ekran doğrudan açılır.")
        self.selection_hint.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")

        if notifications:
            for item in notifications:
                tile = NotificationTile(item)
                tile.clicked.connect(self.select_notification)
                self.tiles.append(tile)
                self.feed_layout.addWidget(tile)
            self.feed_layout.addStretch(1)
            self.select_notification(notifications[0])
        else:
            empty = CardFrame()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(22, 22, 22, 22)
            empty_layout.setSpacing(8)
            empty_title = QLabel("Henüz bildirim yok")
            empty_title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 18px; font-weight: 800;")
            empty_text = QLabel("Yeni görüşme, görev ve satış aksiyonları oluştuğunda bu alan otomatik dolacak.")
            empty_text.setWordWrap(True)
            empty_text.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
            empty_layout.addWidget(empty_title)
            empty_layout.addWidget(empty_text)
            self.feed_layout.addWidget(empty)
            self.feed_layout.addStretch(1)
        layout.addWidget(self.selection_hint)

        button_row = QHBoxLayout()
        open_button = make_button("Aç", self.accept_selected, "primary")
        close_button = make_button("Kapat", self.reject, "ghost")
        self.open_button = open_button
        self.open_button.setEnabled(bool(notifications))
        button_row.addStretch(1)
        button_row.addWidget(open_button)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

    def _make_summary_metric(self, label: str, value: str, tone: str) -> QWidget:
        wrap = QFrame()
        wrap.setStyleSheet(
            f"""
            QFrame {{
                background: {rgba_string(tone, 14)};
                border-radius: 16px;
            }}
            """
        )
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        title = QLabel(label)
        title.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 800;")
        val = QLabel(value)
        val.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 18px; font-weight: 800;")
        layout.addWidget(title)
        layout.addWidget(val)
        return wrap

    def select_notification(self, notification: Dict[str, Any]) -> None:
        self.selected_notification = notification
        if hasattr(self, "open_button"):
            self.open_button.setEnabled(True)
        for tile in self.tiles:
            tile.set_selected(tile.notification["id"] == notification["id"])
        route = notification.get("action_view")
        if route:
            self.selection_hint.setText(f"Seçili kayıt: {notification['title']}  •  Açılacak ekran: {route}")
        else:
            self.selection_hint.setText(f"Seçili kayıt: {notification['title']}")

    def accept_selected(self):
        if not self.selected_notification:
            return
        self.accept()


# Tüm ana sayfaların db, ai ve current_user erişimini ortaklaştıran taban sınıf.
class BasePage(QWidget):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__()
        self.window = window
        self.db = window.db
        self.ai = window.ai
        self.current_user = window.current_user


# Kartların tamamını tıklanabilir hale getiren küçük yardımcı frame.
class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):  # type: ignore[override]
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


# AI cevap üretimini UI thread'i dondurmadan çalıştıran worker sınıfı.
class AIReplyWorker(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, ai_engine: AIEngine, message: str):
        super().__init__()
        self.ai_engine = ai_engine
        self.message = message

    def run(self):
        try:
            reply = self.ai_engine.generate_reply(self.message)
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(reply)


# ─────────────────────────────────────────────────────────
# CALLS CUSTOMER RAIL — Görüşmeler ekranı müşteri yan paneli
# ─────────────────────────────────────────────────────────

# Görüşmeler ekranında sağdaki müşteri seçme/özet rail paneli.
class CallsCustomerRail(QFrame):
    def __init__(self, page: "CallsPage", parent=None):
        super().__init__(parent)
        self.page = page
        self._contacts: List[Dict[str, Any]] = []
        self.selected_contact_id: Optional[int] = None
        self.expanded_width = 312
        self.collapsed_width = 92
        self.expanded = True

        self.setObjectName("CallsCustomerRail")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setMinimumWidth(self.expanded_width)
        self.setMaximumWidth(self.expanded_width)
        apply_shadow(self, 24, 8)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(0)

        self.stack = QStackedWidget()
        self.stack.setObjectName("CustomerRailStack")
        root.addWidget(self.stack, 1)

        self.expanded_view = QWidget()
        expanded_layout = QVBoxLayout(self.expanded_view)
        expanded_layout.setContentsMargins(0, 0, 0, 0)
        expanded_layout.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)
        rail_chip = QLabel("PORTFÖY AKIŞI")
        rail_chip.setStyleSheet(
            f"background: {rgba_string(COLORS['accent'], 16)}; color: {COLORS['accent']}; "
            "padding: 6px 10px; border-radius: 11px; font-size: 10px; font-weight: 900;"
        )
        self.expanded_count = QLabel("0 kayıt")
        self.expanded_count.setStyleSheet(
            f"color: {COLORS['slate_600']}; font-size: 11px; font-weight: 800;"
        )
        self.expand_toggle = QPushButton("<")
        self.expand_toggle.setObjectName("CustomerRailToggle")
        self.expand_toggle.setFixedSize(34, 34)
        self.expand_toggle.setCursor(Qt.PointingHandCursor)
        self.expand_toggle.setToolTip("Müşteri listesini daralt")
        self.expand_toggle.clicked.connect(self.toggle)
        top_row.addWidget(rail_chip)
        top_row.addStretch(1)
        top_row.addWidget(self.expanded_count)
        top_row.addWidget(self.expand_toggle)
        expanded_layout.addLayout(top_row)

        title = QLabel("Müşteri Listesi")
        title.setObjectName("RailTitle")
        expanded_layout.addWidget(title)

        hero = QFrame()
        hero.setObjectName("RailHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(16, 14, 16, 14)
        hero_layout.setSpacing(6)
        self.hero_label = QLabel("Hazır seçim")
        self.hero_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 10px; font-weight: 900; letter-spacing: 1px;")
        self.hero_title = QLabel("Portföy boş")
        self.hero_title.setWordWrap(True)
        self.hero_title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 17px; font-weight: 900;")
        self.hero_meta = QLabel("Henüz müşteri kaydı görünmüyor.")
        self.hero_meta.setWordWrap(True)
        self.hero_meta.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px; line-height: 1.4;")
        hero_layout.addWidget(self.hero_label)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_meta)
        expanded_layout.addWidget(hero)

        list_header = QHBoxLayout()
        list_header.setContentsMargins(0, 0, 0, 0)
        list_header.setSpacing(8)
        list_title = QLabel("Canlı Liste")
        list_title.setObjectName("RailListTitle")
        list_hint = QLabel("Seç ve akışı başlat")
        list_hint.setObjectName("RailListHint")
        list_header.addWidget(list_title)
        list_header.addStretch(1)
        list_header.addWidget(list_hint)
        expanded_layout.addLayout(list_header)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_scroll.setStyleSheet("background: transparent;")
        list_stream = QWidget()
        list_stream.setObjectName("CustomerRailViewport")
        self.list_layout = QVBoxLayout(list_stream)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(10)
        self.list_scroll.setWidget(list_stream)
        expanded_layout.addWidget(self.list_scroll, 1)

        self.compact_view = QWidget()
        compact_layout = QVBoxLayout(self.compact_view)
        compact_layout.setContentsMargins(0, 0, 0, 0)
        compact_layout.setSpacing(12)

        compact_top = QHBoxLayout()
        compact_top.setContentsMargins(0, 0, 0, 0)
        compact_top.addStretch(1)
        self.compact_toggle = QPushButton(">")
        self.compact_toggle.setObjectName("CustomerRailToggle")
        self.compact_toggle.setFixedSize(34, 34)
        self.compact_toggle.setCursor(Qt.PointingHandCursor)
        self.compact_toggle.setToolTip("Müşteri listesini aç")
        self.compact_toggle.clicked.connect(self.toggle)
        compact_top.addWidget(self.compact_toggle)
        compact_top.addStretch(1)
        compact_layout.addLayout(compact_top)

        bubble = QFrame()
        bubble.setObjectName("RailCompactBubble")
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 14, 10, 14)
        bubble_layout.setSpacing(4)
        compact_badge = QLabel("LISTE")
        compact_badge.setAlignment(Qt.AlignCenter)
        compact_badge.setStyleSheet(f"color: {COLORS['accent']}; font-size: 9px; font-weight: 900;")
        self.compact_count = QLabel("0")
        self.compact_count.setAlignment(Qt.AlignCenter)
        self.compact_count.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 24px; font-weight: 900;")
        self.compact_focus = QLabel("Hazır")
        self.compact_focus.setWordWrap(True)
        self.compact_focus.setAlignment(Qt.AlignCenter)
        self.compact_focus.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 10px; font-weight: 800;")
        bubble_layout.addWidget(compact_badge)
        bubble_layout.addWidget(self.compact_count)
        bubble_layout.addWidget(self.compact_focus)
        compact_layout.addWidget(bubble)

        self.compact_avatar_layout = QVBoxLayout()
        self.compact_avatar_layout.setContentsMargins(0, 0, 0, 0)
        self.compact_avatar_layout.setSpacing(8)
        compact_layout.addLayout(self.compact_avatar_layout)
        compact_layout.addStretch(1)

        self.stack.addWidget(self.expanded_view)
        self.stack.addWidget(self.compact_view)
        self.stack.setCurrentWidget(self.expanded_view)

        self.width_group = QParallelAnimationGroup(self)
        self._min_width_anim = QPropertyAnimation(self, b"minimumWidth", self)
        self._max_width_anim = QPropertyAnimation(self, b"maximumWidth", self)
        for anim in (self._min_width_anim, self._max_width_anim):
            anim.setDuration(220)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self.width_group.addAnimation(anim)
        self.width_group.finished.connect(self._on_animation_finished)

    def toggle(self) -> None:
        self.set_expanded(not self.expanded)

    def set_expanded(self, expanded: bool) -> None:
        if self.expanded == expanded:
            return
        self.expanded = expanded
        if expanded:
            self.stack.setCurrentWidget(self.expanded_view)
        current_width = max(self.width(), self.collapsed_width)
        target_width = self.expanded_width if expanded else self.collapsed_width
        self.width_group.stop()
        self._min_width_anim.setStartValue(current_width)
        self._min_width_anim.setEndValue(target_width)
        self._max_width_anim.setStartValue(current_width)
        self._max_width_anim.setEndValue(target_width)
        self.width_group.start()

    def _on_animation_finished(self) -> None:
        self.stack.setCurrentWidget(self.expanded_view if self.expanded else self.compact_view)

    def set_contacts(self, contacts: List[Dict[str, Any]], selected_contact_id: Optional[int]) -> None:
        self._contacts = contacts
        self.selected_contact_id = selected_contact_id
        self._render()

    def set_selected_contact(self, contact_id: Optional[int]) -> None:
        if self.selected_contact_id == contact_id:
            return
        self.selected_contact_id = contact_id
        self._render()

    def _render(self) -> None:
        clear_layout(self.list_layout)
        clear_layout(self.compact_avatar_layout)

        contacts = self._contacts
        self.expanded_count.setText(f"{len(contacts)} kayıt")
        self.compact_count.setText(str(len(contacts)))

        featured = next((item for item in contacts if item["id"] == self.selected_contact_id), None)
        if not featured and contacts:
            featured = contacts[0]

        if featured:
            selected = featured["id"] == self.selected_contact_id
            self.hero_label.setText("SEÇİLİ MÜŞTERİ" if selected else "ÖNE ÇIKAN HESAP")
            self.hero_title.setText(featured["full_name"])
            company = featured.get("company") or "Firma bilgisi yok"
            sales = float(featured.get("total_sales") or 0)
            if sales > 0:
                meta = f"{company} • {format_currency(sales)} satış • Risk %{featured.get('churn_risk', 0)}"
            else:
                meta = (
                    f"{company} • AI {featured.get('ai_score', 0)} • "
                    f"Son temas {format_relative_moment(featured.get('last_contact_at'))}"
                )
            self.hero_meta.setText(meta)
            self.compact_focus.setText(initials(featured["full_name"]))
        else:
            self.hero_label.setText("HAZIR SEÇİM")
            self.hero_title.setText("Portföy boş")
            self.hero_meta.setText("Henüz müşteri kaydı görünmüyor.")
            self.compact_focus.setText("Boş")

        if not contacts:
            empty = QLabel("Müşteri eklendiğinde burada hızlı seçim rayı oluşacak.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; padding: 8px 4px;")
            self.list_layout.addWidget(empty)
            self.list_layout.addStretch(1)
            return

        tones = [COLORS["accent"], COLORS["violet"], COLORS["amber"], COLORS["emerald"], COLORS["cyan"]]
        for index, contact in enumerate(contacts):
            tone = tones[index % len(tones)]
            self.list_layout.addWidget(
                self._build_customer_item(
                    contact,
                    tone,
                    selected=contact["id"] == self.selected_contact_id,
                )
            )
        self.list_layout.addStretch(1)

        for index, contact in enumerate(contacts[:5]):
            avatar = AvatarLabel(initials(contact["full_name"]), tones[index % len(tones)], 42)
            avatar.setToolTip(contact["full_name"])
            self.compact_avatar_layout.addWidget(avatar, 0, Qt.AlignHCenter)
        if len(contacts) > 5:
            more = QLabel(f"+{len(contacts) - 5}")
            more.setAlignment(Qt.AlignCenter)
            more.setStyleSheet(
                f"background: {rgba_string(COLORS['surface'], 180)}; color: {COLORS['slate_600']}; "
                "padding: 7px 0; border-radius: 14px; font-size: 10px; font-weight: 800;"
            )
            self.compact_avatar_layout.addWidget(more)
        self.compact_avatar_layout.addStretch(1)

    def _build_customer_item(self, contact: Dict[str, Any], tone: str, selected: bool = False) -> QWidget:
        item = ClickableFrame()
        item.setAttribute(Qt.WA_StyledBackground, True)
        item.setToolTip("Hızlı görüşme için müşteriyi seç")
        base_bg = rgba_string(tone, 18) if selected else rgba_string(COLORS["surface"], 148)
        hover_bg = rgba_string(tone, 24)
        item.setStyleSheet(
            f"""
            QFrame {{
                background: {base_bg};
                border: none;
                border-radius: 18px;
            }}
            QFrame:hover {{
                background: {hover_bg};
                border: none;
            }}
            """
        )

        layout = QVBoxLayout(item)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)
        avatar = AvatarLabel(initials(contact["full_name"]), tone, 36)
        top.addWidget(avatar, 0, Qt.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        name = QLabel(contact["full_name"])
        name.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 12px; font-weight: 900;")
        company = QLabel(contact.get("company") or "Firma bilgisi yok")
        company.setWordWrap(True)
        company.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 10px;")
        info.addWidget(name)
        info.addWidget(company)
        top.addLayout(info, 1)

        score = QLabel(f"AI {contact.get('ai_score', 0)}")
        score.setAlignment(Qt.AlignCenter)
        score.setStyleSheet(
            f"background: {rgba_string(tone, 24)}; color: {tone}; border-radius: 10px; "
            "padding: 5px 9px; font-size: 10px; font-weight: 900;"
        )
        top.addWidget(score)
        layout.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)
        meta = QLabel(
            f"Son temas {format_relative_moment(contact.get('last_contact_at'))} • Risk %{contact.get('churn_risk', 0)}"
        )
        meta.setWordWrap(True)
        meta.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 10px;")
        status = QLabel(contact.get("status") or "Aktif")
        status.setAlignment(Qt.AlignCenter)
        status.setStyleSheet(
            f"background: {rgba_string(COLORS['slate_900'], 16)}; color: {COLORS['slate_700']}; "
            "padding: 4px 8px; border-radius: 9px; font-size: 9px; font-weight: 800;"
        )
        bottom.addWidget(meta, 1)
        bottom.addWidget(status)
        layout.addLayout(bottom)

        item.clicked.connect(lambda cid=contact["id"]: self.page._select_customer_from_rail(cid))
        return item


# Dashboard ve raporlarda detay aç/kapat destekli KPI kartı.
class _CollapsibleStatCard(QFrame):
    """Stat card that expands/collapses on click to show details."""

    def __init__(self, title: str, value: str, meta: str, meta_color: str,
                 details: List[tuple] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setCursor(Qt.PointingHandCursor)
        self._expanded = False
        self._details = details or []

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 16, 20, 16)
        self.main_layout.setSpacing(6)

        # Header (always visible)
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 800; letter-spacing: 1.2px;")
        
        self.indicator_lbl = QLabel("Detay ▼")
        self.indicator_lbl.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 9px; font-weight: 800;")
        
        header_row.addWidget(t_lbl)
        header_row.addStretch(1)
        header_row.addWidget(self.indicator_lbl)
        self.main_layout.addLayout(header_row)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 28px; font-weight: 900;")
        self.main_layout.addWidget(val_lbl)

        meta_lbl = QLabel(meta)
        meta_lbl.setStyleSheet(f"color: {meta_color}; font-size: 10px; font-weight: 600;")
        self.main_layout.addWidget(meta_lbl)

        # Detail area (hidden by default)
        self.detail_widget = QWidget()
        self.detail_layout = QVBoxLayout(self.detail_widget)
        self.detail_layout.setContentsMargins(0, 8, 0, 0)
        self.detail_layout.setSpacing(4)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {COLORS['slate_100']};")
        self.detail_layout.addWidget(sep)

        for label, val in self._details:
            row = QHBoxLayout()
            row.setContentsMargins(0, 4, 0, 4)
            row.setSpacing(4)
            l = QLabel(label)
            l.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            v = QLabel(str(val))
            v.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 11px; font-weight: 700;")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            row.addWidget(l, 1)
            row.addWidget(v)
            self.detail_layout.addLayout(row)

        self.detail_widget.setMaximumHeight(0)
        self.detail_widget.setVisible(False)
        self.main_layout.addWidget(self.detail_widget)

        apply_shadow(self, 8, 0.06)

    def mousePressEvent(self, event):
        self._toggle()
        super().mousePressEvent(event)

    def _toggle(self):
        self._expanded = not self._expanded
        if self._expanded:
            self.detail_widget.setVisible(True)
            self.detail_widget.setMaximumHeight(16777215)
            self.indicator_lbl.setText("Gizle ▲")
        else:
            self.detail_widget.setMaximumHeight(0)
            self.detail_widget.setVisible(False)
            self.indicator_lbl.setText("Detay ▼")


# ─────────────────────────────────────────────────────────
# DASHBOARD PAGE — Light theme compact design
# ─────────────────────────────────────────────────────────

# Ana kontrol paneli: satış, pipeline, aktivite ve AI önerilerini özetler.
class DashboardPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.main_layout = QVBoxLayout(self.container)
        self.main_layout.setContentsMargins(18, 16, 18, 18)
        self.main_layout.setSpacing(16)
        scroll.setWidget(self.container)
        root.addWidget(scroll)
        self.sales_chart: Optional[LineChartWidget] = None
        self.sales_modes: Dict[str, Dict[str, Any]] = {}
        self.sales_mode_buttons: Dict[str, QPushButton] = {}
        self.sales_metric_labels: List[tuple] = []
        self.refresh()

    def refresh(self):
        clear_layout(self.main_layout)
        summary = self.db.get_dashboard_summary()
        brief = self.ai.dashboard_brief()
        recommendations = self.ai.weekly_recommendations(limit=3)
        self.sales_modes = self._build_sales_modes(summary["sales_series"])
        self.sales_mode_buttons = {}
        self.sales_metric_labels = []

        try:
            pipeline_data = self.db.get_pipeline_summary()
        except Exception:
            pipeline_data = []

        # Welcome Row
        self.main_layout.addWidget(self._build_welcome_row(summary))
        # Stat Cards
        self.main_layout.addWidget(self._build_stat_cards(summary))

        # Content Grid
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        # Left column
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)
        left_layout.addWidget(self._build_sales_panel())

        bottom_row = QWidget()
        bottom_layout = QHBoxLayout(bottom_row)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(16)
        bottom_layout.addWidget(self._build_pipeline_panel(pipeline_data))
        bottom_layout.addWidget(self._build_active_customers(summary))
        left_layout.addWidget(bottom_row)

        # Right column
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(16)
        right_layout.addWidget(self._build_activity_panel(summary))
        right_layout.addWidget(self._build_ai_panel(recommendations, brief))
        right_layout.addStretch(1)

        content_layout.addWidget(left, 3)
        content_layout.addWidget(right, 2)
        self.main_layout.addWidget(content)
        self.main_layout.addStretch(1)

    # ── Welcome Row ─────────────────────────────────────
    def _build_welcome_row(self, summary):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(2)
        title = QLabel(f"Hoş geldin, {self.current_user['full_name'].split()[0]}  👋")
        title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 19px; font-weight: 800;")
        month_name = MONTH_NAMES[date.today().month - 1]
        subtitle = QLabel(f"{month_name} {date.today().year} · Genel bakış")
        subtitle.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
        left.addWidget(title)
        left.addWidget(subtitle)
        layout.addLayout(left, 1)

        if self.window.can("report_export"):
            report_btn = make_button("📊 Rapor AI", self.window.export_report_pdf, "ghost")
            layout.addWidget(report_btn)
        return row

    # ── Stat Cards ──────────────────────────────────────
    def _build_stat_cards(self, summary):
        wrapper = QWidget()
        grid = QHBoxLayout(wrapper)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(16)

        growth = summary["growth"]
        growth_sign = "↑" if growth >= 0 else "↓"
        growth_color = COLORS["accent"] if growth >= 0 else COLORS["rose"]

        cards = [
            ("TOPLAM MÜŞTERİ", str(summary["total_customers"]),
             f"{growth_sign} %{abs(growth)} bu ay eklendi", growth_color,
             [("Aktif müşteri", str(summary["total_customers"])),
              ("Pipeline değeri", format_currency(summary["pipeline_value"])),
              ("Büyüme oranı", f"%{summary['growth']}")]),
            ("BU AY SATIŞ", format_currency(summary["monthly_sales"]),
             f"{growth_sign} %{abs(growth)} geçen aya göre", growth_color,
             [("Bu ay kapanış", format_currency(summary["monthly_sales"])),
              ("Pipeline", format_currency(summary["pipeline_value"])),
              ("Hedef ilerleme", f"%{summary.get('goal_sales_percent', 0)}")]),
            ("BEKLEYEN TEKLİF", str(summary["pending_offer_count"]),
             f"● {format_currency(summary['pending_offer_value'])} değerinde", COLORS["violet"],
             [("Teklif adedi", str(summary["pending_offer_count"])),
              ("Teklif toplamı", format_currency(summary["pending_offer_value"]))]),
            ("YAKLAŞAN TOPLANTI", str(summary["upcoming_call_count"]),
             f"► bugün {summary['today_call_count']} toplantı var", COLORS["cyan"],
             [("Bugünkü", str(summary["today_call_count"])),
              ("Bu hafta", str(summary["upcoming_call_count"]))]),
        ]

        for title, value, meta, meta_color, details in cards:
            card = _CollapsibleStatCard(title, value, meta, meta_color, details)
            grid.addWidget(card)

        return wrapper

    # ── Sales Panel ─────────────────────────────────────
    def _build_sales_panel(self):
        sales_card, sales_body, sales_header = create_card("Satış Performansı", "Hover ile ay detaylarını incele")
        sales_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(6)
        for key, label in [("monthly", "Aylık"), ("cumulative", "Kümülatif"), ("trend", "Trend")]:
            button = make_button(label, lambda _=False, mode=key: self._set_sales_mode(mode), "segment")
            button.setCheckable(True)
            button.setAutoExclusive(True)
            controls_layout.addWidget(button)
            self.sales_mode_buttons[key] = button
        sales_header.addWidget(controls)

        self.sales_chart = LineChartWidget()
        self.sales_chart.setMaximumHeight(200)
        sales_body.addWidget(self.sales_chart)

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(8)
        self.sales_metric_labels = []
        for _ in range(3):
            block = QFrame()
            bg_color = rgba_string(COLORS["slate_500"], 10)
            block.setStyleSheet(f"background: {bg_color}; border-radius: 14px;")
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(10, 8, 10, 8)
            block_layout.setSpacing(2)
            caption = QLabel("")
            caption.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
            value = QLabel("")
            value.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 800;")
            block_layout.addWidget(caption)
            block_layout.addWidget(value)
            metrics_row.addWidget(block, 1)
            self.sales_metric_labels.append((caption, value))
        sales_body.addLayout(metrics_row)
        self._set_sales_mode("monthly")
        return sales_card

    # ── Activity Panel ──────────────────────────────────
    def _build_activity_panel(self, summary):
        activity_card, activity_body, _ = create_card("Son Aktiviteler")
        if not summary["recent_activities"]:
            placeholder = QLabel("Henüz yeni aktivite kaydı yok.")
            placeholder.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
            activity_body.addWidget(placeholder)
            return activity_card

        kind_colors = {
            "Satış": COLORS["accent"], "Görüşme": COLORS["emerald"],
            "Teklif": COLORS["violet"], "Görev": COLORS["amber"],
            "Mail": COLORS["cyan"], "Dosya": COLORS["rose"],
            "Müşteri": COLORS["accent"], "AI": COLORS["violet"],
        }
        kind_icons = {
            "Satış": "💰", "Görüşme": "📞", "Teklif": "📋",
            "Görev": "✅", "Mail": "✉️", "Dosya": "📁",
            "Müşteri": "👤", "AI": "🤖",
        }

        for item in summary["recent_activities"][:5]:
            row = QFrame()
            bg_color = rgba_string(COLORS["slate_500"], 10)
            row.setStyleSheet(f"background: {bg_color}; border-radius: 16px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 10, 12, 10)
            rl.setSpacing(12)

            kind = item.get("kind", "")
            color = kind_colors.get(kind, COLORS["accent"])
            rl.addWidget(AvatarLabel(initials(kind), color, 38), 0, Qt.AlignVCenter)

            col = QVBoxLayout()
            col.setContentsMargins(0, 0, 0, 0)
            col.setSpacing(2)
            t = QLabel(item["title"])
            t.setStyleSheet(f"color: {COLORS['slate_900']}; font-weight: 700; font-size: 13px;")
            t.setWordWrap(True)
            col.addWidget(t)

            desc_text = item.get("description", "").strip()
            if desc_text and desc_text != item["title"]:
                d = QLabel(desc_text)
                d.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
                d.setWordWrap(True)
                col.addWidget(d)

            ts = QLabel(format_datetime(item.get("created_at")))
            ts.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px;")
            col.addWidget(ts)
            rl.addLayout(col, 1)

            icon = kind_icons.get(kind, "📌")
            kind_badge = QLabel(f"{icon} {kind}")
            kind_badge.setStyleSheet(f"""
                QLabel {{
                    background: {rgba_string(color, 18)};
                    color: {color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 800;
                }}
            """)
            rl.addWidget(kind_badge, 0, Qt.AlignVCenter)
            activity_body.addWidget(row)

        return activity_card

    # ── Pipeline Panel ──────────────────────────────────
    def _build_pipeline_panel(self, pipeline_data):
        card, body, header = create_card("Satış Pipeline")
        # Compact 'Canlı' badge
        pill = QLabel("Canlı")
        pill.setObjectName("PipelineLiveBadge")
        pill.setStyleSheet(f"""
            QLabel#PipelineLiveBadge {{
                background: {COLORS['emerald']};
                color: white;
                border-radius: 8px;
                padding: 3px 8px;
                font-size: 9px;
                font-weight: 800;
                min-width: 30px;
                max-height: 20px;
            }}
        """)
        header.addWidget(pill)

        stage_colors = {
            "Potansiyel": COLORS["slate_400"],
            "Görüşme": COLORS["violet"],
            "Teklif": COLORS["amber"],
            "Kazanıldı": COLORS["emerald"],
            "Kaybedildi": COLORS["rose"],
        }

        max_count = 1
        stages = []
        if pipeline_data:
            for item in pipeline_data:
                stages.append((item["stage"], item["count"], stage_colors.get(item["stage"], COLORS["slate_400"])))
                if item["count"] > max_count:
                    max_count = item["count"]
        else:
            stages = [("Potansiyel", 0, COLORS["slate_400"]), ("Görüşme", 0, COLORS["violet"]),
                       ("Teklif", 0, COLORS["amber"]), ("Kazanıldı", 0, COLORS["emerald"]),
                       ("Kaybedildi", 0, COLORS["rose"])]

        for stage_name, count, color in stages:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 2, 0, 2)
            rl.setSpacing(8)

            name = QLabel(stage_name)
            name.setFixedWidth(72)
            name.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px; font-weight: 600;")
            rl.addWidget(name)

            # Use stretch-based bar (not fixed pixel width)
            fill_pct = max(2, int((count / max(max_count, 1)) * 100))
            empty_pct = 100 - fill_pct
            bar_container = QWidget()
            bar_container.setFixedHeight(8)
            bar_lay = QHBoxLayout(bar_container)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            bar_fill = QFrame()
            bar_fill.setFixedHeight(8)
            bar_fill.setStyleSheet(f"background: {color}; border-radius: 4px;")
            bar_empty = QFrame()
            bar_empty.setFixedHeight(8)
            bar_empty.setStyleSheet(f"background: {COLORS['slate_100']}; border-radius: 4px;")
            bar_lay.addWidget(bar_fill, fill_pct)
            bar_lay.addWidget(bar_empty, empty_pct)
            rl.addWidget(bar_container, 1)

            val = QLabel(str(count))
            val.setFixedWidth(26)
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 11px; font-weight: 700;")
            rl.addWidget(val)
            body.addWidget(row)

        return card

    # ── Active Customers ────────────────────────────────
    def _build_active_customers(self, summary):
        card, body, _ = create_card("En Aktif Müşteriler")
        customers = summary["top_customers"][:4]
        cust_colors = [COLORS["accent"], COLORS["violet"], COLORS["amber"], COLORS["emerald"]]

        for i, c in enumerate(customers):
            row = QFrame()
            row.setStyleSheet(f"background: {COLORS['surface_alt']}; border-radius: 16px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(10, 8, 10, 8)
            rl.setSpacing(8)

            color = cust_colors[i % len(cust_colors)]
            rl.addWidget(AvatarLabel(initials(c["full_name"]), color, 30))

            info = QVBoxLayout()
            info.setContentsMargins(0, 0, 0, 0)
            info.setSpacing(1)
            name = QLabel(c["full_name"])
            name.setStyleSheet(f"color: {COLORS['slate_900']}; font-weight: 700; font-size: 12px;")
            score = QLabel(f"{c['ai_score']} puan")
            score.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px;")
            info.addWidget(name)
            info.addWidget(score)
            rl.addLayout(info, 1)

            tag = c.get("tag", "")
            status = c.get("status", "Aktif")
            badge_text = tag if tag in get_badge_tones() else status
            rl.addWidget(BadgeLabel(badge_text))
            body.addWidget(row)

        return card

    # ── AI Suggestions ──────────────────────────────────
    def _build_ai_panel(self, recommendations, brief):
        card, body, header = create_card("AI Koç Önerileri")
        for item_text in recommendations:
            item_row = QWidget()
            il = QHBoxLayout(item_row)
            il.setContentsMargins(0, 2, 0, 2)
            il.setSpacing(8)
            bullet = QLabel("●")
            bullet.setFixedWidth(12)
            bullet.setStyleSheet(f"color: {COLORS['accent']}; font-size: 7px;")
            il.addWidget(bullet, 0, Qt.AlignTop)
            text = QLabel(item_text)
            text.setWordWrap(True)
            text.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px;")
            il.addWidget(text, 1)
            body.addWidget(item_row)
        return card

    # ── Sales mode helpers ──────────────────────────────
    def _build_sales_modes(self, sales_series):
        labels = list(sales_series["labels"])
        monthly_values = [float(v) for v in sales_series["values"]]
        cumulative_values = []
        running = 0.0
        for v in monthly_values:
            running += v
            cumulative_values.append(running)
        trend_values = []
        for i, _ in enumerate(monthly_values):
            window = monthly_values[max(0, i - 2): i + 1]
            trend_values.append(sum(window) / max(len(window), 1))
        return {
            "monthly": {"labels": labels, "values": monthly_values, "series_name": "Aylık kapanış"},
            "cumulative": {"labels": labels, "values": cumulative_values, "series_name": "Kümülatif hacim"},
            "trend": {"labels": labels, "values": trend_values, "series_name": "3 aylık trend"},
        }

    def _set_sales_mode(self, mode: str):
        if mode not in self.sales_modes:
            return
        data = self.sales_modes[mode]
        labels, values = data["labels"], data["values"]
        if self.sales_chart:
            self.sales_chart.set_series(labels, values, data["series_name"])
        if mode in self.sales_mode_buttons:
            self.sales_mode_buttons[mode].setChecked(True)
        if not values or not labels:
            return
        peak_index = max(range(len(values)), key=values.__getitem__)
        if mode == "monthly":
            metrics = [("Son ay", format_currency(values[-1])), ("En güçlü ay", labels[peak_index]), ("Yıllık toplam", format_currency(sum(values)))]
        elif mode == "cumulative":
            metrics = [("Toplam kapanış", format_currency(values[-1])), ("Zirve seviye", labels[peak_index]), ("Ortalama ay", format_currency(values[-1] / max(len(values), 1)))]
        else:
            metrics = [("Son trend", format_currency(values[-1])), ("En sıcak ay", labels[peak_index]), ("Trend farkı", format_currency(values[-1] - values[0]))]
        for (caption_label, value_label), (caption, value) in zip(self.sales_metric_labels, metrics):
            caption_label.setText(caption)
            value_label.setText(value)

# ─────────────────────────────────────────────────────────
# CONTACTS PAGE — Yeniden tasarım
# ─────────────────────────────────────────────────────────
# Müşteri listesinden açılan sağ detay paneli.
class ContactSlidePanel(QFrame):
    """Sağdan süzülen müşteri detay paneli."""
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SlidePanel")
        self.setFixedWidth(480)
        self._contact_id: Optional[int] = None
        self.db: Optional[DatabaseManager] = None
        self.ai: Optional[AIEngine] = None
        self.current_user: Optional[Dict[str, Any]] = None
        self.window_ref = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QFrame()
        header.setStyleSheet(f"background: {COLORS['slate_50']}; border-top-left-radius: 28px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 16, 16)
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{ background: {COLORS['slate_200']}; border: none; border-radius: 18px;
            font-size: 14px; font-weight: 800; color: {COLORS['slate_600']}; }}
            QPushButton:hover {{ background: {COLORS['rose_light']}; color: {COLORS['rose']}; }}
        """)
        self.close_btn.clicked.connect(self._close)
        self.panel_title = QLabel("Müşteri Detay")
        self.panel_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLORS['slate_900']};")
        header_layout.addWidget(self.panel_title, 1)
        header_layout.addWidget(self.close_btn)
        layout.addWidget(header)

        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(20, 16, 20, 20)
        self.content_layout.setSpacing(16)
        scroll.setWidget(self.content)
        layout.addWidget(scroll, 1)

        apply_shadow(self, blur=40, y_offset=0)

    def _close(self):
        self.closed.emit()

    def load_contact(self, contact_id: int):
        self._contact_id = contact_id
        clear_layout(self.content_layout)
        contact = self.db.get_contact(contact_id) if self.db else None
        if not contact:
            self.content_layout.addWidget(QLabel("Müşteri bulunamadı."))
            return

        # Profil kartı
        profile = QFrame()
        profile.setStyleSheet(f"background: {COLORS['accent_light']}; border-radius: 18px;")
        pl = QVBoxLayout(profile)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.setSpacing(10)
        top_row = QHBoxLayout()
        top_row.addWidget(AvatarLabel(initials(contact["full_name"]), COLORS["accent"], 52))
        info = QVBoxLayout()
        name_lbl = QLabel(contact["full_name"])
        name_lbl.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['slate_900']};")
        meta_lbl = QLabel(f"{contact.get('title') or '-'}  •  {contact['company']}")
        meta_lbl.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px;")
        info.addWidget(name_lbl)
        info.addWidget(meta_lbl)
        top_row.addLayout(info, 1)
        pl.addLayout(top_row)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(6)
        for txt in [contact["tag"], contact["status"], contact["priority"]]:
            tags_row.addWidget(BadgeLabel(txt))
        tags_row.addStretch(1)
        pl.addLayout(tags_row)
        self.content_layout.addWidget(profile)

        # Hızlı aksiyonlar
        actions = QHBoxLayout()
        actions.setSpacing(8)
        phone = contact.get("phone") or ""
        if self.window_ref and self.window_ref.can("call_create"):
            actions.addWidget(make_button("Ara", lambda: self.window_ref.start_quick_call(contact_id) if self.window_ref else None, "primary"))
        if self.window_ref and self.window_ref.can("mail_compose"):
            actions.addWidget(make_button("✉️ Mail", lambda: self.window_ref.compose_mail_for_contact(contact_id) if self.window_ref else None, "ghost"))
        actions.addWidget(make_button("WhatsApp", lambda: self.window_ref.open_whatsapp(contact.get("whatsapp") or phone) if self.window_ref else None, "ghost"))
        if self.window_ref and self.window_ref.can("contact_edit"):
            actions.addWidget(make_button("✏️ Düzenle", lambda: self.window_ref.open_contact_dialog(contact) if self.window_ref else None, "ghost"))
        self.content_layout.addLayout(actions)

        # Tab sistemi
        tabs = QTabWidget()
        tabs.setObjectName("DetailTab")

        # Tab 1: Genel
        general_tab = QWidget()
        gt_layout = QVBoxLayout(general_tab)
        gt_layout.setContentsMargins(4, 12, 4, 4)
        gt_layout.setSpacing(12)

        # İletişim bilgileri
        fields = [
            ("Telefon", contact.get("phone") or "-"),
            ("E-posta", contact.get("email") or "-"),
            ("Konum", f"{contact.get('city') or '-'}, {contact.get('country') or '-'}"),
            ("Son Temas", format_datetime(contact.get("last_contact_at"), False)),
            ("Sorumlu", contact.get("assigned_name") or "-"),
        ]
        for label, value in fields:
            row = QHBoxLayout()
            left = QLabel(label)
            left.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_500']}; font-size: 12px;")
            right = QLabel(value)
            right.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 12px;")
            row.addWidget(left)
            row.addStretch(1)
            row.addWidget(right)
            gt_layout.addLayout(row)

        # AI Skor & Yıldız Değerlendirme
        if self.ai and self.db:
            analysis = self.ai.contact_analysis(contact_id)
            score_frame = QFrame()
            score_frame.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 16px;")
            sf_layout = QVBoxLayout(score_frame)
            sf_layout.setContentsMargins(14, 14, 14, 14)
            sf_layout.setSpacing(10)
            # Yıldız derecelendirme
            star_row = QHBoxLayout()
            star_label = QLabel("Müşteri Puanı")
            star_label.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 14px;")
            star_row.addWidget(star_label)
            star_row.addStretch(1)
            stars = StarRatingWidget(analysis["score"])
            star_row.addWidget(stars)
            sf_layout.addLayout(star_row)
            # AI Skor numarası
            score_row = QHBoxLayout()
            score_text = QLabel(f"AI Skoru: {analysis['score']}/100")
            score_text.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px; font-weight: 600;")
            score_row.addWidget(score_text)
            score_row.addStretch(1)
            sf_layout.addLayout(score_row)
            # AI Öneri
            rec = QLabel(f"Öneri: {analysis['recommendation']}")
            rec.setWordWrap(True)
            rec.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px; padding: 8px; background: rgba(255,255,255,0.7); border-radius: 10px;")
            sf_layout.addWidget(rec)
            gt_layout.addWidget(score_frame)

        if contact.get("notes"):
            notes_lbl = QLabel(f"Not: {contact['notes']}")
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px; padding: 10px; background: {COLORS['slate_50']}; border-radius: 12px;")
            gt_layout.addWidget(notes_lbl)

        gt_layout.addStretch(1)
        tabs.addTab(general_tab, "Genel")

        # Tab 2: Timeline
        timeline_tab = QWidget()
        tl_layout = QVBoxLayout(timeline_tab)
        tl_layout.setContentsMargins(4, 12, 4, 4)
        tl_layout.setSpacing(8)
        activities = self.db.list_activities(limit=10, contact_id=contact_id) if self.db else []
        if activities:
            for act in activities:
                act_frame = QFrame()
                act_frame.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 12px;")
                al = QVBoxLayout(act_frame)
                al.setContentsMargins(12, 10, 12, 10)
                al.setSpacing(4)
                at = QLabel(act["title"])
                at.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']}; font-size: 12px;")
                ad = QLabel(act["description"])
                ad.setWordWrap(True)
                ad.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
                am = QLabel(format_datetime(act.get("created_at")))
                am.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px;")
                al.addWidget(at)
                al.addWidget(ad)
                al.addWidget(am)
                tl_layout.addWidget(act_frame)
        else:
            tl_layout.addWidget(QLabel("Henüz aktivite yok."))
        tl_layout.addStretch(1)
        tabs.addTab(timeline_tab, "Timeline")

        # Tab 3: Notlar
        notes_tab = QWidget()
        nt_layout = QVBoxLayout(notes_tab)
        nt_layout.setContentsMargins(4, 12, 4, 4)
        nt_layout.setSpacing(8)
        if self.window_ref and self.window_ref.can("contact_note_create"):
            nt_layout.addWidget(make_button("+ Not Ekle", lambda: self.window_ref.add_note_to_contact(contact_id) if self.window_ref else None, "ghost"))
        notes = self.db.list_contact_notes(contact_id) if self.db else []
        if notes:
            for note in notes:
                nf = QFrame()
                nf.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 12px;")
                nl = QVBoxLayout(nf)
                nl.setContentsMargins(12, 10, 12, 10)
                nl.setSpacing(4)
                nh = QLabel(note["title"])
                nh.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']};")
                nm = QLabel(f"{note.get('author_name') or 'Sistem'} • {format_datetime(note['created_at'])}")
                nm.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 11px;")
                nc = QLabel(note["content"])
                nc.setWordWrap(True)
                nc.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px;")
                nl.addWidget(nh)
                nl.addWidget(nm)
                nl.addWidget(nc)
                nt_layout.addWidget(nf)
        else:
            nt_layout.addWidget(QLabel("Not bulunmuyor."))
        nt_layout.addStretch(1)
        tabs.addTab(notes_tab, "Notlar")

        # Tab 4: Fırsatlar
        if self.window_ref and self.window_ref.can_view("pipeline"):
            opp_tab = QWidget()
            ot_layout = QVBoxLayout(opp_tab)
            ot_layout.setContentsMargins(4, 12, 4, 4)
            ot_layout.setSpacing(8)
            if self.window_ref.can("opportunity_create"):
                ot_layout.addWidget(make_button("+ Fırsat Ekle", lambda: self.window_ref.open_opportunity_dialog(prefill_contact_id=contact_id) if self.window_ref else None, "primary"))
            opps = [o for o in (self.db.list_opportunities() if self.db else []) if o["contact_id"] == contact_id]
            for opp in opps:
                of = QFrame()
                of.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 12px;")
                ol = QHBoxLayout(of)
                ol.setContentsMargins(12, 10, 12, 10)
                left_col = QVBoxLayout()
                ot = QLabel(opp["title"])
                ot.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']};")
                ov = QLabel(format_currency(opp["value"]))
                ov.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px;")
                left_col.addWidget(ot)
                left_col.addWidget(ov)
                ol.addLayout(left_col, 1)
                ol.addWidget(BadgeLabel(opp["stage"]))
                ot_layout.addWidget(of)
            if not opps:
                ot_layout.addWidget(QLabel("Fırsat kaydı yok."))
            ot_layout.addStretch(1)
            tabs.addTab(opp_tab, "Fırsatlar")

        self.content_layout.addWidget(tabs, 1)

        # Sil butonu en altta; yalnızca yetkili rollerde görünür.
        if self.window_ref and self.window_ref.can("contact_delete"):
            del_btn = make_button("Müşteriyi Sil", lambda: self.window_ref.delete_contact(contact_id) if self.window_ref else None, "danger")
            self.content_layout.addWidget(del_btn)


# Müşteri arama, filtreleme, listeleme ve detay panelini yöneten sayfa.
class ContactsPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sol taraf: Liste
        list_area = QWidget()
        list_layout = QVBoxLayout(list_area)
        list_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        list_layout.setSpacing(SECTION_SPACING)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        t = QLabel("Müşteri Listesi")
        t.setObjectName("SectionTitle")
        s = QLabel("Müşteri satırına tıklayarak detay panelini açın.")
        s.setObjectName("SectionSubtitle")
        title_box.addWidget(t)
        title_box.addWidget(s)
        top.addLayout(title_box)
        top.addStretch(1)
        if self.window.can("contact_create"):
            top.addWidget(make_button("+ Müşteri Ekle", self.window.open_contact_dialog, "primary"))
        list_layout.addLayout(top)

        # Filtreler
        filters = CardFrame()
        filter_layout = QHBoxLayout(filters)
        filter_layout.setContentsMargins(14, 10, 14, 10)
        filter_layout.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("SearchInput")
        self.search.setPlaceholderText("Müşteri ara...")
        self.status_combo = self._create_filter_combo(["Tüm Durumlar"] + self.window.status_options)
        self.tag_combo = self._create_filter_combo(["Tüm Etiketler"] + self.window.tag_options)
        self.sort_combo = self._create_filter_combo(["En Yeni", "A-Z", "En Yüksek Satış", "AI Skor"])
        filter_layout.addWidget(self.search, 2)
        filter_layout.addWidget(self.status_combo)
        filter_layout.addWidget(self.tag_combo)
        filter_layout.addWidget(self.sort_combo)
        list_layout.addWidget(filters)

        # Liste (Scroll Area)
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setStyleSheet("background: transparent;")
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_stream = QWidget()
        self.list_stream.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_stream)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(10)
        self.list_scroll.setWidget(self.list_stream)
        list_layout.addWidget(self.list_scroll, 1)

        root.addWidget(list_area, 1)

        # Sağ taraf: Detay paneli
        self.detail_panel = ContactSlidePanel()
        self.detail_panel.db = self.db
        self.detail_panel.ai = self.ai
        self.detail_panel.current_user = self.current_user
        self.detail_panel.window_ref = self.window
        self.detail_panel.closed.connect(self._close_panel)
        self.detail_panel.setVisible(False)
        root.addWidget(self.detail_panel)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.refresh)
        
        self.search.textChanged.connect(self.search_timer.start)
        self.status_combo.currentTextChanged.connect(self.refresh)
        self.tag_combo.currentTextChanged.connect(self.refresh)
        self.sort_combo.currentTextChanged.connect(self.refresh)
        self._contact_ids: List[int] = []
        self.refresh()

    def _create_filter_combo(self, items):
        combo = self.window.create_combo(items)
        combo.setMinimumWidth(168)
        return combo

    def _on_card_clicked(self, cid: int):
        self.detail_panel.db = self.db
        self.detail_panel.ai = self.ai
        self.detail_panel.current_user = self.current_user
        self.detail_panel.window_ref = self.window
        self.detail_panel.load_contact(cid)
        self.detail_panel.setVisible(True)
        self.window.current_contact_id = cid

    def _close_panel(self):
        self.detail_panel.setVisible(False)

    def refresh(self):
        status = "" if self.status_combo.currentText() == "Tüm Durumlar" else self.status_combo.currentText()
        tag = "" if self.tag_combo.currentText() == "Tüm Etiketler" else self.tag_combo.currentText()
        contacts = self.db.list_contacts(
            search=self.search.text(),
            status=status,
            tag=tag,
            sort_by=self.sort_combo.currentText(),
        )
        self._contact_ids = [c["id"] for c in contacts]
        
        clear_layout(self.list_layout)
        
        for contact in contacts:
            self.list_layout.addWidget(self._build_contact_card(contact))
            
        self.list_layout.addStretch(1)

        # Paneli de güncelle
        if self.detail_panel.isVisible() and self.detail_panel._contact_id:
            self.detail_panel.load_contact(self.detail_panel._contact_id)

    def _build_contact_card(self, contact: Dict[str, Any]) -> QWidget:
        card = ClickableFrame()
        border_color = rgba_string(COLORS["slate_900"], 8 if not self.window.is_dark_mode else 16)
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: none;
                border-radius: 18px;
            }}
            QFrame:hover {{
                background: {COLORS['surface_alt']};
            }}
        """)

        card.clicked.connect(lambda c=contact: self._on_card_clicked(c["id"]))
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)
        
        # 1. Avatar
        avatar = AvatarLabel(initials(contact["full_name"]), COLORS["accent"], 38)
        layout.addWidget(avatar, 0, Qt.AlignVCenter)
        
        # 2. İsim & Firma
        info_col = QVBoxLayout()
        info_col.setContentsMargins(0, 0, 0, 0)
        info_col.setSpacing(4)
        name = QLabel(contact["full_name"])
        name.setStyleSheet(f"font-size: 13px; font-weight: 900; color: {COLORS['slate_900']};")
        company = QLabel(contact.get("company") or "Firma bilgisi yok")
        company.setStyleSheet(f"font-size: 11px; color: {COLORS['slate_500']};")
        info_col.addWidget(name)
        info_col.addWidget(company)
        layout.addLayout(info_col, 2)
        
        # 3. İletişim
        contact_col = QVBoxLayout()
        contact_col.setContentsMargins(0, 0, 0, 0)
        contact_col.setSpacing(4)
        phone = QLabel(contact.get("phone") or "-")
        phone.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {COLORS['slate_700']};")
        email = QLabel(contact.get("email") or "-")
        email.setStyleSheet(f"font-size: 11px; color: {COLORS['slate_500']};")
        contact_col.addWidget(phone)
        contact_col.addWidget(email)
        layout.addLayout(contact_col, 2)
        
        # 4. Etiket & AI
        badge_col = QVBoxLayout()
        badge_col.setContentsMargins(0, 0, 0, 0)
        badge_col.setSpacing(6)
        
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.setSpacing(6)
        badge_row.addWidget(BadgeLabel(contact["tag"]))
        badge_row.addWidget(BadgeLabel(contact["status"]))
        badge_row.addStretch(1)
        badge_col.addLayout(badge_row)
        
        score_val = int(contact.get("ai_score", 0))
        star_widget = StarRatingWidget(score_val)
        badge_col.addWidget(star_widget)
        layout.addLayout(badge_col, 2)
        
        # 5. Sağ Taraf: Son Temas ve Detay Butonu
        right_side = QVBoxLayout()
        right_side.setContentsMargins(0, 0, 0, 0)
        right_side.setSpacing(6)
        last_contact = QLabel(f"Son temas: {format_datetime(contact.get('last_contact_at'), False)}")
        last_contact.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {COLORS['slate_500']};")
        right_side.addWidget(last_contact, 0, Qt.AlignRight)
        
        action_btn = make_button("Detaylar", lambda _=False, cid=contact["id"]: self._on_card_clicked(cid), "ghost")
        action_btn.setMinimumWidth(80)
        action_btn.setFixedHeight(28)
        right_side.addWidget(action_btn, 0, Qt.AlignRight)
        
        layout.addLayout(right_side, 1)
        
        return card


# ─────────────────────────────────────────────────────────
# PIPELINE PAGE — Drag & Drop + iyileştirilmiş tasarım
# ─────────────────────────────────────────────────────────
# Pipeline içindeki tek fırsat kartı; sürükle-bırak ve aksiyon menüsü içerir.
class DraggablePipelineCard(QFrame):
    """Sürüklenebilir pipeline kartı."""
    def __init__(self, item: Dict[str, Any], window: "CRMMainWindow", parent=None):
        super().__init__(parent)
        self.item = item
        self.window = window
        self.setObjectName("PipelineCard")
        self.setCursor(QCursor(Qt.OpenHandCursor if self.window.can("opportunity_move") else Qt.ArrowCursor))
        self.setMinimumHeight(100)
        apply_shadow(self, blur=12, y_offset=4)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(item["title"])
        title.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 13px;")
        layout.addWidget(title)

        company = QLabel(f"{item['contact_name']}  •  {item['contact_company']}")
        company.setWordWrap(True)
        company.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
        layout.addWidget(company)

        value_lbl = QLabel(format_currency(item["value"]))
        value_lbl.setStyleSheet(f"font-size: 15px; font-weight: 800; color: {COLORS['slate_900']};")
        layout.addWidget(value_lbl)

        # Butonlar: İlerlet + Menü
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        if item["stage"] not in ("Kazanıldı", "Kaybedildi") and self.window.can("opportunity_move"):
            advance_btn = make_button("İlerlet ▸", lambda _=False, oid=item["id"]: self.window.move_opportunity(oid, 1), "success")
            advance_btn.setFixedHeight(30)
            btn_row.addWidget(advance_btn)

        menu_btn = QToolButton()
        menu_btn.setText("⋯")
        menu_btn.setFixedSize(30, 30)
        menu_btn.setStyleSheet(f"""
            QToolButton {{ background: {COLORS['slate_100']}; border: none; border-radius: 8px;
            font-size: 16px; font-weight: 800; color: {COLORS['slate_600']}; }}
            QToolButton:hover {{ background: {COLORS['accent_light']}; color: {COLORS['accent']}; }}
        """)
        menu = QMenu(menu_btn)
        if self.window.can("opportunity_edit"):
            menu.addAction("Düzenle", lambda _=False, row=item: self.window.open_opportunity_dialog(row))
        if item["stage"] != "Potansiyel" and self.window.can("opportunity_move"):
            menu.addAction("Geri Al", lambda _=False, oid=item["id"]: self.window.move_opportunity(oid, -1))
        if self.window.can_view("contacts"):
            menu.addAction("Müşteri Detay", lambda _=False, cid=item["contact_id"]: self.window.open_contact_detail(cid))
        if self.window.can("opportunity_delete"):
            menu.addSeparator()
            menu.addAction("Sil", lambda _=False, oid=item["id"]: self.window.delete_opportunity(oid))
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        btn_row.addStretch(1)
        btn_row.addWidget(menu_btn)
        layout.addLayout(btn_row)

    def mousePressEvent(self, event):
        if self.window.can("opportunity_move") and event.button() == Qt.LeftButton:
            self.setCursor(QCursor(Qt.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(QCursor(Qt.OpenHandCursor if self.window.can("opportunity_move") else Qt.ArrowCursor))
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event):
        if self.window.can("opportunity_move") and event.buttons() & Qt.LeftButton:
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(str(self.item["id"]))
            drag.setMimeData(mime)
            pixmap = QPixmap(self.size())
            pixmap.fill(Qt.transparent)
            self.render(pixmap)
            drag.setPixmap(pixmap)
            drag.setHotSpot(event.pos())
            drag.exec_(Qt.MoveAction)


# Pipeline'da fırsatların bırakılabildiği aşama sütunu.
class PipelineColumn(QFrame):
    """Pipeline sütunu — drop zone."""
    def __init__(self, stage: str, color: str, window: "CRMMainWindow", parent=None):
        super().__init__(parent)
        self.stage = stage
        self.color = color
        self.window = window
        self.setAcceptDrops(window.can("opportunity_move"))
        self.setObjectName("PipelineColumn")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(10)

    def dragEnterEvent(self, event):
        if self.window.can("opportunity_move") and event.mimeData().hasText():
            event.acceptProposedAction()
            self.setStyleSheet(f"QFrame#PipelineColumn {{ background: {rgba_string(self.color, 20)}; border: none; border-radius: 20px; }}")

    def dragLeaveEvent(self, event):
        self.setStyleSheet("")
        self.setObjectName("PipelineColumn")

    def dropEvent(self, event):
        self.setStyleSheet("")
        self.setObjectName("PipelineColumn")
        if not self.window.require_permission("opportunity_move", "Fırsat aşaması değiştirme"):
            return
        opp_id = int(event.mimeData().text())
        from ..veritabani.db import STAGE_ORDER
        opp = self.window.db.get_opportunity(opp_id)
        if opp:
            try:
                current_index = STAGE_ORDER.index(opp["stage"])
                target_index = STAGE_ORDER.index(self.stage)
                diff = target_index - current_index
                if diff != 0:
                    self.window.db.save_opportunity(
                        {
                            "contact_id": opp["contact_id"],
                            "title": opp["title"],
                            "stage": self.stage,
                            "value": opp["value"],
                            "probability": self.window.db.probability_for_stage(self.stage),
                            "expected_close": opp["expected_close"],
                            "notes": opp["notes"],
                            "owner_user_id": opp["owner_user_id"],
                        },
                        opportunity_id=opp_id,
                        actor_id=self.window.current_user["id"],
                    )
                    self.window.refresh_all_views()
            except ValueError:
                pass
        event.acceptProposedAction()


# Satış fırsatlarını kanban/pipeline görünümünde gösteren sayfa.
class PipelinePage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(SECTION_SPACING)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Satış Pipeline")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Kartları sürükleyerek aşamalar arası taşıyabilirsiniz.")
        subtitle.setObjectName("SectionSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch(1)
        if self.window.can("opportunity_create"):
            top.addWidget(make_button("+ Fırsat Ekle", lambda: self.window.open_opportunity_dialog(), "primary"))
        root.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.board = QWidget()
        self.board_layout = QHBoxLayout(self.board)
        self.board_layout.setContentsMargins(0, 0, 0, 0)
        self.board_layout.setSpacing(12)
        self.scroll.setWidget(self.board)
        root.addWidget(self.scroll, 1)
        self.refresh()

    def refresh(self):
        clear_layout(self.board_layout)
        stages = self.db.get_pipeline_summary()
        for stage in stages:
            column = PipelineColumn(stage["stage"], stage["color"], self.window)
            column.setMinimumWidth(260)
            column.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

            heading = QLabel(f"{stage['stage']}  •  {stage['count']}")
            heading.setStyleSheet(f"font-size: 14px; font-weight: 800; color: {stage['color']};")
            total = QLabel(format_currency(stage["value"]))
            total.setStyleSheet(f"font-size: 12px; color: {COLORS['slate_500']}; font-weight: 600;")
            column.layout.addWidget(heading)
            column.layout.addWidget(total)

            for item in stage["items"]:
                card = DraggablePipelineCard(item, self.window)
                column.layout.addWidget(card)

            column.layout.addStretch(1)
            self.board_layout.addWidget(column, 1)


# ─────────────────────────────────────────────────────────
# CALLS PAGE — Hızlı görüşme sistemi
# ─────────────────────────────────────────────────────────
# Telefon/toplantı kaydı, hızlı arama ve yaklaşan görüşmeleri yöneten sayfa.
class CallsPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        self._active_call_contact_id: Optional[int] = None
        self._active_call_type: str = "Telefon"
        self._call_start_time: Optional[datetime] = None
        self._call_timer: Optional[QTimer] = None
        self._elapsed_seconds: int = 0
        self._suspend_customer_rail_updates = False

        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(24)

        # ── Header ──
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Görüşmeler Merkezi")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Aramalarınızı yönetin, geçmişi inceleyin ve notlarınızı alın.")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        
        top.addStretch(1)
        
        if self.window.can("call_create"):
            btn_cal = make_button("Takvime Ekle", lambda: self.window.open_call_dialog(), "ghost")
            btn_new = make_button("Planlı Görüşme", lambda: self.window.open_call_dialog(), "primary")
            btn_cal.setMinimumHeight(44)
            btn_new.setMinimumHeight(44)
            top.addWidget(btn_cal)
            top.addWidget(btn_new)
        root.addLayout(top)

        # ── Main Content (70/30 Split) ──
        content = QHBoxLayout()
        content.setSpacing(32)

        # ── SOL SÜTUN (Arama Masası + Geçmiş) %70 ──
        left_col = QVBoxLayout()
        left_col.setSpacing(24)

        # 1. Hızlı Arama Masası
        self.quick_panel = self._build_quick_call_panel()
        left_col.addWidget(self.quick_panel)
        history_shell = QHBoxLayout()
        history_shell.setSpacing(18)
        history_col = QVBoxLayout()
        history_col.setSpacing(12)

        # 2. Son Görüşmeler
        h_header = QHBoxLayout()
        h_title = QLabel("📋 Son Görüşmeler")
        h_title.setObjectName("CardTitle")
        self.history_meta = QLabel("")
        self.history_meta.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 12)}; color: {COLORS['slate_700']}; font-weight: 800; font-size: 10px; padding: 4px 10px; border-radius: 10px;")
        h_header.addWidget(h_title)
        h_header.addStretch(1)
        h_header.addWidget(self.history_meta)
        history_col.addLayout(h_header)
        
        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)
        self.history_scroll.setFrameShape(QFrame.NoFrame)
        self.history_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_scroll.setStyleSheet("background: transparent;")
        
        self.history_stream = QWidget()
        self.history_stream.setStyleSheet("background: transparent;")
        self.history_list = QVBoxLayout(self.history_stream)
        self.history_list.setContentsMargins(0, 0, 0, 20)
        self.history_list.setSpacing(10)
        
        self.history_scroll.setWidget(self.history_stream)
        history_col.addWidget(self.history_scroll, 1)
        history_shell.addLayout(history_col, 1)

        self.customer_rail = CallsCustomerRail(self)
        history_shell.addWidget(self.customer_rail)
        left_col.addLayout(history_shell, 1)

        content.addLayout(left_col, 7) # Sol %70

        # ── SAĞ SÜTUN (Metrikler + Ajanda) %30 ──
        right_col = QVBoxLayout()
        right_col.setSpacing(24)

        # 1. Kompakt Metrikler
        m_title = QLabel("Günün Özeti")
        m_title.setObjectName("CardTitle")
        right_col.addWidget(m_title)
        
        self.metrics_body = QVBoxLayout()
        self.metrics_body.setSpacing(12)
        right_col.addLayout(self.metrics_body)

        # 2. Yaklaşan Ajanda
        u_header = QHBoxLayout()
        u_title = QLabel("📅 Yaklaşan")
        u_title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 16px; font-weight: 800;")
        self.upcoming_meta = QLabel("")
        self.upcoming_meta.setStyleSheet(f"background: {rgba_string(COLORS['accent'], 15)}; color: {COLORS['accent']}; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 10px;")
        u_header.addWidget(u_title)
        u_header.addStretch(1)
        u_header.addWidget(self.upcoming_meta)
        right_col.addLayout(u_header)
        
        self.upcoming_scroll = QScrollArea()
        self.upcoming_scroll.setWidgetResizable(True)
        self.upcoming_scroll.setFrameShape(QFrame.NoFrame)
        self.upcoming_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.upcoming_scroll.setStyleSheet("background: transparent;")
        
        self.upcoming_stream = QWidget()
        self.upcoming_stream.setStyleSheet("background: transparent;")
        self.upcoming_list = QVBoxLayout(self.upcoming_stream)
        self.upcoming_list.setContentsMargins(0, 0, 0, 20)
        self.upcoming_list.setSpacing(10)
        
        self.upcoming_scroll.setWidget(self.upcoming_stream)
        right_col.addWidget(self.upcoming_scroll, 1)

        content.addLayout(right_col, 3) # Sağ %30

        root.addLayout(content, 1)
        self.refresh()

    def _build_quick_call_panel(self):
        panel = QFrame()
        panel.setStyleSheet(f"QFrame {{ background: {COLORS['surface']}; border-radius: 16px; border: none; }}")
        
        main_layout = QVBoxLayout(panel)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(16)
        
        # ── Başlık ──
        header = QHBoxLayout()
        title = QLabel("Hızlı Arama Masası")
        title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 16px; font-weight: 800; border: none;")
        hint = QLabel("Müşteriyi seçin ve görüşmeyi başlatın.")
        hint.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; border: none;")
        
        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        title_vbox.addWidget(title)
        title_vbox.addWidget(hint)
        header.addLayout(title_vbox)
        main_layout.addLayout(header)

        # ── Aksiyon Satırı (Seçim ve Başlat) ──
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        
        # Müşteri Seçimi
        self.quick_contact_combo = QComboBox()
        self.quick_contact_combo.setMinimumHeight(44)
        self.quick_contact_combo.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 8)}; border: none; border-radius: 10px; padding: 0 12px; font-size: 13px; color: {COLORS['slate_800']};")
        self.quick_contact_combo.currentIndexChanged.connect(self._update_quick_contact_context)
        action_row.addWidget(self.quick_contact_combo, 3)

        # Tür Seçimi
        type_row = QHBoxLayout()
        type_row.setSpacing(6)
        self.type_phone_btn = QPushButton("📞")
        self.type_meeting_btn = QPushButton("🤝")
        
        for btn in (self.type_phone_btn, self.type_meeting_btn):
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setFixedSize(44, 44)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setToolTip("Tür Seçin")
            
        self.type_phone_btn.setChecked(True)
        self.type_phone_btn.clicked.connect(lambda: self._set_call_type("Telefon"))
        self.type_meeting_btn.clicked.connect(lambda: self._set_call_type("Toplantı"))
        self.type_phone_btn.toggled.connect(lambda _=False: self._apply_quick_panel_theme())
        self.type_meeting_btn.toggled.connect(lambda _=False: self._apply_quick_panel_theme())
        
        type_row.addWidget(self.type_phone_btn)
        type_row.addWidget(self.type_meeting_btn)
        action_row.addLayout(type_row)

        # Başlat / Bitir / Timer
        self.timer_label = QLabel("00:00")
        self.timer_label.setMinimumWidth(60)
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setVisible(False)
        self.timer_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 18px; font-weight: 900; border: none; background: transparent;")
        action_row.addWidget(self.timer_label)
        
        self.start_call_btn = make_button("Görüşme Başlat", self._start_call, "primary")
        self.start_call_btn.setMinimumHeight(44)
        self.start_call_btn.setMinimumWidth(100)
        
        self.end_call_btn = make_button("Bitir", self._end_call, "danger")
        self.end_call_btn.setMinimumHeight(44)
        self.end_call_btn.setMinimumWidth(100)
        self.end_call_btn.setVisible(False)
        
        action_row.addWidget(self.start_call_btn)
        action_row.addWidget(self.end_call_btn)
        
        main_layout.addLayout(action_row)

        # ── Bağlam (Müşteri Detayı) ──
        self.quick_contact_context = QLabel("")
        self.quick_contact_context.setWordWrap(True)
        self.quick_contact_context.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; font-style: italic; border: none; background: transparent;")
        main_layout.addWidget(self.quick_contact_context)

        # ── Sonuç ve Kayıt Alanı (Yeni, Temiz Düzen) ──
        self.result_widget = QFrame()
        self.result_widget.setVisible(False)
        self.result_widget.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 10)}; border-radius: 12px; border: none; margin-top: 10px;")
        result_layout = QVBoxLayout(self.result_widget)
        result_layout.setContentsMargins(16, 16, 16, 16)
        result_layout.setSpacing(12)
        
        res_title = QLabel("Görüşme Detayları")
        res_title.setStyleSheet(f"color: {COLORS['slate_800']}; font-size: 13px; font-weight: 800; border: none; background: transparent;")
        result_layout.addWidget(res_title)
        
        outcome_row = QHBoxLayout()
        outcome_row.setSpacing(8)
        self.outcome_buttons: Dict[str, QPushButton] = {}
        for text, bg, fg in [
            ("Olumlu", COLORS["emerald_light"], COLORS["emerald"]),
            ("Beklemede", COLORS["amber_light"], COLORS["amber"]),
            ("Olumsuz", COLORS["rose_light"], COLORS["rose"]),
        ]:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setAutoExclusive(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ background: {rgba_string(COLORS['slate_500'], 10)}; color: {COLORS['slate_600']}; border: none; border-radius: 8px; font-size: 12px; font-weight: 700; }}
                QPushButton:checked {{ background: {bg}; color: {fg}; border: none; }}
            """)
            btn.setMinimumHeight(38)
            outcome_row.addWidget(btn)
            self.outcome_buttons[text] = btn
            
        result_layout.addLayout(outcome_row)
        
        self.quick_notes = QTextEdit()
        self.quick_notes.setPlaceholderText("Görüşme notlarını buraya girin...")
        self.quick_notes.setMinimumHeight(70)
        self.quick_notes.setMaximumHeight(100)
        self.quick_notes.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 8)}; border: none; border-radius: 8px; padding: 10px; font-size: 12px; color: {COLORS['slate_800']};")
        result_layout.addWidget(self.quick_notes)
        
        save_row = QHBoxLayout()
        save_row.addStretch(1)
        self.quick_save_btn = make_button("Kaydet", self._save_quick_call, "primary")
        self.quick_save_btn.setMinimumHeight(36)
        self.quick_cancel_btn = make_button("İptal", self._cancel_quick_call, "ghost")
        self.quick_cancel_btn.setMinimumHeight(36)
        save_row.addWidget(self.quick_cancel_btn)
        save_row.addWidget(self.quick_save_btn)
        result_layout.addLayout(save_row)
        
        main_layout.addWidget(self.result_widget)
        return panel

    def _set_call_type(self, call_type: str):
        self._active_call_type = call_type

    def _select_customer_from_rail(self, contact_id: int) -> None:
        index = self.quick_contact_combo.findData(contact_id)
        if index >= 0:
            self.quick_contact_combo.setCurrentIndex(index)
        else:
            self._update_quick_contact_context()

    def _populate_contacts(self):
        current_id = self.quick_contact_combo.currentData()
        self._suspend_customer_rail_updates = True
        self.quick_contact_combo.blockSignals(True)
        self.quick_contact_combo.clear()
        contacts = self.db.list_contacts(sort_by="A-Z")
        selected_index = 0
        for contact in contacts:
            self.quick_contact_combo.addItem(f"{contact['full_name']} - {contact['company']}", contact["id"])
            if contact["id"] == current_id:
                selected_index = self.quick_contact_combo.count() - 1
        if self.quick_contact_combo.count():
            self.quick_contact_combo.setCurrentIndex(selected_index)
        self.quick_contact_combo.blockSignals(False)
        self._update_quick_contact_context()
        self._suspend_customer_rail_updates = False

    def _update_quick_contact_context(self):
        contact_id = self.quick_contact_combo.currentData()
        contact = self.db.get_contact(contact_id) if contact_id else None
        if not contact:
            self.quick_contact_context.setText("Görüşme başlatmak için müşteri seçin.")
            if hasattr(self, "customer_rail") and not self._suspend_customer_rail_updates:
                self.customer_rail.set_selected_contact(None)
            return
        last_contact = format_datetime(contact.get("last_contact_at")) if contact.get("last_contact_at") else "Henüz temas yok"
        self.quick_contact_context.setText(
            f"Yetkili: {contact.get('title') or '-'} • Son temas: {last_contact} • Risk %{contact.get('churn_risk', 0)}"
        )
        if hasattr(self, "customer_rail") and not self._suspend_customer_rail_updates:
            self.customer_rail.set_selected_contact(contact_id)

    def _apply_quick_panel_theme(self):
        active_css = f"QPushButton {{ background: {COLORS['accent']}; color: white; border-radius: 10px; font-size: 16px; border: none; }}"
        inactive_css = f"QPushButton {{ background: {rgba_string(COLORS['slate_500'], 10)}; color: {COLORS['slate_600']}; border-radius: 10px; font-size: 16px; border: none; }}"
        self.type_phone_btn.setStyleSheet(active_css if self.type_phone_btn.isChecked() else inactive_css)
        self.type_meeting_btn.setStyleSheet(active_css if self.type_meeting_btn.isChecked() else inactive_css)

    def _build_compact_metric(self, label: str, value: str, tone: str) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"background: {rgba_string(tone, 10)}; border-radius: 12px;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 13px; font-weight: 700; background: transparent;")
        val = QLabel(value)
        val.setStyleSheet(f"color: {tone}; font-size: 20px; font-weight: 900; background: transparent;")
        lay.addWidget(lbl)
        lay.addStretch(1)
        lay.addWidget(val)
        return w

    def _create_call_menu(self, call: Dict[str, Any]) -> QToolButton:
        menu_btn = QToolButton()
        menu_btn.setText("...")
        menu_btn.setFixedSize(30, 30)
        menu_btn.setStyleSheet(
            f"""
            QToolButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: 800;
                color: {COLORS['slate_400']};
            }}
            QToolButton:hover {{
                background: {rgba_string(COLORS['slate_300'], 50)};
                color: {COLORS['slate_800']};
            }}
            """
        )
        menu = QMenu(menu_btn)
        if self.window.can("call_edit"):
            menu.addAction("Düzenle", lambda _=False, row_data=call: self.window.open_call_dialog(row_data))
        if self.window.can("call_delete"):
            menu.addAction("Sil", lambda _=False, cid=call["id"]: self.window.delete_call(cid))
        menu_btn.setMenu(menu)
        menu_btn.setPopupMode(QToolButton.InstantPopup)
        return menu_btn

    def _build_history_card(self, call: Dict[str, Any]) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{ 
                background: {rgba_string(COLORS['surface'], 220)};
                border: none;
                border-radius: 18px;
            }}
            QFrame:hover {{
                background: {rgba_string(COLORS['accent'], 9)};
                border: none;
            }}
        """)
        outer = QVBoxLayout(card)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(6)
        
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(10)

        icon = "📞" if call["call_type"] == "Telefon" else "🤝"
        icon_tone = COLORS["accent"] if call["call_type"] == "Telefon" else COLORS["violet"]
        icon_lbl = QLabel(icon)
        icon_lbl.setAlignment(Qt.AlignCenter)
        icon_lbl.setFixedSize(28, 28)
        icon_lbl.setStyleSheet(f"background: {rgba_string(icon_tone, 14)}; color: {icon_tone}; font-size: 13px; border-radius: 14px; border: none;")
        top.addWidget(icon_lbl, 0, Qt.AlignTop)
        
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        company = (call.get("contact_company") or "").strip()
        title = QLabel(call["contact_name"] if not company else f"{call['contact_name']} • {company}")
        title.setWordWrap(True)
        title.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {COLORS['slate_900']}; border: none; background: transparent;")
        
        meta = QLabel(f"{format_datetime(call['scheduled_at'])} • {call['duration_minutes']} dk")
        meta.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; border: none; background: transparent;")
        
        info.addWidget(title)
        info.addWidget(meta)
        top.addLayout(info, 1)
        
        menu_btn = self._create_call_menu(call)
        top.addWidget(menu_btn, 0, Qt.AlignTop)
        outer.addLayout(top)
        
        badge_row = QHBoxLayout()
        badge_row.setContentsMargins(38, 0, 0, 0)
        badge_row.setSpacing(8)
        
        out = call["outcome"]
        out_bg = COLORS["emerald_light"] if out == "Olumlu" else COLORS["rose_light"] if out == "Olumsuz" else COLORS["amber_light"]
        out_fg = COLORS["emerald"] if out == "Olumlu" else COLORS["rose"] if out == "Olumsuz" else COLORS["amber"]
        out_badge = QLabel(out)
        out_badge.setStyleSheet(f"background: {out_bg}; color: {out_fg}; padding: 2px 8px; border-radius: 6px; font-size: 9px; font-weight: 800; border: none;")
        badge_row.addWidget(out_badge)
        type_badge = QLabel(call["call_type"])
        type_badge.setStyleSheet(f"background: {rgba_string(COLORS['slate_900'], 12)}; color: {COLORS['slate_700']}; padding: 2px 8px; border-radius: 6px; font-size: 9px; font-weight: 800; border: none;")
        badge_row.addWidget(type_badge)
        badge_row.addStretch(1)
        outer.addLayout(badge_row)
        
        notes_text = (call.get("notes") or "").strip()
        if notes_text:
            notes = QLabel(notes_text[:110] + ("..." if len(notes_text) > 110 else ""))
            notes.setWordWrap(True)
            notes.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 10px; border: none; background: transparent; padding-left: 38px;")
            outer.addWidget(notes)
            
        return card

    def _build_upcoming_item(self, item: Dict[str, Any]) -> QWidget:
        line = QFrame()
        line.setStyleSheet(f"background: {rgba_string(COLORS['accent'], 8)}; border: none; border-radius: 10px;")
        layout = QVBoxLayout(line)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        icon = "📞" if item.get("call_type") == "Telefon" else "🤝"
        title = QLabel(f"{icon}  {item['contact_name']}")
        title.setWordWrap(True)
        title.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 12px; border: none; background: transparent;")
        
        meta = QLabel(format_datetime(item["scheduled_at"]))
        meta.setStyleSheet(f"color: {COLORS['accent']}; font-size: 10px; font-weight: 800; border: none; background: transparent; padding-left: 20px;")
        
        layout.addWidget(title)
        layout.addWidget(meta)
        return line

    def _render_metrics(self, calls: List[Dict[str, Any]]) -> None:
        clear_layout(self.metrics_body)
        now = datetime.now()
        today_calls = [call for call in calls if parse_iso(call["scheduled_at"]) and parse_iso(call["scheduled_at"]).date() == now.date()]
        positive = len([call for call in calls if call["outcome"] == "Olumlu"])
        waiting = len([call for call in calls if call["outcome"] == "Beklemede"])
        negative = len([call for call in calls if call["outcome"] == "Olumsuz"])
        
        self.metrics_body.addWidget(self._build_compact_metric("Bugün", str(len(today_calls)), COLORS["accent"]))
        self.metrics_body.addWidget(self._build_compact_metric("Olumlu", str(positive), COLORS["emerald"]))
        self.metrics_body.addWidget(self._build_compact_metric("Beklemede", str(waiting), COLORS["amber"]))
        self.metrics_body.addWidget(self._build_compact_metric("Olumsuz", str(negative), COLORS["rose"]))
        self.metrics_body.addStretch(1)

    def _start_call(self):
        if not self.window.require_permission("call_create", "Görüşme başlatma"):
            return
        contact_id = self.quick_contact_combo.currentData()
        if contact_id is None:
            QMessageBox.warning(self.window, "Uyarı", "Lütfen bir müşteri seçin.")
            return
        if self._call_timer:
            self._call_timer.stop()
            self._call_timer.deleteLater()
            self._call_timer = None
        self._active_call_contact_id = contact_id
        self._call_start_time = datetime.now()
        self._elapsed_seconds = 0
        contact = self.db.get_contact(contact_id)
        if contact and contact.get("phone") and self._active_call_type == "Telefon":
            phone = "".join(ch for ch in (contact.get("phone") or "") if ch.isdigit())
            if phone:
                QDesktopServices.openUrl(QUrl(f"tel:{phone}"))
        self.start_call_btn.setVisible(False)
        self.end_call_btn.setVisible(True)
        self.timer_label.setVisible(True)
        self.timer_label.setText("00:00")
        self._call_timer = QTimer(self)
        self._call_timer.timeout.connect(self._tick_timer)
        self._call_timer.start(1000)

    def _tick_timer(self):
        self._elapsed_seconds += 1
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        self.timer_label.setText(f"{minutes:02d}:{seconds:02d}")

    def _end_call(self):
        if self._call_timer:
            self._call_timer.stop()
        self.end_call_btn.setVisible(False)
        self.result_widget.setVisible(True)
        self.quick_notes.clear()
        if "Olumlu" in self.outcome_buttons:
            self.outcome_buttons["Olumlu"].setChecked(True)

    def _save_quick_call(self):
        if not self.window.require_permission("call_create", "Görüşme kaydetme"):
            return
        outcome = "Beklemede"
        for text, button in self.outcome_buttons.items():
            if button.isChecked():
                outcome = text
                break
        duration = max(1, self._elapsed_seconds // 60)
        now = datetime.now()
        scheduled_at = self._call_start_time or now
        try:
            self.db.save_call(
                {
                    "contact_id": self._active_call_contact_id,
                    "call_type": self._active_call_type,
                    "scheduled_at": scheduled_at.replace(microsecond=0).isoformat(),
                    "duration_minutes": duration,
                    "outcome": outcome,
                    "notes": self.quick_notes.toPlainText().strip(),
                    "reminder_at": None,
                    "owner_user_id": self.current_user["id"],
                },
                actor_id=self.current_user["id"],
            )
            if self._active_call_contact_id:
                self.db.refresh_contact_scores(self._active_call_contact_id)
                self.db.execute(
                    "UPDATE contacts SET last_contact_at = ? WHERE id = ?",
                    (now.replace(microsecond=0).isoformat(), self._active_call_contact_id),
                )
        except Exception as exc:
            QMessageBox.warning(self.window, "Hata", f"Kayıt hatası: {exc}")
        self._reset_quick_call()
        self.window.refresh_all_views()

    def _cancel_quick_call(self):
        self._reset_quick_call()

    def _reset_quick_call(self):
        if self._call_timer:
            self._call_timer.stop()
            self._call_timer.deleteLater()
            self._call_timer = None
        self.result_widget.setVisible(False)
        self.timer_label.setVisible(False)
        self.timer_label.setText("00:00")
        self.start_call_btn.setVisible(True)
        self.end_call_btn.setVisible(False)
        self.quick_notes.clear()
        self._active_call_contact_id = None
        self._call_start_time = None
        self._elapsed_seconds = 0
        self._update_quick_contact_context()

    def refresh(self):
        self._populate_contacts()
        self._apply_quick_panel_theme()
        calls = self.db.list_calls()
        contacts = self.db.list_contacts(sort_by="AI Skor")
        self._render_metrics(calls)
        self.customer_rail.set_contacts(contacts, self.quick_contact_combo.currentData())

        clear_layout(self.history_list)
        recent_calls = calls[:12]
        self.history_meta.setText(f"{len(recent_calls)} kayıt")
        if not recent_calls:
            empty = QLabel("Henüz görüşme kaydı bulunmuyor.")
            empty.setStyleSheet(f"color: {COLORS['slate_500']}; padding: 16px 6px; font-style: italic;")
            self.history_list.addWidget(empty)
        for call in recent_calls:
            self.history_list.addWidget(self._build_history_card(call))
        self.history_list.addStretch(1)

        clear_layout(self.upcoming_list)
        summary = self.db.get_calls_summary()
        self.upcoming_meta.setText(f"{len(summary['upcoming'])} planlı")
        for item in summary["upcoming"]:
            self.upcoming_list.addWidget(self._build_upcoming_item(item))
        if not summary["upcoming"]:
            empty = QLabel("Planlı görüşme yok.")
            empty.setStyleSheet(f"color: {COLORS['slate_500']}; padding: 8px 4px; font-style: italic;")
            self.upcoming_list.addWidget(empty)
        self.upcoming_list.addStretch(1)


# ─────────────────────────────────────────────────────────
# REMAINING PAGES (Calendar, Mail, Tasks, Files, AI, Reports, Team)
# — Kept same, with minor cleanups
# ─────────────────────────────────────────────────────────

# Takvim grid'i ve haftalık ajanda etkinliklerini yöneten sayfa.
class CalendarPage(BasePage):
    """Sıfırdan tasarlanmış takvim & ajanda sayfası."""

    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        import calendar as _cal
        self._cal_module = _cal
        self._current_year = date.today().year
        self._current_month = date.today().month
        self._selected_date = date.today()
        self._events_cache: List[Dict[str, Any]] = []
        self._day_widgets: Dict[str, QWidget] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(16)

        # ─── Sol: Takvim Grid ───
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        # Başlık satırı
        title_row = QHBoxLayout()
        title = QLabel("Takvim & Ajanda")
        title.setObjectName("SectionTitle")
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(make_button("Bugün", self._go_today, "ghost"))
        if self.window.can("call_create"):
            title_row.addWidget(make_button("+ Etkinlik", lambda: self.window.open_call_dialog(), "primary"))
        left_layout.addLayout(title_row)

        # Ay navigasyonu
        nav_card = CardFrame()
        nav_layout = QHBoxLayout(nav_card)
        nav_layout.setContentsMargins(16, 12, 16, 12)
        _nav_btn_style = f"""
            QPushButton {{ background: {COLORS['slate_100']}; border: none; border-radius: 18px;
            font-size: 14px; color: {COLORS['slate_600']}; font-weight: 700; }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; color: {COLORS['accent']}; }}
        """
        prev_btn = QPushButton("◀")
        prev_btn.setFixedSize(36, 36)
        prev_btn.setStyleSheet(_nav_btn_style)
        prev_btn.clicked.connect(self._prev_month)
        next_btn = QPushButton("▶")
        next_btn.setFixedSize(36, 36)
        next_btn.setStyleSheet(_nav_btn_style)
        next_btn.clicked.connect(self._next_month)
        self._month_label = QLabel("")
        self._month_label.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['slate_900']};")
        self._month_label.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(prev_btn)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self._month_label)
        nav_layout.addStretch(1)
        nav_layout.addWidget(next_btn)
        left_layout.addWidget(nav_card)

        # Takvim grid
        self._grid_card = CardFrame()
        self._grid_outer = QVBoxLayout(self._grid_card)
        self._grid_outer.setContentsMargins(12, 12, 12, 12)
        self._grid_outer.setSpacing(0)

        # Gün başlıkları
        day_header = QHBoxLayout()
        day_header.setSpacing(4)
        for name in ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]:
            lbl = QLabel(name)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedHeight(32)
            lbl.setStyleSheet(f"font-size: 11px; font-weight: 700; color: {COLORS['slate_400']};")
            day_header.addWidget(lbl, 1)
        self._grid_outer.addLayout(day_header)

        # Hafta satırları için container
        self._weeks_container = QWidget()
        self._weeks_layout = QVBoxLayout(self._weeks_container)
        self._weeks_layout.setContentsMargins(0, 0, 0, 0)
        self._weeks_layout.setSpacing(4)
        self._grid_outer.addWidget(self._weeks_container, 1)
        left_layout.addWidget(self._grid_card, 1)
        root.addWidget(left_panel, 3)

        # ─── Sağ: Etkinlik paneli ───
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        self._day_title = QLabel("")
        self._day_title.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {COLORS['slate_900']};")
        right_layout.addWidget(self._day_title)

        # Seçili gün etkinlikleri scroll
        events_scroll = QScrollArea()
        events_scroll.setWidgetResizable(True)
        events_scroll.setFrameShape(QFrame.NoFrame)
        events_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._events_container = QWidget()
        self._events_layout = QVBoxLayout(self._events_container)
        self._events_layout.setContentsMargins(0, 0, 0, 0)
        self._events_layout.setSpacing(8)
        events_scroll.setWidget(self._events_container)
        right_layout.addWidget(events_scroll, 1)

        # Yaklaşan etkinlikler
        upcoming_card, self._upcoming_body, _ = create_card("Bu Haftanın Etkinlikleri")
        right_layout.addWidget(upcoming_card)

        root.addWidget(right_panel, 2)
        self._build_calendar()

    # ── Navigasyon ──
    def _go_today(self):
        today = date.today()
        self._current_year = today.year
        self._current_month = today.month
        self._selected_date = today
        self._build_calendar()

    def _prev_month(self):
        if self._current_month == 1:
            self._current_month = 12
            self._current_year -= 1
        else:
            self._current_month -= 1
        self._build_calendar()

    def _next_month(self):
        if self._current_month == 12:
            self._current_month = 1
            self._current_year += 1
        else:
            self._current_month += 1
        self._build_calendar()

    # ── Takvim oluştur ──
    def _build_calendar(self):
        # Eski hafta satırlarını temizle
        clear_layout(self._weeks_layout)
        self._day_widgets.clear()

        # Ay label güncelle
        self._month_label.setText(f"{MONTH_NAMES[self._current_month - 1]} {self._current_year}")

        # Etkinlikleri al
        self._events_cache = self.db.get_calendar_events(self._current_month, self._current_year)
        event_days: set = set()
        for ev in self._events_cache:
            dt = parse_iso(ev.get("event_at"))
            if dt and dt.month == self._current_month and dt.year == self._current_year:
                event_days.add(dt.day)

        # Grid oluştur
        self._cal_module.setfirstweekday(self._cal_module.MONDAY)
        weeks = self._cal_module.monthcalendar(self._current_year, self._current_month)
        today = date.today()

        for week in weeks:
            week_row = QHBoxLayout()
            week_row.setSpacing(4)
            for day in week:
                if day == 0:
                    spacer = QLabel("")
                    spacer.setFixedHeight(52)
                    week_row.addWidget(spacer, 1)
                    continue

                is_today = (day == today.day and self._current_month == today.month and self._current_year == today.year)
                is_selected = (day == self._selected_date.day and self._current_month == self._selected_date.month and self._current_year == self._selected_date.year)
                has_event = day in event_days

                cell = QPushButton()
                cell.setFixedHeight(52)
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                if is_selected:
                    bg, fg, border_css = COLORS['accent'], "white", "none"
                elif is_today:
                    bg, fg, border_css = COLORS['accent_light'], COLORS['accent'], f"2px solid {COLORS['accent']}"
                else:
                    bg, fg, border_css = "transparent", COLORS['slate_700'], "none"

                fw = "800" if is_today or is_selected else "600"
                hover_bg = COLORS['accent_dark'] if is_selected else COLORS['accent_light']
                hover_fg = "white" if is_selected else COLORS['accent']

                cell.setStyleSheet(f"""
                    QPushButton {{ background: {bg}; color: {fg}; border: {border_css};
                    border-radius: 14px; font-size: 13px; font-weight: {fw}; }}
                    QPushButton:hover {{ background: {hover_bg}; color: {hover_fg}; }}
                """)

                # Dot altında gün numarası
                if has_event:
                    cell.setText(f"{day}\n●")
                else:
                    cell.setText(str(day))

                cell.clicked.connect(lambda _=False, d=day: self._select_day(d))
                week_row.addWidget(cell, 1)
                self._day_widgets[f"{day}"] = cell

            self._weeks_layout.addLayout(week_row)

        self._weeks_layout.addStretch(1)
        self._refresh_day_events()
        self._refresh_upcoming()

    def _select_day(self, day: int):
        try:
            self._selected_date = date(self._current_year, self._current_month, day)
        except ValueError:
            return
        self._build_calendar()

    # ── Seçili gün etkinlikleri ──
    def _refresh_day_events(self):
        clear_layout(self._events_layout)
        self._day_title.setText(format_full_date(self._selected_date))

        filtered = []
        for ev in self._events_cache:
            dt = parse_iso(ev.get("event_at"))
            if dt and dt.date() == self._selected_date:
                filtered.append(ev)

        if not filtered:
            empty = QLabel("Bu gün için etkinlik bulunmuyor.")
            empty.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 20px; font-size: 13px;")
            empty.setAlignment(Qt.AlignCenter)
            self._events_layout.addWidget(empty)
            self._events_layout.addStretch(1)
            return

        for ev in filtered:
            card = CardFrame()
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(12)

            kind = ev.get("kind", "Diğer")
            color_map = {"Görüşme": COLORS["accent"], "Görev": COLORS["amber"], "Fırsat": COLORS["emerald"]}
            indicator_color = color_map.get(kind, COLORS["violet"])
            indicator = QLabel()
            indicator.setFixedSize(4, 40)
            indicator.setStyleSheet(f"background: {indicator_color}; border-radius: 2px;")
            card_layout.addWidget(indicator)

            info = QVBoxLayout()
            info.setSpacing(4)
            title = QLabel(ev["title"])
            title.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']}; font-size: 13px;")
            time_lbl = QLabel(format_datetime(ev["event_at"]))
            time_lbl.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            info.addWidget(title)
            info.addWidget(time_lbl)
            card_layout.addLayout(info, 1)
            card_layout.addWidget(BadgeLabel(kind))
            self._events_layout.addWidget(card)

        self._events_layout.addStretch(1)

    # ── Bu haftanın etkinlikleri ──
    def _refresh_upcoming(self):
        clear_layout(self._upcoming_body)
        today = date.today()
        week_end = today + timedelta(days=7)
        upcoming: List[Dict[str, Any]] = []
        all_events = list(self._events_cache)

        if today.day > 24:
            next_m = today.month + 1 if today.month < 12 else 1
            next_y = today.year if today.month < 12 else today.year + 1
            all_events += self.db.get_calendar_events(next_m, next_y)

        for ev in all_events:
            dt = parse_iso(ev.get("event_at"))
            if dt and today <= dt.date() <= week_end:
                upcoming.append(ev)

        upcoming.sort(key=lambda x: x.get("event_at", ""))

        if not upcoming:
            lbl = QLabel("Bu hafta etkinlik bulunmuyor.")
            lbl.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 12px;")
            self._upcoming_body.addWidget(lbl)
            return

        for ev in upcoming[:6]:
            row = QFrame()
            row.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 12px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(12, 8, 12, 8)
            rl.setSpacing(10)
            text = QLabel(f"{ev['title']}  •  {format_datetime(ev['event_at'])}")
            text.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px;")
            text.setWordWrap(True)
            rl.addWidget(text, 1)
            rl.addWidget(BadgeLabel(ev.get("kind", "Diğer")))
            self._upcoming_body.addWidget(row)

    def refresh(self):
        self._build_calendar()


# Mail kayıtları, şablonlar ve otomasyon ayarlarını yöneten sayfa.
class MailPage(BasePage):
    """Sıfırdan tasarlanmış modern mail merkezi."""

    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        self._current_folder = "inbox"
        self._selected_email_id: Optional[int] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(SECTION_SPACING)

        # ─── Header ───
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Mail Merkezi")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("E-posta yönetimi, şablonlar ve otomasyon.")
        subtitle.setObjectName("SectionSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch(1)
        if self.window.can("mail_compose"):
            top.addWidget(make_button("✉ Yeni Mail", lambda: self.window.compose_mail_for_contact(None), "primary"))
        root.addLayout(top)

        # ─── 3 Panel Layout ───
        content = QSplitter(Qt.Horizontal)
        content.setChildrenCollapsible(False)
        content.setHandleWidth(8)

        # Sol: Klasörler + İstatistikler
        sidebar = QWidget()
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(0, 0, 0, 0)
        sb_layout.setSpacing(8)

        folders_card = CardFrame()
        fc_layout = QVBoxLayout(folders_card)
        fc_layout.setContentsMargins(12, 14, 12, 14)
        fc_layout.setSpacing(4)
        fc_title = QLabel("Klasörler")
        fc_title.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 13px; padding-bottom: 6px;")
        fc_layout.addWidget(fc_title)

        self._folder_buttons: Dict[str, QPushButton] = {}
        folder_items = [
            ("inbox", "Gelen Kutusu"),
            ("sent", "Gönderilen"),
            ("templates", "Şablonlar"),
            ("automation", "⚡  Otomasyon"),
        ]
        for key, label in folder_items:
            btn = QPushButton(label)
            btn.setStyleSheet(self._folder_btn_style(key == self._current_folder))
            btn.clicked.connect(lambda _=False, k=key: self._switch_folder(k))
            fc_layout.addWidget(btn)
            self._folder_buttons[key] = btn
        sb_layout.addWidget(folders_card)

        # İstatistik kartı
        stats_card = CardFrame()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(14, 14, 14, 14)
        stats_layout.setSpacing(8)
        stats_title = QLabel("İstatistikler")
        stats_title.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 13px;")
        stats_layout.addWidget(stats_title)
        self._stats_labels: Dict[str, QLabel] = {}
        for key, label_text in [("total", "Toplam"), ("unread", "Okunmamış"), ("sent", "Gönderilen")]:
            row = QHBoxLayout()
            l = QLabel(label_text)
            l.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
            v = QLabel("0")
            v.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 14px;")
            row.addWidget(l)
            row.addStretch(1)
            row.addWidget(v)
            stats_layout.addLayout(row)
            self._stats_labels[key] = v
        sb_layout.addWidget(stats_card)
        sb_layout.addStretch(1)

        # Orta: Mail listesi
        list_card = CardFrame()
        list_main = QVBoxLayout(list_card)
        list_main.setContentsMargins(0, 0, 0, 0)
        list_main.setSpacing(0)
        list_header = QFrame()
        lh_layout = QHBoxLayout(list_header)
        lh_layout.setContentsMargins(16, 12, 16, 12)
        self._list_title = QLabel("Gelen Kutusu")
        self._list_title.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']}; font-size: 14px;")
        lh_layout.addWidget(self._list_title)
        lh_layout.addStretch(1)
        list_main.addWidget(list_header)

        list_scroll = QScrollArea()
        list_scroll.setWidgetResizable(True)
        list_scroll.setFrameShape(QFrame.NoFrame)
        list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_container = QWidget()
        self._list_body = QVBoxLayout(self._list_container)
        self._list_body.setContentsMargins(8, 0, 8, 8)
        self._list_body.setSpacing(2)
        list_scroll.setWidget(self._list_container)
        list_main.addWidget(list_scroll, 1)

        # Sağ: Önizleme
        preview_card = CardFrame()
        preview_main = QVBoxLayout(preview_card)
        preview_main.setContentsMargins(0, 0, 0, 0)
        preview_main.setSpacing(0)
        preview_header = QFrame()
        ph_layout = QHBoxLayout(preview_header)
        ph_layout.setContentsMargins(16, 12, 16, 12)
        self._preview_title_label = QLabel("Önizleme")
        self._preview_title_label.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']}; font-size: 14px;")
        ph_layout.addWidget(self._preview_title_label)
        ph_layout.addStretch(1)
        preview_main.addWidget(preview_header)

        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setFrameShape(QFrame.NoFrame)
        self._preview_container = QWidget()
        self._preview_body = QVBoxLayout(self._preview_container)
        self._preview_body.setContentsMargins(16, 8, 16, 16)
        self._preview_body.setSpacing(12)
        preview_scroll.setWidget(self._preview_container)
        preview_main.addWidget(preview_scroll, 1)

        content.addWidget(sidebar)
        content.addWidget(list_card)
        content.addWidget(preview_card)
        content.setStretchFactor(0, 1)
        content.setStretchFactor(1, 2)
        content.setStretchFactor(2, 3)
        root.addWidget(content, 1)
        self.refresh()

    # ── Yardımcılar ──
    @staticmethod
    def _folder_btn_style(active: bool) -> str:
        return f"""
            QPushButton {{ background: {COLORS['accent_light'] if active else 'transparent'};
            border: none; border-radius: 10px; padding: 10px 14px;
            text-align: left; font-weight: {'700' if active else '500'};
            color: {COLORS['accent'] if active else COLORS['slate_600']}; }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; color: {COLORS['accent']}; }}
        """

    def _switch_folder(self, folder: str):
        self._current_folder = folder
        self._selected_email_id = None
        for key, btn in self._folder_buttons.items():
            btn.setStyleSheet(self._folder_btn_style(key == folder))
        titles = {"inbox": "Gelen Kutusu", "sent": "Gönderilen", "templates": "Şablonlar", "automation": "Otomasyon"}
        self._list_title.setText(titles.get(folder, ""))
        self.refresh()

    # ── Refresh ──
    def refresh(self):
        clear_layout(self._list_body)
        clear_layout(self._preview_body)
        emails = self.db.list_emails()
        unread_count = len([e for e in emails if e.get("is_unread")])
        self._stats_labels["total"].setText(str(len(emails)))
        self._stats_labels["unread"].setText(str(unread_count))
        self._stats_labels["sent"].setText(str(len(emails) - unread_count))

        if self._current_folder == "templates":
            self._show_templates()
            return
        if self._current_folder == "automation":
            self._show_automation()
            return

        # Mail listesini göster
        if not emails:
            empty = QLabel("Henüz mail kaydı bulunmuyor.")
            empty.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_body.addWidget(empty)
        else:
            for email in emails:
                self._list_body.addWidget(self._make_email_row(email))
        self._list_body.addStretch(1)

        if self._selected_email_id:
            self._show_email_preview(self._selected_email_id)
        else:
            placeholder = QLabel("Önizleme görmek için\nbir mail seçin.")
            placeholder.setAlignment(Qt.AlignCenter)
            placeholder.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 40px; font-size: 14px;")
            self._preview_body.addWidget(placeholder)
            self._preview_body.addStretch(1)

    def _make_email_row(self, email):
        btn = QPushButton()
        is_unread = email.get("is_unread", False)
        is_selected = email["id"] == self._selected_email_id

        subject = email.get("subject", "Konu yok")
        recipient = email.get("recipient", "")
        dt = format_datetime(email.get("sent_at") or email.get("created_at"))
        if is_selected:
            row_bg = COLORS["accent_light"]
            border = f"2px solid {COLORS['accent']}"
        elif is_unread:
            row_bg = rgba_string(COLORS["accent"], 16) if self.window.is_dark_mode else "rgba(255,255,255,0.92)"
            border = "none"
        else:
            row_bg = rgba_string(COLORS["slate_500"], 8) if self.window.is_dark_mode else "transparent"
            border = "none"
        btn.setText(f"{subject}\n{recipient}  •  {dt}")
        btn.setStyleSheet(f"""
            QPushButton {{
                text-align: left; padding: 12px 14px; border-radius: 10px;
                background: {row_bg};
                border: {border};
                font-weight: {'700' if is_unread else '500'};
                color: {COLORS['slate_900']};
            }}
            QPushButton:hover {{ background: {COLORS['accent_light']}; }}
        """)
        btn.clicked.connect(lambda _=False, eid=email["id"]: self._select_email(eid))
        return btn

    def _select_email(self, email_id: int):
        self._selected_email_id = email_id
        self.db.mark_email_read(email_id)
        self.refresh()

    def _show_email_preview(self, email_id: int):
        email = self.db.get_email(email_id)
        if not email:
            return
        self._preview_title_label.setText(email["subject"])

        # Konu
        subject = QLabel(email["subject"])
        subject.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {COLORS['slate_900']};")
        subject.setWordWrap(True)
        self._preview_body.addWidget(subject)

        # Meta bilgi kartı
        meta_card = QFrame()
        meta_card.setStyleSheet(f"background: {COLORS['slate_50']}; border-radius: 12px;")
        meta_layout = QVBoxLayout(meta_card)
        meta_layout.setContentsMargins(14, 10, 14, 10)
        meta_layout.setSpacing(4)
        to_label = QLabel(f"Alıcı: {email['recipient']}")
        to_label.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 12px;")
        date_label = QLabel(f"Tarih: {format_datetime(email.get('sent_at') or email['created_at'])}")
        date_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
        meta_layout.addWidget(to_label)
        meta_layout.addWidget(date_label)
        self._preview_body.addWidget(meta_card)

        # İçerik
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(email["body"])
        body.setStyleSheet(f"background: transparent; border: none; color: {COLORS['slate_700']}; font-size: 13px;")
        body.setMinimumHeight(200)
        self._preview_body.addWidget(body, 1)

        # Aksiyonlar
        actions = QHBoxLayout()
        actions.setSpacing(8)
        if self.window.can("mail_compose"):
            actions.addWidget(make_button("↩ Yanıtla", lambda: self.window.compose_mail_for_contact(None), "primary"))
            actions.addWidget(make_button("↪ İlet", lambda: self.window.compose_mail_for_contact(None), "ghost"))
        actions.addStretch(1)
        self._preview_body.addLayout(actions)

    # ── Şablonlar ──
    def _show_templates(self):
        templates = self.db.list_mail_templates()
        if not templates:
            empty = QLabel("Şablon bulunmuyor.")
            empty.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_body.addWidget(empty)
            self._list_body.addStretch(1)
            return
        for tpl in templates:
            card = CardFrame()
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            cl.setSpacing(6)
            name = QLabel(tpl["name"])
            name.setStyleSheet(f"font-weight: 800; color: {COLORS['slate_900']};")
            subject = QLabel(tpl["subject"])
            subject.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
            cl.addWidget(name)
            cl.addWidget(subject)
            btn_row = QHBoxLayout()
            btn_row.addStretch(1)
            if self.window.can("mail_template_use"):
                btn_row.addWidget(make_button("Kullan", lambda _=False, t=tpl["name"]: self.window.compose_mail_with_template(t), "primary"))
            cl.addLayout(btn_row)
            self._list_body.addWidget(card)
        self._list_body.addStretch(1)
        info = QLabel("Bir şablon seçerek mail oluşturabilirsiniz.")
        info.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 24px;")
        info.setAlignment(Qt.AlignCenter)
        self._preview_body.addWidget(info)
        self._preview_body.addStretch(1)

    # ── Otomasyon ──
    def _show_automation(self):
        automations = self.db.list_automations()
        if not automations:
            empty = QLabel("Otomasyon kuralı bulunamadı.")
            empty.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 24px;")
            empty.setAlignment(Qt.AlignCenter)
            self._list_body.addWidget(empty)
            self._list_body.addStretch(1)
            return
        for auto in automations:
            card = CardFrame()
            cl = QHBoxLayout(card)
            cl.setContentsMargins(14, 12, 14, 12)
            label = QLabel(auto["label"])
            label.setStyleSheet(f"font-weight: 700; color: {COLORS['slate_900']};")
            toggle = QPushButton("Açık" if auto["enabled"] else "Kapalı")
            style_button(toggle, "success" if auto["enabled"] else "ghost")
            toggle.clicked.connect(lambda _=False, k=auto["key"], v=bool(auto["enabled"]): self.window.toggle_automation(k, not v))
            toggle.setEnabled(self.window.can("mail_automation_manage"))
            cl.addWidget(label, 1)
            cl.addWidget(toggle)
            self._list_body.addWidget(card)
        self._list_body.addStretch(1)
        info = QLabel("Otomatik mail kurallarını buradan yönetebilirsiniz.")
        info.setStyleSheet(f"color: {COLORS['slate_400']}; padding: 24px;")
        info.setAlignment(Qt.AlignCenter)
        self._preview_body.addWidget(info)
        self._preview_body.addStretch(1)

# Görevleri arama, filtreleme, tamamlama ve önceliklere göre gösteren sayfa.
class TasksPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(20)

        # ── Header ──
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(16)

        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        title = QLabel("Görev Listesi")
        title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 26px; font-weight: 900;")
        self.subtitle = QLabel("Tüm işlerini modern bir listede kolayca takip et.")
        self.subtitle.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 14px;")
        title_box.addWidget(title)
        title_box.addWidget(self.subtitle)
        top.addLayout(title_box)

        top.addStretch(1)

        self.metrics_layout = QHBoxLayout()
        self.metrics_layout.setSpacing(12)
        top.addLayout(self.metrics_layout)

        if self.window.can("task_create"):
            add_btn = make_button("Yeni Görev", lambda: self.window.open_task_dialog(), "primary")
            add_btn.setMinimumHeight(44)
            add_btn.setMinimumWidth(140)
            top.addWidget(add_btn)
        root.addLayout(top)

        # ── Filtre Çubuğu ──
        controls = QFrame()
        controls.setStyleSheet(f"background: {COLORS['surface']}; border-radius: 12px; border: none;")
        c_layout = QHBoxLayout(controls)
        c_layout.setContentsMargins(16, 12, 16, 12)
        c_layout.setSpacing(16)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 16px;")
        c_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Görevlerde ara...")
        self.search_input.setStyleSheet(f"background: transparent; border: none; font-size: 14px; color: {COLORS['slate_900']};")
        c_layout.addWidget(self.search_input, 1)

        sep = QFrame()
        sep.setFixedWidth(0)
        sep.setStyleSheet("background: transparent;")
        c_layout.addWidget(sep)

        self.status_filter = self.window.create_combo(["Tüm Durumlar", "Açık Görevler", "Gecikenler", "Tamamlananlar"])
        self.status_filter.setFixedWidth(160)
        self.status_filter.setStyleSheet(self.status_filter.styleSheet() + f" background: transparent; border: none; color: {COLORS['slate_700']}; font-weight: 600;")
        
        self.priority_filter = self.window.create_combo(["Tüm Öncelikler", "Yüksek", "Orta", "Düşük"])
        self.priority_filter.setFixedWidth(160)
        self.priority_filter.setStyleSheet(self.priority_filter.styleSheet() + f" background: transparent; border: none; color: {COLORS['slate_700']}; font-weight: 600;")

        c_layout.addWidget(self.status_filter)
        c_layout.addWidget(self.priority_filter)
        root.addWidget(controls)

        # ── Görev Listesi Alanı ──
        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setStyleSheet("background: transparent;")
        
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(0, 0, 0, 40)
        self.list_layout.setSpacing(24)
        self.list_scroll.setWidget(self.list_container)
        
        root.addWidget(self.list_scroll, 1)

        self.search_input.textChanged.connect(self.refresh)
        self.status_filter.currentTextChanged.connect(self.refresh)
        self.priority_filter.currentTextChanged.connect(self.refresh)
        self.refresh()

    def _task_matches_filters(self, task: Dict[str, Any]) -> bool:
        query = self.search_input.text().strip().lower()
        status_filter = self.status_filter.currentText()
        priority_filter = self.priority_filter.currentText()
        resolved_status = resolve_task_status(task)
        haystack = " ".join([
            task.get("title", ""), task.get("contact_name") or "",
            task.get("assigned_name") or "", task.get("description") or "",
        ]).lower()
        
        if query and query not in haystack: return False
        if status_filter == "Açık Görevler" and task["is_done"]: return False
        if status_filter == "Gecikenler" and resolved_status != "Gecikti": return False
        if status_filter == "Tamamlananlar" and not task["is_done"]: return False
        if priority_filter != "Tüm Öncelikler" and task["priority"] != priority_filter: return False
        return True

    def _build_metric_pill(self, label: str, value: str, tone: str) -> QWidget:
        pill = QFrame()
        pill.setStyleSheet(f"background: {rgba_string(tone, 12)}; border-radius: 10px;")
        l = QHBoxLayout(pill)
        l.setContentsMargins(14, 6, 14, 6)
        l.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px; font-weight: 700; background: transparent;")
        val = QLabel(value)
        val.setStyleSheet(f"color: {tone}; font-size: 15px; font-weight: 900; background: transparent;")
        l.addWidget(lbl)
        l.addWidget(val)
        return pill

    def _build_task_row(self, task: Dict[str, Any]) -> QWidget:
        row = QFrame()
        is_done = task["is_done"]
        
        if is_done:
            bg_color = rgba_string(COLORS['emerald'], 5)
        else:
            bg_color = rgba_string(COLORS['slate_500'], 8)

        row.setStyleSheet(f"background: {bg_color}; border: none; border-radius: 10px;")
        
        layout = QHBoxLayout(row)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)

        # 1. Tamamlama Butonu (Daha Kibar)
        chk = QPushButton("✓" if is_done else "")
        chk.setFixedSize(24, 24)
        chk.setCursor(Qt.PointingHandCursor)
        if is_done:
            chk.setStyleSheet(f"background: {COLORS['emerald']}; color: white; border: none; border-radius: 12px; font-weight: 900; font-size: 12px;")
        else:
            chk.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 12)}; border: none; border-radius: 12px;")
        chk.clicked.connect(lambda _=False, tid=task["id"]: self.window.toggle_task(tid))
        chk.setEnabled(self.window.can("task_toggle"))
        layout.addWidget(chk)

        # 2. Görev Başlığı ve Detayı (Küçültüldü)
        info_lay = QVBoxLayout()
        info_lay.setSpacing(4)
        
        title_lay = QHBoxLayout()
        title_lay.setSpacing(10)
        title = QLabel(task["title"])
        if is_done:
            title.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {COLORS['slate_500']}; text-decoration: line-through; border: none; background: transparent;")
        else:
            title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {COLORS['slate_900']}; border: none; background: transparent;")
        title_lay.addWidget(title)
        
        if task["priority"] == "Yüksek" and not is_done:
            p_badge = QLabel("🔥 Yüksek")
            p_badge.setStyleSheet(f"color: {COLORS['rose']}; background: {rgba_string(COLORS['rose'], 15)}; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: 800; border: none;")
            title_lay.addWidget(p_badge)
            
        status = resolve_task_status(task)
        if status == "Gecikti" and not is_done:
            d_badge = QLabel("⚠️ Gecikti")
            d_badge.setStyleSheet(f"color: {COLORS['amber']}; background: {rgba_string(COLORS['amber'], 15)}; border-radius: 6px; padding: 2px 6px; font-size: 10px; font-weight: 800; border: none;")
            title_lay.addWidget(d_badge)

        title_lay.addStretch(1)
        info_lay.addLayout(title_lay)

        desc = task.get("description", "").strip()
        if desc:
            desc_lbl = QLabel(desc[:120] + ("..." if len(desc) > 120 else ""))
            desc_lbl.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; border: none; background: transparent;")
            info_lay.addWidget(desc_lbl)
            
        layout.addLayout(info_lay, 1)

        # 3. Meta Veriler (Daha Kompakt)
        meta_lay = QVBoxLayout()
        meta_lay.setSpacing(4)
        
        date_lbl = QLabel(format_datetime(task.get('due_at')))
        date_lbl.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 11px; font-weight: 700; border: none; background: transparent;")
        date_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta_lay.addWidget(date_lbl)
        
        contact = task.get("contact_name")
        if contact:
            c_lbl = QLabel(f"👤 {contact}")
            c_lbl.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; border: none; background: transparent;")
            c_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            meta_lay.addWidget(c_lbl)
            
        layout.addLayout(meta_lay)

        # 4. Aksiyonlar (Daha Küçük İkonlar)
        act_lay = QHBoxLayout()
        act_lay.setSpacing(6)
        act_lay.setContentsMargins(12, 0, 0, 0)
        
        if self.window.can("task_edit"):
            edit_btn = QPushButton("✏️")
            edit_btn.setFixedSize(32, 32)
            edit_btn.setCursor(Qt.PointingHandCursor)
            edit_btn.setStyleSheet(f"QPushButton {{ background: {rgba_string(COLORS['slate_500'], 10)}; border: none; font-size: 13px; border-radius: 16px; }} QPushButton:hover {{ background: {rgba_string(COLORS['slate_500'], 20)}; }}")
            edit_btn.clicked.connect(lambda _=False, row_data=task: self.window.open_task_dialog(row_data))
            act_lay.addWidget(edit_btn)
        if self.window.can("task_delete"):
            del_btn = QPushButton("🗑️")
            del_btn.setFixedSize(32, 32)
            del_btn.setCursor(Qt.PointingHandCursor)
            del_btn.setStyleSheet(f"QPushButton {{ background: {rgba_string(COLORS['rose'], 10)}; border: none; font-size: 13px; border-radius: 16px; }} QPushButton:hover {{ background: {rgba_string(COLORS['rose'], 20)}; }}")
            del_btn.clicked.connect(lambda _=False, tid=task["id"]: self.window.delete_task(tid))
            act_lay.addWidget(del_btn)
        layout.addLayout(act_lay)

        return row

    def _build_list_section(self, title: str, tasks: List[Dict[str, Any]], title_color: str) -> QWidget:
        sec = QWidget()
        sec.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(sec)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        header = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {title_color}; font-size: 14px; font-weight: 800; background: transparent;")
        count = QLabel(str(len(tasks)))
        count.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 20)}; color: {COLORS['slate_700']}; padding: 2px 8px; border-radius: 8px; font-size: 11px; font-weight: 800;")
        header.addWidget(lbl)
        header.addWidget(count)
        header.addStretch(1)
        lay.addLayout(header)

        if not tasks:
            empty = QLabel("Bu kategoride görev bulunmuyor.")
            empty.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 12px; font-style: italic; padding: 6px 0;")
            lay.addWidget(empty)
        else:
            for task in tasks:
                lay.addWidget(self._build_task_row(task))

        return sec

    def refresh(self):
        tasks = self.db.list_tasks(include_done=True)
        filtered_tasks = [task for task in tasks if self._task_matches_filters(task)]
        
        clear_layout(self.metrics_layout)
        completed = len([item for item in tasks if item["is_done"]])
        pending = len([item for item in tasks if not item["is_done"]])
        
        self.metrics_layout.addWidget(self._build_metric_pill("Tamamlanan", str(completed), COLORS["emerald"]))
        self.metrics_layout.addWidget(self._build_metric_pill("Açık Görev", str(pending), COLORS["amber"]))

        clear_layout(self.list_layout)
        
        focus_ids = []
        for task in filtered_tasks:
            if not task["is_done"] and (resolve_task_status(task) in ("Gecikti", "Bugün") or task["priority"] == "Yüksek"):
                focus_ids.append(task["id"])
                
        focus_tasks = [t for t in filtered_tasks if t["id"] in focus_ids]
        planned_tasks = [t for t in filtered_tasks if not t["is_done"] and t["id"] not in focus_ids]
        completed_tasks = [t for t in filtered_tasks if t["is_done"]]

        # Seksiyonları alt alta ekliyoruz
        if focus_tasks:
            self.list_layout.addWidget(self._build_list_section("🔴 Hemen İlgilen (Öncelikli & Geciken)", focus_tasks, COLORS["rose"]))
            
        if planned_tasks or (not focus_tasks and not completed_tasks):
            self.list_layout.addWidget(self._build_list_section("📅 Yaklaşan Görevler", planned_tasks, COLORS["slate_900"]))
            
        if completed_tasks:
            self.list_layout.addWidget(self._build_list_section("✅ Bitenler", completed_tasks, COLORS["emerald"]))
            
        self.list_layout.addStretch(1)



# Yüklenen dosyaları listeleyen, açan, dışa aktaran ve silen sayfa.
class FilesPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(SECTION_SPACING)
        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Dosya Yönetimi")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Yüklenen dosyalar uygulama klasöründe saklanır.")
        subtitle.setObjectName("SectionSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch(1)
        if self.window.can("file_upload"):
            top.addWidget(make_button("Dosya Yükle", self.window.upload_file, "primary"))
        root.addLayout(top)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("SearchInput")
        self.search.setPlaceholderText("Dosya ara...")
        self.category_combo = self.window.create_combo(["Tüm Türler", "Teklif", "Belge", "Rapor"])
        filters.addWidget(self.search, 1)
        filters.addWidget(self.category_combo)
        root.addLayout(filters)

        self.files_area = QScrollArea()
        self.files_area.setFrameShape(QFrame.NoFrame)
        self.files_area.setWidgetResizable(True)
        self.files_widget = QWidget()
        self.files_layout = QVBoxLayout(self.files_widget)
        self.files_layout.setContentsMargins(0, 0, 0, 0)
        self.files_layout.setSpacing(14)
        self.files_area.setWidget(self.files_widget)
        root.addWidget(self.files_area, 1)

        self.search.textChanged.connect(self.refresh)
        self.category_combo.currentTextChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        category = "" if self.category_combo.currentText() == "Tüm Türler" else self.category_combo.currentText()
        files = self.db.list_files(search=self.search.text(), category=category)
        while self.files_layout.count():
            item = self.files_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for item in files:
            card = CardFrame()
            card.setMinimumHeight(94)
            card.setMaximumHeight(94)
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(18, 12, 18, 12)
            card_layout.setSpacing(16)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)
            name = QLabel(item["original_name"])
            name.setObjectName("CardTitle")
            name.setWordWrap(False)
            customer = QLabel(item.get("contact_name") or "Genel")
            customer.setObjectName("CardSubtitle")
            info_layout.addWidget(name)
            info_layout.addWidget(customer)

            meta_layout = QHBoxLayout()
            meta_layout.setSpacing(10)
            meta_layout.setContentsMargins(0, 0, 0, 0)
            meta_layout.addWidget(BadgeLabel(item["category"]))
            size_label = QLabel(format_file_size(int(item["size_bytes"])))
            size_label.setObjectName("CardSubtitle")
            date_label = QLabel(format_datetime(item["uploaded_at"]))
            date_label.setObjectName("CardSubtitle")
            meta_layout.addWidget(size_label)
            meta_layout.addWidget(date_label)
            meta_layout.addStretch(1)

            action_layout = QHBoxLayout()
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setSpacing(8)
            if self.window.can("file_open"):
                open_btn = make_button("Aç", lambda _=False, fid=item["id"]: self.window.open_file(fid), "ghost")
                open_btn.setFixedWidth(72)
                action_layout.addWidget(open_btn)
            if self.window.can("file_export"):
                export_btn = make_button("Dışa Aktar", lambda _=False, fid=item["id"]: self.window.export_file(fid), "ghost")
                export_btn.setFixedWidth(100)
                action_layout.addWidget(export_btn)
            if self.window.can("file_delete"):
                delete_btn = make_button("Sil", lambda _=False, fid=item["id"]: self.window.delete_file(fid), "danger")
                delete_btn.setFixedWidth(72)
                action_layout.addWidget(delete_btn)

            card_layout.addLayout(info_layout, 2)
            card_layout.addLayout(meta_layout, 2)
            card_layout.addStretch(1)
            card_layout.addLayout(action_layout)
            self.files_layout.addWidget(card)

        self.files_layout.addStretch(1)


# AI sohbet arayüzü ve canlı CRM içgörü kartlarını gösteren sayfa.
class AIPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        self.chat_messages: List[Dict[str, str]] = []
        self._ai_busy = False
        self._ai_thread: Optional[QThread] = None
        self._ai_worker: Optional[AIReplyWorker] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        root.setSpacing(SECTION_SPACING)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 6)
        top.setSpacing(12)
        title_box = QVBoxLayout()
        title_box.setSpacing(4)
        self.title_label = QLabel("AI Satış Koçu")
        self.title_label.setObjectName("SectionTitle")
        title_box.addWidget(self.title_label)
        top.addLayout(title_box, 1)

        self.refresh_chat_btn = make_button("Sohbeti Yenile", self.refresh_chat, "ghost")
        self.new_chat_btn = make_button("Yeni Sohbet", self.start_new_chat, "primary")
        top.addWidget(self.refresh_chat_btn)
        top.addWidget(self.new_chat_btn)
        root.addLayout(top)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

        self.chat_container = CardFrame()
        chat_layout = QVBoxLayout(self.chat_container)
        chat_layout.setContentsMargins(18, 18, 18, 18)
        chat_layout.setSpacing(16)

        self.chat_header = QFrame()
        ch_layout = QHBoxLayout(self.chat_header)
        ch_layout.setContentsMargins(0, 0, 0, 0)
        ch_layout.setSpacing(12)
        ch_layout.addWidget(AvatarLabel("AI", COLORS["violet"], 42))

        ai_info = QVBoxLayout()
        ai_info.setContentsMargins(0, 0, 0, 0)
        ai_info.setSpacing(2)
        self.ai_name = QLabel("NexusAI Koç")
        self.ai_status = QLabel("Çevrimiçi · canlı analiz modu")
        ai_info.addWidget(self.ai_name)
        ai_info.addWidget(self.ai_status)
        ch_layout.addLayout(ai_info, 1)

        self.active_badge = QLabel("AI Aktif")
        self.active_badge.setAlignment(Qt.AlignCenter)
        ch_layout.addWidget(self.active_badge)

        self.gear_btn = QToolButton()
        self.gear_btn.setText("Aksiyonlar")
        style_button(self.gear_btn, "ghost")
        self.gear_btn.setPopupMode(QToolButton.InstantPopup)
        self.action_menu = QMenu(self.gear_btn)
        self.action_menu.addAction("Yeni sohbet", self.start_new_chat)
        self.action_menu.addAction("Sohbeti yenile", self.refresh_chat)
        self.action_menu.addAction("İçgörüleri güncelle", self.refresh)
        if self.window.can("ai_settings_manage"):
            self.action_menu.addAction("Ayarları aç", self.window.open_ai_settings_dialog)
        self.gear_btn.setMenu(self.action_menu)
        ch_layout.addWidget(self.gear_btn)

        chat_layout.addWidget(self.chat_header)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.NoFrame)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.chat_stream = QWidget()
        self.chat_stream_layout = QVBoxLayout(self.chat_stream)
        self.chat_stream_layout.setContentsMargins(6, 4, 6, 4)
        self.chat_stream_layout.setSpacing(14)
        self.chat_stream_layout.setAlignment(Qt.AlignTop)
        self.chat_scroll.setWidget(self.chat_stream)
        chat_layout.addWidget(self.chat_scroll, 1)

        self.input_area = QFrame()
        in_layout = QHBoxLayout(self.input_area)
        in_layout.setContentsMargins(16, 16, 16, 16)
        in_layout.setSpacing(12)

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Soru sorun veya analiz isteyin... (ör: Bu ay hedefime ulaşır mıyım?)")
        self.chat_input.returnPressed.connect(self.send_message)
        in_layout.addWidget(self.chat_input, 1)

        self.send_btn = make_button("Gönder", self.send_message, "primary")
        self.send_btn.setMinimumWidth(126)
        in_layout.addWidget(self.send_btn)

        chat_layout.addWidget(self.input_area)

        self.insights_container = CardFrame()
        self.insights_container.setMinimumWidth(340)
        self.insights_container.setMaximumWidth(390)
        insights_layout = QVBoxLayout(self.insights_container)
        insights_layout.setContentsMargins(18, 18, 18, 18)
        insights_layout.setSpacing(14)

        insights_title_box = QVBoxLayout()
        insights_title_box.setSpacing(4)
        self.insights_title = QLabel("AI İçgörüleri")
        self.insights_title.setObjectName("CardTitle")
        self.insights_subtitle = QLabel("Sistemdeki son durumdan üretilen aksiyon önerileri")
        self.insights_subtitle.setObjectName("CardSubtitle")
        insights_title_box.addWidget(self.insights_title)
        insights_title_box.addWidget(self.insights_subtitle)
        insights_layout.addLayout(insights_title_box)

        self.insights_scroll = QScrollArea()
        self.insights_scroll.setWidgetResizable(True)
        self.insights_scroll.setFrameShape(QFrame.NoFrame)
        self.insights_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.insights_stream = QWidget()
        self.insights_body = QVBoxLayout(self.insights_stream)
        self.insights_body.setContentsMargins(0, 0, 0, 0)
        self.insights_body.setSpacing(12)
        self.insights_body.setAlignment(Qt.AlignTop)
        self.insights_scroll.setWidget(self.insights_stream)
        insights_layout.addWidget(self.insights_scroll, 1)

        content_layout.addWidget(self.chat_container, 7)
        content_layout.addWidget(self.insights_container, 3)

        root.addWidget(content)
        self.refresh()

    def _submit_prompt(self, prompt: str) -> None:
        if self._ai_busy:
            return
        self.chat_input.setText(prompt)
        self.send_message()

    def start_new_chat(self) -> None:
        if self._ai_busy:
            return
        self.ai.reset_chat_session()
        self.chat_messages.clear()
        self.chat_input.clear()
        self._render_chat_messages()

    def refresh_chat(self) -> None:
        if self._ai_busy:
            return
        last_prompt = ""
        for item in reversed(self.chat_messages):
            if item["role"] == "user":
                last_prompt = item["text"]
                break
        self.start_new_chat()
        if last_prompt:
            self._submit_prompt(last_prompt)

    def _add_message(self, role: str, text: str) -> None:
        self.chat_messages.append(
            {
                "role": role,
                "text": text,
                "time": datetime.now().strftime("%H:%M"),
            }
        )
        self._render_chat_messages()

    def _scroll_to_bottom(self) -> None:
        scroll_bar = self.chat_scroll.verticalScrollBar()
        QTimer.singleShot(0, lambda: scroll_bar.setValue(scroll_bar.maximum()))

    def _render_chat_messages(self) -> None:
        clear_layout(self.chat_stream_layout)
        if not self.chat_messages:
            self.chat_stream_layout.addWidget(self._build_empty_state())
            self.chat_stream_layout.addStretch(1)
            self._scroll_to_bottom()
            return

        for item in self.chat_messages:
            self.chat_stream_layout.addWidget(self._build_bubble(item["role"], item["text"], item["time"]))
        self.chat_stream_layout.addStretch(1)
        self._scroll_to_bottom()

    def _build_empty_state(self) -> QWidget:
        panel = QFrame()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)

        title = QLabel("Sohbet hazır")
        title.setStyleSheet(f"font-size: 17px; font-weight: 800; color: {COLORS['slate_900']};")
        layout.addWidget(title)

        prompt_row = QHBoxLayout()
        prompt_row.setContentsMargins(0, 6, 0, 0)
        prompt_row.setSpacing(8)
        for prompt in [
            "Bu ay hedefimi yorumla",
            "Riskli müşterileri sırala",
            "Kısa bir kapanış maili yaz",
        ]:
            btn = make_button(prompt, lambda _=False, p=prompt: self._submit_prompt(p), "ghost")
            btn.setMinimumHeight(38)
            prompt_row.addWidget(btn)
        layout.addLayout(prompt_row)
        layout.addStretch(1)

        panel.setStyleSheet(f"background: {rgba_string(COLORS['violet'], 8)}; border: none; border-radius: 24px;")
        return panel

    def _build_bubble(self, role: str, text: str, time: str) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(8)

        bubble_wrap = QVBoxLayout()
        bubble_wrap.setContentsMargins(0, 0, 0, 0)
        bubble_wrap.setSpacing(4)

        bubble = QFrame()
        bubble.setMaximumWidth(640)
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        blayout = QVBoxLayout(bubble)
        blayout.setContentsMargins(16, 14, 16, 14)
        blayout.addWidget(lbl)

        if role == "user":
            bubble.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:1, y2:1,
                        stop:0 {COLORS['accent']},
                        stop:1 {COLORS['accent_dark']}
                    );
                    border: none;
                    border-radius: 20px;
                    border-bottom-right-radius: 8px;
                }}
                QLabel {{ color: white; font-size: 13px; line-height: 1.5; background: transparent; }}
            """)
            hl.addStretch(1)
            bubble_wrap.addWidget(bubble)
            time_lbl = QLabel(time)
            time_lbl.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px; border: none;")
            time_lbl.setAlignment(Qt.AlignRight)
            bubble_wrap.addWidget(time_lbl)
            hl.addLayout(bubble_wrap)
        else:
            bubble.setStyleSheet(f"""
                QFrame {{
                    background: {rgba_string(COLORS['slate_500'], 12)};
                    border: none;
                    border-radius: 20px;
                    border-bottom-left-radius: 8px;
                }}
                QLabel {{ color: {COLORS['slate_900']}; font-size: 13px; line-height: 1.5; background: transparent; }}
            """)
            bubble_wrap.addWidget(bubble)
            time_lbl = QLabel(time)
            time_lbl.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px; border: none;")
            bubble_wrap.addWidget(time_lbl)
            hl.addLayout(bubble_wrap)
            hl.addStretch(1)

        return row

    def _build_insight_card(self, title: str, title_color: str, text: str, action_text: str, callback) -> QWidget:
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 {rgba_string(title_color, 12)},
                    stop: 1 transparent
                );
                border-left: none;
                border-top-right-radius: 16px;
                border-bottom-right-radius: 16px;
            }}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(18, 14, 14, 14)
        vl.setSpacing(10)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet(f"color: {title_color}; font-weight: 800; font-size: 12px; border: none; background: transparent;")
        vl.addWidget(t_lbl)

        txt_lbl = QLabel(text)
        txt_lbl.setWordWrap(True)
        txt_lbl.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px; line-height: 1.5; border: none; background: transparent;")
        vl.addWidget(txt_lbl)

        btn = make_button(action_text, callback, "ghost")
        btn.setMinimumHeight(38)
        vl.addWidget(btn, 0, Qt.AlignLeft)

        return card

    def _build_live_insights(self) -> List[Dict[str, Any]]:
        summary = self.db.get_dashboard_summary()
        segments = self.db.get_ai_segments()
        opportunities = sorted(
            [
                item for item in self.db.list_opportunities()
                if item["stage"] not in ("Kazanıldı", "Kaybedildi")
            ],
            key=lambda item: (item["value"], item["probability"], item["contact_ai_score"]),
            reverse=True,
        )
        risk_contact = summary["risk_customers"][0] if summary["risk_customers"] else None
        top_opportunity = opportunities[0] if opportunities and self.window.can_view("pipeline") else None
        goal_remaining = max(0, 200000 - summary["monthly_sales"])
        high_potential = segments["high_potential"]
        passive = segments["passive"]
        insights: List[Dict[str, Any]] = []

        if risk_contact:
            insights.append(
                {
                    "title": "Acil müşteri riski",
                    "tone": COLORS["rose"],
                    "text": (
                        f"{risk_contact['full_name']} / {risk_contact['company']} hesabında risk "
                        f"%{risk_contact['churn_risk']}. Son teması ve toparlama aksiyonunu kontrol edin."
                    ),
                    "action": "Hemen Ara",
                    "callback": lambda _=False, cid=risk_contact["id"]: self.window.start_quick_call(cid),
                }
            )

        if top_opportunity:
            prompt = (
                f"{top_opportunity['contact_company']} için {top_opportunity['title']} fırsatına "
                "kapanış odaklı kısa bir strateji hazırla."
            )
            insights.append(
                {
                    "title": "Bu haftanın fırsatı",
                    "tone": COLORS["emerald"],
                    "text": (
                        f"{top_opportunity['contact_company']} için {format_currency(top_opportunity['value'])} "
                        f"değerinde {top_opportunity['stage']} aşamasında açık fırsat var."
                    ),
                    "action": "Strateji Al",
                    "callback": lambda _=False, p=prompt: self._submit_prompt(p),
                }
            )

        can_open_reports = self.window.can_view("reports")
        insights.append(
            {
                "title": "Hedef takibi",
                "tone": COLORS["accent"],
                "text": (
                    f"Aylık satış {format_currency(summary['monthly_sales'])}. Hedefe kalan tutar "
                    f"{format_currency(goal_remaining)} ve ilerleme %{summary['goal_sales_percent']}."
                ),
                "action": "Raporu Aç" if can_open_reports else "Dashboard",
                "callback": (lambda _=False: self.window.switch_view("reports")) if can_open_reports else (lambda _=False: self.window.switch_view("dashboard")),
            }
        )

        segment_action_contact = high_potential[0] if high_potential else (passive[0] if passive else None)
        insights.append(
            {
                "title": "AI segmentasyon",
                "tone": COLORS["violet"],
                "text": (
                    f"{len(high_potential)} yüksek potansiyelli ve {len(passive)} pasif müşteri "
                    "otomatik segmentte öne çıktı."
                ),
                "action": "Listeyi Gör",
                "callback": (
                    (lambda _=False, cid=segment_action_contact["id"]: self.window.open_contact_detail(cid))
                    if segment_action_contact else
                    (lambda _=False: self.window.switch_view("contacts"))
                ),
            }
        )

        return insights

    def _render_insights(self) -> None:
        clear_layout(self.insights_body)
        for insight in self._build_live_insights():
            self.insights_body.addWidget(
                self._build_insight_card(
                    insight["title"],
                    insight["tone"],
                    insight["text"],
                    insight["action"],
                    insight["callback"],
                )
            )
        self.insights_body.addStretch(1)

    def _set_ai_busy(self, busy: bool) -> None:
        self._ai_busy = busy
        self.chat_input.setEnabled(not busy)
        self.send_btn.setEnabled(not busy)
        self.refresh_chat_btn.setEnabled(not busy)
        self.new_chat_btn.setEnabled(not busy)
        self.gear_btn.setEnabled(not busy)
        self.ai_status.setText("Yanıt hazırlanıyor..." if busy else "Çevrimiçi · canlı analiz modu")
        self.send_btn.setText("Hazırlanıyor..." if busy else "Gönder")

    def _cleanup_ai_worker(self) -> None:
        if self._ai_thread is not None:
            self._ai_thread.quit()
            self._ai_thread.wait(1000)
            self._ai_thread.deleteLater()
        if self._ai_worker is not None:
            self._ai_worker.deleteLater()
        self._ai_thread = None
        self._ai_worker = None

    def _handle_ai_reply(self, reply: str) -> None:
        self._add_message("ai", reply.replace(" | ", "\n• "))
        self._set_ai_busy(False)
        self._cleanup_ai_worker()

    def _handle_ai_error(self, error_text: str) -> None:
        fallback_message = error_text.strip() or "Yanıt üretilemedi."
        self._add_message("ai", fallback_message)
        self._set_ai_busy(False)
        self._cleanup_ai_worker()

    def _begin_ai_request(self, text: str) -> None:
        self._set_ai_busy(True)
        self._ai_thread = QThread(self)
        self._ai_worker = AIReplyWorker(self.ai, text)
        self._ai_worker.moveToThread(self._ai_thread)
        self._ai_thread.started.connect(self._ai_worker.run)
        self._ai_worker.finished.connect(self._handle_ai_reply)
        self._ai_worker.failed.connect(self._handle_ai_error)
        self._ai_thread.start()

    def _apply_theme(self) -> None:
        self.chat_header.setStyleSheet(
            f"background: {rgba_string(COLORS['slate_500'], 8)}; border-radius: 20px;"
        )
        self.ai_name.setStyleSheet(f"color: {COLORS['slate_900']}; font-weight: 800; font-size: 14px;")
        self.ai_status.setStyleSheet(f"color: {COLORS['emerald']}; font-weight: 700; font-size: 11px;")
        self.active_badge.setStyleSheet(
            f"""
            QLabel {{
                background: {rgba_string(COLORS['emerald'], 24)};
                color: {COLORS['emerald']};
                border-radius: 14px;
                padding: 7px 12px;
                font-size: 11px;
                font-weight: 800;
            }}
            """
        )
        self.input_area.setStyleSheet(
            f"background: {rgba_string(COLORS['slate_500'], 10)}; border-radius: 24px;"
        )
        self.chat_input.setStyleSheet(
            f"""
            QLineEdit {{
                background: {COLORS['surface']};
                color: {COLORS['slate_900']};
                border: none;
                border-radius: 18px;
                padding: 12px 14px;
                font-size: 13px;
            }}
            QLineEdit:focus {{
                background: {rgba_string(COLORS['accent'], 8)};
            }}
            """
        )
        input_palette = self.chat_input.palette()
        input_palette.setColor(QPalette.Text, QColor(COLORS["slate_900"]))
        input_palette.setColor(QPalette.PlaceholderText, QColor(COLORS["slate_500"]))
        self.chat_input.setPalette(input_palette)
        self.send_btn.setStyleSheet(
            f"""
            QPushButton {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['accent']},
                    stop:1 {COLORS['accent_dark']}
                );
                color: white;
                border: none;
                border-radius: 18px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 800;
            }}
            QPushButton:hover {{
                background: {COLORS['accent_dark']};
            }}
            QPushButton:disabled {{
                background: {rgba_string(COLORS['accent'], 90)};
                color: rgba(255, 255, 255, 220);
            }}
            """
        )
        self.action_menu.setStyleSheet(
            f"""
            QMenu {{
                background: {COLORS['surface']};
                color: {COLORS['slate_900']};
                border: none;
                border-radius: 16px;
                padding: 8px;
            }}
            QMenu::item {{
                color: {COLORS['slate_900']};
                padding: 10px 14px;
                border-radius: 10px;
                background: transparent;
            }}
            QMenu::item:selected {{
                background: {rgba_string(COLORS['accent'], 18)};
                color: {COLORS['accent_dark']};
            }}
            """
        )

    def send_message(self):
        if not self.window.require_permission("ai_chat", "AI sohbeti kullanma"):
            return
        text = self.chat_input.text().strip()
        if not text or self._ai_busy:
            return

        self._add_message("user", text)
        self.chat_input.clear()
        self._begin_ai_request(text)

    def refresh(self):
        self._apply_theme()
        self._render_chat_messages()
        self._render_insights()


# Satış, operasyon ve ekip metriklerini grafiklerle gösteren rapor sayfası.
class ReportsPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(16, 14, 16, 16)
        self.layout.setSpacing(14)
        scroll.setWidget(self.container)
        root.addWidget(scroll)
        self.refresh()

    def refresh(self):
        report = self.db.get_reports_summary()
        clear_layout(self.layout)

        # ── Header ──────────────────────────────────────
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Raporlar & Analitik")
        title.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 22px; font-weight: 900;")
        subtitle = QLabel("Günlük, haftalık ve aylık satış performansını detaylı inceleyin")
        subtitle.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px;")
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        top.addLayout(title_col, 1)

        month_name = MONTH_NAMES[date.today().month - 1]
        date_pill = QLabel(f"📅 {month_name} {date.today().year}")
        date_pill.setObjectName("HeaderMetaPill")
        top.addWidget(date_pill)
        if self.window.can("report_export"):
            pdf_btn = make_button("📥 PDF İndir", self.window.export_report_pdf, "primary")
            top.addWidget(pdf_btn)
        self.layout.addLayout(top)

        # ── KPI Stat Cards ──────────────────────────────
        self.layout.addWidget(self._build_stat_cards(report))

        # ── Row 1: Sales Chart + Period Breakdown ───────
        row1 = QWidget()
        row1_layout = QHBoxLayout(row1)
        row1_layout.setContentsMargins(0, 0, 0, 0)
        row1_layout.setSpacing(14)
        row1_layout.addWidget(self._build_chart_panel(report), 3)
        row1_layout.addWidget(self._build_period_breakdown(report), 2)
        self.layout.addWidget(row1)

        # ── Row 2: Stage Funnel + Top Accounts ──────────
        row2 = QWidget()
        row2_layout = QHBoxLayout(row2)
        row2_layout.setContentsMargins(0, 0, 0, 0)
        row2_layout.setSpacing(14)
        row2_layout.addWidget(self._build_funnel_panel(report), 1)
        row2_layout.addWidget(self._build_top_accounts(report), 1)
        self.layout.addWidget(row2)

        # ── Row 3: Team Perf + Task & Call Analytics ────
        row3 = QWidget()
        row3_layout = QHBoxLayout(row3)
        row3_layout.setContentsMargins(0, 0, 0, 0)
        row3_layout.setSpacing(14)
        row3_layout.addWidget(self._build_team_panel(report), 1)
        row3_layout.addWidget(self._build_operations_panel(report), 1)
        self.layout.addWidget(row3)

        self.layout.addStretch(1)

    # ── KPI Cards ────────────────────────────────────────
    def _build_stat_cards(self, report):
        wrapper = QWidget()
        grid = QHBoxLayout(wrapper)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        growth = report["monthly_growth"]
        growth_sign = "↑" if growth >= 0 else "↓"
        growth_color = COLORS["accent"] if growth >= 0 else COLORS["rose"]

        avg_order = report["average_order"]

        cards = [
            ("TOPLAM SATIŞ", format_currency(report["total_sales"]),
             f"{growth_sign} %{abs(growth)} geçen aya göre", growth_color,
             [("Bu ay kapanış", format_currency(report["total_sales"])),
              ("Pipeline değeri", format_currency(report["pipeline_value"])),
              ("Teklif toplamı", format_currency(report["offer_value"])),
              ("Kazanılan", f"{report['won_count']} fırsat"),
              ("Kaybedilen", f"{report['lost_count']} fırsat")]),
            ("YENİ MÜŞTERİ", str(report["new_customers"]),
             f"+{report['new_customers']} bu ay", COLORS["accent"],
             [("Toplam portföy", str(len(report.get("top_accounts", [])))),
              ("Riskli hesap", str(report["risk_customer_count"])),
              ("Aktif teklif", str(report["offer_count"]))]),
            ("KAPANIŞ ORANI", f"%{report['close_rate']}",
             f"Görev tamamlama %{report['task_completion_rate']}", COLORS["emerald"],
             [("Kazanılan", f"{report['won_count']} fırsat"),
              ("Kaybedilen", f"{report['lost_count']} fırsat"),
              ("Görev tamamlama", f"%{report['task_completion_rate']}"),
              ("Çağrı başarı", f"%{report['call_positive_rate']}")]),
            ("ORTALAMA SİPARİŞ", format_currency(avg_order),
             f"{'↓' if avg_order == 0 else '↑'} fırsat başına ortalama", COLORS["violet"],
             [("Fırsat başına", format_currency(avg_order)),
              ("Aktif görev", str(report["active_task_count"])),
              ("Tamamlanan", str(report["completed_task_count"])),
              ("Geciken", str(report["overdue_task_count"]))]),
        ]

        for title_text, value, meta, meta_color, details in cards:
            card = _CollapsibleStatCard(title_text, value, meta, meta_color, details)
            grid.addWidget(card)

        return wrapper

    # ── Sales Chart ──────────────────────────────────────
    def _build_chart_panel(self, report):
        card, body, header = create_card("Aylık Satış Trendi", "Son 12 ayın satış performansı")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        chart = LineChartWidget()
        chart.setMinimumHeight(240)
        chart.setMaximumHeight(260)
        chart.set_series(
            report["sales_series"]["labels"],
            report["sales_series"]["values"],
            "Satış Geliri"
        )
        body.addWidget(chart)

        # Summary metrics under chart
        metrics = QHBoxLayout()
        metrics.setContentsMargins(0, 0, 0, 0)
        metrics.setSpacing(8)
        values = report["sales_series"]["values"]
        total = sum(values)
        avg_val = total / max(len(values), 1)
        peak = max(values) if values else 0
        peak_idx = values.index(peak) if values and peak > 0 else 0
        peak_month = report["sales_series"]["labels"][peak_idx] if report["sales_series"]["labels"] else "-"

        for label, val in [("Yıllık Toplam", format_currency(total)), ("Aylık Ortalama", format_currency(avg_val)), ("En İyi Ay", f"{peak_month} · {format_currency(peak)}")]:
            block = QFrame()
            block.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 10)}; border-radius: 14px;")
            bl = QVBoxLayout(block)
            bl.setContentsMargins(12, 8, 12, 8)
            bl.setSpacing(2)
            c = QLabel(label)
            c.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
            v = QLabel(val)
            v.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 800;")
            bl.addWidget(c)
            bl.addWidget(v)
            metrics.addWidget(block)
        body.addLayout(metrics)
        return card

    # ── Period Breakdown (Daily/Weekly/Monthly) ──────────
    def _build_period_breakdown(self, report):
        card, body, _ = create_card("Dönemsel Analiz", "Günlük · Haftalık · Aylık")
        card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)

        today = date.today()
        now = datetime.now()
        opportunities = self.db.list_opportunities()
        won_opps = [o for o in opportunities if o["stage"] == "Kazanıldı" and o.get("closed_at")]

        # Daily
        today_sales = sum(o["value"] for o in won_opps if parse_iso(o["closed_at"]) and parse_iso(o["closed_at"]).date() == today)
        today_count = len([o for o in won_opps if parse_iso(o["closed_at"]) and parse_iso(o["closed_at"]).date() == today])

        # Weekly
        week_start = today - timedelta(days=today.weekday())
        weekly_sales = sum(o["value"] for o in won_opps if parse_iso(o["closed_at"]) and parse_iso(o["closed_at"]).date() >= week_start)
        weekly_count = len([o for o in won_opps if parse_iso(o["closed_at"]) and parse_iso(o["closed_at"]).date() >= week_start])

        # Monthly
        monthly_sales = report["total_sales"]
        monthly_count = report["won_count"]

        periods = [
            ("📅 Bugün", format_currency(today_sales), f"{today_count} kapanış", COLORS["accent"]),
            ("📆 Bu Hafta", format_currency(weekly_sales), f"{weekly_count} kapanış", COLORS["emerald"]),
            ("🗓️ Bu Ay", format_currency(monthly_sales), f"{monthly_count} kapanış", COLORS["violet"]),
        ]

        for label, value, meta, color in periods:
            row = QFrame()
            row.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 10)}; border-radius: 18px;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(16, 16, 16, 16)
            rl.setSpacing(14)

            dot = QFrame()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(f"background: {color}; border-radius: 4px;")
            rl.addWidget(dot, 0, Qt.AlignVCenter)

            info = QVBoxLayout()
            info.setContentsMargins(0, 0, 0, 0)
            info.setSpacing(2)
            l = QLabel(label)
            l.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; font-weight: 700;")
            info.addWidget(l)
            v = QLabel(value)
            v.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 22px; font-weight: 900;")
            info.addWidget(v)
            m = QLabel(meta)
            m.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 11px; font-weight: 600;")
            info.addWidget(m)
            rl.addLayout(info, 1)
            body.addWidget(row)

        # Goal progress
        goal_pct = report.get("goal_progress", 0)
        goal_frame = QFrame()
        goal_frame.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 10)}; border-radius: 18px;")
        gl = QVBoxLayout(goal_frame)
        gl.setContentsMargins(16, 14, 16, 14)
        gl.setSpacing(8)
        goal_header = QHBoxLayout()
        goal_header.setContentsMargins(0, 0, 0, 0)
        goal_label = QLabel("🎯 Aylık Hedef İlerlemesi")
        goal_label.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px; font-weight: 700;")
        goal_pct_label = QLabel(f"%{goal_pct}")
        goal_pct_label.setStyleSheet(f"color: {COLORS['accent']}; font-size: 14px; font-weight: 800;")
        goal_header.addWidget(goal_label, 1)
        goal_header.addWidget(goal_pct_label)
        gl.addLayout(goal_header)
        gl.addWidget(ProgressRow("İlerleme", goal_pct, COLORS["accent"]))
        body.addWidget(goal_frame)

        return card

    # ── Stage Funnel ─────────────────────────────────────
    def _build_funnel_panel(self, report):
        card, body, _ = create_card("Satış Hunisi", "Aşama bazlı fırsat dağılımı")

        stage_colors = {
            "Potansiyel": COLORS["slate_400"],
            "Görüşme": COLORS["accent"],
            "Teklif": COLORS["amber"],
            "Kazanıldı": COLORS["emerald"],
            "Kaybedildi": COLORS["rose"],
        }
        stage_icons = {
            "Potansiyel": "🔵", "Görüşme": "💬", "Teklif": "📋",
            "Kazanıldı": "✅", "Kaybedildi": "❌",
        }

        total = max(sum(s["count"] for s in report["stage_breakdown"]), 1)

        for stage_data in report["stage_breakdown"]:
            stage = stage_data["stage"]
            count = stage_data["count"]
            value = stage_data["value"]
            share = stage_data["share"]
            color = stage_colors.get(stage, COLORS["slate_400"])
            icon = stage_icons.get(stage, "●")

            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            rl = QVBoxLayout(row)
            rl.setContentsMargins(14, 12, 14, 12)
            rl.setSpacing(6)

            top_row = QHBoxLayout()
            top_row.setContentsMargins(0, 0, 0, 0)
            top_row.setSpacing(8)
            name = QLabel(f"{icon} {stage}")
            name.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 700;")
            top_row.addWidget(name, 1)

            count_badge = QLabel(f"{count} fırsat")
            count_badge.setStyleSheet(f"""
                QLabel {{
                    background: {rgba_string(color, 18)};
                    color: {color};
                    border-radius: 10px;
                    padding: 3px 8px;
                    font-size: 10px;
                    font-weight: 800;
                }}
            """)
            top_row.addWidget(count_badge)
            rl.addLayout(top_row)

            val_label = QLabel(format_currency(value))
            val_label.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px; font-weight: 600;")
            rl.addWidget(val_label)

            # Visual bar
            bar_container = QWidget()
            bar_container.setFixedHeight(8)
            bar_lay = QHBoxLayout(bar_container)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            fill_pct = max(2, share)
            empty_pct = max(1, 100 - fill_pct)
            bar_fill = QFrame()
            bar_fill.setFixedHeight(8)
            bar_fill.setStyleSheet(f"background: {color}; border-radius: 4px;")
            bar_empty = QFrame()
            bar_empty.setFixedHeight(8)
            bar_empty.setStyleSheet(f"background: {COLORS['slate_100']}; border-radius: 4px;")
            bar_lay.addWidget(bar_fill, fill_pct)
            bar_lay.addWidget(bar_empty, empty_pct)
            rl.addWidget(bar_container)

            body.addWidget(row)

        return card

    # ── Top Accounts ─────────────────────────────────────
    def _build_top_accounts(self, report):
        card, body, _ = create_card("En İyi Müşteriler", "Satış ve AI skoru bazlı sıralama")

        team_colors = [COLORS["accent"], COLORS["emerald"], COLORS["amber"], COLORS["violet"], COLORS["rose"]]

        for i, contact in enumerate(report.get("top_accounts", [])[:5]):
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 12, 14, 12)
            rl.setSpacing(12)

            # Rank badge
            rank = QLabel(f"#{i + 1}")
            rank.setFixedSize(32, 32)
            rank.setAlignment(Qt.AlignCenter)
            rank_color = team_colors[i % len(team_colors)]
            rank.setStyleSheet(f"""
                QLabel {{
                    background: {rgba_string(rank_color, 18)};
                    color: {rank_color};
                    border-radius: 10px;
                    font-size: 12px;
                    font-weight: 900;
                }}
            """)
            rl.addWidget(rank)

            info = QVBoxLayout()
            info.setContentsMargins(0, 0, 0, 0)
            info.setSpacing(2)
            name = QLabel(contact["full_name"])
            name.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 700;")
            detail = QLabel(f"{contact.get('company', '-')}  ·  AI: {contact.get('ai_score', 0)}")
            detail.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            info.addWidget(name)
            info.addWidget(detail)
            rl.addLayout(info, 1)

            sales_lbl = QLabel(format_currency(contact.get("total_sales", 0)))
            sales_lbl.setStyleSheet(f"color: {COLORS['accent']}; font-size: 14px; font-weight: 800;")
            rl.addWidget(sales_lbl)

            body.addWidget(row)

        # Risk accounts
        risk_accounts = report.get("risk_accounts", [])
        if risk_accounts:
            sep_label = QLabel("⚠️ Risk Altındaki Hesaplar")
            sep_label.setStyleSheet(f"color: {COLORS['rose']}; font-size: 12px; font-weight: 800;")
            body.addSpacing(6)
            body.addWidget(sep_label)
            for contact in risk_accounts[:3]:
                row = QFrame()
                row.setStyleSheet(f"background: {rgba_string(COLORS['rose'], 8)}; border-radius: 14px;")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 10, 12, 10)
                rl.setSpacing(10)

                warn = QLabel("⚠")
                warn.setFixedWidth(20)
                warn.setStyleSheet(f"font-size: 14px;")
                rl.addWidget(warn)

                info = QVBoxLayout()
                info.setContentsMargins(0, 0, 0, 0)
                info.setSpacing(1)
                name = QLabel(contact["full_name"])
                name.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 12px; font-weight: 700;")
                detail = QLabel(f"Kayıp riski: %{contact.get('churn_risk', 0)} · AI: {contact.get('ai_score', 0)}")
                detail.setStyleSheet(f"color: {COLORS['rose']}; font-size: 11px; font-weight: 600;")
                info.addWidget(name)
                info.addWidget(detail)
                rl.addLayout(info, 1)
                body.addWidget(row)

        return card

    # ── Team Performance ─────────────────────────────────
    def _build_team_panel(self, report):
        card, body, _ = create_card("Ekip Performansı", "Satış ekibinin aylık durumu")

        team_colors = [COLORS["accent"], COLORS["emerald"], COLORS["amber"], COLORS["violet"], COLORS["rose"]]

        for i, user in enumerate(report["team_performance"]):
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 10, 0, 10)
            rl.setSpacing(12)

            color = team_colors[i % len(team_colors)]
            rl.addWidget(AvatarLabel(initials(user["full_name"]), color, 40))

            info = QVBoxLayout()
            info.setContentsMargins(0, 0, 0, 0)
            info.setSpacing(2)
            name = QLabel(user["full_name"])
            name.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 700;")
            meta = QLabel(f"{format_currency(float(user['monthly_sales']))} satış · {user['customer_count']} müşteri")
            meta.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            info.addWidget(name)
            info.addWidget(meta)
            rl.addLayout(info, 1)

            fill_pct = max(2, int(user["performance_percent"]))
            empty_pct = max(1, 100 - fill_pct)
            bar_container = QWidget()
            bar_container.setFixedHeight(10)
            bar_container.setFixedWidth(100)
            bar_lay = QHBoxLayout(bar_container)
            bar_lay.setContentsMargins(0, 0, 0, 0)
            bar_lay.setSpacing(0)
            bar_fill = QFrame()
            bar_fill.setFixedHeight(10)
            bar_fill.setStyleSheet(f"background: {color}; border-radius: 5px;")
            bar_empty = QFrame()
            bar_empty.setFixedHeight(10)
            bar_empty.setStyleSheet(f"background: {COLORS['slate_100']}; border-radius: 5px;")
            bar_lay.addWidget(bar_fill, fill_pct)
            bar_lay.addWidget(bar_empty, empty_pct)
            rl.addWidget(bar_container)

            pct_lbl = QLabel(f"%{user['performance_percent']}")
            pct_lbl.setStyleSheet(f"color: {COLORS['slate_700']}; font-size: 12px; font-weight: 700;")
            pct_lbl.setFixedWidth(36)
            pct_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            rl.addWidget(pct_lbl)

            body.addWidget(row)

        return card

    # ── Operations Panel (Tasks + Calls) ─────────────────
    def _build_operations_panel(self, report):
        card, body, _ = create_card("Operasyon Metrikleri", "Görev ve görüşme analizi")

        # Tasks section
        task_header = QLabel("📋 Görev Durumu")
        task_header.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 800;")
        body.addWidget(task_header)

        task_metrics = [
            ("Toplam Görev", str(report["task_total"]), COLORS["slate_700"]),
            ("Tamamlanan", str(report["completed_task_count"]), COLORS["emerald"]),
            ("Aktif", str(report["active_task_count"]), COLORS["accent"]),
            ("Geciken", str(report["overdue_task_count"]), COLORS["rose"]),
        ]

        task_grid = QHBoxLayout()
        task_grid.setContentsMargins(0, 0, 0, 0)
        task_grid.setSpacing(8)
        for label, value, color in task_metrics:
            block = QFrame()
            block.setStyleSheet(f"background: {rgba_string(color, 8)}; border-radius: 14px;")
            bl = QVBoxLayout(block)
            bl.setContentsMargins(12, 10, 12, 10)
            bl.setSpacing(4)
            v = QLabel(value)
            v.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 900;")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
            l.setAlignment(Qt.AlignCenter)
            bl.addWidget(v)
            bl.addWidget(l)
            task_grid.addWidget(block)
        body.addLayout(task_grid)

        body.addWidget(ProgressRow("Tamamlanma Oranı", report["task_completion_rate"], COLORS["accent"]))
        body.addSpacing(8)

        # Calls section
        call_header = QLabel("📞 Görüşme Analizi")
        call_header.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 13px; font-weight: 800;")
        body.addWidget(call_header)

        call_metrics = [
            ("Toplam Görüşme", str(report["call_total"]), COLORS["slate_700"]),
            ("Olumlu Oran", f"%{report['call_positive_rate']}", COLORS["emerald"]),
            ("Yaklaşan", str(report["upcoming_call_count"]), COLORS["accent"]),
        ]

        call_grid = QHBoxLayout()
        call_grid.setContentsMargins(0, 0, 0, 0)
        call_grid.setSpacing(8)
        for label, value, color in call_metrics:
            block = QFrame()
            block.setStyleSheet(f"background: {rgba_string(color, 8)}; border-radius: 14px;")
            bl = QVBoxLayout(block)
            bl.setContentsMargins(12, 10, 12, 10)
            bl.setSpacing(4)
            v = QLabel(value)
            v.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: 900;")
            v.setAlignment(Qt.AlignCenter)
            l = QLabel(label)
            l.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
            l.setAlignment(Qt.AlignCenter)
            bl.addWidget(v)
            bl.addWidget(l)
            call_grid.addWidget(block)
        body.addLayout(call_grid)

        body.addWidget(ProgressRow("Olumlu Görüşme", report["call_positive_rate"], COLORS["emerald"]))

        return card




# Ekip kartına tıklanınca açılan kullanıcı detay/timeline paneli.
class TeamMemberDetailPanel(QFrame):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SlidePanel")
        self.setFixedWidth(360)
        self.db: Optional[DatabaseManager] = None
        self.window_ref = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setStyleSheet(f"background: {COLORS['slate_50']}; border-top-left-radius: 28px;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 16, 16)
        title = QLabel("Ekip Özeti")
        title.setStyleSheet(f"font-size: 15px; font-weight: 900; color: {COLORS['slate_900']};")
        close_btn = QPushButton("×")
        close_btn.setFixedSize(34, 34)
        close_btn.setStyleSheet(
            f"QPushButton {{ background: {COLORS['slate_200']}; border: none; border-radius: 17px; color: {COLORS['slate_700']}; font-size: 16px; font-weight: 800; }}"
            f"QPushButton:hover {{ background: {COLORS['rose_light']}; color: {COLORS['rose']}; }}"
        )
        close_btn.clicked.connect(self.closed.emit)
        header_layout.addWidget(title, 1)
        header_layout.addWidget(close_btn)
        root.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(18, 18, 18, 18)
        self.body_layout.setSpacing(14)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

    def load_user(self, user: Dict[str, Any]):
        clear_layout(self.body_layout)
        if not self.db:
            return

        profile = QFrame()
        profile.setStyleSheet("background: transparent; border: none;")
        profile_layout = QVBoxLayout(profile)
        profile_layout.setContentsMargins(16, 16, 16, 16)
        profile_layout.setSpacing(10)
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(12)
        top.addWidget(AvatarLabel(initials(user["full_name"]), COLORS["accent"], 50))
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(3)
        name = QLabel(user["full_name"])
        name.setStyleSheet(f"font-size: 17px; font-weight: 900; color: {COLORS['slate_900']};")
        role = QLabel(user["role"])
        role.setStyleSheet(f"color: {COLORS['accent_dark']}; font-size: 11px; font-weight: 800;")
        info.addWidget(name)
        info.addWidget(role)
        top.addLayout(info, 1)
        profile_layout.addLayout(top)
        badges = QHBoxLayout()
        badges.setSpacing(8)
        badges.addWidget(BadgeLabel(user["online_status"]))
        badges.addWidget(BadgeLabel(user["role"]))
        badges.addStretch(1)
        profile_layout.addLayout(badges)
        self.body_layout.addWidget(profile)

        tasks = [task for task in self.db.list_tasks(include_done=True) if task.get("assigned_user_id") == user["id"]]
        calls = [call for call in self.db.list_calls() if call.get("owner_user_id") == user["id"]]
        stats = QGridLayout()
        stats.setHorizontalSpacing(10)
        stats.setVerticalSpacing(10)
        stat_items = [
            ("Aylık Satış", format_currency(float(user["monthly_sales"])), COLORS["amber"]),
            ("Portföy", str(user["customer_count"]), COLORS["violet"]),
            ("Performans", f"%{user['performance_percent']}", COLORS["emerald"]),
            ("Açık İş", str(len([task for task in tasks if not task['is_done']])), COLORS["accent"]),
        ]
        for index, (label, value, tone) in enumerate(stat_items):
            tile = QFrame()
            tile.setStyleSheet("background: transparent; border: none;")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(12, 12, 12, 12)
            tile_layout.setSpacing(4)
            label_widget = QLabel(label)
            label_widget.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
            value_widget = QLabel(value)
            value_widget.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {tone};")
            tile_layout.addWidget(label_widget)
            tile_layout.addWidget(value_widget)
            stats.addWidget(tile, index // 2, index % 2)
        self.body_layout.addLayout(stats)

        summary = QLabel(
            f"Son giriş {format_datetime(user.get('last_login'))}. "
            f"Bu kullanıcı {len(calls)} görüşme ve {len(tasks)} görev kaydında görünüyor."
        )
        summary.setWordWrap(True)
        summary.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px;")
        self.body_layout.addWidget(summary)

        activity_header = QLabel("Kısa Timeline")
        activity_header.setStyleSheet(f"font-size: 12px; font-weight: 900; color: {COLORS['slate_900']};")
        self.body_layout.addWidget(activity_header)
        activities = self.db.list_user_activities(user["id"], limit=8)
        if not activities:
            empty = QLabel("Bu kullanıcı için yakın tarihli aktivite görünmüyor.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            self.body_layout.addWidget(empty)
        for activity in activities:
            row = QFrame()
            row.setStyleSheet("background: transparent; border: none;")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(12, 12, 12, 12)
            row_layout.setSpacing(4)
            title_widget = QLabel(activity.get("title", "Aktivite"))
            title_widget.setWordWrap(True)
            title_widget.setStyleSheet(f"font-size: 12px; font-weight: 800; color: {COLORS['slate_900']};")
            detail_widget = QLabel(activity.get("description", ""))
            detail_widget.setWordWrap(True)
            detail_widget.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
            date_widget = QLabel(format_datetime(activity.get("created_at")))
            date_widget.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px; font-weight: 700;")
            row_layout.addWidget(title_widget)
            row_layout.addWidget(detail_widget)
            row_layout.addWidget(date_widget)
            self.body_layout.addWidget(row)
        self.body_layout.addStretch(1)


# Kullanıcı/ekip listesi, rol filtreleri ve performans özetlerini yöneten sayfa.
class TeamPage(BasePage):
    def __init__(self, window: "CRMMainWindow"):
        super().__init__(window)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(16)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        content_layout.setSpacing(SECTION_SPACING)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Ekip Yönetimi")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Minimal ekip görünümü, sağda kısa özet ve aktivite akışı.")
        subtitle.setObjectName("SectionSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        top.addLayout(title_box)
        top.addStretch(1)
        self.add_button = make_button("Kullanıcı Ekle", lambda: self.window.open_user_dialog(), "primary")
        top.addWidget(self.add_button)
        content_layout.addLayout(top)

        self.info_label = QLabel("")
        self.info_label.setObjectName("SectionSubtitle")
        content_layout.addWidget(self.info_label)

        filters_card = CardFrame()
        filters = QHBoxLayout(filters_card)
        filters.setContentsMargins(14, 12, 14, 12)
        filters.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Kullanıcı adı, e-posta veya telefon ara...")
        self.role_filter = self.window.create_combo(["Tüm Roller"] + ROLE_OPTIONS)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.role_filter)
        content_layout.addWidget(filters_card)

        self.summary_card = CardFrame()
        self.summary_layout = QHBoxLayout(self.summary_card)
        self.summary_layout.setContentsMargins(14, 12, 14, 12)
        self.summary_layout.setSpacing(10)
        content_layout.addWidget(self.summary_card)

        list_header = QVBoxLayout()
        list_header.setSpacing(4)
        list_title = QLabel("Ekip Listesi")
        list_title.setObjectName("CardTitle")
        list_subtitle = QLabel("Her ekip üyesi için bağımsız, detaylı kart görünümü")
        list_subtitle.setObjectName("CardSubtitle")
        list_header.addWidget(list_title)
        list_header.addWidget(list_subtitle)
        content_layout.addLayout(list_header)

        self.list_scroll = QScrollArea()
        self.list_scroll.setWidgetResizable(True)
        self.list_scroll.setFrameShape(QFrame.NoFrame)
        self.list_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_stream = QWidget()
        self.list_layout = QVBoxLayout(self.list_stream)
        self.list_layout.setContentsMargins(6, 6, 6, 6)
        self.list_layout.setSpacing(14)
        self.list_scroll.setWidget(self.list_stream)
        content_layout.addWidget(self.list_scroll, 1)
        root.addWidget(content, 1)

        self.detail_panel = TeamMemberDetailPanel()
        self.detail_panel.db = self.db
        self.detail_panel.window_ref = self.window
        self.detail_panel.closed.connect(self._hide_detail_panel)
        self.detail_panel.setVisible(False)
        root.addWidget(self.detail_panel)

        self.search_input.textChanged.connect(self.refresh)
        self.role_filter.currentTextChanged.connect(self.refresh)
        self.refresh()

    def _hide_detail_panel(self):
        self.detail_panel.setVisible(False)

    def _show_user_detail(self, user: Dict[str, Any]):
        self.detail_panel.load_user(user)
        self.detail_panel.setVisible(True)

    def _build_summary_tile(self, label: str, value: str, tone: str) -> QWidget:
        tile = QFrame()
        tile.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(tile)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(2)
        title = QLabel(label)
        title.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 10px; font-weight: 700;")
        number = QLabel(value)
        number.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {tone};")
        layout.addWidget(title)
        layout.addWidget(number)
        return tile

    def _build_member_card(self, user: Dict[str, Any], allowed: bool) -> QWidget:
        role_color = role_accent_color(user["role"])
        
        card = ClickableFrame()
        border_color = rgba_string(role_color, 20)
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['surface']};
                border: none;
                border-radius: 18px;
            }}
            QFrame:hover {{
                background: {COLORS['surface_alt']};
                border: none;
            }}
        """)

        card.clicked.connect(lambda u=user: self._show_user_detail(u))
        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(AvatarLabel(initials(user["full_name"]), role_color, 44), 0, Qt.AlignTop)

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(4)
        name = QLabel(user["full_name"])
        name.setStyleSheet(f"font-size: 13px; font-weight: 900; color: {COLORS['slate_900']};")
        meta = QLabel(f"{user.get('email') or '-'} • {user.get('phone') or '-'}")
        meta.setWordWrap(True)
        meta.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px;")
        strip = QLabel(
            f"{format_currency(float(user['monthly_sales']))} satış • {user['customer_count']} müşteri • %{user['performance_percent']} performans"
        )
        strip.setWordWrap(True)
        strip.setStyleSheet(f"color: {COLORS['slate_600']}; font-size: 11px; font-weight: 700;")
        info.addWidget(name)
        info.addWidget(meta)
        info.addWidget(strip)
        layout.addLayout(info, 1)

        badges = QVBoxLayout()
        badges.setContentsMargins(0, 0, 0, 0)
        badges.setSpacing(8)
        badges.addWidget(BadgeLabel(user["role"]))
        badges.addWidget(BadgeLabel(user["online_status"]))
        layout.addLayout(badges)

        actions = QVBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        summary_btn = make_button("Özet", lambda _=False, u=user: self._show_user_detail(u), "ghost")
        summary_btn.setMinimumWidth(84)
        summary_btn.setFixedHeight(34)
        actions.addWidget(summary_btn)
        if allowed:
            edit_btn = make_button("Düzenle", lambda _=False, row_data=user: self.window.open_user_dialog(row_data), "ghost")
            edit_btn.setMinimumWidth(84)
            edit_btn.setFixedHeight(34)
            actions.addWidget(edit_btn)
            
            if self.window.can("team_delete"):
                delete_btn = make_button("Sil", lambda _=False, u=user: self.window.delete_user_confirm(u), "danger")
                delete_btn.setMinimumWidth(84)
                delete_btn.setFixedHeight(34)
                actions.addWidget(delete_btn)
        
        layout.addLayout(actions)
        return card

    def refresh(self):
        allowed = self.window.can("team_manage")
        self.add_button.setEnabled(allowed)
        self.info_label.setText("" if allowed else "Bu sayfada yalnızca görüntüleme yetkiniz var.")
        users = self.db.get_team_performance()
        query = self.search_input.text().strip().lower()
        role_filter = self.role_filter.currentText()
        filtered_users = []
        for user in users:
            haystack = " ".join([user.get("full_name", ""), user.get("email", ""), user.get("phone", "")]).lower()
            if query and query not in haystack:
                continue
            if role_filter != "Tüm Roller" and user["role"] != role_filter:
                continue
            filtered_users.append(user)

        clear_layout(self.summary_layout)
        online_count = len([user for user in users if user["online_status"] == "Çevrimiçi"])
        monthly_total = sum(float(user["monthly_sales"]) for user in users)
        total_customers = sum(int(user["customer_count"]) for user in users)
        activity_count = len(self.db.list_activities(limit=20))
        self.summary_layout.addWidget(self._build_summary_tile("Kullanıcı", str(len(users)), COLORS["accent"]))
        self.summary_layout.addWidget(self._build_summary_tile("Çevrimiçi", str(online_count), COLORS["emerald"]))
        self.summary_layout.addWidget(self._build_summary_tile("Portföy", str(total_customers), COLORS["violet"]))
        self.summary_layout.addWidget(self._build_summary_tile("Aylık Satış", format_currency(monthly_total), COLORS["amber"]))
        self.summary_layout.addWidget(self._build_summary_tile("Hareket", str(activity_count), COLORS["rose"]))
        self.summary_layout.addStretch(1)

        clear_layout(self.list_layout)
        if not filtered_users:
            empty = QLabel("Filtreye uygun kullanıcı bulunamadı.")
            empty.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; padding: 8px 4px;")
            self.list_layout.addWidget(empty)
        for user in filtered_users:
            self.list_layout.addWidget(self._build_member_card(user, allowed))
        self.list_layout.addStretch(1)

# Sağdan kayan, son aktiviteleri bildirim gibi gösteren çekmece.
class NotificationDrawer(QFrame):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("SlidePanel")
        self.setFixedWidth(400)
        self.anim = None
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        header = QHBoxLayout()
        self.title_label = QLabel("BİLDİRİMLER")
        self.title_label.setStyleSheet("font-size: 16px; font-weight: 900; letter-spacing: 1px;")
        close_btn = make_button("✕ Kapat", self.hide_drawer, "ghost")
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(close_btn)
        layout.addLayout(header)
        
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(12)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)

    def show_drawer(self):
        self.title_label.setStyleSheet(f"color: {COLORS['slate_900']}; font-size: 16px; font-weight: 900; letter-spacing: 1px;")
        clear_layout(self.body_layout)
        activities = []
        if hasattr(self.parent().window(), "db"):
            summary = self.parent().window().db.get_dashboard_summary()
            activities = summary.get("recent_activities", [])
            
        if not activities:
            lbl = QLabel("Yakın zamanda yeni bildiriminiz yok.")
            lbl.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 13px; background: transparent;")
            self.body_layout.addWidget(lbl)
        else:
            kind_colors = {
                "Satış": COLORS["accent"], "Görüşme": COLORS["emerald"],
                "Teklif": COLORS["violet"], "Görev": COLORS["amber"],
                "Mail": COLORS["cyan"], "Dosya": COLORS["rose"],
                "Müşteri": COLORS["accent"], "AI": COLORS["violet"],
            }
            for item in activities[:15]:
                row = QFrame()
                # Use a very subtle theme-aware background row hover equivalent
                row.setStyleSheet(f"background: {rgba_string(COLORS['slate_500'], 12)}; border-radius: 14px;")
                rl = QHBoxLayout(row)
                rl.setContentsMargins(12, 12, 12, 12)
                rl.setSpacing(12)
                
                kind = item.get("kind", "Sistem")
                c = kind_colors.get(kind, COLORS["accent"])
                rl.addWidget(AvatarLabel(initials(kind), c, 36), 0, Qt.AlignTop)
                
                info = QVBoxLayout()
                info.setContentsMargins(0, 0, 0, 0)
                info.setSpacing(4)
                t = QLabel(item.get("title", ""))
                t.setStyleSheet(f"color: {COLORS['slate_900']}; font-weight: 800; font-size: 13px; background: transparent;")
                t.setWordWrap(True)
                info.addWidget(t)
                
                desc_text = item.get("description", "").strip()
                if desc_text and desc_text != item.get("title", ""):
                    d = QLabel(desc_text)
                    d.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 11px; background: transparent;")
                    d.setWordWrap(True)
                    info.addWidget(d)
                
                ts = QLabel(format_datetime(item.get("created_at")))
                ts.setStyleSheet(f"color: {COLORS['slate_400']}; font-size: 10px; font-weight: 700; background: transparent;")
                info.addWidget(ts)
                rl.addLayout(info, 1)
                self.body_layout.addWidget(row)
                
        self.body_layout.addStretch(1)

        self.raise_()
        self.show()
        parent_w = self.parent().width()
        parent_h = self.parent().height()
        start_rect = QRect(parent_w + 20, 0, self.width(), parent_h)
        end_rect = QRect(parent_w - self.width(), 0, self.width(), parent_h)
        
        self.setGeometry(start_rect)
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(400)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QEasingCurve.OutExpo)
        self.anim.start(QPropertyAnimation.DeleteWhenStopped)

    def hide_drawer(self):
        parent_w = self.parent().width()
        parent_h = self.parent().height()
        start_rect = self.geometry()
        end_rect = QRect(parent_w + 20, 0, self.width(), parent_h)
        
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QEasingCurve.InCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start(QPropertyAnimation.DeleteWhenStopped)
# ─────────────────────────────────────────────────────────
# MAIN WINDOW
# ─────────────────────────────────────────────────────────
# Uygulamanın ana pencere kabuğu; sidebar, header, sayfa geçişleri ve CRUD aksiyonlarını yönetir.
class CRMMainWindow(QMainWindow):
    logout_requested = pyqtSignal()

    VIEW_TITLES = {
        "dashboard": ("Dashboard", "Genel satış görünümü"),
        "contacts": ("Müşteriler", "Müşteri portföyü"),
        "pipeline": ("Satış Pipeline", "Aşama bazlı fırsat akışı"),
        "calls": ("Görüşmeler", "Toplantı ve arama takibi"),
        "calendar": ("Takvim", "Planlanan etkinlikler"),
        "mail": ("Mail Sistemi", "Gelen kutusu ve şablonlar"),
        "tasks": ("Görevler", "Aktif görev yönetimi"),
        "files": ("Dosyalar", "Yüklenen belge arşivi"),
        "ai": ("AI Koç", "Veri tabanlı öneriler"),
        "reports": ("Raporlar", "Satış analitiği"),
        "team": ("Ekip", "Kullanıcı yönetimi"),
    }

    def can(self, permission: str) -> bool:
        return user_can(self.current_user, permission)

    def can_view(self, view_name: str) -> bool:
        return user_can_view(self.current_user, view_name)

    def accessible_views(self) -> List[str]:
        return visible_views_for_role(self.current_user.get("role"), self.VIEW_TITLES.keys())

    def first_accessible_view(self) -> str:
        views = self.accessible_views()
        return views[0] if views else "dashboard"

    def require_permission(self, permission: str, action: str = "Bu işlem") -> bool:
        if self.can(permission):
            return True
        QMessageBox.warning(self, "Yetki", f"{action} için yetkiniz yok.")
        return False

    def require_view(self, view_name: str) -> bool:
        if self.can_view(view_name):
            return True
        title = self.VIEW_TITLES.get(view_name, (view_name, ""))[0]
        QMessageBox.warning(self, "Yetki", f"{title} ekranına erişim yetkiniz yok.")
        return False

    def __init__(self, db: DatabaseManager, ai: AIEngine, current_user: Dict[str, Any]):
        super().__init__()
        self.db = db
        self.ai = ai
        self.current_user = current_user
        self.current_contact_id = self._default_contact_id()
        self.status_options = list(STATUS_OPTIONS)
        self.tag_options = list(TAG_OPTIONS)
        self.priority_options = list(PRIORITY_OPTIONS)

        # Başlangıçta AI skorlarını güncelle (Arka planda)
        try:
            QTimer.singleShot(1000, lambda: threading.Thread(target=self.db.refresh_all_contact_scores, daemon=True).start())
        except Exception:
            pass

        # Dark mode durumu
        self.is_dark_mode = False

        self.setWindowTitle("NexCRM Pro")
        self.resize(1640, 980)
        self.setMinimumSize(1440, 900)
        central = QWidget()
        central.setObjectName("WindowRoot")
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        self.sidebar = self._build_sidebar()
        root.addWidget(self.sidebar)
        self.main_area = QFrame()
        self.main_area.setObjectName("MainArea")
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(18)

        self.header = self._build_header()
        main_layout.addWidget(self.header)

        self.stack_shell = QFrame()
        self.stack_shell.setObjectName("MainStackShell")
        stack_layout = QVBoxLayout(self.stack_shell)
        stack_layout.setContentsMargins(0, 0, 0, 0)
        stack_layout.setSpacing(0)
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        stack_layout.addWidget(self.stack)
        main_layout.addWidget(self.stack_shell, 1)
        root.addWidget(self.main_area, 1)

        self.pages = {
            "dashboard": DashboardPage(self),
            "contacts": ContactsPage(self),
            "pipeline": PipelinePage(self),
            "calls": CallsPage(self),
            "calendar": CalendarPage(self),
            "mail": MailPage(self),
            "tasks": TasksPage(self),
            "files": FilesPage(self),
            "ai": AIPage(self),
            "reports": ReportsPage(self),
            "team": TeamPage(self),
        }
        for name in self.VIEW_TITLES:
            self.stack.addWidget(self.pages[name])

        self.drawer = NotificationDrawer(central)
        self.drawer.hide()

    def resizeEvent(self, event):
        # Pencere boyutu değişirse açık bildirim çekmecesini sağ kenara sabitler.
        super().resizeEvent(event)
        if hasattr(self, "drawer") and self.drawer.isVisible():
            # Keep drawer pinned to the right side if window resizes
            self.drawer.setGeometry(self.centralWidget().width() - self.drawer.width(), 0, self.drawer.width(), self.centralWidget().height())

        self.switch_view("dashboard")

    def _default_contact_id(self):
        # Başlangıçta seçili olacak ilk yüksek skorlu müşteriyi bulur.
        contacts = self.db.list_contacts(sort_by="AI Skor")
        return contacts[0]["id"] if contacts else None

    def create_combo(self, items):
        # Sayfalarda tekrar kullanılan standart combobox üreticisi.
        combo = QComboBox()
        combo.setObjectName("DialogInput")
        combo.setCursor(Qt.PointingHandCursor)
        combo.addItems(items)
        return combo

    def _build_sidebar(self):
        # Sol navigasyon menüsü, marka alanı ve kullanıcı footer'ını oluşturur.
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(286)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(20, 20, 20, 18)
        layout.setSpacing(8)

        brand = QHBoxLayout()
        brand.setContentsMargins(0, 0, 0, 0)
        brand.setSpacing(14)
        brand.addWidget(AvatarLabel("NX", COLORS["accent"], 42))
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(3)
        name = QLabel("NexCRM")
        name.setObjectName("LogoName")
        text.addWidget(name)
        brand.addLayout(text, 1)
        version = QLabel("v2.0")
        version.setObjectName("LogoVersion")
        brand.addWidget(version)
        layout.addLayout(brand)

        self.nav_buttons: Dict[str, QPushButton] = {}
        nav_shell = QWidget()
        nav_layout = QVBoxLayout(nav_shell)
        nav_layout.setContentsMargins(0, 18, 0, 0)
        nav_layout.setSpacing(6)
        sections = [
            (
                "CRM Operasyonları",
                [
                    ("dashboard", "📊", "Dashboard"),
                    ("contacts", "👥", "Müşteriler"),
                    ("pipeline", "🔄", "Pipeline"),
                    ("calls", "📞", "Görüşmeler"),
                ],
            ),
            (
                "Takip Araçları",
                [
                    ("calendar", "📅", "Takvim"),
                    ("tasks", "✅", "Görevler"),
                    ("mail", "✉️", "Mail"),
                    ("files", "📁", "Dosyalar"),
                ],
            ),
            (
                "Akıllı Panel",
                [
                    ("ai", "🤖", "AI Koç"),
                    ("reports", "📈", "Raporlar"),
                    ("team", "🧑", "Ekip"),
                ],
            ),
        ]
        for section_index, (section_name, items) in enumerate(sections):
            visible_items = [item for item in items if self.can_view(item[0])]
            if not visible_items:
                continue
            if section_index:
                nav_layout.addSpacing(10)
            label = QLabel(section_name)
            label.setObjectName("SidebarSectionTitle")
            nav_layout.addWidget(label)

            for key, icon, title in visible_items:
                button = QPushButton(f"{icon}  {title}")
                button.setObjectName("NavButton")
                button.setCursor(Qt.PointingHandCursor)
                button.setProperty("active", False)
                button.clicked.connect(lambda _=False, view=key: self.switch_view(view))
                button.style().unpolish(button)
                button.style().polish(button)
                nav_layout.addWidget(button)
                self.nav_buttons[key] = button
        layout.addWidget(nav_shell)

        layout.addStretch(1)
        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 14, 14, 14)
        footer_layout.setSpacing(10)
        footer_layout.addWidget(AvatarLabel(initials(self.current_user["full_name"]), role_accent_color(self.current_user["role"]), 36))
        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(2)
        user_name = QLabel(self.current_user["full_name"])
        user_name.setObjectName("SidebarUserName")
        user_role = QLabel(self.current_user["role"])
        user_role.setObjectName("SidebarUserRole")
        info.addWidget(user_name)
        info.addWidget(user_role)
        footer_layout.addLayout(info, 1)
        self.theme_button = make_button("☀️ Açık" if self.is_dark_mode else "🌙 Koyu", self.toggle_theme, "segment", flat=True)
        self.theme_button.setToolTip("Temayı Değiştir")
        footer_layout.addWidget(self.theme_button)
        layout.addWidget(footer)
        return sidebar

    def toggle_theme(self):
        # Açık/koyu tema geçişinde global stil ve sayfa bileşenleri yenilenir.
        self.is_dark_mode = not self.is_dark_mode
        apply_theme(self.is_dark_mode)
        from PyQt5.QtWidgets import QApplication
        qApp = QApplication.instance()
        qApp.setStyleSheet(get_app_style(self.is_dark_mode))
        
        # Sidebar Yeniden Yükle
        new_sidebar = self._build_sidebar()
        self.centralWidget().layout().replaceWidget(self.sidebar, new_sidebar)
        self.sidebar.setParent(None)
        self.sidebar.deleteLater()
        self.sidebar = new_sidebar
        
        # Header Yeniden Yükle
        new_header = self._build_header()
        self.main_area.layout().replaceWidget(self.header, new_header)
        self.header.setParent(None)
        self.header.deleteLater()
        self.header = new_header
        
        if hasattr(self, "current_view_name"):
            for name, button in self.nav_buttons.items():
                button.setProperty("active", name == self.current_view_name)
                button.style().unpolish(button)
                button.style().polish(button)
                
        # Sayfaları Sıfırdan Yükle (Statik CSS'lerin güncellenmesi için)
        old_stack = self.stack
        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        
        self.pages = {
            "dashboard": DashboardPage(self),
            "contacts": ContactsPage(self),
            "pipeline": PipelinePage(self),
            "calls": CallsPage(self),
            "calendar": CalendarPage(self),
            "mail": MailPage(self),
            "tasks": TasksPage(self),
            "files": FilesPage(self),
            "ai": AIPage(self),
            "reports": ReportsPage(self),
            "team": TeamPage(self),
        }
        
        for name in self.VIEW_TITLES:
            self.stack.addWidget(self.pages[name])
            
        self.stack_shell.layout().replaceWidget(old_stack, self.stack)
        old_stack.setParent(None)
        old_stack.deleteLater()
        
        # Kaldığımız sayfaya geri dön; rol erişimi değişmişse güvenli ilk ekrana düş.
        if hasattr(self, "current_view_name"):
            target_view = self.current_view_name if self.can_view(self.current_view_name) else self.first_accessible_view()
            self.current_view_name = target_view
            self.stack.setCurrentWidget(self.pages[target_view])
            for name, button in self.nav_buttons.items():
                button.setProperty("active", name == target_view)
                button.style().unpolish(button)
                button.style().polish(button)
            if hasattr(self.pages[target_view], "refresh"):
                self.pages[target_view].refresh()


    def _build_header(self):
        # Üst arama, bildirim, ayarlar ve hızlı ekle alanını oluşturur.
        header = QFrame()
        header.setObjectName("Header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 14, 24, 14)
        layout.setSpacing(14)

        search_shell = QFrame()
        search_shell.setObjectName("SearchShell")
        search_layout = QHBoxLayout(search_shell)
        search_layout.setContentsMargins(16, 0, 16, 0)
        search_layout.setSpacing(10)
        search_label = QLabel("Ara")
        search_label.setStyleSheet(f"color: {COLORS['slate_500']}; font-size: 12px; font-weight: 700;")
        self.search_input = QLineEdit()
        self.search_input.setObjectName("SearchInput")
        self.search_input.setPlaceholderText("Musteri, gorev, firsat veya dosya ara...")
        self.search_input.setMinimumWidth(320)
        self.search_input.returnPressed.connect(self.open_search)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)
        layout.addWidget(search_shell, 2)

        date_pill = QLabel(format_full_date(date.today()))
        date_pill.setObjectName("HeaderMetaPill")
        role_pill = QLabel(self.current_user["role"])
        role_pill.setObjectName("HeaderMetaPill")
        layout.addWidget(date_pill)
        layout.addWidget(role_pill)
        notif_button = QPushButton("🔔 Bildirimler")
        style_button(notif_button, "header")
        notif_button.clicked.connect(self.open_notifications)
        settings_button = QPushButton("⚙️ Ayarlar")
        style_button(settings_button, "header")
        settings_button.clicked.connect(self.open_settings_dialog)
        logout_button = QPushButton("Çıkış Yap")
        style_button(logout_button, "danger")
        logout_button.setCursor(Qt.PointingHandCursor)
        logout_button.setToolTip("Oturumu kapatıp giriş ekranına dön")
        logout_button.clicked.connect(self.logout)
        quick_button = QToolButton()
        quick_button.setText("Hızlı Ekle")
        style_button(quick_button, "primary")
        quick_button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(quick_button)
        quick_actions = [
            ("contact_create", "Müşteri", self.open_contact_dialog),
            ("opportunity_create", "Fırsat", self.open_opportunity_dialog),
            ("call_create", "Görüşme", self.open_call_dialog),
            ("task_create", "Görev", self.open_task_dialog),
            ("mail_compose", "Mail", lambda: self.compose_mail_for_contact(None)),
            ("file_upload", "Dosya", self.upload_file),
        ]
        for permission, label, callback in quick_actions:
            if self.can(permission):
                menu.addAction(label, callback)
        quick_button.setMenu(menu)
        quick_button.setVisible(bool(menu.actions()))
        layout.addWidget(notif_button)
        layout.addWidget(settings_button)
        layout.addWidget(logout_button)
        layout.addWidget(quick_button)
        layout.addWidget(AvatarLabel(initials(self.current_user["full_name"]), role_accent_color(self.current_user["role"]), 38))
        return header

    def _refresh_sidebar_summary(self):
        # Sidebar'daki özet alanları için güvenli yenileme noktası.
        try:
            self.db.get_dashboard_summary()
        except Exception:
            pass

    def switch_view(self, view_name: str):
        # Sidebar seçiminden ilgili sayfaya geçer ve fade animasyonu uygular.
        if view_name not in self.pages:
            return
        if not self.can_view(view_name):
            self.require_view(view_name)
            fallback = self.first_accessible_view()
            if fallback == view_name or fallback not in self.pages:
                return
            view_name = fallback
        if hasattr(self, "current_view_name") and self.current_view_name == view_name:
            self.refresh_current_page()
            return
            
        self.current_view_name = view_name
        widget = self.pages[view_name]
        self.stack.setCurrentWidget(widget)
        for name, button in self.nav_buttons.items():
            button.setProperty("active", name == view_name)
            button.style().unpolish(button)
            button.style().polish(button)
            
        # Animasyonlu Geçiş (Fade-in)
        self._fade_anim = None
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        self._fade_anim = QPropertyAnimation(effect, b"opacity")
        self._fade_anim.setDuration(250)
        self._fade_anim.setStartValue(0.1)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        self._fade_anim.start()
        
        self.refresh_current_page()

    def refresh_current_page(self):
        # Aktif sayfanın kullanıcı bilgisini ve görünümünü günceller.
        current = self.stack.currentWidget()
        if hasattr(current, "current_user"):
            current.current_user = self.current_user
        if hasattr(current, "refresh"):
            current.refresh()
        self._refresh_sidebar_summary()

    def refresh_all_views(self):
        # Veri değişince tüm sayfaları ve sidebar özetini yeniler.
        for page in self.pages.values():
            if hasattr(page, "current_user"):
                page.current_user = self.current_user
            if hasattr(page, "refresh"):
                page.refresh()
        self._refresh_sidebar_summary()

    def open_search(self):
        # Header global aramasını çalıştırır ve seçilen sonuca göre yönlendirir.
        term = self.search_input.text().strip()
        if len(term) < 2:
            QMessageBox.information(self, "Arama", "En az 2 karakter girin.")
            return
        results = self.db.global_search(term)
        if not self.can_view("contacts"):
            results["contacts"] = []
        if not self.can_view("pipeline"):
            results["opportunities"] = []
        if not self.can_view("tasks"):
            results["tasks"] = []
        if not self.can_view("files"):
            results["files"] = []
        dialog = SearchResultsDialog(results, self)
        if dialog.exec_() == QDialog.Accepted and dialog.selected_result:
            result = dialog.selected_result
            if result["kind"] == "contact":
                self.open_contact_detail(result["id"])
            elif result["kind"] == "opportunity":
                self.switch_view("pipeline")
            elif result["kind"] == "task":
                self.switch_view("tasks")
            elif result["kind"] == "file":
                self.switch_view("files")

    def open_notifications(self):
        # Sağ bildirim/aktivite çekmecesini açar.
        self.drawer.show_drawer()

    def logout(self):
        # Oturumu kapatıp ana uygulama akışından login ekranının yeniden açılmasını ister.
        reply = QMessageBox.question(
            self,
            "Çıkış Yap",
            "Oturumu kapatıp giriş ekranına dönmek istiyor musunuz?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.logout_requested.emit()

    def open_contact_detail(self, contact_id: int):
        # Müşteri ekranına geçip sağ detay panelinde ilgili müşteriyi açar.
        """Müşteri detayını açar — artık contacts listesinin slide panelinde."""
        if not self.require_view("contacts"):
            return
        self.current_contact_id = contact_id
        self.switch_view("contacts")
        contacts_page = self.pages["contacts"]
        contacts_page.detail_panel.db = self.db
        contacts_page.detail_panel.ai = self.ai
        contacts_page.detail_panel.current_user = self.current_user
        contacts_page.detail_panel.window_ref = self
        contacts_page.detail_panel.load_contact(contact_id)
        contacts_page.detail_panel.setVisible(True)

    def start_quick_call(self, contact_id: int):
        # Görüşmeler sayfasına geçip hızlı arama müşteri seçimini hazırlar.
        """Hızlı arama başlatmak için calls sayfasına geç ve müşteriyi seç."""
        if not self.require_permission("call_create", "Görüşme başlatma") or not self.require_view("calls"):
            return
        self.switch_view("calls")
        calls_page = self.pages["calls"]
        # ComboBox'ta müşteriyi seç
        for i in range(calls_page.quick_contact_combo.count()):
            if calls_page.quick_contact_combo.itemData(i) == contact_id:
                calls_page.quick_contact_combo.setCurrentIndex(i)
                break

    def open_contact_dialog(self, contact=None):
        # Müşteri ekleme/düzenleme dialogunu açar ve kayıt sonrası skorları yeniler.
        permission = "contact_edit" if contact else "contact_create"
        action = "Müşteri düzenleme" if contact else "Müşteri ekleme"
        if not self.require_permission(permission, action):
            return
        dialog = ContactDialog(self.db.list_users(), contact, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                contact_id = self.db.save_contact(data, contact_id=contact.get("id") if contact else None, actor_id=self.current_user["id"])
                self.current_contact_id = contact_id
                # AI skorlarını otomatik hesapla
                self.db.refresh_contact_scores(contact_id)
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Müşteri", f"Kayıt sırasında hata oluştu:\n{exc}")

    def delete_contact(self, contact_id: int):
        # Onay sonrası müşteri kaydını siler ve görünümü yeniler.
        if not self.require_permission("contact_delete", "Müşteri silme"):
            return
        if QMessageBox.question(self, "Sil", "Müşteri kaydını silmek istediğinize emin misiniz?") != QMessageBox.Yes:
            return
        self.db.delete_contact(contact_id)
        if self.current_contact_id == contact_id:
            self.current_contact_id = self._default_contact_id()
        # Panel kapansın
        contacts_page = self.pages["contacts"]
        contacts_page.detail_panel.setVisible(False)
        self.refresh_all_views()

    def open_opportunity_dialog(self, opportunity=None, prefill_contact_id=None):
        # Fırsat ekleme/düzenleme dialogunu açar ve bağlı müşteri skorunu günceller.
        permission = "opportunity_edit" if opportunity else "opportunity_create"
        action = "Fırsat düzenleme" if opportunity else "Fırsat ekleme"
        if not self.require_permission(permission, action):
            return
        contacts = self.db.list_contacts(sort_by="AI Skor")
        users = self.db.list_users()
        dialog = OpportunityDialog(contacts, users, opportunity, self)
        if prefill_contact_id and not opportunity:
            from .dialogs import select_combo_value
            select_combo_value(dialog.contact, prefill_contact_id)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_opportunity(data, opportunity_id=opportunity.get("id") if opportunity else None, actor_id=self.current_user["id"])
                # İlgili müşterinin AI skorlarını güncelle
                if data.get("contact_id"):
                    self.db.refresh_contact_scores(data["contact_id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Fırsat", f"Kayıt sırasında hata oluştu:\n{exc}")

    def move_opportunity(self, opportunity_id: int, direction: int):
        # Fırsatı pipeline aşamasında ileri/geri taşır.
        if not self.require_permission("opportunity_move", "Fırsat aşaması değiştirme"):
            return
        opp = self.db.get_opportunity(opportunity_id)
        self.db.move_opportunity(opportunity_id, direction)
        if opp and opp.get("contact_id"):
            self.db.refresh_contact_scores(opp["contact_id"])
        self.refresh_all_views()

    def delete_opportunity(self, opportunity_id: int):
        # Onay sonrası fırsatı siler ve müşteri skorunu yeniler.
        if not self.require_permission("opportunity_delete", "Fırsat silme"):
            return
        if QMessageBox.question(self, "Sil", "Fırsatı silmek istediğinize emin misiniz?") != QMessageBox.Yes:
            return
        opp = self.db.get_opportunity(opportunity_id)
        self.db.delete_opportunity(opportunity_id)
        if opp and opp.get("contact_id"):
            self.db.refresh_contact_scores(opp["contact_id"])
        self.refresh_all_views()

    def open_call_dialog(self, call=None):
        # Görüşme planlama/düzenleme dialogunu açar.
        permission = "call_edit" if call else "call_create"
        action = "Görüşme düzenleme" if call else "Görüşme planlama"
        if not self.require_permission(permission, action):
            return
        dialog = CallDialog(self.db.list_contacts(sort_by="AI Skor"), self.db.list_users(), call, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_call(data, call_id=call.get("id") if call else None, actor_id=self.current_user["id"])
                if data.get("contact_id"):
                    self.db.refresh_contact_scores(data["contact_id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Görüşme", f"Kayıt sırasında hata oluştu:\n{exc}")

    def plan_call_for_contact(self, contact_id: int):
        # Müşteri detayından tek müşteriye ön seçili görüşme planlar.
        if not self.require_permission("call_create", "Görüşme planlama"):
            return
        dialog = CallDialog(self.db.list_contacts(sort_by="AI Skor"), self.db.list_users(), None, self)
        from .dialogs import select_combo_value
        select_combo_value(dialog.contact, contact_id)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_call(data, actor_id=self.current_user["id"])
                self.db.refresh_contact_scores(contact_id)
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Görüşme", f"Kayıt sırasında hata oluştu:\n{exc}")

    def delete_call(self, call_id: int):
        # Görüşme kaydını siler ve bağlı müşteri skorlarını tazeler.
        if not self.require_permission("call_delete", "Görüşme silme"):
            return
        if QMessageBox.question(self, "Sil", "Görüşme kaydını silmek istediğinize emin misiniz?") != QMessageBox.Yes:
            return
        call = self.db.get_call(call_id)
        self.db.delete_call(call_id)
        if call and call.get("contact_id"):
            self.db.refresh_contact_scores(call["contact_id"])
        self.refresh_all_views()

    def open_task_dialog(self, task=None):
        # Görev ekleme/düzenleme dialogunu açar.
        permission = "task_edit" if task else "task_create"
        action = "Görev düzenleme" if task else "Görev ekleme"
        if not self.require_permission(permission, action):
            return
        dialog = TaskDialog(self.db.list_contacts(sort_by="AI Skor"), self.db.list_users(), task, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_task(data, task_id=task.get("id") if task else None, actor_id=self.current_user["id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Görev", f"Kayıt sırasında hata oluştu:\n{exc}")

    def toggle_task(self, task_id: int):
        # Görevin tamamlandı durumunu tersine çevirir.
        if not self.require_permission("task_toggle", "Görev tamamlama"):
            return
        self.db.toggle_task(task_id)
        self.refresh_all_views()

    def delete_task(self, task_id: int):
        # Onay sonrası görev kaydını siler.
        if not self.require_permission("task_delete", "Görev silme"):
            return
        if QMessageBox.question(self, "Sil", "Görevi silmek istiyor musunuz?") != QMessageBox.Yes:
            return
        self.db.delete_task(task_id)
        self.refresh_all_views()

    def compose_mail_for_contact(self, contact_id):
        # Seçili müşteriyle veya harici alıcıyla yeni mail kaydı oluşturur.
        if not self.require_permission("mail_compose", "Mail oluşturma"):
            return
        dialog = EmailDialog(self.db.list_contacts(sort_by="AI Skor"), self.db.list_mail_templates(), preselected_contact_id=contact_id, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_email(data, actor_id=self.current_user["id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Mail", f"Mail kaydedilirken hata oluştu:\n{exc}")

    def compose_mail_with_template(self, template_name: str):
        # Belirli şablon ön seçili şekilde mail oluşturur.
        if not self.require_permission("mail_template_use", "Mail şablonu kullanma"):
            return
        dialog = EmailDialog(self.db.list_contacts(sort_by="AI Skor"), self.db.list_mail_templates(), template_name=template_name, parent=self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_email(data, actor_id=self.current_user["id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Mail", f"Mail kaydedilirken hata oluştu:\n{exc}")

    def toggle_automation(self, key: str, enabled: bool):
        # Mail otomasyonunun açık/kapalı ayarını değiştirir.
        if not self.require_permission("mail_automation_manage", "Mail otomasyonu yönetme"):
            return
        self.db.set_automation_enabled(key, enabled)
        self.refresh_all_views()

    def upload_file(self):
        # Dosya seçimi, kategori ve müşteri eşleştirmesiyle upload akışını yönetir.
        if not self.require_permission("file_upload", "Dosya yükleme"):
            return
        source, _ = QFileDialog.getOpenFileName(self, "Dosya Seç")
        if not source:
            return
        contact_name_map = {f"{c['full_name']} - {c['company']}": c["id"] for c in self.db.list_contacts(sort_by="AI Skor")}
        contact_names = ["Genel"] + list(contact_name_map.keys())
        category_names = ["Teklif", "Belge", "Rapor"]
        from PyQt5.QtWidgets import QInputDialog
        category, ok = QInputDialog.getItem(self, "Dosya Türü", "Kategori", category_names, 0, False)
        if not ok:
            return
        contact_label, ok = QInputDialog.getItem(self, "İlgili Müşteri", "Müşteri", contact_names, 0, False)
        if not ok:
            return
        try:
            self.db.upload_file(source, contact_name_map.get(contact_label), category, uploaded_by=self.current_user["id"])
            self.refresh_all_views()
        except Exception as exc:
            QMessageBox.warning(self, "Dosya", f"Dosya yüklenirken hata oluştu:\n{exc}")

    def open_file(self, file_id: int):
        # Yüklü dosyayı işletim sisteminin varsayılan uygulamasıyla açar.
        if not self.require_permission("file_open", "Dosya açma"):
            return
        path = self.db.get_file_path(file_id)
        if not path:
            QMessageBox.warning(self, "Dosya", "Dosya yolu bulunamadı.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def export_file(self, file_id: int):
        # CRM'deki dosyayı kullanıcının seçtiği konuma kopyalar.
        if not self.require_permission("file_export", "Dosya dışa aktarma"):
            return
        path = self.db.get_file_path(file_id)
        if not path:
            QMessageBox.warning(self, "Dışa Aktar", "Dosya bulunamadı.")
            return
        target, _ = QFileDialog.getSaveFileName(self, "Dışa Aktar", path.name)
        if not target:
            return
        shutil.copy2(str(path), target)
        QMessageBox.information(self, "Dışa Aktar", "Dosya başarıyla dışa aktarıldı.")

    def delete_file(self, file_id: int):
        # Dosya kaydını ve varsa fiziksel dosyayı siler.
        if not self.require_permission("file_delete", "Dosya silme"):
            return
        if QMessageBox.question(self, "Sil", "Dosya kaydını silmek istediğinize emin misiniz?") != QMessageBox.Yes:
            return
        self.db.delete_file(file_id)
        self.refresh_all_views()

    def open_user_dialog(self, user=None):
        # Yetkili roller için kullanıcı ekleme/düzenleme dialogunu açar.
        if not self.require_permission("team_manage", "Kullanıcı yönetimi"):
            return
        dialog = UserDialog(user, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.save_user(data, user_id=user.get("id") if user else None, actor_id=self.current_user["id"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Kullanıcı", f"Kayıt sırasında hata oluştu:\n{exc}")

    def delete_user_confirm(self, user: Dict[str, Any]):
        # Kullanıcı silme işlemini sadece Süper Admin için onaylı şekilde yapar.
        if not self.require_permission("team_delete", "Kullanıcı silme"):
            return
        
        reply = QMessageBox.warning(
            self,
            "Kullanıcıyı Sil",
            f"{user['full_name']} ({user['role']}) kullanıcısını silmek istediğinize emin misiniz?\n\nBu işlem geri alınamaz.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return
        
        try:
            ok, msg = self.db.delete_user(user["id"])
            if ok:
                QMessageBox.information(self, "Başarı", msg)
                self.refresh_all_views()
            else:
                QMessageBox.warning(self, "Hata", msg)
        except Exception as exc:
            QMessageBox.warning(self, "Hata", f"Silme işlemi başarısız oldu:\n{exc}")

    def add_note_to_contact(self, contact_id: int):
        # Müşteri detayına yeni not ekler.
        if not self.require_permission("contact_note_create", "Müşteri notu ekleme"):
            return
        dialog = NoteDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return
            try:
                self.db.add_contact_note(contact_id, self.current_user["id"], data["title"], data["content"])
                self.refresh_all_views()
            except Exception as exc:
                QMessageBox.warning(self, "Not", f"Not kaydı sırasında hata oluştu:\n{exc}")

    def open_ai_settings_dialog(self):
        # AI key/model ayarları için küçük ayar penceresini açar.
        if not self.require_permission("ai_settings_manage", "AI ayarları yönetme"):
            return
        settings = {
            "ai_api_key": self.db.get_setting("ai_api_key"),
            "ai_model": self.db.get_setting("ai_model", "openrouter/free"),
        }
        from .dialogs import AISettingsDialog
        dialog = AISettingsDialog(settings, self)
        if dialog.exec_() == QDialog.Accepted:
            for key, value in dialog.get_ai_payload().items():
                self.db.set_setting(key, value)
            self.ai.reload_settings()
            QMessageBox.information(self, "Ayarlar", "AI ayarları başarıyla güncellendi.")

    def open_settings_dialog(self):
        # Profil, şifre, SMTP ve AI ayarlarını tek pencerede yönetir.
        settings = {
            "smtp_host": self.db.get_setting("smtp_host"),
            "smtp_port": self.db.get_setting("smtp_port", "587"),
            "smtp_user": self.db.get_setting("smtp_user"),
            "smtp_sender": self.db.get_setting("smtp_sender"),
            "ai_api_key": self.db.get_setting("ai_api_key"),
            "ai_model": self.db.get_setting("ai_model", "openrouter/free"),
        }
        can_manage_system_settings = self.can("settings_system_manage")
        dialog = SettingsDialog(self.current_user, settings, self, allow_system_settings=can_manage_system_settings)
        if dialog.exec_() == QDialog.Accepted:
            profile = dialog.get_profile_payload()
            password_data = dialog.get_password_payload()
            if not profile["full_name"].strip() or not profile["email"].strip():
                QMessageBox.warning(self, "Ayarlar", "Profil alanlarında ad ve e-posta zorunludur.")
                return
            if any(password_data.values()):
                if not all(password_data.values()):
                    QMessageBox.warning(self, "Şifre", "Şifre değiştirmek için üç alanı da doldurmalısınız.")
                    return
                if password_data["new_password"] != password_data["confirm_password"]:
                    QMessageBox.warning(self, "Şifre", "Yeni şifre ile tekrar alanı uyuşmuyor.")
                    return
                if len(password_data["new_password"]) < 6:
                    QMessageBox.warning(self, "Şifre", "Yeni şifre en az 6 karakter olmalıdır.")
                    return
                success, message = self.db.change_password(self.current_user["id"], password_data["current_password"], password_data["new_password"])
                if not success:
                    QMessageBox.warning(self, "Şifre", message)
                    return
            updated_payload = {
                "full_name": profile["full_name"],
                "email": profile["email"],
                "phone": profile["phone"],
                "role": self.current_user["role"],
                "password": "",
                "is_active": bool(self.current_user["is_active"]),
            }
            try:
                self.db.save_user(updated_payload, user_id=self.current_user["id"], actor_id=self.current_user["id"])
            except Exception as exc:
                QMessageBox.warning(self, "Ayarlar", f"Profil kaydedilirken hata oluştu:\n{exc}")
                return
            if can_manage_system_settings:
                for key, value in dialog.get_smtp_payload().items():
                    self.db.set_setting(key, value)
                for key, value in dialog.get_ai_payload().items():
                    self.db.set_setting(key, value)
                self.ai.reload_settings()
            self.current_user = self.db.get_user(self.current_user["id"]) or self.current_user
            self.refresh_all_views()
            QMessageBox.information(self, "Ayarlar", "Ayarlar kaydedildi.")

    def open_whatsapp(self, phone: str):
        # Telefon numarasını wa.me formatına çevirip WhatsApp bağlantısı açar.
        cleaned = "".join(ch for ch in phone if ch.isdigit())
        if cleaned.startswith("0"):
            cleaned = f"90{cleaned[1:]}"
        if not cleaned:
            QMessageBox.warning(self, "WhatsApp", "Geçerli bir telefon numarası yok.")
            return
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{cleaned}"))

    def export_report_pdf(self):
        # Rapor verilerini temel bir PDF dosyasına yazar.
        if not self.require_permission("report_export", "Rapor dışa aktarma"):
            return
        report = self.db.get_reports_summary()
        target, _ = QFileDialog.getSaveFileName(self, "Raporu PDF Olarak Kaydet", "nexcrm-rapor.pdf", "PDF Files (*.pdf)")
        if not target:
            return
        writer = QPdfWriter(target)
        writer.setPageSizeMM(QSizeF(210, 297))
        writer.setResolution(120)
        painter = QPainter(writer)
        painter.setRenderHint(QPainter.Antialiasing)
        y = 80
        painter.setPen(Qt.black)
        painter.setFont(QApplication.font())
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(80, y, "NexCRM Pro Raporu")
        y += 50
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(80, y, f"Olusturma tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        y += 40
        metrics = [
            ("Toplam Satis", format_currency(report["total_sales"])),
            ("Yeni Musteri", str(report["new_customers"])),
            ("Kapanis Orani", f"%{report['close_rate']}"),
            ("Ortalama Siparis", format_currency(report["average_order"])),
        ]
        for label, value in metrics:
            painter.drawText(80, y, f"{label}: {value}")
            y += 30
        y += 20
        painter.drawText(80, y, "Ekip performansi")
        y += 24
        for user in report["team_performance"]:
            painter.drawText(100, y, f"{user['full_name']} - {format_currency(float(user['monthly_sales']))} - %{user['performance_percent']}")
            y += 24
        painter.end()
        QMessageBox.information(self, "PDF", "Rapor PDF olarak dışa aktarıldı.")
