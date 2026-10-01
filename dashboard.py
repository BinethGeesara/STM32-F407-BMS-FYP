"""Main window - top nav, two-column workspace."""
import time

from PyQt5.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QMainWindow, QScrollArea,
    QSizePolicy, QStackedWidget, QTabBar, QVBoxLayout, QWidget,
)
from PyQt5.QtCore import Qt, QTimer

from config import (
    BALANCE_PWM_DUTY, BALANCE_PWM_FREQ_HZ, BALANCE_SWITCHES,
    CELL_COUNT, COMMAND_INTERVAL_MS, SWITCH_TYPES,
    TARGET_DEVICE,
    LOG_DIR_ADC1, LOG_DIR_TEMP, LOG_DIR_VOLTAGE,
    LOG_ROTATE_ON_CONNECT,
)
from csv_logger import CSVLogger
from rtt_connection import RTTLink
from rtt_controller import STM32Controller
from theme import (
    BG, ERROR, SUCCESS, TEXT, TEXT_DIM, TEXT_MUTED, WARNING, app_stylesheet,
)
from widgets import (
    BalancingWidget,
    CellControlWidget,
    ConnectionWidget,
    ConsoleWidget,
    MonitoringWidget,
    PWMControlWidget,
)


# ------------------------------------------------------- command sequences

def _off_commands() -> list:
    """PWM duties 0 and PWM off first, then every switch off.

    The P=1 / P=0 pair is deliberate. The firmware's P=0 stops the timer but
    leaves the compare registers alone, and F<freq> restarts the outputs
    whatever P says. Enabling once with every duty already 0 forces the compare
    registers to 0, so nothing can come out of the PWM pins until the final
    P=1 of the start sequence.
    """
    cmds = [f"D{ch}=0" for ch in range(1, 5)]
    cmds += ["P=1", "P=0"]
    cmds += [f"A{c}=0" for c in range(1, CELL_COUNT + 1)]
    return cmds


def _balance_on_commands() -> list:
    """PWM setup (still disabled), the switches in order, PWM enable last."""
    cmds = [f"F{BALANCE_PWM_FREQ_HZ}"]
    cmds += [f"D{ch}={d}" for ch, d in sorted(BALANCE_PWM_DUTY.items())]
    cmds += [f"S{c}{sw}=1" for c, sw in BALANCE_SWITCHES]
    cmds.append("P=1")
    return cmds


def _all_off(states: dict) -> bool:
    return not any(any(sw.values()) for sw in states.values())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # ---- link + protocol ------------------------------------------
        self.link = RTTLink(TARGET_DEVICE)
        self.stm32 = STM32Controller(self.link)

        # ---- CSV loggers ----------------------------------------------
        self.log_adc1 = CSVLogger(
            LOG_DIR_ADC1, ["ch0_mA", "ch1_mA", "ch2_mA", "ch3_mA"], "adc1"
        )
        self.log_temp = CSVLogger(
            LOG_DIR_TEMP, ["t1", "t2", "t3", "t4"], "temp"
        )
        self.log_voltage = CSVLogger(
            LOG_DIR_VOLTAGE, ["v1_mv", "v2_mv", "v3_mv", "v4_mv"], "voltage"
        )
        self._session_t0 = time.monotonic()

        # ---- BQ76907 debug line ----------------------------------------
        self._bq_count = 0
        self._bq_last_t = None
        self._bq_last_mv = None
        self._bq_conn_t = time.monotonic()
        self._bq_err = False
        self._bq_dbg = ""
        self._bq_color = None
        self._bq_level = None      # last state written to the console log
        self._bq_timer = QTimer(self)
        self._bq_timer.timeout.connect(self._update_bq_debug)
        self._bq_timer.start(250)

        # ---- automatic balancing state ---------------------------------
        self._phase = "idle"        # idle | starting | running | stopping
        self._balance_verified = False
        self._balance_expected = self._expected_balance_states()
        self._phase_timer = QTimer(self)
        self._phase_timer.setSingleShot(True)
        self._phase_timer.timeout.connect(self._on_phase_timer)

        # ---- window ----------------------------------------------------
        self.setWindowTitle("STM32 Cell Switch Controller")
        self.setGeometry(80, 80, 1440, 900)
        self.setMinimumSize(1100, 720)

        self._build_ui()
        self._wire()

        self._set_controls_enabled(False)

        self.link.start()
        QTimer.singleShot(300, self.link.request_connect)

    # ------------------------------------------------------------------- UI

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 20)
        root.setSpacing(16)

        # ---- top navigation bar ----------------------------------------
        nav = QHBoxLayout()
        self.nav_tabs = QTabBar()
        self.nav_tabs.addTab("Main Controls")
        self.nav_tabs.addTab("Console")
        self.nav_tabs.currentChanged.connect(self._on_nav_changed)
        nav.addWidget(self.nav_tabs)
        nav.addStretch()
        root.addLayout(nav)

        # ---- main stacked area ------------------------------------------
        self.stack = QStackedWidget()
        self.stack.addWidget(self._build_main_page())
        self.stack.addWidget(self._build_console_page())
        root.addWidget(self.stack, 1)

    def _build_main_page(self) -> QWidget:
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # ---- LEFT column ----------------------------------------------
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.connection_widget = ConnectionWidget()
        left_layout.addWidget(self.connection_widget)

        self.sub_tabs = QTabBar()
        self.sub_tabs.addTab("Cells")
        self.sub_tabs.addTab("PWM Control")
        self.sub_tabs.addTab("Cell Balancing")
        self.sub_tabs.currentChanged.connect(self._on_subtab_changed)
        left_layout.addWidget(self.sub_tabs)

        self.sub_stack = QStackedWidget()

        self.cell_widget = CellControlWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(self.cell_widget)
        self.sub_stack.addWidget(scroll)

        self.pwm_widget = PWMControlWidget()
        self.sub_stack.addWidget(self.pwm_widget)

        self.balancing_widget = BalancingWidget()
        self.sub_stack.addWidget(self.balancing_widget)

        left_layout.addWidget(self.sub_stack, 1)

        # ---- RIGHT column ---------------------------------------------
        self.monitoring_widget = MonitoringWidget()

        layout.addWidget(left, 2)
        layout.addWidget(self.monitoring_widget, 3)
        return page

    def _build_console_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.console_widget = ConsoleWidget()

        self.status_label = QLabel("Starting up")
        self.status_label.setObjectName("Muted")
        self.status_label.setStyleSheet(
            f"background: rgba(255,255,255,0.03); padding: 10px 14px;"
            f"border-radius: 8px; color: {TEXT_MUTED};"
        )

        self.bq_debug = QLabel("BQ76907  \u00b7  not connected")
        self.bq_debug.setWordWrap(True)

        layout.addWidget(self.console_widget, 1)
        layout.addWidget(self.bq_debug)
        layout.addWidget(self.status_label)
        return page

    # -------------------------------------------------------------- wiring

    def _wire(self):
        # ---- connection ----------------------------------------------
        self.connection_widget.connect_clicked.connect(self._toggle_connection)
        self.connection_widget.sync_clicked.connect(self._sync_state)
        self.link.connection_status.connect(self._on_connection_status)
        self.link.reconnect_attempt.connect(
            self.connection_widget.set_reconnect_attempt
        )

        # ---- console / link ------------------------------------------
        self.link.line_received.connect(self.console_widget.append_response)
        self.link.line_received.connect(self._on_line_debug)
        self.link.command_written.connect(self.console_widget.append_command)
        self.console_widget.command_sent.connect(self._on_raw)

        # ---- controller -> UI ----------------------------------------
        self.stm32.state_changed.connect(self.cell_widget.apply_states)
        self.stm32.error_reported.connect(self._on_error)

        self.stm32.cell_voltages_changed.connect(
            self.cell_widget.apply_cell_voltages
        )
        self.stm32.cell_temps_changed.connect(
            self.cell_widget.apply_cell_temperatures
        )
        self.stm32.adc1_changed.connect(self.monitoring_widget.push_adc1)
        self.stm32.cell_voltages_changed.connect(self._on_bq_cells)

        # ---- controller -> CSV loggers -------------------------------
        self.stm32.adc1_changed.connect(self._log_adc1)
        self.stm32.cell_temps_changed.connect(self._log_temp)
        self.stm32.cell_voltages_changed.connect(self._log_voltage)

        # ---- cell -> controller --------------------------------------
        self.cell_widget.switch_command.connect(self._on_switch)
        self.cell_widget.all_off_command.connect(self._on_all_off)

        # ---- pwm -> controller ---------------------------------------
        self.pwm_widget.pwm_command.connect(self._on_raw)

        # ---- balancing -----------------------------------------
        self.balancing_widget.start_clicked.connect(self._start_balancing)
        self.balancing_widget.stop_clicked.connect(self._stop_balancing)
        self.stm32.state_changed.connect(self._on_state_for_balance)

    # ------------------------------------------------------------ actions

    def _on_nav_changed(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def _on_subtab_changed(self, idx: int):
        self.sub_stack.setCurrentIndex(idx)

    def _toggle_connection(self):
        if self.link.is_connected():
            delay_ms = self._shutdown_outputs()
            QTimer.singleShot(delay_ms, self.link.request_disconnect)
            self._status("Turning outputs off, then disconnecting", TEXT_MUTED)
        else:
            self.link.request_connect()

    def _sync_state(self):
        if self.stm32.query_state():
            self._status("Queried target state", TEXT_MUTED)

    def _on_connection_status(self, connected: bool, message: str):
        self.connection_widget.set_connected(connected, message)

        lost_while_on = False
        if not connected and self._phase != "idle":
            lost_while_on = self._phase in ("starting", "running")
            self._phase_timer.stop()
            self._phase = "idle"
            self.balancing_widget.set_phase("idle")

        self._set_controls_enabled(connected)
        self._status(message, SUCCESS if connected else ERROR)
        if lost_while_on:
            self.balancing_widget.set_status(
                "Link lost while balancing - the target may still have its "
                "switches / PWM ON", ERROR)

        if connected:
            self._bq_count = 0
            self._bq_last_t = None
            self._bq_err = False
            self._bq_dbg = ""
            self._bq_level = None
            self._bq_conn_t = time.monotonic()
            if LOG_ROTATE_ON_CONNECT:
                self._open_logs()
            self.stm32.reset_local_state()
            QTimer.singleShot(200, self.stm32.query_state)
        else:
            if LOG_ROTATE_ON_CONNECT:
                self._close_logs()
            self.stm32.reset_local_state()

    def _on_error(self, line: str):
        if line.startswith("BQ_ERR"):
            self._bq_err = True
        self._status(line, ERROR)
        self.console_widget.append_error(line)

    def _on_switch(self, cell: int, sw_type: str, state: bool):
        if self.stm32.set_switch(cell, sw_type, state):
            self._status(
                f"Cell {cell} {sw_type} → {'ON' if state else 'OFF'}", TEXT_MUTED
            )

    def _on_all_off(self):
        if self.stm32.all_off():
            self._status("Turning all cells off", TEXT_MUTED)

    def _on_raw(self, command: str):
        self.stm32.send_raw(command)

    def _set_controls_enabled(self, enabled: bool):
        # While auto balancing owns the outputs, the manual controls stay
        # locked (the console too, so a typed command can't bypass the lock).
        manual = enabled and self._phase == "idle"
        self.cell_widget.set_enabled(manual)
        self.console_widget.set_input_enabled(manual)
        self.pwm_widget.set_enabled(manual)
        self.balancing_widget.set_link_ready(enabled)

    def _status(self, text: str, color: str = TEXT_MUTED):
        self.status_label.setText(text)

    # ------------------------------------------------------- BQ76907 debug

    def _on_bq_cells(self, mvs: list):
        self._bq_count += 1
        self._bq_last_t = time.monotonic()
        self._bq_last_mv = list(mvs)
        self._bq_err = False

    def _on_line_debug(self, line: str):
        if line.startswith("BQ_DBG:"):
            self._bq_dbg = line[7:].strip()

    def _update_bq_debug(self):
        now = time.monotonic()
        level = None                       # only ok / nodata / stale get logged
        log = ""
        if not self.link.is_connected():
            text, color = "BQ76907  \u00b7  not connected", TEXT_DIM
        elif self._bq_last_t is None:
            waited = now - self._bq_conn_t
            if waited < 3.0:
                text, color = "BQ76907  \u00b7  waiting for first BQ_CELLS...", TEXT_MUTED
            else:
                text = (f"BQ76907  \u00b7  NO DATA  \u00b7  no BQ_CELLS line in "
                        f"{waited:.0f} s")
                if self._bq_err:
                    text += "  \u00b7  target reported BQ_ERR (I2C read failed)"
                color = ERROR
                level = "nodata"
                log = "BQ76907: NO DATA - no BQ_CELLS line received after 3 s"
        else:
            age = now - self._bq_last_t
            mv = " / ".join(str(v) for v in self._bq_last_mv)
            if age <= 2.0:
                text = (f"BQ76907  \u00b7  OK  \u00b7  {mv} mV  \u00b7  "
                        f"{age:.1f} s ago  \u00b7  #{self._bq_count}")
                color = SUCCESS
                level = "ok"
                log = f"BQ76907: voltages arriving ({mv} mV)"
            else:
                text = (f"BQ76907  \u00b7  STALE  \u00b7  last update {age:.0f} s ago"
                        f"  \u00b7  {mv} mV")
                color = ERROR
                level = "stale"
                log = "BQ76907: voltage data stopped arriving"
        if self._bq_dbg and color == ERROR:
            text += f"  \u00b7  {self._bq_dbg}"

        self.bq_debug.setText(text)
        if color != self._bq_color:
            self._bq_color = color
            self.bq_debug.setStyleSheet(
                f"background: rgba(255,255,255,0.03); padding: 8px 14px;"
                f"border-radius: 8px; color: {color}; font-size: 11px;"
                f"font-family: 'JetBrains Mono', 'Consolas', monospace;")

        # one line in the console log per state change, not one per tick
        if level is not None and level != self._bq_level:
            self._bq_level = level
            self.console_widget.append_note(log)

    # ------------------------------------------------------ auto balancing

    @staticmethod
    def _expected_balance_states() -> dict:
        states = {c: {sw: False for sw in SWITCH_TYPES}
                  for c in range(1, CELL_COUNT + 1)}
        for cell, sw in BALANCE_SWITCHES:
            states[cell][sw] = True
        return states

    def _send_all(self, cmds: list) -> bool:
        ok = True
        for cmd in cmds:
            ok = self.stm32.send_raw(cmd) and ok
        return ok

    def _start_balancing(self):
        if self._phase != "idle":
            return
        if not self.link.is_connected():
            self._status("Not connected", ERROR)
            return

        cmds = _off_commands() + _balance_on_commands() + ["Q"]
        self.link.clear_queue()
        if not self._send_all(cmds):
            self._status("Could not queue the balancing sequence", ERROR)
            return

        self._phase = "starting"
        self._balance_verified = False
        self.pwm_widget.apply_external(False, None, {ch: 0 for ch in range(1, 5)})
        self.balancing_widget.set_phase("starting")
        self.balancing_widget.set_status(
            "Turning everything off, then applying the balancing setup...",
            TEXT_MUTED)
        self._set_controls_enabled(True)          # locks Cells / PWM / console
        self._status("Automatic balancing: starting", TEXT_MUTED)
        self._phase_timer.start(len(cmds) * COMMAND_INTERVAL_MS + 300)

    def _stop_balancing(self):
        if self._phase in ("starting", "running") and self.link.is_connected():
            self._begin_stop()

    def _begin_stop(self) -> int:
        """Drop anything still queued, send the all-off sequence, and return
        how many ms it takes to drain."""
        cmds = _off_commands() + ["Q"]
        self.link.clear_queue()
        self._send_all(cmds)

        self._phase = "stopping"
        self._balance_verified = False
        self.pwm_widget.apply_external(False, None, {ch: 0 for ch in range(1, 5)})
        self.balancing_widget.set_phase("stopping")
        self.balancing_widget.set_status("Turning everything off...", TEXT_MUTED)
        self._set_controls_enabled(self.link.is_connected())
        self._status("Automatic balancing: stopping", TEXT_MUTED)

        ms = len(cmds) * COMMAND_INTERVAL_MS + 300
        self._phase_timer.start(ms)
        return ms

    def _shutdown_outputs(self) -> int:
        """Queue the safe-shutdown commands; return ms needed to drain them."""
        if self._phase != "idle":
            return self._begin_stop()
        self.stm32.all_off()
        return CELL_COUNT * COMMAND_INTERVAL_MS + 300

    def _on_phase_timer(self):
        if self._phase == "starting":
            self._phase = "running"
            self.pwm_widget.apply_external(
                True, BALANCE_PWM_FREQ_HZ, BALANCE_PWM_DUTY)
            self._refresh_balance_status()
            self._status("Automatic balancing: running", TEXT_MUTED)

        elif self._phase == "stopping":
            self._phase = "idle"
            self.balancing_widget.set_phase("idle")
            self._set_controls_enabled(self.link.is_connected())
            if _all_off(self.stm32.states):
                self.balancing_widget.set_status(
                    "Stopped - all switches off (confirmed), PWM off", SUCCESS)
            else:
                self.balancing_widget.set_status(
                    "Stopped - off commands sent, but the target has not "
                    "confirmed all switches off. Check the Cells tab.", WARNING)
            self._status("Automatic balancing: stopped", TEXT_MUTED)

    def _on_state_for_balance(self, states: dict):
        if self._phase in ("starting", "running"):
            self._balance_verified = (states == self._balance_expected)
            if self._phase == "running":
                self._refresh_balance_status()

    def _refresh_balance_status(self):
        if self._balance_verified:
            self.balancing_widget.set_status(
                "Running - switch states confirmed by the target", SUCCESS)
        else:
            self.balancing_widget.set_status(
                "Running - waiting for the target to confirm the switch states",
                WARNING)

    # ---------------------------------------------------------- logging

    def _open_logs(self):
        self._session_t0 = time.monotonic()
        self.log_adc1.open()
        self.log_temp.open()
        self.log_voltage.open()
        self.console_widget.append_note(
            f"Logging to {LOG_DIR_ADC1}, {LOG_DIR_TEMP}, {LOG_DIR_VOLTAGE}"
        )

    def _close_logs(self):
        self.log_adc1.close()
        self.log_temp.close()
        self.log_voltage.close()

    def _log_adc1(self, counts):
        self.log_adc1.write(counts, time.monotonic() - self._session_t0)

    def _log_temp(self, counts):
        self.log_temp.write(counts, time.monotonic() - self._session_t0)

    def _log_voltage(self, mvs):
        self.log_voltage.write(mvs, time.monotonic() - self._session_t0)

    # ------------------------------------------------------------ shutdown

    def closeEvent(self, event):
        if self.link.is_connected():
            # pending_commands() is only refreshed by the 1 Hz heartbeat, so
            # it can't be trusted here. Wait for the known drain time instead.
            flush_ms = self._shutdown_outputs()
            deadline = time.monotonic() + flush_ms / 1000.0
            while time.monotonic() < deadline:
                QApplication.processEvents()
                time.sleep(0.02)

        self._close_logs()
        self.link.shutdown()
        if not self.link.wait(3000):
            self.link.terminate()
            self.link.wait(500)
        event.accept()