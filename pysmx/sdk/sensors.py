import struct
from dataclasses import dataclass, field
from enum import IntEnum
from typing import ClassVar

from pysmx.utils import BytesEnum


class SensorTestMode(BytesEnum):
    OFF = b"\0"

    # Return the raw, uncalibrated value of each sensor
    UNCALIBRATED_VALUES = b"0"

    # Return the calibrated value of each sensor
    CALIBRATED_VALUES = b"1"

    # Return the sensor noise value
    NOISE = b"2"

    # Return the sensor tare value
    TARE = b"3"


class PanelTestMode(BytesEnum):
    # The values also correspond with the protocol and must not be changed.
    # These are panel-side diagnostics modes
    OFF = b"0"
    PRESSURE_TEST = b"1"


# TODO: This might be backwards?
class Panel(IntEnum):
    DOWN_LEFT = 0
    DOWN = 1
    DOWN_RIGHT = 2
    LEFT = 3
    CENTER = 4
    RIGHT = 5
    UP_LEFT = 6
    UP = 7
    UP_RIGHT = 8


# TODO: This might be different
class Sensor(IntEnum):
    UP = 0
    RIGHT = 1
    DOWN = 2
    LEFT = 3


@dataclass
class SMXDetailData(object):
    sig1: bool
    sig2: bool
    sig3: bool
    bad_sensor_0: bool
    bad_sensor_1: bool
    bad_sensor_2: bool
    bad_sensor_3: bool
    dummy: bool
    sensors: list[int]
    dip: int  # 4 bits
    bad_sensor_dip_0: bool
    bad_sensor_dip_1: bool
    bad_sensor_dip_2: bool
    bad_sensor_dip_3: bool

    # fmt: off
    STRUCT_FMT: ClassVar[str] = (
        "<"
        "8?"
        "4h"
        "B"
        "4?"
    )
    # fmt: on

    @classmethod
    def from_packed_bytes(cls, data: bytes) -> "SMXDetailData":
        new_data: list[int] = []

        # First 8 bits are all bools
        for i in range(8):
            new_data.append(1 if data[0] & (1 << i) else 0)

        # The next 8 bytes are int16's in Little Endian mode
        for i in range(1, 9, 2):
            new_data.append(data[i])
            new_data.append(data[i + 1])

        # The last byte is split into 2 nibbles.
        # The first nibble is 4 bits for the dip switch
        new_data.append(data[9] & 0x0F)

        # The last nibble is 4 bools for bad sensor dip
        for i in range(4, 8):
            new_data.append(1 if data[9] & (1 << i) else 0)

        unpacked = list(struct.unpack(cls.STRUCT_FMT, bytes(new_data)))

        (
            sig1,
            sig2,
            sig3,
            bad_sensor_0,
            bad_sensor_1,
            bad_sensor_2,
            bad_sensor_3,
            dummy,
        ) = unpacked[0:8]
        sensors = unpacked[8:12]
        dip = unpacked[12]
        (
            bad_sensor_dip_0,
            bad_sensor_dip_1,
            bad_sensor_dip_2,
            bad_sensor_dip_3,
        ) = unpacked[13:17]

        return SMXDetailData(
            sig1,
            sig2,
            sig3,
            bad_sensor_0,
            bad_sensor_1,
            bad_sensor_2,
            bad_sensor_3,
            dummy,
            sensors,
            dip,
            bad_sensor_dip_0,
            bad_sensor_dip_1,
            bad_sensor_dip_2,
            bad_sensor_dip_3,
        )


@dataclass
class SMXSensorTestData(object):
    """
    Data for the current `SensorTestMode`. The interpretation of the sensor_level
    depends on the mode.
    """

    # If false, sensor_level[n][*] is zero because we didn't receive a response from
    # that panel
    have_data_from_panel: list[bool] = field(default_factory=list)  # 9 Panels

    # Sensor data. Interpretation depends on the mode
    # TODO: All of these 9 * 4 lists could maybe be their own class?
    sensor_level: list[list[int]] = field(default_factory=lambda: [[] for _ in range(9)])  # 9 Panels, 4 Sensors

    # TODO: Find out what this means
    bad_sensor_input: list[list[int]] = field(default_factory=lambda: [[] for _ in range(9)])  # 9 Panels, 4 Sensors

    # The DIP switch settings on each panel. This is used for diagnostics displays.
    dip_switch_per_panel: list[int] = field(default_factory=list)  # 9 Panels

    # Bad sensor selection jumper indication for each panel
    bad_jumper: list[list[int]] = field(default_factory=lambda: [[] for _ in range(9)])  # 9 Panels, 4 Sensors

    @classmethod
    def from_detail_data(cls, data: list[SMXDetailData]) -> "SMXSensorTestData":
        have_data_from_panel: list[bool] = []
        sensor_level: list[list[int]] = []
        bad_sensor_input: list[list[int]] = []
        dip_switch_per_panel: list[int] = []
        bad_jumper: list[list[int]] = []

        for panel in range(9):
            pad = data[panel]
            # Check the header. this is always `0 1 0` to identify it as a response, and
            # not as random steps from the player.
            # TODO: I wonder if this is really necessary?
            if pad.sig1 != 0 or pad.sig2 != 1 or pad.sig3 != 0:
                have_data_from_panel.append(False)
                continue

            # Looks like we have a proper set of data
            have_data_from_panel.append(True)

            # These bits are true if that sensor's most recent reading is invalid
            bad_sensor_input.append([pad.bad_sensor_0, pad.bad_sensor_1, pad.bad_sensor_2, pad.bad_sensor_3])

            dip_switch_per_panel.append(pad.dip)

            bad_jumper.append(
                [
                    pad.bad_sensor_dip_0,
                    pad.bad_sensor_dip_1,
                    pad.bad_sensor_dip_2,
                    pad.bad_sensor_dip_3,
                ]
            )

            sensor_level.append(pad.sensors)

        return SMXSensorTestData(
            have_data_from_panel,
            sensor_level,
            bad_sensor_input,
            dip_switch_per_panel,
            bad_jumper,
        )
