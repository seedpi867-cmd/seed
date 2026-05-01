"""
Tool: shell_exec
Run a shell command in sandbox/. Returns stdout.
args: {"cmd": "command string"}
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SANDBOX = ROOT / "sandbox"

# Hard-blocked patterns — these can never be run, no exceptions.
# Protects the awake loop, services, SSH access, and the host OS.
BLOCKED = [
    # Self-destruction / service kill
    "systemctl stop", "systemctl disable", "systemctl kill",
    "systemctl mask", "systemctl reset-failed",
    "service seed", "killall python", "kill -9",
    "pkill -f awake", "pkill -f seed-brain",
    # Filesystem nukes
    "rm -rf /", "rm -rf ~", "rm -rf $HOME",
    "rm -rf /home", "rm -rf ./", "rm -fr /",
    "shred", "wipefs", "mkfs",
    # System control
    "reboot", "shutdown", "halt", "poweroff", "init 0", "init 6",
    "sudo reboot", "sudo shutdown", "sudo halt",
    # Privilege escalation / auth changes
    "sudo passwd", "passwd seed", "chpasswd",
    "visudo", "sudoers",
    "authorized_keys", "ssh-keygen -R",
    # Systemd / service file modification
    "/etc/systemd", "/lib/systemd", "/usr/lib/systemd",
    "seed-brain.service", "seed-brain-web.service",
    # Destructive disk ops
    "dd if=", "dd of=/dev",
    # Fork bomb / infinite loops
    ":(){ :|:& };", "fork bomb",
    # Package removal
    "apt remove", "apt purge", "apt autoremove",
    "pip uninstall", "pip3 uninstall",
    # Critical path writes via shell
    "/home/seed/seed-brain/loops/",
    "/home/seed/seed-brain/runtime/",
    "/home/seed/seed-brain/boot/",
    # Network reconfiguration — never touch WiFi or network stack
    "ip link set", "ifconfig down", "ifconfig wlan", "ifconfig eth",
    "iptables -F", "iptables --flush",
    "ufw disable", "ufw reset",
    "nmcli", "nmtui",
    "wpa_cli", "wpa_supplicant",
    "netplan apply", "netplan generate", "netplan try",
    "/etc/netplan", "/etc/wpa_supplicant", "/etc/network/interfaces",
    "network-config", "50-cloud-init.yaml",
    "iw dev", "iwconfig", "rfkill",
    # Cron wipe
    "crontab -r",
]


def _is_blocked(cmd: str) -> str | None:
    """Return the matched blocked pattern, or None if safe."""
    lower = cmd.lower()
    for pattern in BLOCKED:
        if pattern.lower() in lower:
            return pattern
    return None


def run(args: dict, task: dict = None, root: Path = None) -> tuple[bool, str]:
    cmd = (args.get("cmd") or args.get("command") or "").strip()
    if not cmd:
        return False, "No command provided"

    blocked_by = _is_blocked(cmd)
    if blocked_by:
        return False, f"HARD BLOCK — command contains '{blocked_by}'. This action is permanently forbidden to protect system integrity."

    SANDBOX.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=60, cwd=str(SANDBOX)
        )
        output = (result.stdout + result.stderr).strip()
        success = result.returncode == 0
        return success, output[:1000]
    except subprocess.TimeoutExpired:
        return False, "Command timed out (60s)"
    except Exception as e:
        return False, str(e)
