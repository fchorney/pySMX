from contextlib import contextmanager
from dataclasses import dataclass

import hid


SMX_USB_VENDOR_ID = 0x2341
SMX_USB_PRODUCT_ID = 0x8037
SMX_USB_PRODUCT_NAME = "StepManiaX"


@dataclass
class SMXHIDDevice(object):
    vendor_id: int
    product_id: int
    serial_number: str

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
        devices.push(
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
    p2: bool


def get_smx_stage_info(device: SMXHIDDevice) -> str:
    with dev.open() as dev:
        c = dev.write("f\n")
        print(f"Wrote {d} bytes")

        data = dev.read()
        print(data)

        sret = "".join([chr(x) for x in data])
        print(sret)

    return "gotem"
