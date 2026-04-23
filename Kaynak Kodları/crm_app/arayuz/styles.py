from __future__ import annotations

# Bu dosya uygulamanın tema paletlerini ve global Qt stylesheet kurallarını üretir.
# Sayfalar kendi özel stillerini kullanırken ana renkleri buradaki COLORS sözlüğünden alır.

# Uygulamanın açık tema renk paleti.
COLORS_LIGHT = {
    # ── Primary accent: Indigo ──
    "accent": "#6366f1",
    "accent_dark": "#4f46e5",
    "accent_light": "#eef2ff",
    # ── Ink (deep text) ──
    "ink": "#0f172a",
    "ink_soft": "#1e293b",
    # ── Neutral scale: cool slate ──
    "slate_50": "#f8fafc",
    "slate_100": "#f1f5f9",
    "slate_200": "#e2e8f0",
    "slate_300": "#cbd5e1",
    "slate_400": "#94a3b8",
    "slate_500": "#64748b",
    "slate_600": "#475569",
    "slate_700": "#334155",
    "slate_800": "#1e293b",
    "slate_900": "#0f172a",
    # ── Semantic: success ──
    "emerald": "#10b981",
    "emerald_light": "#d1fae5",
    # ── Semantic: warning ──
    "amber": "#f59e0b",
    "amber_light": "#fef3c7",
    # ── Semantic: danger ──
    "rose": "#f43f5e",
    "rose_light": "#ffe4e6",
    # ── Semantic: info / highlight ──
    "violet": "#8b5cf6",
    "violet_light": "#ede9fe",
    # ── Semantic: secondary accent ──
    "cyan": "#06b6d4",
    "cyan_light": "#cffafe",
    # ── Surfaces ──
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "outline": "#e2e8f0",
    "outline_soft": "#f1f5f9",
}

# Uygulamanın koyu tema renk paleti.
COLORS_DARK = {
    "accent": "#818cf8", # Elegant soft indigo for dark mode
    "accent_dark": "#6366f1",
    "accent_light": "rgba(129, 140, 248, 0.15)",
    
    "ink": "#ffffff",
    "ink_soft": "#f8fafc",
    
    "slate_50": "#09090b",
    "slate_100": "#18181b",
    "slate_200": "#27272a",
    "slate_300": "#3f3f46",
    "slate_400": "#52525b",
    "slate_500": "#a1a1aa",
    "slate_600": "#d4d4d8",
    "slate_700": "#e4e4e7",
    "slate_800": "#f4f4f5",
    "slate_900": "#ffffff",
    
    "emerald": "#34d399",
    "emerald_light": "rgba(52, 211, 153, 0.15)",
    "amber": "#fbbf24",
    "amber_light": "rgba(251, 191, 36, 0.15)",
    "rose": "#fb7185",
    "rose_light": "rgba(251, 113, 133, 0.15)",
    "violet": "#a78bfa",
    "violet_light": "rgba(167, 139, 250, 0.15)",
    "cyan": "#22d3ee",
    "cyan_light": "rgba(34, 211, 238, 0.15)",
    
    "surface": "#09090b",
    "surface_alt": "#18181b",
    "outline": "#27272a",
    "outline_soft": "#3f3f46",
}

# Aktif tema renkleri çalışma anında bu sözlük üzerinden okunur.
COLORS = COLORS_LIGHT.copy()

# Tema değişince global renk sözlüğünü tek noktadan günceller.
def apply_theme(is_dark: bool) -> None:
    theme = COLORS_DARK if is_dark else COLORS_LIGHT
    COLORS.clear()
    COLORS.update(theme)


# PyQt widgetlarının genel görünümünü belirleyen ana stylesheet'i üretir.
def get_app_style(is_dark: bool = False) -> str:
    # Tema tipine göre ana arka plan ve kart renkleri seçilir.
    # Use global COLORS since apply_theme logic handles contents
    # We can use QPalette logic and distinct CSS rules
    bg_gradient = (
        "stop:0 #050505, stop:0.48 #0a0a0b, stop:1 #121214" 
        if is_dark else
        "stop:0 #f0f0ff, stop:0.48 #f5f3ff, stop:1 #eef2ff"
    )
    
    sidebar_gradient = (
        "stop:0 #000000, stop:0.45 #050505, stop:1 #0a0a0b"
        if is_dark else
        "stop:0 #0f0a2a, stop:0.45 #1a1145, stop:1 #1e1b4b"
    )
    
    card_bg = "rgba(24, 24, 27, 230)" if is_dark else "rgba(255, 255, 255, 240)"
    panel_bg = "rgba(14, 14, 16, 230)" if is_dark else "rgba(241, 245, 249, 235)"
    row_bg = "rgba(39, 39, 42, 180)" if is_dark else "rgba(255, 255, 255, 236)"
    ghost_bg = "rgba(255, 255, 255, 0.06)" if is_dark else "rgba(255, 255, 255, 225)"
    scroll_handle_bg = "rgba(255, 255, 255, 40)" if is_dark else "rgba(157, 144, 130, 180)"
    
    return f"""
* {{
    outline: none; /* Removes all focus dotted lines */
}}

QWidget {{
    background: transparent;
    color: {COLORS['slate_700']};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    border: none;
}}

QFrame {{
    border: none;
}}

QWidget:disabled {{
    color: {COLORS['slate_400']};
}}

QLabel {{
    background: transparent;
    border: none;
}}

QMainWindow,
QWidget#WindowRoot {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        {bg_gradient}
    );
}}

QFrame#Sidebar {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        {sidebar_gradient}
    );
    border: none;
    border-radius: 32px;
}}

QWidget#MainArea,
QFrame#MainArea {{
    background: transparent;
}}

QFrame#MainStackShell {{
    background: {'rgba(255, 255, 255, 0.04)' if is_dark else 'rgba(255, 255, 255, 0.28)'};
    border: none;
    border-radius: 34px;
}}

QStackedWidget#MainStack {{
    background: transparent;
}}

QFrame#Header {{
    background: {card_bg};
    border: none;
    border-radius: 30px;
}}

QFrame#SearchShell {{
    background: {panel_bg};
    border: none;
    border-radius: 20px;
}}

QLabel#HeaderEyebrow {{
    color: {COLORS['accent']};
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}}

QLabel#HeaderMetaPill {{
    background: rgba(15, 118, 110, 26);
    color: {COLORS['accent_dark']};
    border: none;
    border-radius: 16px;
    padding: 8px 12px;
    font-size: 11px;
    font-weight: 700;
}}

QLabel#LogoName {{
    color: white;
    font-size: 20px;
    font-weight: 800;
}}

QLabel#LogoVersion {{
    color: rgba(255, 255, 255, 0.74);
    font-size: 11px;
    font-weight: 700;
    background: rgba(255, 255, 255, 0.1);
    border: none;
    border-radius: 14px;
    padding: 5px 10px;
}}

QFrame#SidebarAccentCard {{
    background: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 22px;
}}

QLabel#SidebarAccentCaption {{
    color: rgba(255, 255, 255, 0.62);
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
}}

QLabel#SidebarAccentValue {{
    color: white;
    font-size: 28px;
    font-weight: 800;
}}

QLabel#SidebarAccentNote {{
    color: rgba(255, 255, 255, 0.72);
    font-size: 12px;
}}

QFrame#NavGroup {{
    background: rgba(255, 255, 255, 0.065);
    border: none;
    border-radius: 22px;
}}

QLabel#SidebarSection {{
    color: rgba(255, 255, 255, 0.42);
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 6px 2px 0 6px;
}}

QLabel#SidebarSectionTitle {{
    color: rgba(255, 255, 255, 0.48);
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1.4px;
    text-transform: uppercase;
    padding: 10px 8px 6px 8px;
}}

QLabel#SidebarSectionCaption {{
    color: rgba(255, 255, 255, 0.42);
    font-size: 10px;
    font-weight: 700;
    padding-bottom: 3px;
}}

QLabel#SidebarSectionCount {{
    min-width: 24px;
    min-height: 22px;
    max-height: 22px;
    background: rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.72);
    border-radius: 11px;
    font-size: 10px;
    font-weight: 900;
}}

QPushButton#NavButton {{
    min-height: 46px;
    border: none;
    border-radius: 18px;
    padding: 0 18px;
    text-align: left;
    color: rgba(255, 255, 255, 0.8);
    background: transparent;
    font-family: "Segoe UI", "Segoe UI Emoji";
    font-size: 13px;
    font-weight: 800;
}}

QPushButton#NavButton:hover {{
    color: white;
    background: rgba(255, 255, 255, 0.1);
    padding-left: 22px;
}}

QPushButton#NavButton[active="true"] {{
    color: white;
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(99, 102, 241, 0.62),
        stop:0.52 rgba(139, 92, 246, 0.34),
        stop:1 rgba(255, 255, 255, 0.08)
    );
    border-left: 4px solid rgba(255, 255, 255, 0.82);
    padding-left: 14px;
}}

QFrame#SidebarFooter {{
    background: rgba(255, 255, 255, 0.08);
    border: none;
    border-radius: 22px;
}}

QLabel#SidebarUserName {{
    color: white;
    font-size: 13px;
    font-weight: 700;
}}

QLabel#SidebarUserRole {{
    color: rgba(255, 255, 255, 0.56);
    font-size: 11px;
}}

QLabel#PageTitle {{
    color: {COLORS['slate_900']};
    font-size: 24px;
    font-weight: 800;
}}

QLabel#PageSubtitle {{
    color: {COLORS['slate_500']};
    font-size: 12px;
}}

QLabel#SectionTitle {{
    color: {COLORS['slate_900']};
    font-size: 24px;
    font-weight: 800;
}}

QLabel#SectionSubtitle {{
    color: {COLORS['slate_500']};
    font-size: 12px;
}}

QLabel#CardTitle {{
    color: {COLORS['slate_900']};
    font-size: 15px;
    font-weight: 800;
}}

QLabel#CardSubtitle {{
    color: {COLORS['slate_500']};
    font-size: 12px;
}}

QLineEdit#SearchInput,
QLineEdit#DialogInput,
QTextEdit#DialogInput,
QPlainTextEdit#DialogInput,
QComboBox#DialogInput,
QDateTimeEdit#DialogInput,
QDateEdit#DialogInput,
QSpinBox#DialogInput {{
    background: {ghost_bg};
    color: {COLORS['slate_900']};
    border: none;
    border-radius: 18px;
    padding: 11px 14px;
}}

QLineEdit#SearchInput {{
    background: {panel_bg};
}}

QLineEdit#SearchInput:focus,
QLineEdit#DialogInput:focus,
QTextEdit#DialogInput:focus,
QPlainTextEdit#DialogInput:focus,
QComboBox#DialogInput:focus,
QDateTimeEdit#DialogInput:focus,
QDateEdit#DialogInput:focus,
QSpinBox#DialogInput:focus {{
    background: {card_bg};
    border: none;
}}

QComboBox#DialogInput {{
    padding-right: 28px;
}}

QComboBox::drop-down {{
    border: none;
    background: transparent;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background: {card_bg};
    border: none;
    outline: none;
    border-radius: 14px;
    color: {COLORS['slate_900']};
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['slate_900']};
}}

QTextEdit,
QPlainTextEdit {{
    border-radius: 18px;
    border: none;
}}

QPushButton,
QToolButton {{
    min-height: 42px;
    border: none;
}}

QPushButton#PrimaryButton,
QToolButton#PrimaryAction {{
    background: {COLORS['accent']};
    color: white;
    border: none;
    border-radius: 18px;
    padding: 0 16px;
    font-weight: 800;
}}

QPushButton#PrimaryButton:hover,
QToolButton#PrimaryAction:hover {{
    background: {COLORS['accent_dark']};
}}

QPushButton#GhostButton,
QToolButton#GhostAction,
QPushButton#HeaderIcon {{
    background: {ghost_bg};
    color: {COLORS['slate_700']};
    border: none;
    border-radius: 18px;
    padding: 0 15px;
    font-weight: 700;
}}

QPushButton#GhostButton:hover,
QToolButton#GhostAction:hover,
QPushButton#HeaderIcon:hover {{
    color: {COLORS['accent']};
    background: {COLORS['accent_light']};
}}

QPushButton#DangerButton {{
    background: {COLORS['rose_light']};
    color: {COLORS['rose']};
    border: none;
    border-radius: 18px;
    padding: 0 15px;
    font-weight: 800;
}}

QPushButton#DangerButton:hover {{
    background: {COLORS['rose']};
    color: white;
}}

QPushButton#SuccessButton {{
    background: {COLORS['emerald_light']};
    color: {COLORS['emerald']};
    border: none;
    border-radius: 18px;
    padding: 0 15px;
    font-weight: 800;
}}

QPushButton#SuccessButton:hover {{
    background: {COLORS['emerald']};
    color: white;
}}

QPushButton#SegmentButton {{
    min-height: 38px;
    background: {'rgba(30, 41, 59, 180)' if is_dark else 'rgba(226, 232, 240, 180)'};
    color: {COLORS['slate_500']};
    border: none;
    border-radius: 16px;
    padding: 0 14px;
    font-weight: 800;
}}

QPushButton#SegmentButton:hover {{
    background: {COLORS['accent_light']};
    color: {COLORS['accent']};
}}

QPushButton#SegmentButton:checked {{
    background: {card_bg};
    color: {COLORS['slate_900']};
}}

QPushButton#OutcomeButton {{
    border-radius: 16px;
    padding: 0 18px;
    font-weight: 800;
    border: none;
}}

QPushButton#CallTypeIcon {{
    min-height: 44px;
    background: {'rgba(30, 41, 59, 190)' if is_dark else 'rgba(226, 232, 240, 190)'};
    border: none;
    border-radius: 18px;
    padding: 0 16px;
    color: {COLORS['slate_700']};
    font-weight: 700;
}}

QPushButton#CallTypeIcon:hover,
QPushButton#CallTypeIcon:checked {{
    background: {COLORS['accent_light']};
    color: {COLORS['accent_dark']};
}}

QFrame#Card,
QFrame#QuickCallPanel,
QFrame#PipelineCard,
QFrame#CallCard {{
    background: {card_bg};
    border: none;
    border-radius: 28px;
}}

QFrame#CallsCustomerRail {{
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 {'rgba(9, 9, 11, 0.95)' if is_dark else 'rgba(255, 255, 255, 0.95)'},
        stop: 0.58 {COLORS['accent_light']},
        stop: 1 {COLORS['violet_light']}
    );
    border: none;
    border-radius: 26px;
}}
QFrame#RailHero,
QFrame#RailCompactBubble {{
    background: {'rgba(9, 9, 11, 0.65)' if is_dark else 'rgba(255, 255, 255, 0.65)'};
    border: none;
    border-radius: 20px;
}}
QWidget#CustomerRailViewport,
QStackedWidget#CustomerRailStack {{
    background: transparent;
    border: none;
}}
QPushButton#CustomerRailToggle {{
    background: {'rgba(255, 255, 255, 0.1)' if is_dark else 'rgba(0, 0, 0, 0.05)'};
    color: {COLORS['slate_700']};
    border: none;
    border-radius: 14px;
    font-size: 15px;
    font-weight: 900;
}}
QPushButton#CustomerRailToggle:hover {{
    background: {COLORS['accent_light']};
    color: {COLORS['accent']};
}}
QLabel#RailTitle {{
    color: {COLORS['slate_900']};
    font-size: 20px;
    font-weight: 900;
}}
QLabel#RailListTitle {{
    color: {COLORS['slate_900']};
    font-size: 12px;
    font-weight: 800;
}}
QLabel#RailListHint {{
    color: {COLORS['slate_500']};
    font-size: 10px;
    font-weight: 700;
}}

QFrame#PipelineColumn {{
    background: {'rgba(30, 41, 59, 170)' if is_dark else 'rgba(255, 255, 255, 170)'};
    border: none;
    border-radius: 26px;
}}

QFrame#SlidePanel {{
    background: {card_bg};
    border: none;
    border-top-left-radius: 30px;
    border-bottom-left-radius: 30px;
}}

QFrame#SlidePanelOverlay {{
    background: rgba(13, 27, 40, 0.4);
}}

QFrame#DetailTab {{
    background: transparent;
    border: none;
}}

QTableWidget#DataTable {{
    background: {row_bg};
    border: none;
    border-radius: 24px;
    gridline-color: transparent;
    selection-background-color: {COLORS['accent_light']};
    selection-color: {COLORS['slate_900']};
}}

QTableWidget#DataTable::item {{
    padding: 12px 10px;
    border: none;
}}

QTableCornerButton::section {{
    background: transparent;
    border: none;
}}

QHeaderView::section {{
    background: transparent;
    color: {COLORS['slate_500']};
    padding: 14px 12px;
    border: none;
    font-size: 11px;
    font-weight: 800;
}}

QTreeWidget,
QListWidget {{
    background: {row_bg};
    border: none;
    border-radius: 22px;
    padding: 8px;
}}

QTreeWidget::item,
QListWidget::item {{
    padding: 9px 10px;
    border-radius: 12px;
}}

QTreeWidget::item:selected,
QListWidget::item:selected {{
    background: {COLORS['accent_light']};
    color: {COLORS['slate_900']};
}}

QProgressBar {{
    background: {COLORS['slate_100']};
    border: none;
    border-radius: 8px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
}}

QProgressBar::chunk {{
    background: {COLORS['accent']};
    border-radius: 8px;
}}

QTabWidget::pane {{
    border: none;
    background: transparent;
}}

QTabBar::tab {{
    background: {'rgba(255, 255, 255, 0.08)' if is_dark else 'rgba(15, 23, 42, 0.05)'};
    color: {COLORS['slate_500']};
    border-radius: 16px;
    padding: 8px 18px;
    margin-right: 8px;
    font-weight: 700;
}}

QTabBar::tab:hover {{
    background: {'rgba(255, 255, 255, 0.12)' if is_dark else 'rgba(15, 23, 42, 0.08)'};
    color: {COLORS['slate_700']};
}}

QTabBar::tab:selected {{
    background: {COLORS['accent']};
    color: white;
}}

QDialog {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:1,
        {bg_gradient}
    );
}}

QDialogButtonBox QPushButton {{
    min-height: 42px;
    border-radius: 18px;
    padding: 0 16px;
    font-weight: 800;
    background: {ghost_bg};
    border: none;
    color: {COLORS['slate_700']};
}}

QDialogButtonBox QPushButton:hover {{
    background: {COLORS['accent_light']};
    color: {COLORS['accent']};
}}

QDialogButtonBox QPushButton#PrimaryButton {{
    background: {COLORS['accent']};
    color: white;
    border: none;
}}

QDialogButtonBox QPushButton#PrimaryButton:hover {{
    background: {COLORS['accent_dark']};
}}

QDialogButtonBox QPushButton#GhostButton {{
    background: {ghost_bg};
    color: {COLORS['slate_700']};
    border: none;
}}

QCheckBox {{
    spacing: 8px;
    color: {COLORS['slate_600']};
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 6px;
    border: none;
    background: {ghost_bg};
}}

QCheckBox::indicator:checked {{
    background: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

QMenu {{
    background: {card_bg};
    color: {COLORS['slate_900']};
    border: none;
    border-radius: 18px;
    padding: 8px;
}}

QMenu::item {{
    color: {COLORS['slate_900']};
    background: transparent;
    padding: 9px 14px;
    border-radius: 12px;
}}

QMenu::item:selected {{
    background: {COLORS['accent_light']};
    color: {COLORS['accent_dark']};
}}

QMenu::item:disabled {{
    color: {COLORS['slate_400']};
}}

QToolTip {{
    background: {COLORS['slate_900']};
    color: {COLORS['slate_50']};
    border: none;
    padding: 8px 10px;
    border-radius: 10px;
}}

QScrollArea,
QAbstractScrollArea {{
    background: transparent;
    border: none;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 4px 0;
}}

QScrollBar::handle:vertical {{
    background: {scroll_handle_bg};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {COLORS['accent']};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}

QSplitter::handle {{
    background: transparent;
    border: none;
}}

QGroupBox {{
    border: none;
    margin-top: 1ex;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top center;
    padding: 0 3px;
}}
"""
