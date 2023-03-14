from dataclasses import dataclass

from pysmx.hid.pipe import send_command
from pysmx.sdk.config import SMXStageConfig
from pysmx.sdk.device_info import SMXDeviceInfo


# StepManiaX API Commands
SMX_API_CMD_GET_DEVICE_INFO = b"i"
SMX_API_CMD_GET_CONFIG = b"g"
SMX_API_CMD_GET_CONFIG_V5 = b"G"
SMX_API_CMD_FACTORY_RESET = b"f"
SMX_API_CMD_SET_LIGHT_STRIP = b"L"

# StepManiaX Special API Commands
SMX_API_SPECIAL_CMD_GET_DEVICE_INFO = b"devinfo"
SMX_API_SPECIAL_CMD_GET_INPUTS = b"input"


# TODO: This might make more sense to put in a different file?
@dataclass
class SMXStageInputs(object):
    down_left: bool
    down: bool
    down_right: bool
    left: bool
    center: bool
    right: bool
    up_left: bool
    up: bool
    up_right: bool


def smx_get_device_info(pad: int) -> SMXDeviceInfo:
    data = send_command(pad, SMX_API_CMD_GET_DEVICE_INFO, has_output=True)
    return SMXDeviceInfo.from_bytes(data)


def smx_get_device_info_anytime(pad: int) -> SMXDeviceInfo:
    data = send_command(pad, SMX_API_SPECIAL_CMD_GET_DEVICE_INFO, has_output=True)
    return SMXDeviceInfo.from_bytes(data)


def smx_get_inputs(pad: int) -> SMXStageInputs:
    data = send_command(pad, SMX_API_SPECIAL_CMD_GET_INPUTS, has_output=True)
    return SMXStageInputs(*map(bool, list(data)))


def smx_get_stage_config(
    pad: int, device_info: SMXDeviceInfo | None = None
) -> SMXStageConfig:
    if device_info is None:
        device_info = smx_get_device_info(pad)

    # Determine proper command based on firmware version
    cmd = SMX_API_CMD_GET_CONFIG
    if device_info.firmware_version >= 5:
        cmd = SMX_API_CMD_GET_CONFIG_V5

    data = send_command(pad, cmd, has_output=True)

    # TODO: We can probably delete this at some point
    assert data[0] == ord(cmd)

    data_len = len(data)
    payload_size = data[1]

    # This command reads back the configuration we wrote with "w" or the defaults if we
    # haven't written any
    # TODO: Should we return default SMXStageConfig when we fail?
    if data_len < 2:
        print("Communication error: Invalid Configuration Packet")
        return SMXStageConfig()

    if data_len < payload_size + 2:
        print("Communication error: Invalid Configuration Packet Size")
        return SMXStageConfig()

    # TODO: Handle the old format "g" and convert to new format

    # Trim to the payload_size
    # Currently this seems to return 251 bytes. The last byte seems to be '\n'
    return SMXStageConfig.from_packed_bytes(data[2 : payload_size + 2])


def smx_factory_reset(pad: int, device_info: SMXDeviceInfo | None = None) -> None:
    if device_info is None:
        device_info = smx_get_device_info(pad)

    # Send a factory reset command, and then read the new configuration
    send_command(pad, SMX_API_CMD_FACTORY_RESET)
    print("Factory Reset")

    config = smx_get_stage_config(pad, device_info=device_info)

    # Factory reset resets the platform strip color saved to the configuration, but it
    # doesn't apply it to the lights.
    # Do this for firmware v5 and up.
    if device_info.firmware_version >= 5:
        led_strip_index = 0  # Always 0
        number_of_leds = 44
        light_cmd = [ord(SMX_API_CMD_SET_LIGHT_STRIP), led_strip_index, number_of_leds]

        for _ in range(number_of_leds):
            light_cmd.extend(config.platform_strip_color)

    send_command(pad, bytes(light_cmd))
