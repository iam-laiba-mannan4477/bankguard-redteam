"""Build a self-contained static copy of the demo (replay + results, no live model).

python -m demo.export_static [out_dir]      default: demo/static_site/

Needs no server and no key. Upload the folder's contents to a Hugging Face Static Space.
The page detects there is no server, shows replay mode and reads data/*.json.
"""
import json
import shutil
import sys
from pathlib import Path

from bank.state import Bank
from demo.app import ACCOUNT, STATIC, load_replays, load_results

DEFAULT_OUT = Path(__file__).resolve().parent / "static_site"


def export(out=DEFAULT_OUT):
    out = Path(out)
    (out / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(STATIC / "index.html", out / "index.html")
    files = {"results": load_results(), "replays": load_replays(),
             "seed": Bank("C-1").list_transactions(ACCOUNT, limit=50)}
    for name, data in files.items():
        (out / "data" / f"{name}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(f"Static site written to {export(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT)}")
