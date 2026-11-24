"""Test suite verifying structural and reference integrity of frontend and webapp assets."""
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

# Ensure Backend/ directory is in path
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def test_asset_files_exist():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    for base in [root / "frontend", root / "Backend" / "webapp"]:
        assert (base / "index.html").is_file(), f"Missing index.html in {base}"
        assert (base / "satellite.html").is_file(), f"Missing satellite.html in {base}"
        assert (base / "css" / "landing.css").is_file(), f"Missing landing.css in {base}"
        assert (base / "css" / "satellite.css").is_file(), f"Missing satellite.css in {base}"
        assert (base / "js" / "landing.js").is_file(), f"Missing landing.js in {base}"
        assert (base / "js" / "satellite.js").is_file(), f"Missing satellite.js in {base}"


def test_html_references_resolve():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    link_pattern = re.compile(r'<link\b[^>]*href=["\']([^"\']+)["\']', re.IGNORECASE)
    script_pattern = re.compile(r'<script\b[^>]*src=["\']([^"\']+)["\']', re.IGNORECASE)

    for base in [root / "frontend", root / "Backend" / "webapp"]:
        for html_name in ["index.html", "satellite.html"]:
            html_file = base / html_name
            content = html_file.read_text(encoding="utf-8")

            # Check CSS links
            for href in link_pattern.findall(content):
                if href.startswith("http://") or href.startswith("https://") or href.startswith("/"):
                    continue
                target = base / href
                assert target.is_file(), f"Broken stylesheet reference '{href}' in {html_file}"
                assert target.stat().st_size > 0, f"Empty stylesheet '{href}' in {html_file}"

            # Check JS scripts
            for src in script_pattern.findall(content):
                if src.startswith("http://") or src.startswith("https://") or src.startswith("/"):
                    continue
                target = base / src
                assert target.is_file(), f"Broken script reference '{src}' in {html_file}"
                assert target.stat().st_size > 0, f"Empty script '{src}' in {html_file}"


def test_frontend_webapp_synchronization():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    f_base = root / "frontend"
    w_base = root / "Backend" / "webapp"

    targets = [
        "index.html",
        "satellite.html",
        "css/landing.css",
        "css/satellite.css",
        "js/landing.js",
        "js/satellite.js",
    ]

    for rel_path in targets:
        f_file = f_base / rel_path
        w_file = w_base / rel_path
        assert f_file.is_file(), f"Frontend file missing: {f_file}"
        assert w_file.is_file(), f"Webapp file missing: {w_file}"
        assert f_file.read_text(encoding="utf-8") == w_file.read_text(encoding="utf-8"), (
            f"Content mismatch between {f_file} and {w_file}"
        )


def test_javascript_syntax_sanity():
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    node_exe = shutil.which("node")

    for js_path in [
        root / "frontend" / "js" / "landing.js",
        root / "frontend" / "js" / "satellite.js",
    ]:
        code = js_path.read_text(encoding="utf-8")
        assert len(code) > 1000, f"Script {js_path.name} unexpectedly small ({len(code)} bytes)"
        if node_exe:
            # Strictly validate JS syntax with node -c
            res = subprocess.run([node_exe, "-c", str(js_path)], capture_output=True, text=True)
            assert res.returncode == 0, f"Syntax error in {js_path.name}: {res.stderr}"


if __name__ == "__main__":
    test_asset_files_exist()
    test_html_references_resolve()
    test_frontend_webapp_synchronization()
    test_javascript_syntax_sanity()
    print("All frontend asset and integrity tests passed successfully!")
