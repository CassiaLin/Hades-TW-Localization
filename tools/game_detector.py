"""Steam Hades 1 installation path detector for Windows and cross-platform CLI."""

import json
import os
from pathlib import Path
from typing import Optional


COMMON_HADES_DIRS = [
    Path(r"D:\SteamLibrary\steamapps\common\Hades"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\Hades"),
    Path(r"C:\Program Files\Steam\steamapps\common\Hades"),
    Path(r"E:\SteamLibrary\steamapps\common\Hades"),
    Path(r"F:\SteamLibrary\steamapps\common\Hades"),
]


def is_valid_hades_dir(path: Path) -> bool:
    """Return True if path points to a valid Hades 1 installation root."""
    if not path or not path.exists() or not path.is_dir():
        return False
    return (path / "Content" / "Game" / "Text" / "Languages.sjson").is_file()


def _steam_library_folders() -> list[Path]:
    """Read Steam libraryfolders.vdf via Windows registry to discover custom library paths."""
    libs: list[Path] = []
    if os.name != "nt":
        return libs
    try:
        import re
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path_str, _ = winreg.QueryValueEx(key, "SteamPath")
        steam_path = Path(steam_path_str)
        libs.append(steam_path)
        vdf = steam_path / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            txt = vdf.read_text(encoding="utf-8", errors="ignore")
            for m in re.findall(r'"path"\s+"([^"]+)"', txt):
                libs.append(Path(m.replace("\\\\", "\\")))
    except OSError:
        pass
    return libs


def detect_hades_dir(
    cli_game_dir: Optional[str | Path] = None,
    config_path: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve the Hades 1 installation root directory, or None if not found."""
    candidates: list[Path] = []
    if cli_game_dir:
        candidates.append(Path(cli_game_dir))

    if config_path and config_path.is_file():
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(cfg, dict) and cfg.get("hades"):
                candidates.append(Path(cfg["hades"]))
        except (OSError, json.JSONDecodeError):
            pass

    env_dir = os.environ.get("HADES_GAME_DIR")
    if env_dir:
        candidates.append(Path(env_dir))

    for lib in _steam_library_folders():
        candidates.append(lib / "steamapps" / "common" / "Hades")

    candidates.extend(COMMON_HADES_DIRS)

    for cand in candidates:
        if is_valid_hades_dir(cand):
            return cand.resolve()
    return None
