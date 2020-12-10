# -*- coding: utf-8 -*-
"""
Created on Sun Sep 13 12:54:17 2020

@author: Peter
"""
from datetime import datetime

def try_parsing_date(text):
    for fmt in ('%Y-%m-%d','%Y%m%d', '%Y.%m.%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError('no valid date format found')

# def generate_fields(a_dict):
#     for k, v in a_dict.items():
#         if not isinstance(v, dict):
#             if isinstance(v, str):
#                 if v and 'description' in k:
#                     a_dict[k] = [v, 'TEXT', False
#         else:
#             a_dict[k] = convert_paths_and_commands(v)
    
# 'name': [cfg['model']['name'], 'TEXT', False],