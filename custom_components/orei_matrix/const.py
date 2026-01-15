"""Constants for the Orei HDMI Matrix integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "orei_matrix"

# Connection settings
DEFAULT_PORT: Final = 8000
DEFAULT_TIMEOUT: Final = 5
DEFAULT_SCAN_INTERVAL: Final = 30
COMMAND_DELAY: Final = 0.1

# Configuration keys
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_NAME: Final = "name"
CONF_SCAN_INTERVAL: Final = "scan_interval"

# Device info
ATTR_FIRMWARE_VERSION: Final = "firmware_version"
ATTR_MODEL: Final = "model"
ATTR_MAC_ADDRESS: Final = "mac_address"

# Number of inputs and outputs
NUM_INPUTS: Final = 8
NUM_OUTPUTS: Final = 8
NUM_PRESETS: Final = 8
NUM_USER_EDIDS: Final = 3

# EDID Options mapping (z value -> description)
EDID_OPTIONS: Final = {
    1: "1080P, 2.0CH",
    2: "1080P, 5.1CH",
    3: "1080P, 7.1CH",
    4: "4K30, 2.0CH",
    5: "4K30, 5.1CH",
    6: "4K30, 7.1CH",
    7: "4K60 (4:2:0), 2.0CH",
    8: "4K60 (4:2:0), 5.1CH",
    9: "4K60 (4:2:0), 7.1CH",
    10: "4K60 (4:4:4), 2.0CH",
    11: "4K60 (4:4:4), 5.1CH",
    12: "4K60 (4:4:4), 7.1CH",
    13: "1080P HDR, 2.0CH",
    14: "1080P HDR, 5.1CH",
    15: "1080P HDR, 7.1CH",
    16: "4K30 HDR, 2.0CH",
    17: "4K30 HDR, 5.1CH",
    18: "4K30 HDR, 7.1CH",
    19: "4K60 (4:2:0) HDR, 2.0CH",
    20: "4K60 (4:2:0) HDR, 5.1CH",
    21: "4K60 (4:2:0) HDR, 7.1CH",
    22: "4K60 (4:4:4) HDR, 2.0CH",
    23: "4K60 (4:4:4) HDR, 5.1CH",
    24: "4K60 (4:4:4) HDR, 7.1CH",
    25: "4K120 (4:2:0) HDR, 2.0CH",
    26: "4K120 (4:2:0) HDR, 5.1CH",
    27: "4K120 (4:2:0) HDR, 7.1CH",
    28: "4K120 (4:4:4) HDR, 2.0CH",
    29: "4K120 (4:4:4) HDR, 5.1CH",
    30: "4K120 (4:4:4) HDR, 7.1CH",
    31: "8K FRL10G HDR, 2.0CH",
    32: "8K FRL10G HDR, 5.1CH",
    33: "8K FRL10G HDR, 7.1CH",
    34: "8K FRL12G HDR, 2.0CH",
    35: "8K FRL12G HDR, 5.1CH",
    36: "8K FRL12G HDR, 7.1CH",
    37: "User EDID 1",
    38: "User EDID 2",
    39: "User EDID 3",
}

# Reverse mapping for EDID
EDID_OPTIONS_REVERSE: Final = {v: k for k, v in EDID_OPTIONS.items()}

# HDCP Options
HDCP_OPTIONS: Final = {
    1: "HDCP 1.4",
    2: "HDCP 2.2",
    3: "Follow Sink",
    4: "Follow Source",
    5: "User Mode",
}

HDCP_OPTIONS_REVERSE: Final = {v: k for k, v in HDCP_OPTIONS.items()}

# Scaler Options
SCALER_OPTIONS: Final = {
    1: "Pass-through",
    2: "8K to 4K",
    3: "8K/4K to 1080p",
    4: "Auto (Follow Sink)",
}

SCALER_OPTIONS_REVERSE: Final = {v: k for k, v in SCALER_OPTIONS.items()}

# HDR Options
HDR_OPTIONS: Final = {
    1: "Pass-through",
    2: "HDR to SDR",
    3: "Auto (Follow Sink)",
}

HDR_OPTIONS_REVERSE: Final = {v: k for k, v in HDR_OPTIONS.items()}

# LCD On Time Options
LCD_TIME_OPTIONS: Final = {
    0: "Off",
    1: "Always On",
    2: "15 Seconds",
    3: "30 Seconds",
    4: "60 Seconds",
}

LCD_TIME_OPTIONS_REVERSE: Final = {v: k for k, v in LCD_TIME_OPTIONS.items()}

# External Audio Mode Options
EXT_AUDIO_MODE_OPTIONS: Final = {
    0: "Bind to Input",
    1: "Bind to Output",
    2: "Matrix Mode",
}

EXT_AUDIO_MODE_OPTIONS_REVERSE: Final = {v: k for k, v in EXT_AUDIO_MODE_OPTIONS.items()}

# External Audio Source Options (for matrix mode)
EXT_AUDIO_SOURCE_OPTIONS: Final = {
    1: "Input 1",
    2: "Input 2",
    3: "Input 3",
    4: "Input 4",
    5: "Input 5",
    6: "Input 6",
    7: "Input 7",
    8: "Input 8",
    9: "Output 1 ARC",
    10: "Output 2 ARC",
    11: "Output 3 ARC",
    12: "Output 4 ARC",
    13: "Output 5 ARC",
    14: "Output 6 ARC",
    15: "Output 7 ARC",
    16: "Output 8 ARC",
}

EXT_AUDIO_SOURCE_OPTIONS_REVERSE: Final = {v: k for k, v in EXT_AUDIO_SOURCE_OPTIONS.items()}

# IP Mode Options
IP_MODE_OPTIONS: Final = {
    0: "Static",
    1: "DHCP",
}

IP_MODE_OPTIONS_REVERSE: Final = {v: k for k, v in IP_MODE_OPTIONS.items()}

# Connection Status
CONNECTION_STATUS: Final = {
    "connect": "Connected",
    "sync": "Syncing",
    "disconnect": "Disconnected",
}

# CEC Commands
CEC_INPUT_COMMANDS: Final = [
    "on",
    "off",
    "menu",
    "back",
    "up",
    "down",
    "left",
    "right",
    "enter",
    "play",
    "pause",
    "stop",
    "rew",
    "ff",
    "mute",
    "vol-",
    "vol+",
    "previous",
    "next",
]

CEC_OUTPUT_COMMANDS: Final = [
    "on",
    "off",
    "mute",
    "vol-",
    "vol+",
    "active",
]

# Services
SERVICE_SEND_COMMAND: Final = "send_command"
SERVICE_SAVE_PRESET: Final = "save_preset"
SERVICE_RECALL_PRESET: Final = "recall_preset"
SERVICE_CLEAR_PRESET: Final = "clear_preset"
SERVICE_SET_ROUTING: Final = "set_routing"
SERVICE_SET_ALL_ROUTING: Final = "set_all_routing"
SERVICE_CEC_COMMAND: Final = "cec_command"
SERVICE_COPY_EDID: Final = "copy_edid"
SERVICE_SET_LOGO: Final = "set_logo"

# Platforms
PLATFORMS: Final = [
    "switch",
    "select",
    "button",
    "sensor",
    "number",
    "text",
]
