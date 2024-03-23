from pysmx.sdk.api import SMXAPI
from pysmx.sdk.sensors import PanelTestMode


x = SMXAPI()

x._find_stages()

x.set_panel_test_mode(1, PanelTestMode.PRESSURE_TEST)

import pdb

pdb.set_trace()
