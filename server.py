import sys
from pathlib import Path

# Inside a built .dxt, vendored deps live alongside this file under `lib/`.
# Harmless in dev when the package is already installed in the active env.
sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))

from clockify_mcp.server import main

if __name__ == "__main__":
    main()
