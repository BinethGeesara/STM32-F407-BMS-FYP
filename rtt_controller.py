"""Protocol layer - raw ADC values from the target."""
import re

from PyQt5.QtCore import QObject, pyqtSignal

from config import BITS_PER_CELL, CELL_COUNT, SWITCH_BITS, SWITCH_TYPES

STATE_RE = re.compile(r"STATE:\s*0x([0-9A-Fa-f]{1,4})")
CELL_RE  = re.compile(r"Cell(\d):\s*MT=(\d)\s*MB=(\d)\s*NEG=(\d)")

ADC_RE   = re.compile(r"^ADC:\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)")
TEMP_RE  = re.compile(r"^TEMP:\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)")
BQCELLS_RE = re.compile(r"^BQ_CELLS:\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)")
BQSTACK_RE = re.compile(r"^BQ_STACK:\s*(\d+)")
BQSUM_RE   = re.compile(r"^BQ_SUMCELLS:\s*(-?\d+)")
BQSTAT_RE  = re.compile(r"^BQ_BATTSTAT:\s*0x([0-9A-Fa-f]+)")
BQERR_RE   = re.compile(r"^BQ_ERR:")


def decode_state_word(word: int) -> dict:
    states = {}
    for cell in range(1, CELL_COUNT + 1):
        base = (cell - 1) * BITS_PER_CELL
        states[cell] = {
            sw: bool((word >> (base + SWITCH_BITS[sw])) & 1)
            for sw in SWITCH_TYPES
        }
    return states


class STM32Controller(QObject):
    """High-level control interface over an RTTLink."""

    state_changed   = pyqtSignal(dict)
    error_reported  = pyqtSignal(str)

    # ---- live data ----
    # ADC1: signed current in mA for the four channels [ch0, ch1, ch2, ch3]
    # (converted + filtered on the firmware from raw ADC counts)
    adc1_changed   = pyqtSignal(list)

    # ADC2: raw counts that represent the four cell temperatures
    #       (already converted to a display value in _counts_to_temp)
    cell_temps_changed = pyqtSignal(list)     # [t1, t2, t3, t4]

    # BQ76907 cell voltages (still used by the cell cards' ⚡ badges)
    cell_voltages_changed = pyqtSignal(list)  # [v1, v2, v3, v4] volts

    # Optional, kept for compatibility but no longer drives the chart
    stack_changed       = pyqtSignal(float)
    batt_status_changed = pyqtSignal(int)

    def __init__(self, link):
        super().__init__()
        self.link = link
        self._states = {
            cell: {sw: False for sw in SWITCH_TYPES}
            for cell in range(1, CELL_COUNT + 1)
        }
        self.link.line_received.connect(self.handle_line)

    # --------------------------------------------------------- commands ----

    def set_switch(self, cell, switch_type, state) -> bool:
        if not (1 <= cell <= CELL_COUNT) or switch_type not in SWITCH_TYPES:
            return False
        return self.link.send_command(f"S{cell}{switch_type}={1 if state else 0}")

    def set_cell_all(self, cell, state) -> bool:
        if not (1 <= cell <= CELL_COUNT):
            return False
        return self.link.send_command(f"A{cell}={1 if state else 0}")

    def all_off(self) -> bool:
        ok = True
        for cell in range(1, CELL_COUNT + 1):
            ok = self.set_cell_all(cell, False) and ok
        return ok

    def query_state(self) -> bool:
        return self.link.send_command("Q")

    def send_raw(self, command) -> bool:
        return self.link.send_command(command)

    # ---------------------------------------------------------- parsing ----

    def handle_line(self, line: str):
        # --- switch state (STATE:0xNNNN is authoritative) ---------------
        m = STATE_RE.search(line)
        if m:
            self._apply(decode_state_word(int(m.group(1), 16)))
            return

        m = CELL_RE.search(line)
        if m:
            cell = int(m.group(1))
            if cell in self._states:
                self._states[cell] = {
                    "MT":  m.group(2) == "1",
                    "MB":  m.group(3) == "1",
                    "NEG": m.group(4) == "1",
                }
                self.state_changed.emit(self.states)
            return

        # --- ADC1: raw counts, straight to the chart --------------------
        m = ADC_RE.match(line)
        if m:
            counts = [int(m.group(i)) for i in range(1, 5)]   # c0..c3
            self.adc1_changed.emit(counts)
            return

        # --- ADC2: raw counts that are the cell temperatures ------------
        m = TEMP_RE.match(line)
        if m:
            counts = [int(m.group(i)) for i in range(1, 5)]   # t1..t4
            self.cell_temps_changed.emit(counts)
            return

        # --- BQ76907 cell voltages -------------------------------------
        m = BQCELLS_RE.match(line)
        if m:
            mvs = [int(m.group(i)) for i in range(1, 5)]
            self.cell_voltages_changed.emit(mvs)      # was: [mv / 1000.0 for mv in mvs]
            return

        m = BQSTACK_RE.match(line)
        if m:
            self.stack_changed.emit(int(m.group(1)) / 1000.0)
            return

        m = BQSUM_RE.match(line)
        if m:
            self.stack_changed.emit(int(m.group(1)) / 1000.0)
            return

        m = BQSTAT_RE.match(line)
        if m:
            self.batt_status_changed.emit(int(m.group(1), 16))
            return

        if BQERR_RE.match(line):
            self.error_reported.emit(line)
            return

        if line.startswith("ERR"):
            self.error_reported.emit(line)

    def _apply(self, states: dict):
        if states != self._states:
            self._states = states
        self.state_changed.emit(self.states)

    def reset_local_state(self):
        for cell in self._states:
            for sw in self._states[cell]:
                self._states[cell][sw] = False
        self.state_changed.emit(self.states)

    @property
    def states(self):
        return {c: dict(s) for c, s in self._states.items()}

    def is_connected(self) -> bool:
        return self.link.is_connected()