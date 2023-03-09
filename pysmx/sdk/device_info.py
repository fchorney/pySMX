import struct
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class SMXDeviceInfo(object):
    """
    SMXDeviceInfo contains device information for the requested stage.

    This will tell us what the stages Serial Number, Firmware Version, and Player
    settings are set to.
    """

    serial: str
    firmware_version: int
    player: int

    # Struct is expected to be 23 bytes long
    # fmt: off
    STRUCT_FMT: ClassVar[str] = (
        "<"    # Little Endian
        "c"    # `cmd`: Always 'I'
        "B"    # `packet_size`: Not Used
        "c"    # `player`: '0' for P1 and '1' for P2
        "c"    # `unused2`: Not Used
        "16B"  # `serial`: 16 Byte Serial Number
        "H"    # `firmware_version`: Firmware Version
        "c"    # `unused3`: Not Used, always '\n'
    )
    # fmt: on

    @classmethod
    def from_bytes(cls, data: bytes) -> "SMXDeviceInfo":
        unpacked = struct.unpack(cls.STRUCT_FMT, data)

        # Player is the 2nd byte. We add 1 to it so we have 1 and 2 instead of 0 and 1
        player = int(unpacked[2]) + 1

        # Serial Number is a Hex Encoded string for all values in the packet
        serial = "".join([f"{x:02X}" for x in unpacked[4:20]])

        # Firmware version exists in byte 20
        firmware_version = unpacked[20]

        return SMXDeviceInfo(serial, firmware_version, player)
