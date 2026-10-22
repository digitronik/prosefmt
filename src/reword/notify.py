"""Cross-platform desktop notifications.

Linux:   notify-send (libnotify)
macOS:   osascript
Windows: PowerShell toast
Fallback: stderr
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from reword.clipboard import Platform, detect_platform


def notify(title: str, body: str = "", urgency: str = "normal", timeout_ms: int = 3000) -> None:
    """Show a desktop notification (best-effort, never raises)."""
    plat = detect_platform()

    try:
        if plat in (Platform.LINUX_X11, Platform.LINUX_WAYLAND) and shutil.which("notify-send"):
            cmd = [
                "notify-send",
                "-u",
                urgency,
                "-t",
                str(timeout_ms),
                "-h",
                "string:x-dunst-stack-tag:reword",
                title,
            ]
            if body:
                cmd.append(body)
            subprocess.run(cmd, check=False, capture_output=True)

        elif plat == Platform.MACOS:
            script = f'display notification "{_esc(body)}" with title "{_esc(title)}"'
            subprocess.run(["osascript", "-e", script], check=False, capture_output=True)

        elif plat == Platform.WINDOWS:
            ps = (
                "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                "ContentType = WindowsRuntime] > $null; "
                f'$xml = "<toast><visual><binding template=\\"ToastText02\\"><text id=\\"1\\">'
                f'{_esc(title)}</text><text id=\\"2\\">{_esc(body)}</text>'
                '</binding></visual></toast>"; '
                "$t = New-Object Windows.Data.Xml.Dom.XmlDocument; $t.LoadXml($xml); "
                "[Windows.UI.Notifications.ToastNotificationManager]::"
                'CreateToastNotifier("Reword").Show('
                "[Windows.UI.Notifications.ToastNotification]::new($t))"
            )
            subprocess.run(["powershell.exe", "-Command", ps], check=False, capture_output=True)

        else:
            _stderr_fallback(title, body)

    except Exception:
        _stderr_fallback(title, body)


def _esc(s: str) -> str:
    return s.replace('"', '\\"').replace("\n", " ")


def _stderr_fallback(title: str, body: str) -> None:
    msg = f"[reword] {title}"
    if body:
        msg += f": {body}"
    print(msg, file=sys.stderr)
