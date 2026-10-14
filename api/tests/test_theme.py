import importlib.util
import os
import tomllib
from pathlib import Path


def test_theme_sources_are_clean() -> None:
    root = Path(os.environ["SENTINEL_ROOT"])
    path = root / "scripts" / "check_theme.py"
    spec = importlib.util.spec_from_file_location("check_theme", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.scan(root) == []


def test_generated_tokens_match_the_source_file() -> None:
    root = Path(os.environ["SENTINEL_ROOT"])
    with (root / "theme" / "tokens.toml").open("rb") as handle:
        data = tomllib.load(handle)
    from app import theme_tokens

    assert theme_tokens.COLORS == data["colors"]
    assert theme_tokens.LAYOUT_PX["sidebar_width"] == data["layout_px"]["sidebar_width"]
    assert theme_tokens.OVERLAY_LINE_WIDTH == data["layout_px"]["border_width"]
    assert theme_tokens.OVERLAY_BGR == theme_tokens.BGR["white"]
