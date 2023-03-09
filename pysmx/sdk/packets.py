from contextlib import contextmanager
from dataclasses import dataclass
from time import monotonic_ns

import hid
from loguru import logger

from pysmx.exceptions import SMXPacketTimeoutError, SMXStageHIDError
from pysmx.utils import pad_list, s_to_ns


# USB Communication Packet Flags
PACKET_FLAG_START_OF_COMMAND = 0x04
PACKET_FLAG_END_OF_COMMAND = 0x01
PACKET_FLAG_HOST_CMD_FINISHED = 0x02
PACKET_FLAG_DEVICE_INFO = 0x80

# HID Report Codes
HID_REPORT_INPUT = 0x03
HID_REPORT_COMMAND = 0x06


# Special Packets
EMPTY_PACKET = pad_list([5, 5], 64)
ACK_PACKET = pad_list([6, 7], 64)


@dataclass
class SMXHID(object):
    vendor_id: int
    product_id: int
    serial_number: str

    def _device(self):
        connected = False
        retries = 3
        try_count = 0

        # We need to use serial number here because vendor and product id's are the same
        # for all stages
        d = hid.device()
        while True:
            try:
                d.open(self.vendor_id, self.product_id, self.serial_number)
                connected = True
            except OSError:
                logger.warning(f"Could not open HID device: {self}")

            if connected or (try_count := try_count + 1) == retries:
                break

        if try_count == retries:
            logger.error(f"Could not connect to HID device after {retries} trys")
            raise SMXStageHIDError()
        return d

    @contextmanager
    def open(self, /, non_blocking=True):
        d = self._device()

        rc = d.set_nonblocking(non_blocking)
        logger.debug(f"Set HID Device to Non-Blocking: {rc}")

        try:
            yield d
        finally:
            d.close()


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
        if (idx := idx + packet_size) >= cmd_len:
            break

    return packets


def handle_packet(packet: list[int], current_packet: list[int], report_id: int) -> bool:
    # If packet is finished, return True
    if not packet:
        return False

    packet_report_id = packet[0]
    if packet_report_id == report_id == HID_REPORT_INPUT:
        # Input State.
        # We don't need to send any special command to get this info, it just gets sent
        # over constantly.

        # We have 16-Bits to define 9 inputs. Throw both bytes into a single int
        input_state = ((packet[2] & 0xFF) << 8) | ((packet[1] & 0xFF) << 0)

        # Use bitwise operations to grab the 9 input states
        for i in range(9):
            current_packet.append((input_state & (1 << i)) != 0)

        # Signal that the packet is done
        return True

    if packet_report_id == report_id == HID_REPORT_COMMAND:
        # A HID serial packet
        if len(packet) < 3:
            return False

        cmd = packet[1]
        byte_len = packet[2]

        if cmd & PACKET_FLAG_DEVICE_INFO == PACKET_FLAG_DEVICE_INFO:
            # This is a response to RequestDeviceInfo. Since any application can send
            # this, we ignore the packet if we didn't request it, since it might be
            # requested for a different program.
            # TODO: We need a way to tell this function if we are doing a
            # RequestDeviceInfo, so we can ignore any other ones.
            # This is kind of annoying because I don't want to just throw another
            # argument into this function >:|
            pass

        if (3 + byte_len) > len(packet):
            print("Communication error: oversized packet (ignored)")
            return False

        data = packet[3 : 3 + byte_len]

        if cmd & PACKET_FLAG_START_OF_COMMAND == PACKET_FLAG_START_OF_COMMAND and len(current_packet) > 0:
            # When we get a start packet, the read buffer should already be empty. If it
            # isn't, we got a command that didn't end with an END_OF_COMMAND packet and
            # something is wrong. This shouldn't happen, so warn about it and recover by
            # clearing the junk in the buffer.
            print(f"Got PACKET_FLAG_START_OF_COMMAND, but we had {len(current_packet)} " "bytes in the read buffer")
            current_packet.clear()

        current_packet.extend(data)

        # Note that if PACKET_FLAG_HOST_CMD_FINISHED is set, PACKET_FLAG_END_OF_COMMAND
        # will always also be set
        if cmd & PACKET_FLAG_HOST_CMD_FINISHED == PACKET_FLAG_HOST_CMD_FINISHED:
            # This tells us that a command we wrote to the device has finished
            # executing, and it's safe to start writing another.
            logger.debug("Packet Complete")

        if cmd & PACKET_FLAG_END_OF_COMMAND == PACKET_FLAG_END_OF_COMMAND:
            return True

    return False


def send_packets(
    hid: SMXHID,
    packets: list[list[int]],
    acknowledge: bool,
    report_id: int,
) -> bytes:
    current_packet: list[int] = []
    timeout_seconds = s_to_ns(3)
    current_time = monotonic_ns()

    with hid.open() as dev:
        for packet in packets:
            if packet != EMPTY_PACKET:
                logger.debug(f"Sending Packet: {packet}")
                count = dev.write(packet)

                assert count == len(packet)

        # We are either expecting resulting data, or an acknowledgement
        while True:
            # If we don't get a response we expect in timeout_seconds, then error
            # out
            if monotonic_ns() - current_time >= timeout_seconds:
                logger.error(f"Packet {packet} timed out")
                raise SMXPacketTimeoutError()

            # Grab the raw data from the HID device. Continue if it is empty
            raw_data = dev.read(64)
            if len(raw_data) == 0:
                continue

            logger.debug(f"RAW DATA: {raw_data}")

            # If we are expecting an acknowledgement, check if the raw_data is equal to
            # an acknowledgemenet packet
            if acknowledge and raw_data == ACK_PACKET:
                break

            # Else we parse the packet until it is finished
            if handle_packet(raw_data, current_packet, report_id):
                break

        # We have our response packet
        logger.debug(f"Current Packet [Length: {len(current_packet)}] {current_packet}")
        return bytes(current_packet)
