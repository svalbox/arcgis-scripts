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

from importlib import reload
from pathlib import Path
import logging

import geopandas as gpd
from sqlalchemy import create_engine
from shapely.geometry import Point
from functools import partial
import pyproj
from shapely.ops import transform

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
             
    
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger()
logger.info('Started.')

sr_out = "epsg:32633"

# engine = create_engine('postgresql://db_reader:asdfQWER1234@svalbox:5433/svalbox')
# sql = 'SELECT * FROM svalbox.petroleum_wells'
# gdf_bounds = gpd.read_postgis(sql, con=engine, geom_col='shape')

gdf = gpd.read_file(r"C:\Users\Peter\Downloads\borehole_data.gpkg")


gdf = gdf[(gdf["Type"].str.contains("Coal"))]
rename = {'Borehole':"name", 'NPD_well_I':"borehole_id", 
'Easting':"easting",
'Northing':"northing", 'Spudded':"spudded", 'Completed':"completed", 
 'Operating':"operator", 
'Elevation':"elevation", 'Total_dept':"total_depth", 'Youngest_a':"youngest_age", 
'Oldest_age':"oldest_age",'Youngest_f':"youngest_formation", 'Oldest_for':"oldest_formation",
'Material_l':"material_location", 'Source':"source",
"Geometry":"shape","OBJECTID":"objectid",
'Geothermal_gradient':"geothermal_gradient"}
gdf = gdf.drop("Spudded__s",axis=1)
gdf = gdf.drop("Complete_1",axis=1)


# gdf = gdf[(gdf["NPD_well_I"]!=' ') | (gdf["Borehole"]=="Kvadehuken 0")]
# rename = {'Borehole':"name", 'NPD_well_I':"npd_id", 
# 'Easting':"easting",
# 'Northing':"northing", 'Spudded':"spudded", 'Completed':"completed", 
# 'Spudded__s':"spudded_2", 'Complete_1':"completed_2", 'Operating':"operator", 
# 'Elevation':"elevation", 'Total_dept':"total_depth", 'Youngest_a':"youngest_age", 
# 'Oldest_age':"oldest_age",'Youngest_f':"youngest_formation", 'Oldest_for':"oldest_formation",
# 'Material_l':"material_location", 'Source':"source",
# "Geometry":"shape","OBJECTID":"objectid",
# 'Geothermal_gradient':"geothermal_gradient"}

# gdf = gdf[(gdf["Type"]=="Research")]
# rename = {'Borehole':"name", 'NPD_well_I':"borehole_id", 
# 'Easting':"easting",
# 'Northing':"northing", 'Spudded':"spudded", 'Completed':"completed", 
# 'Operating':"operator", 
# 'Elevation':"elevation", 'Total_dept':"total_depth", 'Youngest_a':"youngest_age", 
# 'Oldest_age':"oldest_age",'Youngest_f':"youngest_formation", 'Oldest_for':"oldest_formation",
# 'Material_l':"material_location", 'Source':"source",
# "Geometry":"shape","OBJECTID":"objectid",
# 'Geothermal_gradient':"geothermal_gradient"}
# gdf = gdf.drop("Spudded__s",axis=1)
# gdf = gdf.drop("Complete_1",axis=1)

gdf = gdf.drop("Comment",axis=1)
gdf = gdf.drop("Type",axis=1)

gdf = gdf.rename(columns=rename)
gdf.objectid = np.arange(1,len(gdf)+1)
gdf = gdf.rename(columns={'geometry': 'shape'}).set_geometry('shape')

gdf["hc_discovery"] = None

gdf["hc_shows"] = gdf["Hydrocarbo"].apply(lambda x: "gas/oil" if "gas" and "liquid" in x else "oil" if "liquid" in x else "gas" if "gas" in x else None)

gdf = gdf.drop("Hydrocarbo",axis=1)
for key in gdf.keys():
    gdf[key] = gdf[key].apply(lambda x: x if not (isinstance(x,str) and x==' ') else None)
    

gdf["total_depth"] = gdf["total_depth"].apply(lambda x: x if (isinstance(x,float)) else None)

logger.info(f"The following Table colums were added:\n{gdf.columns.tolist()}")
    
write_engine = create_engine('postgresql://svalbox:geologyUNIS2020@svalbox:5433/svalbox')
# gpd.GeoDataFrame(gdf, geometry = "shape", crs=gdf.crs).to_postgis("wells_research", write_engine,schema = "svalbox", if_exists='append')
# gpd.GeoDataFrame(gdf, geometry = "shape", crs=gdf.crs).to_postgis("wells_petroleum", write_engine,schema = "svalbox", if_exists='append')
gpd.GeoDataFrame(gdf, geometry = "shape", crs=gdf.crs).to_postgis("wells_coal", write_engine,schema = "svalbox", if_exists='append')



