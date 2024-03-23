# pySMX
[![Build Status](https://github.com/fchorney/pysmx/workflows/build/badge.svg)](https://github.com/fchorney/pysmx/actions?query=workflow:build)
[![Python Version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

StepManiaX SDK for Python

## Status

Currently fairly incomplete. A lot of core functionality exists, but the rest of the SDK needs to be finished. At some point I can write out a list
of functions currently enabled and which ones have yet to be added.


### Ported Functions

- Get Device Info: Get basic stage information such as Player jumper, serial number, firmware version
- Get Config v5: Get the stage configuration (version 5 and up)
- Write Config v5: Write the stage configuration (version 5 and up)
- Factory Reset: Factory reset the stage to original settings
- Set Light Strip: Set the color of the underglow light strips (Currently only used in factory\_reset function)
- Force Recalibration: Force the stage to perform a recalibration
- Get Sensor Test Data: Get sensor test data for modes [uncalibrated, calibrated, noise, tare]
- Set Serial Numbers: Sets a stage serial if it doesn't exist yet. Does nothing if one exists
- Set Panel Test Mode: Turn on/off panel test mode

### Functions Left to Port

- Set Lights: Set panel lights (This seems fairly complicated at a quick glance)
- Upload GIF Data: Upload GIF Data to Panels
- Re-Enable Auto Lights: Assume this just turns auto GIFs on the pads back on to default?

## Installation (macOS)

These are the instructions that I have been using to run this on my system so far.

1. Use pyenv to install Python 3.10.x or use System Python if its 3.10.x or greater (This will probably work on newer pythons, but I don't know personally).
2. Use [Homebrew](https://brew.sh/) to install `libusb`

```
brew install libusb
```

3. Make sure to add the following lines to your `~/.zshrc` or `~/.bashrc`

```
# LibUSB Settings
  export DYLD_LIBRARY_PATH=/opt/homebrew/lib
```

4. Maybe restart here just to make sure everything is installed properly
5. Download this repo onto your macOS system somewhere
6. Inside this repo set up a python venv, activate it, and install the software into the venv

```
python -m venv venv
. venv/bin/activate
pip install --upgrade pip
pip install -e .
```
7. Now you can play around with the code. The following script will show you the configs for the 2 connected pads. If you have just one, leave out the last line:

```
from pysmx.sdk.api import SMXAPI

smxapi = SMXAPI()
print(smxapi.get_stage_config(1))
print(smxapi_get_stage_config(2))
```

8. Run your script with `python script_name.py`. This assumes you have the `venv` still activated.

## Using pySMX to set your stage settings without needing to connect to a windows computer

As this API/SDK is still unfinished, you can use the included script to set your stages sensor values to whatever you want.

Following the above instructions to set this repo up and use the code, you can then do the following.

1. Modify the `set_stage_configs.py` python file to your specified SMX Config.
2. Look at the `make_new_config` function and follow modification instructions.
3. If you need help with this, just reach out and I can probably help.
4. Make sure you have the venv activated and run the script.

```
python set_stage_configs.py
```

## 3rd Party Software

### LibUSB
You need to have `libUSB` installed to run this. I have personally installed it with Homebrew and added `export DYLD_LIBRARY_PATH=/opt/homebrew/lib` to my `zshrc` file.

## Attribution

This SDK is hevily based on the official open source StepManiaX-SDK: https://github.com/steprevolution/stepmaniax-sdk

## License

pysmx is provided under an MIT License.
