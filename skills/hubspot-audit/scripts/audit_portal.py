# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "requests>=2.31",
#   "python-dotenv>=1.0",
# ]
# ///
"""
Compatibility shim. The audit engine moved to audit.py in 3.0; this file
forwards its arguments so existing instructions keep working.

    uv run scripts/audit.py --scope full|marketing|sales
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("audit_portal.py is now audit.py; forwarding. Update your command to "
          "`uv run scripts/audit.py`.", file=sys.stderr)
    from audit import main
    main()
