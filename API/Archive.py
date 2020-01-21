# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 12:25:25 2020

@author: peterbe
"""

import os
import sys
import datetime as dt
import pandas as pd
import numpy as np
from distutils.dir_util import copy_tree
from shutil import copyfile
from pathlib import Path

class ArchiveClient:
    def __init__(self,archivedir='Z:/VOM-DB'):
        self.ArchiveDir = archivedir
        
    def createName(self,parameters,id_svalbox):
        dictionary_region = {'Spitsbergen':'Spit',
                             'Hopen':'Hope',
                             'Kong Karls Land':'Kong',
                             'Edgeøya':'Edge',
                             'Barentsøya':'Bare',
                             'Tusenøyane':'Tuse',
                             'Nordaustlandet':'Nord',
                             'Kvitøya':'Kvit',
                             'Prins Kalrs Forland':'Prin',
                             'Bjørnøya':'Bjor',
                             'Other':'O',
                             } 
        dictionary_acquisition = {'Handheld':'H',
                             'Boat':'B',
                             'UAV':'U',
                             'Combination':'C',
                             'Other':'O'
                             }
        
        ## Changing the date formatting
        try:
            date = dt.datetime.strptime(parameters["model_date"], '%d.%m.%Y %H:%M:%S')
        except ValueError:
            try:
                date = dt.datetime.strptime(parameters["model_date"], '%d.%m.%Y')
            except:
                raise
        date = date.strftime("%Y%m%d")
        
        self.name = f'{parameters["model_operator"]}_{id_svalbox}_{date}_{dictionary_region[parameters["model_locality"]]}_{parameters["model_place"].replace(" ", "")}_{parameters["model_name"].replace(" ", "")}_{dictionary_acquisition[parameters["model_acq_type"]]}'
        
    def storeMetadata(self,folder_photo,file_model,file_modeltextures,file_description,file_imgoverview,id_svalbox,id_sketchfab):
        dir_target=os.path.join(self.ArchiveDir,self.name)
        Path(dir_target).mkdir(parents=True, exist_ok=True)
        
        copy_tree(folder_photo, os.path.join(dir_target,'photos'))
        copyfile(file_model, os.path.join(dir_target,'3Dmodel.'+file_model.split('.')[-1]))
        copyfile(file_modeltextures, os.path.join(dir_target,'3Dmodeltextures.'+file_model.split('.')[-1]))
        copyfile(file_description, os.path.join(dir_target,'description.'+file_description.split('.')[-1]))
        copyfile(file_imgoverview, os.path.join(dir_target,'image_overview.'+file_imgoverview.split('.')[-1]))
        with open(os.path.join(dir_target,"id.txt"), "w") as text_file:
            text_file.write(f'Svalbox ID: {id_svalbox}\nSketchFab ID: {id_sketchfab}')
        
        return dir_target
        
        
        
        