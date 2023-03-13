import asyncio
import errno
import os
from contextlib import contextmanager
from dataclasses import dataclass

import hid

from pysmx.hid.pipe import IN_PIPE, OUT_PIPE, PIPE_READ_BUFFER_SIZE
from pysmx.sdk.device_info import SMXDeviceInfo


# StepManiaX Stage Hardware Identification
SMX_USB_VENDOR_ID = 0x2341
SMX_USB_PRODUCT_ID = 0x8037
SMX_USB_PRODUCT_NAME = "StepManiaX"

# USB Communication Packet Flags
PACKET_FLAG_START_OF_COMMAND = 0x04
PACKET_FLAG_END_OF_COMMAND = 0x01
PACKET_FLAG_HOST_CMD_FINISHED = 0x02
PACKET_FLAG_DEVICE_INFO = 0x80


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


def make_send_packets(cmd: bytes) -> list[list[int]]:
    packets: list[list[int]] = []
    cmd_len = len(cmd)
    idx = 0

    while True:
        flags = 0
        packet_size = min(cmd_len - idx, 61)

        if idx == 0:
            # This is the first packet we're sending
            flags |= PACKET_FLAG_START_OF_COMMAND

        if idx + packet_size == cmd_len:
            # This is the last packet we're sending
            flags |= PACKET_FLAG_END_OF_COMMAND

        # Report ID / Flags / Packet Size
        packet = [5, flags, packet_size]

        # Add command data
        packet.extend(cmd[idx : idx + packet_size])

        # Pad command to 64 bytes
        packet.extend([0 for idx in range(64 - len(packet))])

        packets.append(packet)

        # Once we have all packets generated, break out
        if idx := idx + packet_size >= cmd_len:
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
                data = fd.read(PIPE_READ_BUFFER_SIZE)
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
                send_packet = True

                # Add Custom Commands Here so we can bypass `make_send_packets`
                if cmd == b"devinfo":
                    packets = [make_device_info_packet()]
                elif cmd == b"input":
                    # Get the pad input
                    # Just write the result to the OUT_PIPE here
                    send_packet = False

                    # We can send back 9 ints where 1 = true and 0 = false
                    with OUT_PIPE.open("wb") as f:
                        f.write(bytes([0, 0, 0, 0, 0, 0, 0, 0, 0]))
                else:
                    packets = make_send_packets(cmd)

                if send_packet:
                    for packet in packets:
                        print(f"Sending Packet: {packet}")
                        dev.write(packet)
                cmd = None
            await asyncio.sleep(0.00001)


async def read_usb(queue, dev):
    """
    Producer:

    Read from the USB Device constantly and put any ata into the async queue
    """
    while True:
        data = dev.read(64)
        await queue.put(data)

        data = None
        await asyncio.sleep(0.00001)


async def handle_usb(queue):
    """
    Consumer:

    Consume any data in the async queue and build the packets received.
    """
    current_packet = []
    while True:
        item = await queue.get()
        handle_packet(item, current_packet)

        # TODO: -69 in a sentinel value, maybe put this in a const
        if current_packet and current_packet[-1] == -69:
            cp = current_packet[:-1]

            if len(cp) == 0:
                print("Acknowledged")

                # Send Sentinel value
                # TODO: Make this a const?
                cp = [0]
            else:
                print(f"Current Packet [{len(cp)}]: {cp}")

            # Write the packet bytes to the OUT Pipe
            with OUT_PIPE.open("wb") as f:
                f.write(bytes(cp))
            current_packet.clear()
        await asyncio.sleep(0.00001)


def handle_packet(packet: list[int], current_packet: list[int]) -> None:
    if not packet:
        return

    report_id = packet[0]
    if report_id == 3:
        pass
        # Input State.
        # We could also read this as a normal HID button change.
        # input_state = ((packet[2] & 0xFF) << 8) | ((packet[1] & 0xFF) << 0)

        # for i in range(9):
        #   INPUT_STATE[i] = (input_state & (1 << i)) != 0

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
            info = SMXDeviceInfo.from_bytes(bytes(data))
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
