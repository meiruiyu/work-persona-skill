#!/usr/bin/env python3
"""Screenshot the fixed 900x1200 HTML poster as a high-resolution PNG."""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import struct
import subprocess
import tempfile
import time
from pathlib import Path


CSS_WIDTH, CSS_HEIGHT = 900, 1200
DEFAULT_SCALE = 2


def browser_path() -> str | None:
    configured = os.environ.get("MARVIS_CHROMIUM_PATH")
    candidates = [
        configured,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("microsoft-edge"),
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def verify_png(path: Path, expected_size: tuple[int, int]) -> None:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("The browser did not produce a valid PNG file.")
    image_size = struct.unpack(">II", data[16:24])
    if image_size != expected_size:
        raise SystemExit(f"Unexpected report size {image_size}; expected {expected_size}.")
    if len(data) < 5000:
        raise SystemExit("The rendered report is unexpectedly small and may be blank.")


def stop_process_group(process: subprocess.Popen, force: bool = False) -> None:
    """Best-effort Chrome cleanup; a finished screenshot must not fail on cleanup."""
    sig = signal.SIGKILL if force else signal.SIGTERM
    try:
        os.killpg(process.pid, sig)
        return
    except (PermissionError, ProcessLookupError):
        pass
    try:
        process.kill() if force else process.terminate()
    except (PermissionError, ProcessLookupError):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--scale", type=int, choices=(1, 2, 3), default=DEFAULT_SCALE)
    args = parser.parse_args()

    html_path = Path(args.html).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_size = (CSS_WIDTH * args.scale, CSS_HEIGHT * args.scale)
    if not html_path.exists():
        raise SystemExit(f"HTML report not found: {html_path}")
    browser = browser_path()
    if not browser:
        raise SystemExit(
            "No Chromium browser found. Install Chrome/Chromium or set MARVIS_CHROMIUM_PATH; "
            "do not replace the deterministic screenshot with AI image generation."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Chrome does not guarantee an atomic overwrite. Remove a previous report so
    # the stability loop cannot mistake the old PNG for a newly rendered frame.
    output_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="marvis-chrome-") as profile_dir:
        command = [
            browser,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-sync",
            "--hide-scrollbars",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=1500",
            f"--force-device-scale-factor={args.scale}",
            f"--window-size={CSS_WIDTH},{CSS_HEIGHT}",
            f"--user-data-dir={profile_dir}",
            f"--screenshot={output_path}",
            html_path.as_uri(),
        ]
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        deadline = time.monotonic() + 15
        last_size = -1
        stable_checks = 0
        while process.poll() is None and time.monotonic() < deadline:
            size = output_path.stat().st_size if output_path.exists() else 0
            if size > 0 and size == last_size:
                stable_checks += 1
            else:
                stable_checks = 0
                last_size = size
            if stable_checks >= 3:
                stop_process_group(process)
                break
            time.sleep(0.1)
        if process.poll() is None:
            stop_process_group(process)
        try:
            _, stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            stop_process_group(process, force=True)
            _, stderr = process.communicate()
        if not output_path.exists() or output_path.stat().st_size == 0:
            detail = stderr.strip()[-2000:] or f"browser exited with code {process.returncode}"
            raise SystemExit(f"Chromium screenshot failed: {detail}")
    verify_png(output_path, output_size)
    print(json.dumps({
        "report_png": str(output_path),
        "source_html": str(html_path),
        "renderer": "chromium_screenshot",
        "width": output_size[0],
        "height": output_size[1],
        "css_width": CSS_WIDTH,
        "css_height": CSS_HEIGHT,
        "scale": args.scale,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
