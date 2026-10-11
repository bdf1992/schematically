"""Run the existing structural checks without invoking workstation export code."""

import json
import runpy
from pathlib import Path


def main():
    model = runpy.run_path(str(Path(__file__).with_name("fraktal.py")), run_name="fraktal")
    instance = model["build"](depth=3)
    requirements = model["check"](instance)
    bites = model["bites"]()
    survivors = model["survivors"]()
    result = {
        "knodes": model["count"](instance),
        "requirements": {key: breaks for key, (_, _, breaks) in requirements.items()},
        "bites": bites,
        "survivors": survivors,
        "limits": model["LIMITS"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    failed = any(result["requirements"].values())
    failed |= any(reported != [key] for key, reported in bites.items())
    failed |= any(not reported for reported in survivors.values())
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
