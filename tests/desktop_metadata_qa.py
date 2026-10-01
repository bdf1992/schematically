"""Desktop metadata QA.

Static checks that the desktop Tauri shell's config carries the identity Windows'
file-properties dialog, SmartScreen prompt, the NSIS uninstall entry and the WiX
Manufacturer field read: `bundle.publisher`, `bundle.copyright` and
`bundle.shortDescription` are present and non-empty, the declared version matches
`Cargo.toml`'s `[package]` version, and `productName` matches the first window's
title. No cargo, no browser. The checking function runs over a parsed config object
so it can be run again, in this file, against two broken copies to prove it bites.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_metadata(conf: dict, cargo_version: str) -> None:
    bundle = conf['bundle']
    for field in ('publisher', 'copyright', 'shortDescription'):
        value = bundle.get(field)
        assert isinstance(value, str) and value.strip(), f'bundle.{field} must be present and non-empty'

    assert conf['version'] == cargo_version, (
        f"tauri.conf.json version {conf['version']!r} must equal Cargo.toml's [package] version {cargo_version!r}"
    )

    windows = conf['app']['windows']
    assert windows, 'app.windows must declare at least one window'
    assert conf['productName'] == windows[0]['title'], (
        f"productName {conf['productName']!r} must equal the first window's title {windows[0]['title']!r}"
    )


def _cargo_package_version(cargo_toml: str) -> str:
    match = re.search(r'^\[package\]\s*(?:.*\n)*?^version\s*=\s*"([^"]+)"', cargo_toml, re.MULTILINE)
    assert match, 'Cargo.toml [package] version not found'
    return match.group(1)


def _assert_bites(broken: dict, cargo_version: str, label: str) -> None:
    try:
        check_metadata(broken, cargo_version)
    except AssertionError:
        return
    raise AssertionError(f'check_metadata did not fail on {label}')


def main() -> None:
    conf = json.loads((ROOT / 'desktop/src-tauri/tauri.conf.json').read_text(encoding='utf-8'))
    cargo_toml = (ROOT / 'desktop/src-tauri/Cargo.toml').read_text(encoding='utf-8')
    cargo_version = _cargo_package_version(cargo_toml)

    check_metadata(conf, cargo_version)

    no_publisher = json.loads(json.dumps(conf))
    del no_publisher['bundle']['publisher']
    _assert_bites(no_publisher, cargo_version, 'publisher removed')

    mismatched_version = json.loads(json.dumps(conf))
    mismatched_version['version'] = cargo_version + '-mismatch'
    _assert_bites(mismatched_version, cargo_version, 'version mismatched')

    print('PASS desktop metadata QA')


if __name__ == '__main__':
    main()
