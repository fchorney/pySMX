from dataclasses import dataclass


@dataclass
class SMXStageInputs(object):
    down_left: bool
    down: bool
    down_right: bool
    left: bool
    center: bool
    right: bool
    up_left: bool
    up: bool
    up_right: bool
