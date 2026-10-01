"""Configuration settings."""
# --------------------------------------------------------------- Logging ----
import os
from datetime import datetime

# Root folder for all CSV logs. Created automatically on startup.
LOG_ROOT = os.path.join(os.path.expanduser("~"), "STM32_Logs")

# One sub-folder per data type. Keeps things tidy when you have dozens of runs.
LOG_DIR_ADC1    = os.path.join(LOG_ROOT, "ADC1")
LOG_DIR_TEMP    = os.path.join(LOG_ROOT, "TEMP")
LOG_DIR_VOLTAGE = os.path.join(LOG_ROOT, "VOLTAGE")

# When True a new CSV file is opened every time the GUI connects.
# When False logging continues across reconnects until the app closes.
LOG_ROTATE_ON_CONNECT = True

# Flush to disk this often (rows). Smaller = safer, larger = faster.
LOG_FLUSH_EVERY = 20
# ---------------------------------------------------------------- J-Link ----
TARGET_DEVICE = "STM32F407VG"

RTT_UP_BUFFER = 0
RTT_DOWN_BUFFER = 0
RTT_DOWN_CHUNK = 128
READ_CHUNK = 2048
RTT_SEARCH_RANGES = "0x20000000 0x20000"
RTT_CHECK_TIMEOUT = 5.0

# ---------------------------------------------------------------- Timing ----
POLL_INTERVAL_MS = 10
COMMAND_INTERVAL_MS = 40
ECHO_TIMEOUT_S = 1.5

# ------------------------------------------------------------- Reconnect ----
AUTO_RECONNECT = True
RECONNECT_DELAY_MS = 1000
MAX_RECONNECT_DELAY_MS = 15000
MAX_RECONNECT_ATTEMPTS = 0

# ------------------------------------------------------------------ Cells ----
CELL_COUNT = 4
SWITCH_TYPES = ["MT", "MB", "NEG"]
SWITCH_LABELS = {
    "MT":  "Main Top",
    "MB":  "Main Bus (Pos)",
    "NEG": "Bus Negative",
}
SWITCH_BITS = {"MT": 0, "MB": 1, "NEG": 2}
BITS_PER_CELL = 4

# ---- Blueprint colours (one per cell) ----
CELL_COLORS = ["#FF4365", "#FFD700", "#39FF6A", "#00D9FF"]
CELL_COLOR_NAMES = ["Red", "Yellow", "Neon Green", "Cyan"]

# --------------------------------------------------------- Chart geometry ----
CHART_WINDOW = 600                # keep 600 samples (~10 min at 1 Hz)
CHART_POINTS = 300                # how many to draw

# ADC1 is converted on the firmware into signed current (mA) before it's
# sent over RTT. Y axis is auto-scaled in monitoring_widget.py; these are
# the fallback/clamp limits - set them to match your current sensor's
# range (this default assumes a +/-20 A sensor, e.g. ACS712-20A).
ADC_CURRENT_Y_MIN, ADC_CURRENT_Y_MAX = -20000.0, 20000.0

# ADC2 → temperature: raw counts. Just used for display formatting.
# If you have a real thermistor equation, apply it in rtt_controller.py.
TEMP_DISPLAY_MIN, TEMP_DISPLAY_MAX = 0.0, 100.0

# ---- ADC channel colours (four ADC1 channels) ----
ADC_CH_COLORS = ["#00D9FF", "#FFD700", "#39FF6A", "#FF4365"]
ADC_CH_LABELS = ["CH0", "CH1", "CH2", "CH3"]
# ---------------------------------------------------------- Host throttling ----
# The link process forwards at most one line per prefix per this many seconds.
# 0 = forward every line. TEMP is a slow signal, so cap it; ADC feeds the
# chart and is left alone.
TELEMETRY_MIN_INTERVAL_S = {
    "TEMP:": 0.25,
}

# ------------------------------------------------------ Auto balancing ----
# "Cell Balancing" tab. Start = everything OFF (PWM duties 0, PWM off, all
# switches off), lock the manual tabs, then apply the setup below.
BALANCE_TITLE = "Transferring from Cell 1 to Cell 3"

# Switches turned ON, in this order (cell, type). All others stay OFF.
BALANCE_SWITCHES = [(2, "MT"), (4, "NEG"), (2, "MB"), (3, "MB"), (3, "NEG")]

BALANCE_PWM_FREQ_HZ = 71000
BALANCE_PWM_DUTY = {1: 0, 2: 0, 3: 0, 4: 30}      # percent per channel