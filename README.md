# STM32 Active Cell Balancing GUI , with F407 Firmware

Host GUI for the RTT command interface in `main.c`.

## Layout

The widgets now live in a real package. `dashboard.py` does `from widgets import ...`, which only works if `widgets/__init__.py` exists.

```text
stm32_gui/
├── main.py
├── dashboard.py
├── config.py
├── rtt_connection.py     # worker thread, owns every pylink call
├── rtt_controller.py     # command building + reply parsing
└── widgets/
    ├── __init__.py
    ├── connection_widget.py
    ├── cell_control_widget.py
    └── console_widget.py
```

Run with `python main.py` from inside `stm32_gui/`.

## Firmware behaviour the host has to work around

Commands must be paced. `StartTask03` ticks every 20 ms and does `RTT_ReadCommand()` then `process_rtt_command()`. `RTT_ReadCommand` drains every buffered character and overwrites `rtt_command` on each newline, but `process_rtt_command` handles one line per tick. Send four commands inside one tick and three of them vanish. The worker writes one command per 40 ms.

The target echoes your command back. `RTT_ReadCommand` calls `SEGGER_RTT_Write(0, &ch, 1)` for each accepted character and does not echo the newline, so the up-stream reads `S1MT=1OK: Cell1 MT ON`. Any parser testing `startswith("OK:")` fails. `_consume_echo` strips it, with a marker search as a backstop.

Down buffer 0 is 16 bytes in the stock `SEGGER_RTT_Conf.h`. Writes are chunked and the return value of `rtt_write` is honoured, so a partially accepted write is retried rather than truncated.

## Design notes

- All J-Link access is inside `RTTLink.run()`. The GUI thread sets flags and appends to a queue. Reconnect backoff is timed in that loop, not with a `QTimer` created on the wrong thread.
- `STATE:0x%04X` is the source of truth for the switch display. Clicking a button paints it dashed-amber (pending) until the target confirms.
- Bit layout, per `set_switch()`: 4 bits per cell, cell N at `(N-1)*4`, MT = +0, MB = +1, NEG = +2.
- `Q` is sent on connect so the UI matches the hardware rather than assuming.

## If it still won't connect

- RTT control block not found usually means `SEGGER_RTT_Init()` ran but the block sits outside the search range. Adjust `RTT_SEARCH_RANGES` in `config.py` (currently `0x20000000 0x20000`, the F405 SRAM).
- Close J-Link Commander, Ozone, or an STM32CubeIDE debug session first. The probe allows one host connection.
- Confirm `TARGET_DEVICE` matches your part.
