# -*- coding: utf-8 -*-
"""
Created on Mon Aug 24 11:49:29 2020

@author: Peter Betlem
@institution: The University Centre in Svalbard
@year: 2020
"""

# import standard libs
import sys
import os

# import specialised libs
import yaml
import pathlib
from API.common import try_parsing_date

def convert_paths_and_commands(a_dict):
    for k, v in a_dict.items():
        if not isinstance(v, dict):
            if isinstance(v, str):
                if v and ('path' in k):    # all paths that are supplied in the config file are automatically converted to Path type
                    a_dict[k] = pathlib.Path(v)
                elif v and ('date' in k):
                    a_dict[k] = try_parsing_date(v)
            elif isinstance(v, int):
                if v and ('date' in k):
                    a_dict[k] = try_parsing_date(str(v))
            elif isinstance(v, list):
                if len(v) > 1:
                    a_dict[k] = ', '.join(str(item) for item in v)
                else:
                    a_dict[k] = str(v[0])
        else:
            a_dict[k] = convert_paths_and_commands(v)
    return a_dict


def read_yaml(yml_path):
    yml_path = pathlib.Path(yml_path)
    with open(yml_path,'r', encoding="utf-8") as ymlfile:
        cfg = yaml.load(ymlfile, Loader=yaml.SafeLoader)
         
    return convert_paths_and_commands(cfg)
