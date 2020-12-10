# -*- coding: utf-8 -*-
"""
Created on Thu Dec 10 12:19:41 2020

@author: Peter
"""

try:
    import arcpy
except:
    try:
        import archook
        archook.get_arcpy(pro=True)
    except:
        print("Check https://github.com/JamesRamm/archook for installation.")


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
from API import SketchFab as SF
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
                
def append_gdf_bounds(gdf_bounds, table, engine, attempts = 2, logger = logging.getLogger()):
    while attempts > 0:
        attempts -= 1
        logger.info("Attempting to connect to PostGIS...")
        try:
            gpd.GeoDataFrame(gdf_bounds, geometry = "shape", crs=gdf_bounds.crs).to_postgis(table, engine,schema = "svalbox", if_exists='append')
            logger.info("Updated PostGIS table.")
            return 1
        except SA.exc.DBAPIError as exc:
            logger.info(f'Connection failed. Attempts left: {attempts}')
            if attempts < 0:
                raise
                
class catalog_dom():
    
        def __init__(self, cfg, logger = logging.getLogger()):
        
            self.logger = logger
            
            if type(cfg) == Path:
                self.cfg = ryaml(cfg)
            with open(Path(
                     cfg['data']['package_directory'],
                     cfg['data']['description_file']
                     ), 
            'r') as file:
                self.cfg["model"]["description"] = file.read().replace('\n', '')
            postgis_user = 'svalbox:5433/svalbox'
            self.engine = create_engine(f'postgresql://svalbox:{Passwords("postGIS_svalbox",postgis_user)}@{postgis_user}',
                                              pool_size=10,
                                              max_overflow=2,
                                              pool_recycle=300,
                                              pool_pre_ping=True,
                                              pool_use_lifo=True)
            
            self.get_server_data()
            
            
        def _arcpy_functions(self, epsg_no):
            
            arcpy.env.workspace = Path("./ArcGIS_dummy/Dummy_project.gdb")
            self.cfg['temp_env'] = os.environ.get('TEMP', 'TMP')
            arcpy.env.overwriteOutput = True
            
            model_path = Path('in_memory', '3D')
            footprint_path = Path('in_memory', 'footprint')
            footprint_proj_path = Path(self.cfg['temp_env'], 'outcrop_outline.shp')  # Env for Project can't be in_memory
            simplify_path = Path(self.cfg['temp_env'], 'simplified.shp')
    
            # Import 3D file
            self.logger.info('Importing 3D model')
            arcpy.Import3DFiles_3d(in_files=os.path.join(
                                        self.cfg['data']['package_directory'],
                                        self.cfg['data']['model_file']),
                                   out_featureClass=model_path,
                                   spatial_reference=self.cfg['data']['model_crs'],
                                   )
    
            # Convert to footprint and project to WGS84UTM33N
            self.logger.info('Calculating footprints')
            arcpy.MultiPatchFootprint_3d(in_feature_class=model_path,
                                         out_feature_class=footprint_path)
   
            self.logger.info('Footprint calculated. Projecting...')
            arcpy.Project_management(in_dataset=footprint_path,
                                     out_dataset=footprint_proj_path,
                                     out_coor_system=arcpy.SpatialReference(epsg_no),
                                     )
    
            self.logger.info('Projected. Simplifying path...')
            arcpy.SimplifyPolygon_cartography(in_features=footprint_proj_path,
                                              out_feature_class=simplify_path,
                                              algorithm='POINT_REMOVE',
                                              tolerance=10)
            
            return gpd.GeoDataFrame(simplify_path).geometry.iloc[0]
            
        def get_server_data(self):
       
           sql = 'SELECT * FROM svalbox.dom'

           self.gdf_bounds = get_gdf_bounds(sql, self.engine)
           #gdf_bounds.plot()

        def create_new_entry(self):
                    
            db_list = self.gdf_bounds.loc[
                self.gdf_bounds["dom_identifier"].str.contains(f"{self.cfg['metadata']['acquisition_date'].year}-"),
                "image_identifier"
                ]
            
            db_list.sort_values(inplace=True, ascending=False)
            db_latest = db_list.head(1).str.split('-').iloc[0]
            if int(db_latest[0]) == self.cfg['metadata']['acquisition_date'].year:
                dbID_no = str(int(db_latest[1]) + 1).zfill(4)
            else:
                dbID_no = "1".zfill(4)
            
            self.cfg['dom_identifier'] = \
                f"{self.cfg['metadata']['acquisition_date'].year}-{dbID_no}"
                
            self.idx = idx = self.gdf_bounds.index.max()+1
            self.gdf_bounds.loc[idx] = self.gdf_bounds.loc[0].copy()
            self.gdf_bounds.loc[idx,"objectid"] = self.gdf_bounds.objectid.max()+1
            self.gdf_bounds.drop(
                self.gdf_bounds[
                    self.gdf_bounds["objectid"] != self.gdf_bounds.objectid.max()
                    ].index,
                inplace=True
                )
            
            
            self.gdf_bounds["shape"] = self._arcpy_functions(epsg_no = int(self.gdf_bounds.crs.to_authority()[1]))
            
        def check_sketchfab_for_model(self):
            SketchFab = SF.SketchfabClient()
            SketchFab.check_upload(self.cfg['metadata']['sketchfab_id'], 1000, 750)
            print(self.cfg['metadata']['sketchfab_id'])
            print(SketchFab.response['uid'])
            if self.cfg['metadata']['sketchfab_id'] == SketchFab.response['uid']:
                return SketchFab
            else:
                self.logger.error("Failed to find model on SketchFab... Double check input config.")
                raise
            
        def store_data(self):
            SketchFab = self.check_sketchfab_for_model()
            self.create_new_entry()
          
            self.cfg['data']['model_long'] = self.gdf_bounds.centroid.x
            self.cfg['data']['model_lat'] = self.gdf_bounds.centroid.y
            
            WordPress = WP.WordpressClient()
            ArchiveClient = AC.ArchiveClient(archivedir='\\svalbox\Svalbox-DB_server\DOM-DB')
                

            try:
                self.cfg = ArchiveClient.store_dom_data(self.cfg)
            except:
                self.logger.error("Failed to archive DOM data onto server. Contact admin.")
                raise
            
            if not all (key in self.cfg for key in ('svalbox_url','svalbox_imgid')):
                # Double check whether file already exists on Wordpress, if it does, ignore
                try:
                    WordPress.upload_worpress_media(
                        Path(
                            self.cfg['data']['package_directory'],
                            self.cfg['data']['overview_img']
                            )
                        )

                except: 
                    self.logger.error("Failed to upload DOM datapage to Svalbox.no. Contact admin.")
                    self.logger.warning("Removing archived 360 image files...")
                    ArchiveClient.undo_store_360_image()
                    raise
                self.cfg['svalbox']['svalbox_url'] = WordPress.imsrc
                self.cfg['svalbox']['svalbox_imgid'] = WordPress.imID
             
            del self.cfg['data_path']
            
            if not all (key in self.cfg["metadata"] for key in ("svalbox_post_id")):
                try:
                    WordPress.generate_html(
                        iframe= SketchFab.embed_modelSimple(SketchFab.response['uid'], 1000, 750),
                        modelname="DOM_" + self.cfg['dom_identifier'],
                        description=self.cfg["model"]["description"],
                        model_info={
                            'Locality': self.cfg['model']['name'],
                            'Area': self.cfg['model']['place'],
                            'Region': self.cfg['model']['region'],
                            'Northing/Longitude': round(self.cfg['data']['model_long'],2),
                            'Easting/Latitude': round(self.cfg['data']['model_lat'],2),
                            'Spatial reference': 'epsg:32633'#+str(self.cfg['metadata']['epsg']), # expand upon this...
                        },
                        model_specs={
                            'Date acquired': self.cfg['metadata']['acquisition_date'],
                            'Acquisition method': self.cfg['metadata']['acquisition_type'],
                            'Acquired by': self.cfg['metadata']['acquisition_user'],
                            'Processed by': self.cfg['metadata']['processing_user'],
                            '# images': self.cfg['metadata']['processing_images'],
                            'Calibration': self.cfg['metadata']['processing_calibration'],
                            'Average distance (m)': self.cfg['metadata']['acquisition_distance2outcrop'],
                            'Resolution (cm/pix)': self.cfg['metadata']['processing_resolution'],
                            'Operator': self.cfg['metadata']['operator'],
                            'Reference': self.cfg['metadata']['reference']})
    
                    post = {'title': "DOM_" + self.cfg['dom_identifier'],
                        # 'slug': 'rest-api-1',
                        'status': 'publish',
                        'author': '4',
                        'excerpt': f"DOM featuring {self.cfg['dom_identifier']} in {self.cfg['model']['place']}.",
                        'format': 'standard',
                        # 'portfolio_tag':model_tag_split,
                        'portfolio_category': [22], # Category 22 is the 
                        'content':WordPress.html
                        }
                
                    WordPress.create_wordpress_post(
                        post, 
                        featured_media = WordPress.imID,
                        publish=False
                        )
                    self.cfg['svalbox']['svalbox_post_id'] = WordPress.postresponse['id']
                except:
                    ArchiveClient.undo_store_dom_data()
                    WordPress.delete_wordpress_media(self.cfg['svalbox']["svalbox_imgid"])
                    raise
            
            try:
                def parse_dict(init, lkey=''):
                    ret = {}
                    for rkey,val in init.items():
                        key = lkey+rkey
                        if isinstance(val, dict):
                            ret.update(parse_dict(val, ''))
                        else:
                            ret[key] = val
                    return ret
                for key in [i for i in self.gdf_bounds.columns.tolist() if i in parse_dict(self.cfg)]:
                    self.gdf_bounds.loc[self.idx,key] = parse_dict(self.cfg)[key] # have to update the values before committing :)
                append_gdf_bounds(self.gdf_bounds, table = "dom_projection",engine = self.engine)
                self.engine.dispose()
                
            except:
                self.logger.error("Failed to catalog data in PostGIS. Contact admin.")
                self.logger.warning("Removing archived data...")
                ArchiveClient.undo_store_dom_data()
                self.logger.warning("Removing uploaded image from Svalbox...")
                WordPress.delete_wordpress_media(self.cfg['svalbox']["svalbox_imgid"])
                WordPress.delete_wordpress_post(self.cfg['svalbox']["svalbox_post_id"])
                raise
                
            ArchiveClient.store_cfg_as_yml(self.cfg)
            self.logger.info(f"Successfully submitted {self.cfg['image_identifier']}")
            
if '__main__' == __name__:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    logger = logging.getLogger()
    logger.info('Started.')
    
    yaml_path = Path(r'\\svalbox\Svalbox-DB\IMG360-DB\2020\2020-0042\generation_settings.yml')
    cfg = ryaml(yaml_path)
    # cfg['data_path'] = Path(yaml_path.parent, f"360img_{yaml_path.parent.stem}")
    logger.info(f'Processing {cfg["data_path"].stem}')
    
    if cfg['unis_project_no'] == None:
        raise
        
    dom = catalog_dom(cfg)
    dom.store_data()
    