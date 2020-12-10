# -*- coding: utf-8 -*-
"""
Created on Tue Sep 22 13:42:03 2020

@author: Peter Betlem
@institution: UNIS
@year: 2020
"""

try:
    import arcpy
except:
    from Archook import archook
    archook.get_arcpy(pro=True)
import os
from API.RetrievePasswords import Passwords
from API.SketchFab import SketchfabClient
from API.Wordpress import WordpressClient
from API.Archive import ArchiveClient as AC
import API.ArcGISPro as AGP
from API.common import try_parsing_date
import API.read_yaml as ryaml
import sys
from time import sleep

import numpy as np
import pandas as pd
from datetime import datetime

from importlib import reload


cfg = ryaml.read_yaml("handsample_config.yaml")

AGP.StoreSample(cfg)