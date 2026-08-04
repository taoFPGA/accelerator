#!/bin/bash

# Source Vivado 2026.1 environment. Resolved per-user ($USER) rather than
# hardcoded to one person's path -- each user needs their own install under
# /data/project/tsmc65/users/<you>/xilinx/2026.1/ for this to work for them.
VIVADO_SETTINGS="/data/project/tsmc65/users/${USER}/xilinx/2026.1/Vivado/settings64.sh"

if [ ! -f "$VIVADO_SETTINGS" ]; then
    echo "Vivado settings not found at $VIVADO_SETTINGS" >&2
    echo "Install Vivado 2026.1 (Vivado Design Suite edition) to /data/project/tsmc65/users/${USER}/xilinx/2026.1/ first." >&2
    return 1 2>/dev/null || exit 1
fi

source "$VIVADO_SETTINGS"

echo "Vivado 2026.1 environment loaded for ${USER}. Type 'vivado' to launch."
