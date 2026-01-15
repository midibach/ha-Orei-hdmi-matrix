# Orei HDMI Matrix Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/your-github-username/ha-orei-matrix.svg)](https://github.com/your-github-username/ha-orei-matrix/releases)
[![License](https://img.shields.io/github/license/your-github-username/ha-orei-matrix.svg)](LICENSE)

A comprehensive Home Assistant custom integration for the **Orei BK-808 8x8 HDMI 2.1 Matrix** with audio extraction. This integration provides full control over your HDMI matrix via TCP/IP, including video routing, audio extraction, EDID management, CEC control, and more.

## Features

### Video Routing
- **Per-output source selection** - Route any of 8 inputs to any of 8 outputs
- **Route all outputs** - Quickly route all outputs to a single input
- **8 preset slots** - Save, recall, and clear routing presets

### Output Controls
- **HDCP mode** - HDCP 1.4, HDCP 2.2, Follow Sink, Follow Source, User Mode
- **Scaler mode** - Pass-through, 8K→4K, 8K/4K→1080p, Auto
- **HDR mode** - Pass-through, HDR to SDR, Auto
- **Stream enable/disable** - Enable or disable video output per port
- **ARC support** - Audio Return Channel control per output

### Audio Features
- **External audio extraction** - Enable/disable per output
- **Audio routing modes** - Bind to Input, Bind to Output, Matrix Mode
- **Audio source selection** - Route audio from any input or ARC source

### EDID Management
- **39 EDID presets** - Comprehensive EDID options from 1080p to 8K
- **Copy EDID** - Copy EDID from connected displays to inputs
- **Custom EDID** - 3 user-uploadable EDID slots

### CEC Control
- **Input CEC commands** - Power, menu navigation, playback, volume
- **Output CEC commands** - Power, volume, active source

### System
- **Power control** - Turn the matrix on/off
- **Panel lock** - Lock/unlock front panel buttons
- **Beep control** - Enable/disable button feedback sounds
- **LCD logo** - Customize the LCD display text
- **LCD timeout** - Configure screen timeout
- **Reboot/Reset** - Restart or factory reset the device

### Diagnostics
- **Connection status** - Monitor input/output connection states
- **Device information** - Model, firmware version, IP/MAC address

## Supported Devices

- **Orei BK-808** - 8x8 HDMI 2.1 Matrix with Audio Extraction

This integration may work with other Orei matrices that use the same command protocol.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/your-github-username/ha-orei-matrix`
5. Select "Integration" as the category
6. Click "Add"
7. Search for "Orei HDMI Matrix" and install
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Extract the `custom_components/orei_matrix` folder
3. Copy it to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant

## Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Orei HDMI Matrix"
4. Enter the IP address of your matrix
5. Optionally adjust the port (default: 8000) and device name

### Options

After setup, you can configure:
- **Update interval** - How often to poll the device (5-300 seconds)

## Entities Created

The integration creates the following entities for your matrix:

### Switches
| Entity | Description |
|--------|-------------|
| Power | Main power switch |
| Beep | Enable/disable button sounds |
| Panel Lock | Lock front panel buttons |
| Output X Stream | Enable/disable video output |
| Output X ARC | Enable/disable Audio Return Channel |
| Output X External Audio | Enable/disable audio extraction |

### Selects
| Entity | Description |
|--------|-------------|
| Output X Source | Select input source (1-8) |
| Output X HDCP | HDCP mode selection |
| Output X Scaler | Resolution scaler mode |
| Output X HDR Mode | HDR handling mode |
| Input X EDID | EDID preset selection |
| Output X Ext Audio Source | Audio source for extraction |
| External Audio Mode | Global audio routing mode |
| LCD On Time | Screen timeout setting |

### Buttons
| Entity | Description |
|--------|-------------|
| Reboot | Restart the device |
| Factory Reset | Reset to factory defaults |
| Save Preset 1-8 | Save current routing |
| Recall Preset 1-8 | Load saved routing |
| Clear Preset 1-8 | Delete saved routing |
| Route All to Input 1-8 | Quick routing shortcuts |
| Input/Output X CEC commands | CEC control buttons |

### Sensors
| Entity | Description |
|--------|-------------|
| Input X Status | Connection status |
| Output X Status | Connection status |
| Output X Current Source | Currently selected input |
| Model | Device model number |
| Firmware Version | Current firmware |
| IP Address | Network address |
| MAC Address | Hardware address |

### Text
| Entity | Description |
|--------|-------------|
| LCD Logo | Custom display text |

## Services

The integration provides the following services for advanced automation:

### `orei_matrix.send_command`
Send a raw command to the matrix.

```yaml
service: orei_matrix.send_command
data:
  device_id: "your_device_id"
  command: "status!"
```

### `orei_matrix.set_routing`
Route an input to a specific output.

```yaml
service: orei_matrix.set_routing
data:
  device_id: "your_device_id"
  output: 1
  input: 3
```

### `orei_matrix.set_all_routing`
Route all outputs to a single input.

```yaml
service: orei_matrix.set_all_routing
data:
  device_id: "your_device_id"
  input: 2
```

### `orei_matrix.save_preset`
Save current routing to a preset slot.

```yaml
service: orei_matrix.save_preset
data:
  device_id: "your_device_id"
  preset: 1
```

### `orei_matrix.recall_preset`
Recall a saved preset.

```yaml
service: orei_matrix.recall_preset
data:
  device_id: "your_device_id"
  preset: 1
```

### `orei_matrix.cec_command`
Send a CEC command to connected devices.

```yaml
service: orei_matrix.cec_command
data:
  device_id: "your_device_id"
  target_type: "output"
  target_number: 1
  command: "on"
```

### `orei_matrix.copy_edid`
Copy EDID from an output to inputs.

```yaml
service: orei_matrix.copy_edid
data:
  device_id: "your_device_id"
  input: 0  # 0 = all inputs
  output: 1
```

## Example Automations

### Switch to Gaming PC when PS5 turns on
```yaml
automation:
  - alias: "Auto-switch to Gaming TV"
    trigger:
      - platform: state
        entity_id: sensor.orei_matrix_input_1_status
        to: "Connected"
    action:
      - service: select.select_option
        target:
          entity_id: select.orei_matrix_output_1_source
        data:
          option: "Input 1"
```

### Movie night preset with CEC
```yaml
script:
  movie_night:
    sequence:
      - service: orei_matrix.recall_preset
        data:
          device_id: "your_device_id"
          preset: 1
      - service: orei_matrix.cec_command
        data:
          device_id: "your_device_id"
          target_type: "output"
          target_number: 0  # All outputs
          command: "on"
```

### Dashboard button card
```yaml
type: button
name: "All to Apple TV"
icon: mdi:apple
tap_action:
  action: call-service
  service: orei_matrix.set_all_routing
  data:
    device_id: "your_device_id"
    input: 4
```

## Network Configuration

The matrix uses TCP/IP for communication:
- **Default Port:** 8000
- **Protocol:** ASCII commands
- **Connection:** Persistent TCP socket

Ensure your matrix has a static IP address or DHCP reservation for reliable operation.

## Troubleshooting

### Cannot connect to matrix
- Verify the IP address is correct
- Ensure port 8000 is not blocked by firewall
- Check that the matrix is powered on and connected to the network
- Try accessing the matrix via Telnet to verify connectivity

### Entities show unavailable
- Check network connectivity
- Verify the matrix hasn't entered power saving mode
- Review Home Assistant logs for error messages

### Commands not responding
- The matrix may need a brief delay between commands
- Try reducing the polling interval if commands are being dropped

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This integration is not affiliated with or endorsed by Orei. Use at your own risk.

## Credits

- Developed for the Home Assistant community
- Protocol documentation from Orei BK-808 user manual
