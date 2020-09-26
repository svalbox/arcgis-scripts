# -*- coding: utf-8 -*-
"""
Created on Mon Jan 20 12:25:25 2020

@author: peterbe
"""

import os
import sys
from datetime import datetime
import pandas as pd
import numpy as np
from distutils.dir_util import copy_tree
from shutil import copyfile
from pathlib import Path
import yaml

class ArchiveClient:
    def __init__(self,archivedir='Z:/VOM-DB'):
        self.ArchiveDir = archivedir
        
    def createName(self,cfg,id_svalbox):
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
        if isinstance(cfg['metadata']['acquisition_date'],datetime):
            date = datetime.strftime(cfg['metadata']['acquisition_date'],"%Y%m%d")
        else:
            raise TypeError
        
        self.name = f'{cfg["metadata"]["operator"]}_{cfg["metadata"]["svalbox_post_id"]}_{date}_{dictionary_region[cfg["model"]["region"]]}_{cfg["model"]["place"].replace(" ", "")}_{cfg["model"]["name"].replace(" ", "")}_{dictionary_acquisition[cfg["metadata"]["acquisition_type"]]}'

        
    def storeMetadata(self,folder_photo,file_model,file_modeltextures,file_description,file_imgoverview,id_svalbox,id_sketchfab):
        dir_target=os.path.join(self.ArchiveDir,self.name)
        dir_target = dir_target.replace('\\','/')
        Path(dir_target).mkdir(parents=True, exist_ok=True)
        
        copy_tree(folder_photo, os.path.join(dir_target,'Data'))
        copyfile(file_model, os.path.join(dir_target,file_model.split('\\')[-1]))
        copyfile(file_modeltextures, os.path.join(dir_target,file_model.split('\\')[-1]+'.'+file_modeltextures.split('.')[-1]))
        copyfile(file_description, os.path.join(dir_target,'description.'+file_description.split('.')[-1]))
        copyfile(file_imgoverview, os.path.join(dir_target,'image_overview.'+file_imgoverview.split('.')[-1]))
        with open(os.path.join(dir_target,"id.txt"), "w") as text_file:
            text_file.write(f'Svalbox ID: {id_svalbox}\nSketchFab ID: {id_sketchfab}')
        
        return dir_target
        
    def store_360_image(self,cfg):
        self.storage_path = target_data_path = Path(
            self.ArchiveDir,
            str(cfg['image_acquisition_date'].year), 
            cfg['image_identifier']
            )
        target_data_path.mkdir(parents=True, exist_ok=True)
        target_data_path = Path(target_data_path,"360img_"+cfg['image_identifier']+cfg['data_path'].suffix)
        if target_data_path.is_file():
            print("File already exists on server!")
            raise
        else:
            copyfile(cfg['data_path'],target_data_path)
        cfg['data_path'] = Path(target_data_path)
        
        return cfg
    
    def store_cfg_as_yml(self,cfg):
        with open(Path(self.storage_path,'generation_settings.yml'), 'w') as outfile:
            yaml.dump(cfg, outfile, default_flow_style=False)
        
        
        
        