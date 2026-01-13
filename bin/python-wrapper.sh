#!/bin/bash
# Cross-platform Python wrapper for WSL/Windows compatibility

# Check if running in WSL
if grep -qEi "(Microsoft|WSL)" /proc/version 2>/dev/null; then
    # WSL: Use Windows Python 3.11
    PYTHON="/mnt/c/Users/lefab/AppData/Local/Programs/Python/Python311/python.exe"
else
    # Native Linux/Mac: Use system python
    PYTHON="python3"
fi

# Execute python with all arguments
exec "$PYTHON" "$@"
