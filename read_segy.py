# -*- coding: utf-8 -*-
"""
Created on Thu Nov 19 12:44:19 2020

@author: Peter
"""

import segyio
import numpy as np
import pandas as pd
import geopandas as gpd

with segyio.open(r'\\petrel-8\data\DATABASE\GEOPHYSICS\SEISMIC\NPD\BA\BA-2515-91.sgy',ignore_geometry = True) as f:
    f.mmap()
    # print(f.bin)
    print(f.text)