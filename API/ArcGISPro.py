import os
import sys
from time import sleep

import numpy as np
import pandas as pd
import arcpy

from importlib import reload
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
