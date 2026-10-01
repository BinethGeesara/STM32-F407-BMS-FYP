"""Thread-safe CSV logger for live RTT streams.

One instance per data type. The logger keeps its own file handle and buffer;
writes happen on the GUI thread (all signals come from STM32Controller which
lives on the GUI thread) so no locking is strictly required, but we use a
QLock anyway for safety if you ever move to a worker thread.
"""
import csv
import os
from datetime import datetime
from threading import Lock

from config import LOG_FLUSH_EVERY


class CSVLogger:
    """Appends rows to a timestamped CSV. Rotate per session if requested."""

    def __init__(self, folder: str, columns: list, prefix: str):
        self.folder = folder
        self.columns = columns           # e.g. ["ch0", "ch1", "ch2", "ch3"]
        self.prefix = prefix             # e.g. "adc1"
        self._fh = None
        self._writer = None
        self._rows_since_flush = 0
        self._lock = Lock()
        self._path = ""
        self._enabled = True
        os.makedirs(folder, exist_ok=True)

    # ----------------------------------------------------------- public --

    @property
    def path(self) -> str:
        return self._path

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, on: bool):
        self._enabled = on

    def open(self):
        """Open a fresh file. Safe to call repeatedly."""
        with self._lock:
            self._close_locked()
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._path = os.path.join(self.folder, f"{self.prefix}_{ts}.csv")
            self._fh = open(self._path, "w", newline="")
            self._writer = csv.writer(self._fh)
            self._writer.writerow(["timestamp", "host_time"] + self.columns)
            self._rows_since_flush = 0

    def write(self, values: list, timestamp: float | None = None):
        """Append one row. `timestamp` is seconds since session start."""
        if not self._enabled or self._writer is None:
            return
        with self._lock:
            host = datetime.now().isoformat(timespec="milliseconds")
            ts = f"{timestamp:.4f}" if timestamp is not None else ""
            try:
                self._writer.writerow([ts, host] + [f"{v}" for v in values])
            except Exception:
                return
            self._rows_since_flush += 1
            if self._rows_since_flush >= LOG_FLUSH_EVERY:
                try:
                    self._fh.flush()
                except Exception:
                    pass
                self._rows_since_flush = 0

    def close(self):
        with self._lock:
            self._close_locked()

    # ----------------------------------------------------------- private --

    def _close_locked(self):
        if self._fh is not None:
            try:
                self._fh.flush()
                self._fh.close()
            except Exception:
                pass
        self._fh = None
        self._writer = None