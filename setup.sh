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

# Free (Vivado ML Standard / WebPACK-tier) node-locked license, generated per-user
# from the AMD licensing portal against this machine's Host ID. $HOME already
# resolves per-user, so no extra templating needed here unlike VIVADO_SETTINGS above.
XILINX_LICENSE_FILE_PATH="$HOME/.Xilinx/Xilinx.lic"
if [ -f "$XILINX_LICENSE_FILE_PATH" ]; then
    export XILINXD_LICENSE_FILE="$XILINX_LICENSE_FILE_PATH"
else
    echo "Warning: no Xilinx license found at $XILINX_LICENSE_FILE_PATH -- Vivado will fail to launch until one is generated (AMD licensing portal, Host ID from this machine's MAC address) and placed there." >&2
fi

echo "Vivado 2026.1 environment loaded for ${USER}. Type 'vivado' to launch."
