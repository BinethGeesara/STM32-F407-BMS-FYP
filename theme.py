# ---- Base surfaces ----
BG           = "#0B0D10"          # deeper charcoal
PANEL        = "#15181D"          # card base
PANEL_GLASS  = "qlineargradient(x1:0, y1:0, x2:0, y2:1," \
               " stop:0 #1B1F26, stop:1 #14171C)"
PANEL_SOLID  = "#1B1F26"          # flat fallback
BORDER       = "rgba(255,255,255,0.06)"
BORDER_HOVER = "rgba(255,255,255,0.16)"
INNER_DARK   = "#0E1116"
HAIRLINE     = "rgba(255,255,255,0.04)"

# ---- Text ----
TEXT         = "#F2F4F8"
TEXT_MUTED   = "#9AA3B0"
TEXT_DIM     = "#5C6470"

# ---- Accents (slightly saturated for premium feel) ----
ACCENT       = "#22D3EE"
ACCENT_ALT   = "#A78BFA"
SUCCESS      = "#34D399"
WARNING      = "#FBBF24"
ERROR        = "#F87171"
GOLD         = "#FBBF24"

# ---- Fonts ----
FONT_FAMILY  = "'Inter', 'SF Pro Display', 'Segoe UI', sans-serif"
FONT_MONO    = "'JetBrains Mono', 'SF Mono', 'Consolas', monospace"

# ---- Radii ----
RADIUS_CARD  = 14
RADIUS_PILL  = 999
RADIUS_INPUT = 8


def app_stylesheet() -> str:
    return f"""
        /* ---- Root defaults: colors + family ONLY, no font-size ---- */
        QWidget {{
            background: {BG};
            color: {TEXT};
            font-family: {FONT_FAMILY};
        }}
        QMainWindow {{ background: {BG}; }}

        /* ---- Baseline font size for "normal" widgets ---- */
        QLabel,
        QPushButton,
        QLineEdit,
        QPlainTextEdit,
        QSpinBox,
        QTabBar,
        QCheckBox,
        QGroupBox {{
            font-size: 13px;
        }}

        /* ---- Glass cards with a soft top highlight ---- */
        QFrame#GlassCard, QGroupBox#GlassCard {{
            background: {PANEL_GLASS};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_CARD}px;
        }}

        /* ---- Text hierarchy ---- */
        QLabel#Heading {{
            color: {TEXT_MUTED};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 2px;
        }}
        QLabel#Title {{
            color: {TEXT};
            font-size: 16px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        QLabel#Body  {{ color: {TEXT}; font-size: 13px; }}
        QLabel#Muted {{ color: {TEXT_MUTED}; font-size: 12px; }}
        QLabel#Value {{ color: {TEXT}; font-size: 22px; font-weight: 700; }}
        QLabel#Badge {{
            background: {PANEL};
            color: {TEXT};
            border-radius: {RADIUS_PILL}px;
            padding: 6px 12px;
            font-size: 13px;
        }}

        /* ---- Pill buttons ---- */
        QPushButton#Pill {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #20242B, stop:1 #171A20);
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_PILL}px;
            padding: 9px 20px;
            font-size: 12px;
            font-weight: 600;
        }}
        QPushButton#Pill:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #2A2F38, stop:1 #1D2128);
            border-color: {BORDER_HOVER};
        }}
        QPushButton#Pill:pressed {{ background: {ACCENT}; color: #05080B; }}
        QPushButton#Pill:disabled {{ color: {TEXT_DIM}; border-color: {BORDER}; }}

        /* ---- Tabs ---- */
        QTabBar::tab {{
            background: transparent;
            color: {TEXT_DIM};
            padding: 9px 18px;
            margin-right: 4px;
            border: none;
            border-radius: {RADIUS_PILL}px;
            font-size: 12px;
            font-weight: 600;
        }}
        QTabBar::tab:selected {{
            background: {PANEL_SOLID};
            color: {TEXT};
            border: 1px solid {BORDER};
        }}
        QTabBar::tab:hover:!selected {{ color: {TEXT_MUTED}; }}

        /* ---- Sliders ---- */
        QSlider::groove:horizontal {{
            height: 6px; background: {INNER_DARK}; border-radius: 3px;
        }}
        QSlider::handle:horizontal {{
            width: 18px; height: 18px; margin: -7px 0;
            background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                       stop:0 #FFFFFF, stop:0.4 {ACCENT}, stop:1 {ACCENT});
            border-radius: 9px;
            border: 2px solid {BG};
        }}
        QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}

        /* ---- Inputs ---- */
        QLineEdit, QSpinBox, QPlainTextEdit {{
            background: {INNER_DARK};
            color: {TEXT};
            border: 1px solid {BORDER};
            border-radius: {RADIUS_INPUT}px;
            padding: 8px 10px;
            selection-background-color: {ACCENT};
        }}
        QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {{
            border-color: {ACCENT};
        }}

        /* ---- Scrollbars ---- */
        QScrollBar:vertical {{ background: transparent; width: 8px; margin: 0; }}
        QScrollBar::handle:vertical {{
            background: {BORDER_HOVER}; border-radius: 4px; min-height: 30px;
        }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 8px; }}
        QScrollBar::handle:horizontal {{
            background: {BORDER_HOVER}; border-radius: 4px; min-width: 30px;
        }}
    """


def toggle_switch_qss(checked_color: str) -> str:
    """Bigger iOS-style toggle. Width 56, height 30."""
    return f"""
        QCheckBox {{ spacing: 0; }}
        QCheckBox::indicator {{
            width: 56px; height: 30px; border-radius: 15px;
            background: {INNER_DARK};
            border: 1px solid {BORDER};
        }}
        QCheckBox::indicator:hover {{ border-color: {BORDER_HOVER}; }}
        QCheckBox::indicator:checked {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {checked_color}, stop:1 {checked_color});
            border: 1px solid {checked_color};
        }}
    """