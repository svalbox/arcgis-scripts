import os
import sys
from time import sleep
import datetime

import numpy as np
import pandas as pd
import arcpy
from API import Wordpress as WP

from importlib import reload
from pathlib import Path
import logging
logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logger = logging.getLogger()
logger.info('Started.')

sr_out = arcpy.SpatialReference(32633)

def CreateFields(fc,fields):
    for field in fields:
        if fields[field][2]:
            arcpy.AddField_management(fc, field, fields[field][1], field_length=fields[field][2])
        else:
            arcpy.AddField_management(fc, field, fields[field][1])

def AddFields(fc,fields):
    '''

    :param fc: database connection to which fields should be added. For now, fields are a global parameter. This is
        likely to be changed in future updates.
    :return:
    '''
    for field in fields:
        if not (len(arcpy.ListFields(fc,field))>0):
            try:
                arcpy.AddField_management(fc, field, fields[field][1])
                arcpy.AddMessage(f'{field} did not exist and has been created...')
            except arcpy.ExecuteError:
                arcpy.AddError('Adding and removing fields requires the ArcGIS service to be shut down. Please use '
                               'ArcMAP to temporarily shut down the server. And do not forget restarting it again...'
                                   'P.S.: Please check Error 100 description on SvalDocs, when encountered.')
                raise
                
def create_fields_from_config(fc,a_dict):
    for k, v in a_dict.items():
        if not isinstance(v, dict):
            if not k in ['geodatabase','temp_env']:
                lstFields = [i.name for i in arcpy.ListFields(fc['path'])]
                if not k in lstFields:
                    if isinstance(v, str):
                        if v and ('description' in k or 'comment' in k):
                             arcpy.AddField_management(fc['path'], k, 'TEXT', field_length=5000)
                        else:
                             arcpy.AddField_management(fc['path'], k, 'TEXT', field_length=100)
                    elif isinstance(v, datetime.date):
                        arcpy.AddField_management(fc['path'], k, 'DATE')
                    elif isinstance(v, int):
                        arcpy.AddField_management(fc['path'], k, 'LONG')
                    elif isinstance(v, float):
                        arcpy.AddField_management(fc['path'], k, 'DOUBLE')
        else:
            pass
            #create_fields_from_config(fc, v)
    
    
def check_classes_v2(classes):
    for fc in classes:
        fc_path = classes[fc]['path'] = os.path.join(arcpy.env.workspace, classes[fc]['name'])

        # Check if feature classes exist
        if not arcpy.Exists(classes[fc]['path']):
            arcpy.AddMessage('\nCreating {} feature class...'.format(fc))
            arcpy.CreateFeatureclass_management(arcpy.env.workspace, os.path.basename(fc_path), fc,
                                                spatial_reference=sr_out)
    return classes

def CheckClasses(classes,fields):
    for fc in classes:
        fc_path = classes[fc]['path'] = os.path.join(arcpy.env.workspace, classes[fc]['name'])

        # Check if feature classes exist
        if not arcpy.Exists(classes[fc]['path']):
            arcpy.AddMessage('\nCreating {} feature class...'.format(fc))
            arcpy.CreateFeatureclass_management(arcpy.env.workspace, os.path.basename(fc_path), fc,
                                                spatial_reference=sr_out)
            CreateFields(fc_path,fields)
        else:
            AddFields(fc_path,fields)
    return classes

def CreateGeometries(config,classes,fields,**kwargs):
    """Create geometries based on the model file provided or get center coordinates
       from dialog"""


    # Before this step, all fields need to be put into their available dict structure
    # otherwise there will be an issue with the continuation of the script
    if 'xtrafields' in kwargs:
        fields.update(kwargs['xtrafields'])

    arcpy.AddMessage('Starting to create geometries...')



    # Construct feature classes
    
    classes = CheckClasses(classes,fields)

    #     for some reason it wants an editing session, probably because it´s versioned and must be locked
    edit = arcpy.da.Editor(arcpy.env.workspace)
    try:
        edit.startEditing(True, False)
        edit.startOperation()
    except:
        pass

    fields_list = fields.items()
    fields_keys = [x[0] for x in fields_list]
    fields_values = [x[1][0] for x in fields_list]

    if not config['data']['model_file'] == "":
        logger.info('Opening model')
        arcpy.AddMessage('Model was specified.\nAttempting to fetch coordinates for footprint and centroid...')
        model_path = os.path.join('in_memory', '3D')
        footprint_path = os.path.join('in_memory', 'footprint')
        footprint_proj_path = os.path.join(config['temp_env'], 'simple.shp')  # Env for Project can't be in_memory
        simplify_path = os.path.join('in_memory', 'simple')

        # Import 3D file
        logger.info('Importing 3D model')
        arcpy.Import3DFiles_3d(in_files=os.path.join(
                                    config['data']['package_directory'],
                                    config['data']['model_file']),
                               out_featureClass=model_path,
                               spatial_reference=config['data']['model_crs'],
                               )

        # Convert to footprint and project to WGS84UTM33N
        logger.info('Calculating footprints')
        arcpy.AddMessage('Model imported. Getting footprint...')
        arcpy.MultiPatchFootprint_3d(in_feature_class=model_path,
                                     out_feature_class=footprint_path)

        arcpy.AddMessage('Footprint calculated. Projecting...')
        logger.info('Projecting...')
        arcpy.Project_management(in_dataset=footprint_path,
                                 out_dataset=footprint_proj_path,
                                 out_coor_system=sr_out,
                                 )

        arcpy.AddMessage('Projected. Simplifying...')
        logger.info('Projected. Simplifying...')
        arcpy.SimplifyPolygon_cartography(in_features=footprint_proj_path,
                                          out_feature_class=simplify_path,
                                          algorithm='POINT_REMOVE',
                                          tolerance=10)

        with arcpy.da.InsertCursor(classes['POLYGON']['path'], fields_keys + ["SHAPE@"]) as cursor_poly:
            arcpy.AddMessage('Created Simplified Polygon.')
            logger.info('Created Simplified Polygon.')
            with arcpy.da.SearchCursor(simplify_path, ['SHAPE@', 'SHAPE@XY']) as cursor_search:
                for row in cursor_search:
                    # Create centroid point
                    centroid_point = row[1]
                    logger.info(fields_keys)
                    logger.info(row)
        
                    poly_row=cursor_poly.insertRow(fields_values + [row[0]])
        
        
                    coords_long = centroid_point[0]
                    coords_lat = centroid_point[1]
    
    


    elif (config['model_file'] == "" 
          and not config['data']['model_long'] == "" 
          and not config['data']['model_lat'] != ""):
        #
        arcpy.AddMessage('No model.\nTaking coordinates from dialog...')
        centroid_coords = arcpy.Point(config['data']['coords_long'], config['data']['coords_lat'])

        centroid_geom = arcpy.PointGeometry(centroid_coords, config['data']['model_crs'])
        centroid_proj = centroid_geom.projectAs(sr_out)
        centroid_point = centroid_proj.firstPoint
        
    else:
        raise ValueError('No spatial data/coordinates provided.')

    with arcpy.da.InsertCursor(classes['POINT']['path'], fields_keys + ["SHAPE@"]) as cursor_pnt:
        point_row=cursor_pnt.insertRow(fields_values + [centroid_point])
        arcpy.AddMessage('Created centre point.')

    try:
        edit.stopOperation()
        edit.stopEditing(True)
    except:
        pass

    return coords_long, coords_lat

def StoreProjectCampaign(cfg,**kwargs):
    arcpy.env.workspace = cfg['geodatabase']
    cfg['temp_env'] = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True
    
    classes = {'POINT': {'name': 'points'},
               'POLYGON': {'name': 'polygons'}
               }
    
    classes = check_classes_v2(classes)
    
    try:
        latest = arcpy.da.SearchCursor(
            classes['POINT']['path'], 
            ["campaign_identifier"], 
            f"campaign_identifier LIKE '{datetime.date.today().year}-%'", 
            sql_clause = (None, "ORDER BY campaign_identifier DESC")
            ).next()[0]
        if int(latest.split('-')[0]) == cfg['start_date'].year:
                    dbID_no = str(int(latest.split('-')[1]) + 1).zfill(4)
        else: 
            raise
    except:
        dbID_no = "1".zfill(4)
    
    cfg['campaign_identifier'] = \
        f"{cfg['campaign_start_date'].year}-{dbID_no}"
    for key in classes:
        create_fields_from_config(classes[key],cfg)
        
    field_keys = [i.name for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    field_values = [cfg[i.name] for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    for key in classes:
        
        with arcpy.da.InsertCursor(classes[key]['path'], field_keys) as cursor_pnt:
            point_row=cursor_pnt.insertRow(field_values)
            
def Store360Image(cfg,**kwargs):
    arcpy.env.workspace = cfg['geodatabase']
    cfg['temp_env'] = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True
    
    classes = {'POINT': {'name': 'images360'},
               }
    
    classes = check_classes_v2(classes)
    
    try:
        latest = arcpy.da.SearchCursor(
            classes['POINT']['path'], 
            ["image_identifier"], 
            f"image_identifier LIKE '{datetime.date.today().year}-%'", 
            sql_clause = (None, "ORDER BY image_identifier DESC")
            ).next()[0]
        if int(latest.split('-')[0]) == cfg['image_acquisition_date'].year:
                    dbID_no = str(int(latest.split('-')[1]) + 1).zfill(4)
        else: 
            raise
    except:
        dbID_no = "1".zfill(4)
    
    cfg['image_identifier'] = \
        f"{cfg['image_acquisition_date'].year}-{dbID_no}"
        
    # WordPress = WP.WordpressClient()
    # cfg['data_path'].rename(Path(cfg['data_path'].parent,"360img_"+cfg['image_identifier']+cfg['data_path'].suffix))
    # cfg['data_path'] = Path(cfg['data_path'].parent,"360img_"+cfg['image_identifier']+cfg['data_path'].suffix)
    
    # WordPress.upload_worpress_media(cfg['data_path'])
    # cfg['svalbox_URL'] = WordPress.imsrc
    # cfg['svalbox_imgID'] = WordPress.imID
    
    del cfg['data_path']
        
    centroid_coords = arcpy.Point(cfg['image_longitude_wgs84'], cfg['image_latitude_wgs84'])
    # If getting an error when running that the geometries are not supported, make sure to check that the Z and/or M coordinates are correctly defined here!
    centroid_geom = arcpy.PointGeometry(centroid_coords, arcpy.SpatialReference(4326))
    centroid_proj = centroid_geom.projectAs(sr_out)
    centroid_point = centroid_proj.firstPoint
        
    for key in classes:
        create_fields_from_config(classes[key],cfg)
        
    field_keys = [i.name for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    field_values = [cfg[i.name] for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    
    for key in classes:
        with arcpy.da.InsertCursor(classes[key]['path'], field_keys + ["SHAPE@"]) as cursor_pnt:
            point_row=cursor_pnt.insertRow(field_values + [centroid_point])
            
def StoreSample(cfg,**kwargs):
    arcpy.env.workspace = cfg['geodatabase']
    cfg['temp_env'] = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True
    
    classes = {'POINT': {'name': 'handsamples'},
               }
    classes = check_classes_v2(classes)
    
    try:
        latest = arcpy.da.SearchCursor(
            classes['POINT']['path'], 
            ["sample_identifier"], 
            f"sample_identifier LIKE '{datetime.date.today().year}-%'", 
            sql_clause = (None, "ORDER BY sample_identifier DESC")
            ).next()[0]
        if int(latest.split('-')[0]) == cfg['sampling_date'].year:
                    dbID_no = str(int(latest.split('-')[1]) + 1).zfill(4)
        else: 
            raise
    except:
        dbID_no = "1".zfill(4)
    
    cfg['sample_identifier'] = \
        f"{cfg['sampling_date'].year}-{dbID_no}"
        
    cfg['sample_name'] = f'Rock sample ({cfg["sample_identifier"]})'
        
    del cfg['data_path']
        
    centroid_coords = arcpy.Point(cfg['sampling_longitude_wgs84'], cfg['sampling_latitude_wgs84'])
    centroid_geom = arcpy.PointGeometry(centroid_coords, arcpy.SpatialReference(4326))
    centroid_proj = centroid_geom.projectAs(sr_out)
    centroid_point = centroid_proj.firstPoint
        
    for key in classes:
        create_fields_from_config(classes[key],cfg)
        
    field_keys = [i.name for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    field_values = [cfg[i.name] for i in arcpy.ListFields(classes[key]['path']) if i.name in cfg]
    
    for key in classes:
        with arcpy.da.InsertCursor(classes[key]['path'], field_keys + ["SHAPE@"]) as cursor_pnt:
            point_row=cursor_pnt.insertRow(field_values + [centroid_point])
    

def UpdateDatabaseFields(classes,fields, Svalbox_postID):
    classes=CheckClasses(classes,fields)
    fields_list = fields.items()
    fields_keys = [x[0] for x in fields_list]
    fields_values = [x[1][0] for x in fields_list]


    for fc in classes:
        with arcpy.da.UpdateCursor(classes[fc]['path'], ["svalbox_postID"] + fields_keys) as cursor:
            for row in cursor:
                if row[0] == Svalbox_postID:
                    cursor.updateRow([row[0]] + fields_values)
