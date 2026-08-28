#!/bin/bash

# Source whichever Vivado version is actually installed for this user, rather
# than hardcoding one specific version -- different machines on this project
# have ended up with different Vivado versions installed (e.g. 2025.2 here
# vs. 2026.1 on whichever machine produced report/synthesis_data.md's actual
# results), and a hardcoded version string only works for whoever originally
# wrote it. Resolved per-user ($USER) for the same reason the license path
# below already is.
XILINX_BASE="/data/project/tsmc65/users/${USER}/xilinx"

# Prefer this version if it's present -- it's the one this project's real
# synthesis/implementation/bitstream results (report/synthesis_data.md) were
# actually produced with, so checkpoints in dbs/ are guaranteed compatible.
# Otherwise, fall back to the newest version actually installed.
PREFERRED_VERSION="2026.1"

if [ -f "$XILINX_BASE/$PREFERRED_VERSION/Vivado/settings64.sh" ]; then
    VIVADO_VERSION="$PREFERRED_VERSION"
else
    VIVADO_VERSION=$(ls "$XILINX_BASE" 2>/dev/null | grep -E '^[0-9]{4}\.[0-9]+$' | sort -V | tail -1)
fi

if [ -z "$VIVADO_VERSION" ]; then
    echo "No Vivado installation found under $XILINX_BASE/<version>/Vivado/" >&2
    echo "Install Vivado (any recent version) to $XILINX_BASE/<version>/ first." >&2
    return 1 2>/dev/null || exit 1
fi

VIVADO_SETTINGS="$XILINX_BASE/$VIVADO_VERSION/Vivado/settings64.sh"

if [ "$VIVADO_VERSION" != "$PREFERRED_VERSION" ]; then
    echo "Note: using Vivado $VIVADO_VERSION ($PREFERRED_VERSION not found on this machine)." >&2
    echo "This project's synthesis/implementation results were produced with $PREFERRED_VERSION -- checkpoints in dbs/ may not open in an older version." >&2
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

echo "Vivado $VIVADO_VERSION environment loaded for ${USER}. Type 'vivado' to launch."
