import asyncio
import errno
import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import hid


SMX_USB_VENDOR_ID = 0x2341
SMX_USB_PRODUCT_ID = 0x8037
SMX_USB_PRODUCT_NAME = "StepManiaX"

PIPE_DIR = Path(__file__).parent / "pipes"
IN_PIPE = PIPE_DIR / "input"
OUT_PIPE = PIPE_DIR / "output"

INPUT_STATE = {
    0: False,
    1: False,
    2: False,
    3: False,
    4: False,
    5: False,
    6: False,
    7: False,
    8: False,
    9: False,
}


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


@dataclass
class SMXDeviceInfo(object):
    serial: str
    firmware_version: int
    player: int

    @classmethod
    def from_int_array(cls, data: list[int]) -> "SMXDeviceInfo":
        struct_fmt = "<cBcc16BHc"
        data_info_packet = struct.unpack(struct_fmt, bytes(data))
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


PACKET_FLAG_START_OF_COMMAND = 0x04
PACKET_FLAG_END_OF_COMMAND = 0x01
PACKET_FLAG_HOST_CMD_FINISHED = 0x02
PACKET_FLAG_DEVICE_INFO = 0x80


async def make_send_packets(cmd: str) -> list[list[int]]:
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
        packet.extend(ord(x) for x in cmd[i : i + packet_size])

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
                    print(data)
                    cmd = data
            except OSError as err:
                if err.errno == errno.EAGAIN or err.errno == errno.EWOULDBLOCK:
                    cmd = None
                else:
                    raise
            if cmd is not None:
                if cmd == b"gotem":
                    packets = [make_device_info_packet()]
                elif cmd == b"input":
                    print(INPUT_STATE)
                    cmd = None
                else:
                    packets = await make_send_packets(cmd.decode("UTF-8"))

                # This is just a hack to allow for some custom commands
                if cmd is not None:
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
            print(f"Current Packet [{len(cp)}]: {cp}")
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
            info = SMXDeviceInfo.from_int_array(data)
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
            if len(current_packet) != 0:
                current_packet.append(-69)


async def run(dev):
    queue = asyncio.Queue()

    # Make sure device is blocking
    result = dev.set_nonblocking(False)
    print(f"Set Nonblocking: {result}")

    await asyncio.gather(write_usb(dev), read_usb(queue, dev), handle_usb(queue))


def get_smx_stage_info(device: SMXHIDDevice) -> str:
    with device.open() as dev:
        c = dev.write("f\n".encode("UTF-8"))
        print(f"Wrote {c} bytes")

        data = dev.read(24)
        print(data)

        sret = "".join([chr(x) for x in data])
        print(sret)

    return "gotem"
