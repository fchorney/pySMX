import asyncio
import errno
import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field
from os import mkfifo
from pathlib import Path
from typing import ClassVar

import hid


# StepManiaX Stage Hardware Identification
SMX_USB_VENDOR_ID = 0x2341
SMX_USB_PRODUCT_ID = 0x8037
SMX_USB_PRODUCT_NAME = "StepManiaX"

# USB Communication Packet Flags
PACKET_FLAG_START_OF_COMMAND = 0x04
PACKET_FLAG_END_OF_COMMAND = 0x01
PACKET_FLAG_HOST_CMD_FINISHED = 0x02
PACKET_FLAG_DEVICE_INFO = 0x80

# FIFO Pipe Locations
PIPE_DIR = Path(__file__).parent / "pipes"
IN_PIPE = PIPE_DIR / "input"
OUT_PIPE = PIPE_DIR / "output"


@dataclass
class SMXDeviceInfo(object):
    serial: str
    firmware_version: int
    player: int

    @classmethod
    def from_int_list(cls, data: list[int]) -> "SMXDeviceInfo":
        return cls.from_bytes(bytes(data))

    @classmethod
    def from_bytes(cls, data: bytes) -> "SMXDeviceInfo":
        struct_fmt = "<cBcc16BHc"
        data_info_packet = struct.unpack(struct_fmt, data)
        return SMXDeviceInfo(
            "".join([f"{x:02X}" for x in data_info_packet[4:20]]),
            data_info_packet[20],
            int(data_info_packet[2]) + 1,
        )

    def __str__(self):
        return (
            f'SMXDeviceInfo<serial: "{self.serial}", firmware_version: '
            f"{self.firmware_version}, player: {self.player}>"
        )


def send_command(pad: int, cmd: bytes, /, has_output: bool = False) -> bytes:
    # Make sure the input and output FIFOs exist
    if not IN_PIPE.is_fifo():
        mkfifo(str(IN_PIPE))
    if not OUT_PIPE.is_fifo():
        mkfifo(str(OUT_PIPE))

    # Write the command to the INPUT FIFO
    with IN_PIPE.open("wb") as f:
        f.write(str(pad).encode("UTF-8") + b":" + cmd)

    # Sit and wait for the result
    while True:
        data = b""
        with OUT_PIPE.open("rb") as f:
            data = f.read(4096)

        # If we expect a non empty response, keep checking the pipe until we get one
        # TODO: Maybe add a timeout here?
        if not has_output:
            break
        else:
            # Using a single 0 as sentinel data
            if len(data) != 1 or data[0] != 0:
                break

    return data


def api_get_device_info(pad: int) -> SMXDeviceInfo:
    data = send_command(pad, b"i", has_output=True)
    return SMXDeviceInfo.from_bytes(data)


@dataclass
class PackedSensorSettings(object):
    # Load Cell Thresholds
    load_cell_low_threshold: int
    load_cell_high_threshold: int

    # FSR Thresholds
    fsr_low_threshold: list[int]  # 4 values
    fsr_high_threshold: list[int]  # 4 values

    combined_low_threshold: int
    combined_high_threshold: int

    # This must be left unchanged
    reserved: int

    STRUCT_FMT: ClassVar[str] = (
        "<"  # Little Endian
        "B"  # loadCellLowThreshold
        "B"  # loadCellHighThreshold
        "4B"  # fsrLowThreshold
        "4B"  # fsrHighThreshold
        "H"  # combinedLowThreshold
        "H"  # combinedHighThreshold
        "H"  # reserved
    )

    @classmethod
    def from_int_list(cls, data: list[int]) -> "PackedSensorSettings":
        """
        We expect 13 values in the list
        """
        return PackedSensorSettings(
            data[0], data[1], data[2:6], data[6:10], data[10], data[11], data[12]
        )


@dataclass
class SMXStageConfig(object):
    # The firmware version of the master controller. Where supported (version 2 and up),
    # this will always read back the firmware version. This will defalt to 0xFF on
    # version 1, and we'll always write 0xFF here so it doesn't change on that firmware
    # version.
    # We don't need this since we can read the 'I' command which also reports the
    # version, but this allows panels to also know the master version.
    master_version: int = 0xFF

    # The version of this config packet. This can be used by the firmware to know which
    # values have been filled in. Any values not filled in will always be 0xFF, which
    # can be tested for, but that doesn't work for values where 0xFF is a valid value.
    # This value is unrelated to the firmware version, and just indicates which fields
    # in this packet have been set.
    # Note that we don't need to increase this any time we add a field, only when it's
    # important that we be able to tell if a field is set or not.
    #
    # Versions:
    # - 0xFF: This is a config packet from before configVersion was added.
    # - 0x00: configVersion added
    # - 0x02: panelThreshold0Low through panelThreshold8High added
    # - 0x03: debounceDelayMs added
    config_version: int = 0x05

    # Packed flags (master_version >= 4)
    flags: int = 0

    # Panel thresholds are labelled by their numpad position. Eg: Panel8 is up.
    # If SMXDeviceInfo.firmware_version is 1, Panel7 corresponds to all of Up, Down,
    # Left, and Right, and Panel2 corresponds to UpLeft, UpRight, DownLeft, and
    # DownRight. For later firmware versions, each panel is configured independently.
    # Setting a value to 0xFF disables that threshold.

    # These are internal tunables and should be left unchanged
    debounce_no_delay_milliseconds: int = 0
    debounce_delay_milliseconds: int = 0
    panel_debounce_microseconds: int = 4000
    auto_calibration_max_deviation: int = 100
    bad_sensor_minimum_delay_seconds: int = 15
    auto_calibration_averages_per_update: int = 60
    auto_calibration_samples_per_average: int = 500

    # The maximum tare value to calibrate to (except on startup)
    auto_calibration_max_tare: int = 0xFFFF

    # Which sensors on each panel to enable. This can be used to disable sensors that we
    # know aren't populated. This is packed, with four sensors on two pads per byte:
    # enabled_sensors[0] & 1 is the first sensor on the first pad, and so on
    enabled_sensors: list[int] = field(default_factory=list)  # 5 panels

    # How long the master controller will wait for a lights command before assuming the
    # game has gone away and resume auto-lights. This is in 128ms units
    auto_lights_timeout: int = 1000 // 128  # 7.8125 units

    # The color to use for each panel when auto-lighting in master mode. This doesn't
    # apply when the pads are in autonomous lighting mode (no master), since they don't
    # store any configuration by themselves. These clors should be scaled to the 0 - 170
    # range
    step_color: list[int] = field(default_factory=list)  # 3 * 9 values

    # The default color to set the platform LED strip to
    platform_strip_color: list[int] = field(default_factory=list)  # 3 values

    # Which panels to enable auto-lighting for. Disabled panels will be unlit.
    # 0x01 = panel 0, 0x02 = panel 1, 0x04 = panel 2, etc. This only affects the master
    # controller's built-in auto lighting and not lights data sent from the SDK
    auto_light_panel_mask: int = 0xFFFF

    # The rotation of the panel, where 0 is the standard rotation, 1 means the panel is
    # rotated right 90 degrees, 2 is rotated 180 degrees, and 3 is rotated 270 degrees.
    # Note: This value is unused
    panel_rotation: int = 0x00

    # Per-panel sensor settings
    panel_settings: list[PackedSensorSettings] = field(default_factory=list)  # 9 panels

    # These are internal tunables and should be left unchanged
    pre_details_delay_milliseconds: int = 5

    # Pad the struct to 250 bytes. This keeps this struct size from changing as we add
    # fields, so the ABI doesn't change. Applications should leave any data in here
    # unchanged when calling api_set_config
    padding: list[int] = field(default_factory=list)  # 49 values

    # fmt: off
    STRUCT_FMT: ClassVar[str] = (
        (
            "<"  # Little Endian
            "B"  # masterVersion
            "B"  # configVersion
            "B"  # flags
            "H"  # debounceNodelayMilliseconds
            "H"  # demounceDelayMilliseconds
            "H"  # panelDebounceMicroseconds
            "B"  # autoCalibrationMaxDeviation
            "B"  # badSensorMinimumDelaySeconds
            "H"  # autoCalibrationAveragesPerUpdate
            "H"  # autoCalibrationSamplesPerAverage
            "H"  # autoCalibrationMaxTare
            "5B"  # enabledSensors (5)
            "B"  # autoLightsTimeout
            "27B"  # stepColor (3 * 9)
            "3B"  # platformStripColor (3)
            "H"  # autoLightPanelMask
            "B"  # panelRotation
        )
        + (9 * PackedSensorSettings.STRUCT_FMT[1:])
        + (
            "B"  # preDetailsDelayMilliseconds
            "49B"  # padding
        )
    )
    # fmt: on

    @classmethod
    def from_bytes(cls, data: bytes) -> "SMXStageConfig":
        unpacked = list(struct.unpack(cls.STRUCT_FMT, data))

        # PackedSensorSettings contains 13 values, and we need 9 PackedSensorSettings
        # objects.
        # We know the data starts at item 49, and we need 117 values total
        sensor_objects = 9
        sensor_value_count = 13
        sensor_items = sensor_value_count * sensor_objects
        sensor_idx = 49
        sensor_end_idx = sensor_idx + sensor_items
        p_sensor_data = unpacked[sensor_idx:sensor_end_idx]

        # Chop the data into `sensor_value_count` chunks, and pass them to a class
        # method to create the PackedSensorSettings objects
        packed_sensor_settings = [
            PackedSensorSettings.from_int_list(
                p_sensor_data[i : i + sensor_value_count]
            )
            for i in range(0, sensor_items, sensor_value_count)
        ]

        # TODO: This is kind of gross? Is there a better way to do this?
        return SMXStageConfig(
            unpacked[0],
            unpacked[1],
            unpacked[2],
            unpacked[3],
            unpacked[4],
            unpacked[5],
            unpacked[6],
            unpacked[7],
            unpacked[8],
            unpacked[9],
            unpacked[10],
            unpacked[11:16],
            unpacked[16],
            unpacked[17:44],
            unpacked[44:47],
            unpacked[47],
            unpacked[48],
            packed_sensor_settings,
            unpacked[166],
            unpacked[167:216],
        )


def api_read_config(
    pad: int, device_info: SMXDeviceInfo | None = None
) -> SMXStageConfig:
    # Get device info so we know what command to send
    # TODO: Save this with some sort of global pad object so we don't need to keep
    # asking for it
    if device_info is None:
        device_info = api_get_device_info(pad)

    cmd = b"G" if device_info.firmware_version >= 5 else b"g"
    data = send_command(pad, cmd, has_output=True)

    assert data[0] == ord(cmd)
    size = data[1]

    # This command reads back the configuration we wrote with "w" or the defaults if we
    # haven't written any
    if len(data) < 2:
        print("Communication error: invalid configuration packet")

    if len(data) < size + 2:
        print("Communication error: invalid configuration packet size")
        # Return the default?
        # TODO: Decide what makes the most sense here
        return SMXStageConfig()

    # TODO: Handle the old format "g" and convert to new format

    # Trim to the given size.
    # Currently this seems to return 251 bytes (with a new line at the end)
    return SMXStageConfig.from_bytes(data[2 : size + 2])


def api_factory_reset(pad: int) -> None:
    # Send a factory reset command, and then read the new configuration
    send_command(pad, b"f")
    print("Factory Reset")

    # Get device info so we know what command to send
    info = api_get_device_info(pad)

    # Grab the config
    config = api_read_config(pad, device_info=info)

    if info.firmware_version >= 5:
        # Factory reset resets the platform strip color saved to the configuration but
        # doesn't apply it to the lights. Do that now
        led_strip_index = 0  # Always 0
        number_of_leds = 44
        light_cmd: list[int] = [ord("L"), led_strip_index, number_of_leds]

        for i in range(44):
            light_cmd.extend(config.platform_strip_color)

        print(f"Light Cmd: {light_cmd}")

        data = send_command(pad, bytes(light_cmd))
        print(f"Light Cmd: {data.decode('UTF-8')}")


INPUT_STATE = {
    0: False,
    1: False,  # Up
    2: False,
    3: False,  # Left
    4: False,  # Center
    5: False,  # Right
    6: False,
    7: False,  # Down
    8: False,
}


@dataclass
class SMXStage(object):
    up_left: bool
    up: bool
    up_right: bool
    left: bool
    middle: bool
    right: bool
    down_left: bool
    down: bool
    down_right: bool

    def __str__(self):
        # Just show the 5 SMX panels. We can extend this to all 9 at a later time.
        return (
            f"SMXStage<up: {self.up}, left: {self.left}, middle: {self.middle}, "
            f"right: {self.right}, down: {self.down}>"
        )


@dataclass
class SMXHIDDevice(object):
    vendor_id: int
    product_id: int
    serial_number: str

    def make_device(self):
        d = hid.device()
        d.open(self.vendor_id, self.product_id, self.serial_number)

        return d

    @contextmanager
    def open(self):
        d = hid.device()
        d.open(self.vendor_id, self.product_id, self.serial_number)

        try:
            yield d
        finally:
            d.close()


def find_smx_devices() -> list[SMXHIDDevice]:
    """
    Find all StepManiaX Stage USB devices attached to the computer. If no devices are
    found, an empty list is returned.

    Returns:
        :obj:`list[SMXHIDDevice]`: List of StepManiaX Stage HID Devices
    """
    devices: list[SMXHIDDevice] = []

    # This should enumerate through 0 or more StepManiaX Stages
    for device_dict in hid.enumerate(SMX_USB_VENDOR_ID, SMX_USB_PRODUCT_ID):
        # Since StepManiaX uses the default Arduino IDs, let's check the product name to
        # make sure this isn't some other Arduino device.
        if device_dict["product_string"] != SMX_USB_PRODUCT_NAME:
            continue

        # Make a device object for each SMX Stage
        devices.append(
            SMXHIDDevice(
                device_dict["vendor_id"],
                device_dict["product_id"],
                device_dict["serial_number"],
            )
        )
    return devices


async def make_send_packets(cmd: bytes) -> list[list[int]]:
    packets: list[list[int]] = []
    i = 0

    while True:
        flags = 0
        packet_size = min(len(cmd) - i, 61)

        first_packet = i == 0
        if first_packet:
            flags |= PACKET_FLAG_START_OF_COMMAND

        last_packet = i + packet_size == len(cmd)
        if last_packet:
            flags |= PACKET_FLAG_END_OF_COMMAND

        # Report ID / Flags / Packet Size
        packet = [5, flags, packet_size]

        # Add command data as int
        packet.extend(x for x in cmd[i : i + packet_size])

        # Pad command to 64 bytes
        pad_amount = 64 - len(packet)
        packet.extend([0 for i in range(pad_amount)])

        packets.append(packet)

        i += packet_size

        # Once we have all packets generated, break out
        if i >= len(cmd):
            break

    return packets


def make_device_info_packet() -> list[int]:
    packet = [5, PACKET_FLAG_DEVICE_INFO, 0]
    packet.extend([0 for i in range(64 - len(packet))])

    return packet


async def write_usb(dev):
    cmd = None

    with IN_PIPE.open("rb") as fd:
        os.set_blocking(fd.fileno(), False)
        while True:
            try:
                data = fd.read(1024)
                if data != b"":
                    print(b"Writing Command: " + data)
                    cmd = data
            except OSError as err:
                if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                    cmd = None
                else:
                    raise
            if cmd is not None:
                # Pull Pad and CMD out
                pad, cmd = cmd.split(b":")

                packets = await make_send_packets(cmd)
                for packet in packets:
                    print(f"Sending Packet: {packet}")
                    dev.write(packet)
                cmd = None
            await asyncio.sleep(0.00001)


async def read_usb(queue, dev):
    while True:
        # print("P")
        data = dev.read(64)
        await queue.put(data)
        data = []
        await asyncio.sleep(0.00001)


async def handle_usb(queue):
    current_packet = []
    while True:
        # print("C")
        item = await queue.get()
        await handle_packet(item, current_packet)

        if current_packet and current_packet[-1] == -69:
            cp = current_packet[:-1]

            if len(cp) == 0:
                print("Acknowledged")
                cp = [0]
            else:
                print(f"Current Packet [{len(cp)}]: {cp}")

            # Write the packet bytes to the OUT Pipe
            with OUT_PIPE.open("wb") as f:
                f.write(bytes(cp))
            current_packet.clear()
        await asyncio.sleep(0.00001)


async def handle_packet(packet: list[int], current_packet: list[int]) -> None:
    if not packet:
        print("No Packet")
        return

    # str_packet = "".join([chr(x) for x in packet])
    # print(f"Packet to Str: {{{str_packet}}}")

    report_id = packet[0]
    # TODO: Use one of them fancy switches here?
    if report_id == 3:
        pass
        # Input State.
        # We could also read this as a normal HID button change.
        input_state = ((packet[2] & 0xFF) << 8) | ((packet[1] & 0xFF) << 0)

        for i in range(9):
            INPUT_STATE[i] = (input_state & (1 << i)) != 0

    elif report_id == 6:
        # A HID serial packet
        if len(packet) < 3:
            return

        cmd = packet[1]
        byte_len = packet[2]

        # print(f"CMD: {cmd}, Byte Len: {byte_len}")

        if (3 + byte_len) > len(packet):
            print("Communication error: oversized packet (ignored)")
            return

        data = packet[3 : 3 + byte_len]
        # print(f"Data: {data}")

        if cmd & PACKET_FLAG_DEVICE_INFO == PACKET_FLAG_DEVICE_INFO:
            info = SMXDeviceInfo.from_int_list(data)
            print(info)

        # If we're not active, ignore all packets other than device info. This is always
        # false while we're in Open() waiting for the device info response.
        # TODO: Define when we should be actively checking the USB output
        # if not active:
        #     return

        if (
            cmd & PACKET_FLAG_START_OF_COMMAND == PACKET_FLAG_START_OF_COMMAND
            and len(current_packet) > 0
        ):
            # When we get a start packet, the read buffer should already be empty. If it
            # isn't, we got a command that didn't end with an END_OF_COMMAND packet and
            # something is wrong. This shouldn't happen, so warn about it and recover by
            # clearing the junk in the buffer.
            print(
                f"Got PACKET_FLAG_START_OF_COMMAND, but we had {len(current_packet)} "
                "bytes in the read buffer"
            )
            current_packet.clear()

        current_packet.extend(data)

        # Note that if PACKET_FLAG_HOST_CMD_FINISHED is set, PACKET_FLAG_END_OF_COMMAND
        # will always also be set
        if cmd & PACKET_FLAG_HOST_CMD_FINISHED == PACKET_FLAG_HOST_CMD_FINISHED:
            # This tells us that a command we wrote to the device has finished
            # executing, and it's safe to start writing another.
            print("Current command is complete")

        if cmd & PACKET_FLAG_END_OF_COMMAND == PACKET_FLAG_END_OF_COMMAND:
            current_packet.append(-69)


async def run(dev):
    queue = asyncio.Queue()

    # Make sure device is blocking
    result = dev.set_nonblocking(False)
    print(f"Set Nonblocking: {result}")

    await asyncio.gather(write_usb(dev), read_usb(queue, dev), handle_usb(queue))
