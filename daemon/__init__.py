"""
TILLU Daemon Process
Always-watching ambient intelligence. Never stops. No scheduler dependency.
Lazy import — do not import DaemonProcess at module level to avoid
loading the full chain stack on import.
"""

__all__ = ["DaemonProcess"]


def __getattr__(name: str):
    if name == "DaemonProcess":
        from .core import DaemonProcess
        return DaemonProcess
    raise AttributeError(f"module 'daemon' has no attribute {name!r}")
