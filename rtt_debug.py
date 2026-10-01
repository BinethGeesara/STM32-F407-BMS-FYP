"""Standalone RTT attach diagnostic. Does NOT touch the GUI."""
import time
import pylink

DEVICE = "STM32F407VG"
SEARCH = "0x20000000 0x20000"

def banner(msg):
    print(f"\n=== {msg} ===")

banner("Opening J-Link")
j = pylink.JLink()
j.open()
print("firmware:", j.firmware_version)
print("s/n     :", j.serial_number)
j.set_tif(pylink.enums.JLinkInterfaces.SWD)

banner("connect() signature")
import inspect
try:
    print(inspect.signature(pylink.JLink.connect))
except Exception as e:
    print("could not introspect:", e)

banner("Attempt: plain connect (no reset)")
try:
    j.connect(DEVICE)
    print("connect() OK")
    print("target voltage:", j.hardware_version())
except Exception as e:
    print("connect() failed:", e)

banner("Check RTT BEFORE starting")
try:
    print("up buffers:", j.rtt_get_num_up_buffers())
except Exception as e:
    print("rtt_get_num_up_buffers raised:", e)

banner("Try SetRTTSearchRanges")
try:
    j.exec_command(f"SetRTTSearchRanges {SEARCH}")
    print("search range set")
except Exception as e:
    print("SetRTTSearchRanges failed:", e)

banner("rtt_start() attempt")
try:
    r = j.rtt_start()
    print("rtt_start returned:", r)
except Exception as e:
    print("rtt_start raised:", e)

banner("Poll for buffers, 20 seconds")
deadline = time.time() + 20
while time.time() < deadline:
    try:
        n = j.rtt_get_num_up_buffers()
    except Exception as e:
        n = f"err({e})"
    print(f"  t+{time.time() - (deadline - 20):5.1f}s  up_buffers={n}")
    if isinstance(n, int) and n > 0:
        print("  >>> FOUND RTT CONTROL BLOCK")
        break
    try:
        j.rtt_start()
    except Exception:
        pass
    time.sleep(1.0)

banner("Attempt halt + retry")
try:
    j.halt()
    print("halted")
    for _ in range(10):
        try:
            if j.rtt_get_num_up_buffers() > 0:
                print("found after halt")
                break
        except Exception:
            pass
        try:
            j.rtt_start()
        except Exception:
            pass
        time.sleep(0.5)
    j.go()
    print("resumed")
except Exception as e:
    print("halt path failed:", e)

banner("Final buffer count")
try:
    print("up buffers  :", j.rtt_get_num_up_buffers())
    print("down buffers:", j.rtt_get_num_down_buffers())
except Exception as e:
    print("final check raised:", e)

banner("Close")
try:
    j.rtt_stop()
except Exception:
    pass
j.close()
print("done")