# -*- coding: utf-8 -*-
"""
Created on Sat Sep 26 13:50:31 2020

@author: Peter Betlem
@institution: UNIS
@year: 2020

@Comment: the following functions are to (eventually) replace the ArcGIS-pro solution.
They rely on a direct connection to the PostGIS database, implementing geopandas rather than arcpy.
"""

import os
import sys
from time import sleep
import datetime

import numpy as np
import pandas as pd
from API import Wordpress as WP

from importlib import reload
from pathlib import Path
import logging

import geopandas as gpd
from sqlalchemy import create_engine
import sqlalchemy as SA
from shapely.geometry import Point
from functools import partial
import pyproj
from shapely.ops import transform
from API.read_yaml import read_yaml as ryaml
from API import Archive as AC
from API import Wordpress as WP
from API.RetrievePasswords import Passwords

def convert_crs(geom,crs_in,crs_out="epsg:32633"):
    project = partial(
        pyproj.transform,
        pyproj.Proj(crs_in), # source coordinate system
        pyproj.Proj(crs_out))
    return transform(project, geom)

def detect_lon_lat(cfg):
    try:
        split_lat = cfg['image_latitude_wgs84'].split(" ")
        cfg['image_latitude_wgs84'] = int(split_lat[0]) + \
            int(split_lat[1])/60 + float(split_lat[2])/3600
        cfg['image_latitude_wgs84'] = round(cfg['image_latitude_wgs84'], 6)
        split_lon = cfg['image_longitude_wgs84'].split(" ")
        cfg['image_longitude_wgs84'] = int(split_lon[0]) + \
            int(split_lon[1])/60 + float(split_lon[2])/3600
        cfg['image_longitude_wgs84'] = round(cfg['image_longitude_wgs84'], 6)
        return cfg
    except:
        return cfg
    
def get_gdf_bounds(sql, engine, attempts = 2, logger = logging.getLogger()):
    while attempts > 0:
        attempts -= 1
        logger.info("Attempting to connect to PostGIS...")
        try:
            gdf_bounds = gpd.read_postgis(sql, con=engine, geom_col='shape')
            logger.info("Read PostGIS table.")
            return gdf_bounds
        except SA.exc.DBAPIError as exc:
            logger.info(f'Connection failed. Attempts left: {attempts}')
            if attempts < 0:
                raise
                
def append_gdf_bounds(gdf_bounds, engine, attempts = 2, logger = logging.getLogger()):
    while attempts > 0:
        attempts -= 1
        logger.info("Attempting to connect to PostGIS...")
        try:
            gpd.GeoDataFrame(gdf_bounds, geometry = "shape", crs=gdf_bounds.crs).to_postgis("images360", engine,schema = "svalbox", if_exists='append')
            logger.info("Updated PostGIS table.")
            return 1
        except SA.exc.DBAPIError as exc:
            logger.info(f'Connection failed. Attempts left: {attempts}')
            if attempts < 0:
                raise

class catalog_360img():
    
        def __init__(self,cfg, logger = logging.getLogger()):
        
            self.logger = logger
            
            if type(cfg) == Path:
                cfg = ryaml(cfg)
       
            self.cfg = detect_lon_lat(cfg)
            postgis_user = 'svalbox:5433/svalbox'
            self.engine = create_engine(f'postgresql://svalbox:{Passwords("postGIS_svalbox",postgis_user)}@{postgis_user}',
                                              pool_size=10,
                                              max_overflow=2,
                                              pool_recycle=300,
                                              pool_pre_ping=True,
                                              pool_use_lifo=True)
            
            self.get_server_data()
            
            
        def get_server_data(self):
       
           sql = 'SELECT * FROM svalbox.images360'

           self.gdf_bounds = get_gdf_bounds(sql, self.engine)
           #gdf_bounds.plot()

        def create_new_entry(self):
                    
            db_list = self.gdf_bounds.loc[
                self.gdf_bounds["image_identifier"].str.contains(f"{self.cfg['image_acquisition_date'].year}-"),
                "image_identifier"
                ]
            
            db_list.sort_values(inplace=True, ascending=False)
            db_latest = db_list.head(1).str.split('-').iloc[0]
            if int(db_latest[0]) == self.cfg["image_acquisition_date"].year:
                dbID_no = str(int(db_latest[1]) + 1).zfill(4)
            else:
                dbID_no = "1".zfill(4)
            
            self.cfg['image_identifier'] = \
                f"{self.cfg['image_acquisition_date'].year}-{dbID_no}"
                
            
            self.idx = idx = self.gdf_bounds.index.max()+1
            self.gdf_bounds.loc[idx] = self.gdf_bounds.loc[0].copy()
            self.gdf_bounds.loc[idx,"objectid"] = self.gdf_bounds.objectid.max()+1
            self.gdf_bounds.drop(
                self.gdf_bounds[
                    self.gdf_bounds["objectid"] != self.gdf_bounds.objectid.max()
                    ].index,
                inplace=True
                )
            
            shape = convert_crs(
                Point(
                    self.cfg['image_latitude_wgs84'],
                    self.cfg['image_longitude_wgs84']
                    ),
                crs_in = "epsg:4326")
               
            self.gdf_bounds["shape"] = shape
           
           
        def store_data(self):
            self.create_new_entry()
          
            WordPress = WP.WordpressClient()
            ArchiveClient = AC.ArchiveClient()
                
            try:
                self.cfg = ArchiveClient.store_360_image(self.cfg)
            except:
                self.logger.error("Failed to archive 360 image onto server. Contact admin.")
            
            if not all (key in self.cfg for key in ('svalbox_url','svalbox_i0wpurl','svalbox_imgid')):
                # Double check whether file already exists on Wordpress, if it does, ignore
                try:
                    WordPress.upload_worpress_media(self.cfg['data_path'])
                except: 
                    self.logger.error("Failed to upload 360 image to Svalbox.no. Contact admin.")
                    self.logger.warning("Removing archived 360 image files...")
                    ArchiveClient.undo_store_360_image()
                    raise
                self.cfg['svalbox_url'] = WordPress.imsrc
                self.cfg['svalbox_i0wpurl'] = "https://i0.wp.com/"+WordPress.imsrc.split("http://")[1]
                self.cfg['svalbox_imgid'] = WordPress.imID
               
            del self.cfg['data_path']
            
            try:
                for key in [i for i in self.gdf_bounds.columns.tolist() if i in self.cfg]:
                    self.gdf_bounds.loc[self.idx,key] = self.cfg[key] # have to update the values before committing :)
                append_gdf_bounds(self.gdf_bounds,self.engine)
                self.engine.dispose()
            except:
                self.logger.error("Failed to catalog data in PostGIS. Contact admin.")
                self.logger.warning("Removing archived image file...")
                ArchiveClient.undo_store_360_image()
                self.logger.warning("Removing uploaded image from Svalbox...")
                WordPress.delete_wordpress_media(self.cfg["svalbox_imgid"])
                raise
                
            ArchiveClient.store_cfg_as_yml(self.cfg)
            self.logger.info(f"Successfully submitted {self.cfg['image_identifier']}")
            
        def rebuild_database(self):
            
            if not self.gdf_bounds.image_identifier.str.contains(self.cfg["image_identifier"]).any():
                self.create_new_entry()
                
                for key in [i for i in self.gdf_bounds.columns.tolist() if i in self.cfg]:
                        self.gdf_bounds.loc[self.idx,key] = self.cfg[key] # have to update the values before committing :)
                self.gdf_bounds.loc[self.idx,"objectid"] = int(self.cfg["data_path"].parent.stem.split("-")[1].lstrip('0'))
                
                del self.cfg['data_path']
                
                append_gdf_bounds(self.gdf_bounds,self.engine)
                self.engine.dispose()
            
            else:
                self.logger.warning(f"Found existing image_identifier that matches the one specified in config ({self.cfg['image_identifier']}), aborting.")
       
if '__main__' == __name__:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logger = logging.getLogger()
    logger.info('Started.')
    
    yaml_path = Path(r'\\svalbox\Svalbox-DB\IMG360-DB\2020\2020-0042\generation_settings.yml')
    cfg = ryaml(yaml_path)
    cfg['data_path'] = Path(yaml_path.parent, f"360img_{yaml_path.parent.stem}")
    logger.info(f'Processing {cfg["data_path"].stem}')
    cfg['comment']
    
    if cfg['unis_project_no'] == None:
        raise
        
    img360 = catalog_360img(cfg)
    # img360.store_data()
    
    img360.rebuild_database()
    
    
    
   