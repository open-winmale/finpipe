import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
# 仓根入 path：tests 里 `from tools import xxx`（如 audit_units）在任意环境可用
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
