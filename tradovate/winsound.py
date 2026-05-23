import os
import threading


def Beep(frequency=1000, duration=100):
    """Simulate beep on macOS using terminal escape sequences."""
    try:
        print(f"\a", end="", flush=True)
    except:
        pass
