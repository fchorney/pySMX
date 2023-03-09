from time import sleep

from loguru import logger

from pysmx.sdk.api import SMXAPI
from pysmx.sdk.config import PackedSensorSettings, SMXStageConfig


# Create an instance of the API
smxapi = SMXAPI()

# Forcefully find stages
smxapi._find_stages()

# Step Colors
step_red = [128, 0, 0]
step_blue = [0, 0, 128]

# Sensor Values: Currently all panels are set to the same settings
sensor_data = [33, 42, 220, 220, 220, 220, 222, 222, 222, 222, 65535, 65535, 0]

# Create out ITL Config from scratch
itl_config = SMXStageConfig()
itl_config.master_version = 5
itl_config.config_version = 2
itl_config.flags = 3
itl_config.debounce_no_delay_milliseconds = 15
itl_config.debounce_delay_milliseconds = 0
itl_config.panel_debounce_microseconds = 4000
itl_config.auto_calibration_max_deviation = 100
itl_config.bad_sensor_minimum_delay_seconds = 15
itl_config.auto_calibration_averages_per_update = 300
itl_config.auto_calibration_samples_per_average = 100
itl_config.auto_calibration_max_tare = 65535
itl_config.enabled_sensors = [15, 15, 15, 15, 0]
itl_config.auto_lights_timeout = 8
itl_config.step_color.extend(
    step_red + step_blue + step_red + step_blue + step_red + step_blue + step_red + step_blue + step_red
)
itl_config.platform_strip_color = [255, 0, 0]
itl_config.auto_light_panel_mask = 186
itl_config.panel_rotation = 0
itl_config.panel_settings = [PackedSensorSettings.from_unpacked_values(sensor_data) for _ in range(0, 9)]
itl_config.pre_details_delay_milliseconds = 5
itl_config.padding = [255 for _ in range(0, 49)]

for idx in smxapi.stages.keys():
    logger.info(f"Updating Stage {idx}")

    logger.debug("Waiting for config write to be enabled for next stage...")
    sleep(1.2)

    logger.debug(f"Current Config for Stage {idx}:\n{smxapi.stages[idx].config}")
    smxapi.stages[idx].config = itl_config
    smxapi.write_stage_config(idx)
    logger.debug(f"New Config for Stage {idx}:\n{smxapi.stages[idx].config}")

logger.info("Finished")
