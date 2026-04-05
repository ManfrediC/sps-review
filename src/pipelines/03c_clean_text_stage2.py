from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[2]
PRIMARY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "03b_clean_text.py"


# Load the canonical cleanup stage lazily so this compatibility wrapper keeps
# working without duplicating the residual-cleanup logic.
def load_primary_cleanup_module():
    spec = importlib.util.spec_from_file_location("clean_text_primary_module", PRIMARY_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# Preserve the historical `03c` command by forwarding its arguments to `03b`
# with the explicit residual-cleanup flag.
def main(argv: Sequence[str] | None = None) -> None:
    cleanup_module = load_primary_cleanup_module()
    forwarded_args = ["--stage2", *((list(argv) if argv is not None else sys.argv[1:]))]
    cleanup_module.main(forwarded_args)


if __name__ == "__main__":
    main()
