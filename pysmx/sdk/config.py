import struct
from dataclasses import dataclass, field
from typing import ClassVar


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

    # Struct is expected to be 16 bytes long
    # fmt: off
    STRUCT_FMT: ClassVar[str] = (
        "<"   # Little Endian
        "B"   # loadCellLowThreshold
        "B"   # loadCellHighThreshold
        "4B"  # fsrLowThreshold
        "4B"  # fsrHighThreshold
        "H"   # combinedLowThreshold
        "H"   # combinedHighThreshold
        "H"   # reserved
    )
    # fmt: on

    @classmethod
    def from_unpacked_values(cls, data: list[int]) -> "PackedSensorSettings":
        """
        This constructor assumes that we have already unpacked the struct data.
        A packed struct would be 16 bytes, but unpacked we only have 13 values which is
        what we expect here.

        This data gets unpacked in the SMXStageConfig constructor
        """
        # Lets write out all the variables here just for clarity
        load_cell_low_threshold = data[0]
        load_cell_high_threshold = data[1]
        fsr_low_threshold = data[2:6]
        fsr_high_threshold = data[6:10]
        combined_low_threshold = data[10]
        combined_high_threshold = data[11]
        reserved = data[12]

        return PackedSensorSettings(
            load_cell_low_threshold,
            load_cell_high_threshold,
            fsr_low_threshold,
            fsr_high_threshold,
            combined_low_threshold,
            combined_high_threshold,
            reserved,
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
            "<"    # Little Endian
            "B"    # masterVersion
            "B"    # configVersion
            "B"    # flags
            "H"    # debounceNodelayMilliseconds
            "H"    # demounceDelayMilliseconds
            "H"    # panelDebounceMicroseconds
            "B"    # autoCalibrationMaxDeviation
            "B"    # badSensorMinimumDelaySeconds
            "H"    # autoCalibrationAveragesPerUpdate
            "H"    # autoCalibrationSamplesPerAverage
            "H"    # autoCalibrationMaxTare
            "5B"   # enabledSensors (5)
            "B"    # autoLightsTimeout
            "27B"  # stepColor (3 * 9)
            "3B"   # platformStripColor (3)
            "H"    # autoLightPanelMask
            "B"    # panelRotation
        )
        + (9 * PackedSensorSettings.STRUCT_FMT[1:])  # TODO: A better way to do this?
        + (
            "B"    # preDetailsDelayMilliseconds
            "49B"  # padding
        )
    )
    # fmt: on

    @classmethod
    def from_packed_bytes(cls, data: bytes) -> "SMXStageConfig":
        unpacked = list(struct.unpack(cls.STRUCT_FMT, data))

        # A PackedSensorSettings object contains 13 values, and we need to read in 9
        # PackedSensorSettings objects. One for each panel.
        # We know the data starts at item 49, and we need (9 * 13) values total
        # Note: According to the source SDK this shouldn't really change. If more values
        # get placed into the config, theoretically they would go in the extra padding
        # data at the end.
        sensor_objects = 9
        sensor_value_count = 13
        sensor_items = sensor_value_count * sensor_objects
        sensor_idx = 49
        sensor_end_idx = sensor_idx + sensor_items
        p_sensor_data = unpacked[sensor_idx:sensor_end_idx]

        # Chop the data into `sensor_value_count` chunks, and pass them to a class
        # method to create the PackedSensorSettings objects
        packed_sensor_settings = [
            PackedSensorSettings.from_unpacked_values(
                p_sensor_data[i : i + sensor_value_count]
            )
            for i in range(0, sensor_items, sensor_value_count)
        ]

        # For clarity, let's write out all the values here
        (
            master_version,
            config_version,
            flags,
            debounce_no_delay_milliseconds,
            debounce_delay_milliseconds,
            panel_debounce_microseconds,
            auto_calibration_max_deviation,
            bad_sensor_minimum_delay_seconds,
            auto_calibration_averages_per_update,
            auto_calibration_samples_per_average,
            auto_calibration_max_tare,
        ) = unpacked[0:11]
        enabled_sensors = unpacked[11:16]
        auto_lights_timeout = unpacked[16]
        step_color = unpacked[17:44]
        platform_strip_color = unpacked[44:47]
        auto_light_panel_mask = unpacked[47]
        panel_rotation = unpacked[48]
        pre_details_delay_milliseconds = unpacked[166]
        padding = unpacked[167:216]

        # TODO: This is kind of gross? Is there a better way to do this?
        return SMXStageConfig(
            master_version,
            config_version,
            flags,
            debounce_no_delay_milliseconds,
            debounce_delay_milliseconds,
            panel_debounce_microseconds,
            auto_calibration_max_deviation,
            bad_sensor_minimum_delay_seconds,
            auto_calibration_averages_per_update,
            auto_calibration_samples_per_average,
            auto_calibration_max_tare,
            enabled_sensors,
            auto_lights_timeout,
            step_color,
            platform_strip_color,
            auto_light_panel_mask,
            panel_rotation,
            packed_sensor_settings,
            pre_details_delay_milliseconds,
            padding,
        )
