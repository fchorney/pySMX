from time import sleep

from loguru import logger

from pysmx.sdk.api import SMXAPI
from pysmx.sdk.config import PackedSensorSettings, SMXStageConfig


# WARNING: I have ONLY tested this on my own pads. Gen 5 FSR style SMX pads.
# Use this script and SDK at your own risk.


# Basic Colors
RGB_RED = [255, 0, 0]
RGB_GREEN = [0, 255, 0]
RGB_BLUE = [0, 0, 255]


####################################################
# !!!!!!!!!!!!! MODIFY THIS FUNCTION !!!!!!!!!!!!! #
####################################################
def make_new_config(player: int, old_config: SMXStageConfig) -> SMXStageConfig:
    # Players are referenced as 1 and 2, so -1 to get array index.
    player_idx = player - 1

    #######################
    # Modify Values Below #
    #######################

    # All values will be in an array of 2, left is for Player 1, and right is for Player 2.
    # You may have a single stage that could be set to either Player 1 or Player 2. Make a note of this when modifying
    # the values below.

    # Set brighness for panel StepColor. 0 to 1 will be multiplied against any color values
    brightness = [0.5, 0.5][player_idx]

    # Which sensors on each panel to enable. This can be used to disable sensors that we know aren't populated.
    # This is packed, with four sensors on two panels per byte:
    # enabled_sensors[0] & 0xF0 is the 4 sensors on the first panel
    # enabled_sensors[0] & 0x0F is the 4 sensors on the second panel, etc
    # Note: You can modify this, but be sure you know what you are doing.
    # The default is set so all 4 sensors are enabled on Up, Down, Left, Right and the rest of the panels are disabled
    enabled_sensors = [[15, 15, 15, 15, 0], [15, 15, 15, 15, 0]][player_idx]

    # Array of RGB values for the stage underglow. 0-255 for each color.
    # Defaults to RED
    platform_strip_color = [RGB_RED, RGB_RED][player_idx]

    # Determines which panels to enable auto-lighting for. Disabled panels will be unlit.
    # 0x01 =  panel 0, 0x02 = panel 1, etc
    # Defaults to all panels enabled.
    # Use 0xAA to only enable Up, Down, Left, Right
    auto_light_mask = [0x01FF, 0x01FF][player_idx]

    # If use_step_color is true we will use the following `step_color` to set the color the panels light up when
    # stepped on.
    use_step_color = [True, True][player_idx]

    # If you want to set specific colors when each arrow is stepped on, you can modify this block.
    # Panels are defined from top to bottom, left to right.
    # By default I'm setting disabled panels to `0x00` (doesn't matter anyway), and enabled panels to blue.
    # `step_color` needs to be a flat list of 27 values. (3 [RGB] * 9 [Panel])
    # WARNING: The step colors should be scaled from 0-255, to 0-170 using the `step_color_scale` function
    step_color: list[int] | None = None
    if use_step_color:
        x = [0, 0, 0]
        s = [int(c * brightness) for c in step_color_scale(RGB_BLUE)]
        step_color = []
        step_color.extend(*[[x + s + x + s + x + s + x + s + x], [x + s + x + s + x + s + x + s + x]][player_idx])

    # Default Sensor Data
    # load_cell_low_threshold - Presumably load cell release threshold (Don't have a load cell pad myself)
    # load_cell_high_threshold - Presumably load cell press threshold (Don't have a load cell pad myself)
    # fsr_low_threshold - 4 values. FSR Release thresholds for the 4 individual sensors
    # fsr_high_threshold - 4 values. FSR Press thresholds for the 4 individual sensors
    # combined_low_threshold - Absolutely no idea. Defaults to 65535
    # combined_high_threshold - Absolutely no idea. Defaults to 65535
    # reserved - This must be left unchanged. Defaults to 0
    # Note: Sensor data must be a list of 13 flat values.
    # These default settings will set all 4 FSR sensors to 220 release threshold, and 222 press threshold.
    sensor_data = [33, 42, 220, 220, 220, 220, 222, 222, 222, 222, 65535, 65535, 0]

    # Personally I play with all panels sharing the same settings, so the default values here will be applied to all
    # panels. If you want to modify this, you would need to use `PackedSensorSettings.from_unpacked_values(sensor_data)`
    # for all 9 panels.
    panel_settings = [PackedSensorSettings.from_unpacked_values(sensor_data) for _ in range(0, 9)]

    # Individual Panel Settings Example.
    # You can play around with this if you want more granularity
    # panel_settings = [
    #     PackedSensorSettings.from_unpacked_values(
    #         [33, 42, 150, 123, 150, 150, 201, 195, 204, 204, 65535, 65535, 0]
    #     ),
    #     ... 7 more ...
    #     PackedSensorSettings.from_unpacked_values(
    #         [33, 42, 120, 133, 140, 130, 211, 185, 204, 204, 65535, 65535, 0]
    #     ),
    # ]

    # Just modify old config with the relevant changes, so we aren't accidentally overwriting things we shouldn't be
    config = old_config
    config.enabled_sensors = enabled_sensors
    config.platform_strip_color = [int(x * brightness) for x in platform_strip_color]
    config.auto_light_panel_mask = auto_light_mask
    if step_color:
        # Enable flags to use step color
        config.flags &= ~(1 << 0)
        config.step_color = step_color
    config.panel_settings = panel_settings

    return config


def step_color_scale(rgb_color: list[int]) -> list[int]:
    """
    Scales a 0-255 RGB color list to a 0-170 RGB color list for Step Colors
    """
    return [c * 170 // 255 for c in rgb_color]


def main():
    # Create an instance of the API
    smxapi = SMXAPI()

    # Forcefully find stages
    smxapi._find_stages()

    stage_players = smxapi.stages.keys()

    for player in stage_players:
        # Grab the old config
        logger.info(f"Grabbing old config for p{player}")
        old_config = smxapi.get_stage_config(player)

        # Create new config from old config
        new_config = make_new_config(player, old_config)

        logger.info(f"Updating p{player}")

        logger.debug("Waiting for config write to be enabled...")
        sleep(1.2)

        logger.debug(f"Current Config for Stage {player}:\n{smxapi.stages[player].config}")
        smxapi.write_stage_config(player, new_config)
        logger.debug(f"New Config for Stage {player}:\n{smxapi.stages[player].config}")

    logger.info("Finished")


if __name__ == "__main__":
    main()
