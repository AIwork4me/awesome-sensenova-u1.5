import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

# Pipeline scripts use kebab-case filenames (e.g. scripts/select-pilot.py) but
# tests import them as underscore modules; register an alias for each.
for _p in sorted((ROOT / "scripts").glob("*-*.py")):
    _name = _p.stem.replace("-", "_")
    if _name in sys.modules:
        continue
    _spec = importlib.util.spec_from_file_location(_name, _p)
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_name] = _mod
    _spec.loader.exec_module(_mod)
