from dataclasses import dataclass, field
from time import monotonic_ns

import hid
from loguru import logger

from pysmx.exceptions import SMXRateLimitError, SMXStageNotFoundError
from pysmx.sdk.config import SMXStageConfig
from pysmx.sdk.device_info import SMXDeviceInfo
from pysmx.sdk.inputs import SMXStageInputs
from pysmx.sdk.packets import (
    HID_REPORT_COMMAND,
    HID_REPORT_INPUT,
    PACKET_FLAG_DEVICE_INFO,
    SMXHID,
    make_send_packets,
    send_packets,
)
from pysmx.sdk.sensors import SensorTestMode, SMXDetailData, SMXSensorTestData
from pysmx.utils import BytesEnum, pad_list, s_to_ns


# StepManiaX API Commands
class APICommand(BytesEnum):
    GET_DEVICE_INFO = b"i"
    GET_CONFIG = b"g"
    GET_CONFIG_V5 = b"G"
    WRITE_CONFIG = b"w"
    WRITE_CONFIG_V5 = b"W"
    FACTORY_RESET = b"f"
    SET_LIGHT_STRIP = b"L"
    FORCE_RECALIBRATION = b"C"
    GET_SENSOR_TEST_DATA = b"y"


# StepManiaX Stage Hardware Identification
SMX_USB_VENDOR_ID = 0x2341
SMX_USB_PRODUCT_ID = 0x8037
SMX_USB_PRODUCT_NAME = "StepManiaX"


@dataclass
class SMXStage(object):
    hid: SMXHID
    device_info: SMXDeviceInfo
    _config: SMXStageConfig | None = None

    def _api_get_stage_config(self) -> SMXStageConfig:
        # Determine proper command based on firmware version
        cmd = APICommand.GET_CONFIG
        if self.device_info.firmware_version >= 5:
            cmd = APICommand.GET_CONFIG_V5

        data = self.send_command(cmd)
        assert data[0] == ord(cmd)

        data_len = len(data)
        payload_size = data[1]

        # This command reads back the configuration we wrote with b"w", or the defaults
        # if we havent read any
        if data_len < 2 or data_len < payload_size + 2:
            logger.warning("Communication Error: Invalid Configuration Packet")
            return SMXStageConfig()

        # TODO: Handle the old format b"g" and convert to new format

        # Trim to the payload_size
        # Currently this seems to return 251 bytes (payload is 250). The last byte seems
        # to be b"\n"
        return SMXStageConfig.from_packed_bytes(data[2 : payload_size + 2])

    def _api_write_stage_config(self, config: SMXStageConfig | None = None) -> None:
        # Determine proper command based on firmware version
        cmd: bytes = APICommand.WRITE_CONFIG
        if self.device_info.firmware_version >= 5:
            cmd = APICommand.WRITE_CONFIG_V5

        # Use the config we currently have saved here if one is not given
        if config is None:
            config = self.config

        # Save the config to this object
        self._config = config

        # TODO: Handle the old format b"w"

        # Get the config data
        cmd = cmd + self._config.to_packed_bytes()

        self.send_command(cmd, acknowledge=True)

    @property
    def config(self) -> SMXStageConfig:
        if self._config is not None:
            return self._config
        self._config = self._api_get_stage_config()
        return self._config

    @config.setter
    def config(self, value: SMXStageConfig) -> None:
        self._config = value

    def send_command(
        self,
        cmd: bytes,
        /,
        acknowledge=False,
        report_id: int = HID_REPORT_COMMAND,
    ) -> bytes:
        debug_str = (f"Sending Command [acknowledge: {acknowledge}]: ").encode("UTF-8")
        logger.debug(debug_str + cmd)
        packets = make_send_packets(cmd)
        return send_packets(self.hid, packets, acknowledge, report_id)


@dataclass
class GTimers(object):
    # TODO: If you write a script to write the config, you'd need to wait 1 second before you can because of this
    wc_seconds: int = s_to_ns(1)
    wc_time: int = monotonic_ns()


TIMERS = GTimers()


@dataclass
class SMXAPI(object):
    stages: dict[int, SMXStage] = field(default_factory=dict)

    def write_stage_config(self, player: int, config: SMXStageConfig | None = None) -> SMXStageConfig:
        stage = self._get_stage(player)

        # Rate limit updating the configuration, to prevent excess EEPROM wear. This is
        # just a safeguard in case applications try to change the configuration in
        # realtime. If we've written the configuration recently, stop. We'll write the
        # most recent configuration once enough time has passes.
        if (time := monotonic_ns()) - TIMERS.wc_time >= TIMERS.wc_seconds:
            TIMERS.wc_time = time
        else:
            logger.error(
                f"Can not write config. Please wait {(TIMERS.wc_seconds - (time - TIMERS.wc_time))/1000000000} seconds"
            )
            raise SMXRateLimitError()

        stage._api_write_stage_config(config)

        return self.get_stage_config(player)

    def get_sensor_test_data(self, player: int, mode: SensorTestMode) -> SMXSensorTestData:
        stage = self._get_stage(player)
        data = stage.send_command(APICommand.GET_SENSOR_TEST_DATA + mode)
        logger.debug("Get Sensor Test Data")

        # Make sure this is the correct packet structure
        # TODO: Maybe just make this a check and raise and exception if it's not?
        assert data[0] == b"y"[0]
        assert data[1] == mode[0]
        size = data[2] * 2

        # TODO: This whole format is super strange to me and I don't get why it is how
        # it is, but maybe figure it out better and try to explain it at some point

        # Copy the data and remove it from the serial buffer
        # This is Little Endian formatted 8-bit bytes placed into 16-bit bytes
        items: list[int] = []
        for i in range(3, size + 3, 2):
            value = data[i + 1] << 8 | data[i]
            items.append(value)

        panel_data: list[SMXDetailData] = []

        # Cycle through each panel and grab the data
        for panel in range(9):
            idx: int = 0
            out_bytes: list[int] = []

            # Read each byte in our extrated items
            # Range 10 here is because the `SMXDetailData` is 80 bits long, thus we need
            # to go through every 10 bytes
            for _ in range(10):
                result: int = 0

                # Read each bit in each byte
                for bit in range(8):
                    new_bit = items[idx] & (1 << panel)
                    result |= new_bit << bit
                    idx += 1

                # We need to shift the result by the panel to move it back to fit within
                # a 8-bit byte
                out_bytes.append(result >> panel)

            panel_data.append(SMXDetailData.from_packed_bytes(bytes(out_bytes)))

        return SMXSensorTestData.from_detail_data(panel_data)

    def force_recalibration(self, player: int) -> None:
        # TODO: Test this function
        stage = self._get_stage(player)

        logger.debug("Force Recalibration")
        stage.send_command(APICommand.FORCE_RECALIBRATION, acknowledge=True)

    def get_inputs(self, player: int) -> SMXStageInputs:
        stage = self._get_stage(player)

        logger.debug("Get Inputs")
        return SMXStageInputs(*stage.send_command(b"", report_id=HID_REPORT_INPUT))

    def factory_reset(self, player: int) -> None:
        stage = self._get_stage(player)

        # Send a factory reset command, and then read the new config
        logger.debug("Factory Reset")
        stage.send_command(APICommand.FACTORY_RESET, acknowledge=True)

        # Factory reset resets the platform strip color saved to the configuration, but
        # it doesn't actually apply it to the lights.
        # Do this for firmware v5 and up
        config = stage.config
        if stage.device_info.firmware_version >= 5:
            led_strip_index = 0  # Always 0
            number_of_leds = 44
            light_cmd = [
                ord(APICommand.SET_LIGHT_STRIP),
                led_strip_index,
                number_of_leds,
            ]

            for _ in range(number_of_leds):
                light_cmd.extend(config.platform_strip_color)

        stage.send_command(bytes(light_cmd), acknowledge=True)

    def get_stage_config(self, player: int) -> SMXStageConfig:
        # We automatically grab the config when accessing it from the SMXStage for the
        # first time.
        # This function only exists if we really want to forcefully re-query for the
        # config for whatever reason.
        stage = self._get_stage(player)
        config = stage._api_get_stage_config()
        stage.config = config

        return stage.config

    def get_device_info(self, player: int) -> SMXDeviceInfo:
        stage = self._get_stage(player)
        device_info = SMXDeviceInfo.from_bytes(stage.send_command(APICommand.GET_DEVICE_INFO))

        # Update the stage device info if we request it after enumeration
        stage.device_info = device_info

        return stage.device_info

    def _find_stages(self) -> None:
        logger.debug("Finding Stages...")

        # This should enumerate through 0 to 2 StepManiaX Stages
        for device_dict in hid.enumerate(SMX_USB_VENDOR_ID, SMX_USB_PRODUCT_ID):
            # Since StepManiaX uses the default Arduino IDs, let's check the product
            # name to make sure this isn't some other Arduino device.
            if device_dict["product_string"] != SMX_USB_PRODUCT_NAME:
                continue

            # For each stage, grab the device info and config and add the stage to our
            # stages dict
            stage_hid = SMXHID(
                device_dict["vendor_id"],
                device_dict["product_id"],
                device_dict["serial_number"],
            )

            # This is a special RequestDeviceInfo packet. This is the same as sending an
            # 'i' command, but we can send it safely at any time, even if another
            # application is talking to the device, so we can do this during
            # enumeration.
            packet = pad_list([5, PACKET_FLAG_DEVICE_INFO, 0], 64)

            device_info = SMXDeviceInfo.from_bytes(send_packets(stage_hid, [packet], False, HID_REPORT_COMMAND))
            self.stages[device_info.player] = SMXStage(stage_hid, device_info)

        logger.info(self.stages)

    def _get_stage(self, player: int) -> SMXStage:
        retries = 3  # Times to retry the connection before giving up
        try_count = 0

        # First check if we currently don't even have a Stage object for the requested
        # player
        while True:
            has_stage = player in self.stages.keys()

            if not has_stage:
                logger.debug(f"No Stage for {player}")
                # Enumerate all stages and fill our `stages` dict
                self._find_stages()
            else:
                break

            if (try_count := try_count + 1) == retries:
                break

        # If we ran out of retries to find the stage at all, it's probably not
        # connected, error out
        if try_count == retries:
            logger.error(f"Could not find stage for player {player} after {retries} trys")
            raise SMXStageNotFoundError()

        return self.stages[player]
