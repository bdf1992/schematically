"""Shared browser launch policy for RC QA.

Use CHROMIUM_PATH only when the caller explicitly supplies a system browser.
Otherwise let Playwright launch the Chromium revision installed for its own version.
"""
from __future__ import annotations
import os
from pathlib import Path


def chromium_launch_kwargs(*, disable_gpu: bool = False) -> dict:
    args = ["--no-sandbox"]
    if disable_gpu:
        args.append("--disable-gpu")
    kwargs = {"headless": True, "args": args}
    explicit = os.environ.get("CHROMIUM_PATH", "").strip()
    if explicit:
        path = Path(explicit)
        if not path.exists():
            raise RuntimeError(f"CHROMIUM_PATH does not exist: {explicit}")
        kwargs["executable_path"] = explicit
    return kwargs
