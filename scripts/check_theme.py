"""Fail when first-party source introduces a color, size, gradient, or blur outside theme/tokens.toml."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

SCAN_DIRS = ("api", "web", "worker", "scripts", "theme")
EXTENSIONS = {".py", ".ts", ".tsx", ".css", ".toml", ".mjs", ".js", ".json", ".yml", ".yaml", ".sh"}
SKIP_DIRS = {"node_modules", ".next", "__pycache__", ".venv", ".git"}
SKIP_FILES = {"package-lock.json"}
GENERATED_CSS = "web/app/tokens.css"
ALLOWED_COLOR_NAMES = {"navy", "cream", "white", "cyan", "charcoal", "status_online"}
DEFINITION_FILES = {
    "theme/tokens.toml",
    "docs/DESIGN.md",
    "web/app/tokens.css",
    "api/app/theme_tokens.py",
    "worker/app/theme_tokens.py",
}
# These two tokens exist only for one surface each. The hex may be declared in the
# theme file, the design doc, and generated output. A var() use is allowed only
# on the selector named here.
RESTRICTED_SURFACES = {
    "charcoal": {
        "variable": "--sentinel-charcoal",
        "selector": ".chat-frame",
        "use": "the assistant panel",
    },
    "status_online": {
        "variable": "--sentinel-status-online",
        "selector": ".status-online",
        "use": "connection status indicators",
    },
}

HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
RAW_PX = re.compile(r"\d+px", re.IGNORECASE)
RAW_WEIGHT = re.compile(r"font-weight\s*:\s*\d+", re.IGNORECASE)
RAW_SIZE = re.compile(r"font-size\s*:\s*\d+", re.IGNORECASE)
RAW_WEIGHT_JS = re.compile(r"fontWeight\s*[:=]\s*['\"]?\d+")
RAW_SIZE_JS = re.compile(r"fontSize\s*[:=]\s*['\"]?\d+")
FUNCTION_COLOR = re.compile(r"\b(?:rgb|rgba|hsl|hsla|hwb)\s*\(", re.IGNORECASE)
GRADIENT_CALL = re.compile(r"(?:linear|radial|conic)-gradient\s*\(", re.IGNORECASE)
BACKDROP_BLUR = re.compile(r"backdrop-filter\s*:", re.IGNORECASE)
BLUR_CALL = re.compile(r"(?<![\w-])blur\s*\(", re.IGNORECASE)
COMPOSER_CLASS = ".senti-composer"
PALETTE = re.compile(
    r"(?<![A-Za-z0-9_-])(?:red|green|orange|yellow|purple|gray|grey|slate|zinc|neutral|stone|emerald|rose|sky|indigo|amber|lime|teal|cyan|fuchsia|pink|violet|black|white)-(?:50|\d{2,3})\b"
)


def load_colors(root: Path) -> dict[str, str]:
    with (root / "theme" / "tokens.toml").open("rb") as handle:
        colors = tomllib.load(handle)["colors"]
    if set(colors) != ALLOWED_COLOR_NAMES:
        raise SystemExit(
            "theme colors must be exactly navy, cream, white, cyan, charcoal, and status_online"
        )
    return colors


def selector_at(text: str, index: int) -> str:
    brace = text.rfind("{", 0, index)
    if brace < 0:
        return ""
    previous = text.rfind("}", 0, brace)
    return " ".join(text[previous + 1 : brace].split())


def restricted_violations(relative: str, text: str, colors: dict[str, str]) -> list[str]:
    found: list[str] = []
    if relative not in DEFINITION_FILES:
        upper = text.upper()
        for name, spec in RESTRICTED_SURFACES.items():
            if colors[name].upper() in upper:
                found.append(f"{relative}: {name} is limited to {spec['use']}")
    for name, spec in RESTRICTED_SURFACES.items():
        needle = f"var({spec['variable']})"
        start = 0
        while True:
            index = text.find(needle, start)
            if index < 0:
                break
            selector = selector_at(text, index)
            if relative != "web/app/globals.css" or selector != spec["selector"]:
                found.append(f"{relative}: {spec['variable']} is limited to {spec['selector']} ({spec['use']})")
            start = index + len(needle)
    return found


def effect_violations(relative: str, text: str) -> list[str]:
    found: list[str] = []
    for pattern, label in (
        (GRADIENT_CALL, "gradient"),
        (BACKDROP_BLUR, "backdrop blur"),
        (BLUR_CALL, "blur"),
    ):
        for match in pattern.finditer(text):
            selector = selector_at(text, match.start())
            parts = [part.strip() for part in selector.split(",") if part.strip()]
            if relative == "web/app/globals.css" and parts and all(COMPOSER_CLASS in part for part in parts):
                continue
            found.append(f"{relative}: {label} is limited to {COMPOSER_CLASS}")
    return found


def design_colors(root: Path) -> set[str]:
    text = (root / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    return {match.upper() for match in re.findall(r"#[0-9A-Fa-f]{6}", text)}


def is_generated_css(path: Path, root: Path) -> bool:
    return path.resolve().as_posix().endswith(GENERATED_CSS)


def scan(root: Path) -> list[str]:
    colors = load_colors(root)
    allowed = {value.upper() for value in colors.values()}
    violations: list[str] = []
    if design_colors(root) != allowed:
        violations.append("docs/DESIGN.md colors differ from theme/tokens.toml")
    for directory in SCAN_DIRS:
        base = root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts) or path.name in SKIP_FILES:
                continue
            if path.suffix.lower() not in EXTENSIONS:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            relative = path.relative_to(root).as_posix()
            for match in HEX.finditer(text):
                if match.group(0).upper() not in allowed:
                    violations.append(f"{relative}: color {match.group(0)}")
            violations.extend(restricted_violations(relative, text, colors))
            violations.extend(effect_violations(relative, text))
            if is_generated_css(path, root):
                continue
            for pattern, label in (
                (RAW_PX, "raw px"),
                (RAW_WEIGHT, "raw font-weight"),
                (RAW_SIZE, "raw font-size"),
                (RAW_WEIGHT_JS, "raw fontWeight"),
                (RAW_SIZE_JS, "raw fontSize"),
                (FUNCTION_COLOR, "color function"),
                (PALETTE, "palette utility"),
            ):
                found = pattern.search(text)
                if found:
                    violations.append(f"{relative}: {label} ({found.group(0)})")
    return violations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    violations = scan(args.root)
    if violations:
        for item in violations:
            print(item)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
