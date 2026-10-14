"""Write CSS variables and Python constants from theme/tokens.toml."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

PIXEL = "px"
WEIGHT_PROP = "font-weight"
MIN_SIZE = 13
MIN_WEIGHT = 500


def percent(opacity: float) -> str:
    return f"{round(opacity * 100, 4):g}%"


def pixel(value: int) -> str:
    return f"{int(value)}{PIXEL}"


def to_bgr(value: str) -> tuple[int, int, int]:
    channel = value.removeprefix("#")
    red = int(channel[0:2], 16)
    green = int(channel[2:4], 16)
    blue = int(channel[4:6], 16)
    return (blue, green, red)


def py_literal(value: object) -> str:
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, tuple):
        return "(" + ", ".join(py_literal(item) for item in value) + ")"
    if isinstance(value, dict):
        inner = ", ".join(f"{py_literal(key)}: {py_literal(item)}" for key, item in value.items())
        return "{" + inner + "}"
    raise TypeError(f"unsupported token value: {type(value)!r}")


def load_tokens(root: Path) -> dict:
    path = root / "theme" / "tokens.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    colors = data["colors"]
    if set(colors) != {"navy", "cream", "white", "cyan", "charcoal", "status_online"}:
        raise SystemExit(
            "theme colors must be exactly navy, cream, white, cyan, charcoal, and status_online"
        )
    for name, value in colors.items():
        if len(value) != 7 or not value.startswith("#"):
            raise SystemExit(f"invalid color token: {name}")
    for role, spec in data["type"].items():
        if not isinstance(spec, dict):
            continue
        if spec["size"] < MIN_SIZE or spec["weight"] < MIN_WEIGHT:
            raise SystemExit(f"type.{role} is below the design minimum")
    return data


def render_css(data: dict) -> str:
    colors = data["colors"]
    opacity = data["opacity"]
    layout_px = data["layout_px"]
    type_tokens = data["type"]
    lines = [
        "/* Generated from theme/tokens.toml. Do not edit. */",
        ":root {",
    ]
    for name, value in colors.items():
        lines.append(f"  --sentinel-{name.replace('_', '-')}: {value};")
    for name, value in opacity.items():
        token = name.replace("_", "-")
        lines.append(f"  --opacity-{token}: {value};")
    mixes = {
        "surface": ("white", "surface"),
        "surface-strong": ("white", "surface_strong"),
        "line": ("cream", "line"),
        "text-secondary": ("cream", "text_secondary"),
        "grid-color": ("cream", "grid"),
        "dashed-line": ("cream", "dashed"),
    }
    for variable, (color_name, opacity_name) in mixes.items():
        lines.append(
            "  --"
            + variable
            + ": color-mix(in srgb, var(--sentinel-"
            + color_name
            + ") "
            + percent(opacity[opacity_name])
            + ", transparent);"
        )
    # Opaque panel: the same white ratio mixed into navy, so text never sits on the map.
    lines.append(
        "  --panel: color-mix(in srgb, var(--sentinel-white) "
        + percent(opacity["surface"])
        + ", var(--sentinel-navy));"
    )
    lines.append(
        "  --panel-strong: color-mix(in srgb, var(--sentinel-white) "
        + percent(opacity["surface_strong"])
        + ", var(--sentinel-navy));"
    )
    lines.append(
        "  --composer-fill: color-mix(in srgb, var(--sentinel-navy) "
        + percent(opacity["composer"])
        + ", transparent);"
    )
    lines.append(
        "  --glow-blue: color-mix(in srgb, var(--sentinel-cyan) "
        + percent(opacity["glow"])
        + ", var(--sentinel-navy));"
    )
    lines.append(
        "  --glow-blue-deep: color-mix(in srgb, var(--sentinel-cyan) "
        + percent(opacity["glow_deep"])
        + ", var(--sentinel-navy));"
    )
    lines.append(
        "  --aurora-cream: color-mix(in srgb, var(--sentinel-cream) "
        + percent(opacity["cream_hint"])
        + ", var(--sentinel-navy));"
    )
    for name, value in layout_px.items():
        lines.append(f"  --{name.replace('_', '-')}: {pixel(value)};")
    lines.append(f"  --video-column: {data['layout']['video_or_media_column_pct']}%;")
    lines.append(f"  --aurora-height: {data['layout']['aurora_height_pct']}%;")
    lines.append(f"  --aurora-drift: {data['layout']['aurora_drift_pct']}%;")
    lines.append(f"  --font-family: {type_tokens['family']};")
    lines.append(f"  --line-height-tight: {type_tokens['line_height_tight']};")
    lines.append(f"  --line-height-body: {type_tokens['line_height_body']};")
    lines.append(f"  --section-tracking: {type_tokens['section_tracking_em']}em;")
    for role, spec in type_tokens.items():
        if not isinstance(spec, dict):
            continue
        token = role.replace("_", "-")
        lines.append(f"  --size-{token}: {pixel(spec['size'])};")
        lines.append(f"  --weight-{token}: {spec['weight']};")
    lines.append("}")
    lines.append("")
    for weight in data["fonts"]["weights"]:
        filename = f"poppins-latin-{weight}-normal.woff2"
        lines.append("@font-face {")
        lines.append(f"  font-family: {type_tokens['face_family']!r};")
        lines.append("  font-style: normal;")
        lines.append(f"  {WEIGHT_PROP}: {weight};")
        lines.append("  font-display: swap;")
        lines.append(f'  src: url("/fonts/{filename}") format("woff2");')
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def render_python(data: dict) -> str:
    colors = data["colors"]
    bgr = {name: to_bgr(value) for name, value in colors.items()}
    type_roles = {role: spec for role, spec in data["type"].items() if isinstance(spec, dict)}
    body = [
        '"""Generated from theme/tokens.toml. Do not edit."""',
        "",
        f"COLORS = {py_literal(colors)}",
        f"BGR = {py_literal(bgr)}",
        f"OPACITY = {py_literal(data['opacity'])}",
        f"LAYOUT_PX = {py_literal(data['layout_px'])}",
        f"VIDEO_COLUMN_PCT = {py_literal(data['layout']['video_or_media_column_pct'])}",
        f"TYPE = {py_literal(type_roles)}",
        f"FONT_FAMILY = {py_literal(data['type']['family'])}",
        "OVERLAY_BGR = BGR['white']",
        "OVERLAY_LINE_WIDTH = LAYOUT_PX['border_width']",
        "",
    ]
    return "\n".join(body)


def generate(root: Path) -> None:
    data = load_tokens(root)
    css_path = root / "web" / "app" / "tokens.css"
    css_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.write_text(render_css(data), encoding="utf-8")
    python = render_python(data)
    for relative in (Path("api") / "app" / "theme_tokens.py", Path("worker") / "app" / "theme_tokens.py"):
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(python, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    generate(args.root)


if __name__ == "__main__":
    main()
