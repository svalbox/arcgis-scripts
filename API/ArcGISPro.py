import os
import sys
from time import sleep

import numpy as np
import pandas as pd

from importlib import reload

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

def CreateGeometries(model_html,classes,fields,**kwargs):
    """Create geometries based on the model file provided or get center coordinates
       from dialog"""

    if 'xtrafields' in kwargs:
        fields.update(kwargs['xtrafields'])

    sr_out = arcpy.SpatialReference(32633)

    arcpy.AddMessage('Starting to create geometries...')



    # Construct feature classes
    classes = CheckClasses(classes,fields)

    #     for some reason it wants an editing session, probably because it´s versioned and must be locked
    edit = arcpy.da.Editor(arcpy.env.workspace)
    edit.startEditing(True, False)
    edit.startOperation()

    # Update urls for PDF and image, html for popup
    # fields['svalbox_url'][0] = posturl
    # fields['url_pdf'][0] = media_params['Image']['url'] # TODO : make sure whether to really implement 3D pdfs...
    fields['popup_html'][0] = model_html
    fields_list = fields.items()
    fields_keys = [x[0] for x in fields_list]
    fields_values = [x[1][0] for x in fields_list]

    if not model_model == "":
        arcpy.AddMessage('Model was specified.\nAttempting to fetch coordinates for footprint and centroid...')
        model_path = os.path.join('in_memory', '3D')
        footprint_path = os.path.join('in_memory', 'footprint')
        footprint_proj_path = os.path.join(temp_env, 'simple.shp')  # Env for Project can't be in_memory
        simplify_path = os.path.join('in_memory', 'simple')

        # Import 3D file
        arcpy.Import3DFiles_3d(in_files=model_model,
                               out_featureClass=model_path,
                               spatial_reference=sr_in,
                               )

        # Convert to footprint and project to WGS84UTM33N
        arcpy.AddMessage('Model imported. Getting footprint...')
        arcpy.MultiPatchFootprint_3d(in_feature_class=model_path,
                                     out_feature_class=footprint_path)

        arcpy.AddMessage('Footprint calculated. Projecting...')
        arcpy.Project_management(in_dataset=footprint_path,
                                 out_dataset=footprint_proj_path,
                                 out_coor_system=sr_out,
                                 )

        arcpy.AddMessage('Projected. Simplifying...')
        arcpy.SimplifyPolygon_cartography(in_features=footprint_proj_path,
                                          out_feature_class=simplify_path,
                                          algorithm='POINT_REMOVE',
                                          tolerance=10)

        cursor_poly = arcpy.da.InsertCursor(classes['POLYGON']['path'], fields_keys + ["SHAPE@"])
        arcpy.AddMessage('Created Simplified Polygon.')
        for row in arcpy.da.SearchCursor(simplify_path, ['SHAPE@', 'SHAPE@XY']):
            # Create centroid point
            centroid_point = row[1]

            poly_row=cursor_poly.insertRow(fields_values + [row[0]])


            coords_long = centroid_point[0]
            coords_lat = centroid_point[1]




    elif model_model == "":
        #
        arcpy.AddMessage('No model.\nTaking coordinates from dialog...')
        centroid_coords = arcpy.Point(coords_long, coords_lat)

        centroid_geom = arcpy.PointGeometry(centroid_coords, sr_in)
        centroid_proj = centroid_geom.projectAs(sr_out)
        centroid_point = centroid_proj.firstPoint

    with arcpy.da.InsertCursor(classes['POINT']['path'], fields_keys + ["SHAPE@"]) as cursor_pnt:
        point_row=cursor_pnt.insertRow(fields_values + [centroid_point])
        arcpy.AddMessage('Created centre point.')






    #CheckClasses(classes,tempfields)

   # for fc in classes:
    #    with arcpy.da.UpdateCursor(classes[fc]['path'], ["OID@"] + tempfields_keys) as cursor:
     #       for row in cursor:
      #          arcpy.AddMessage(row)
       #         arcpy.AddMessage(poly_row)
        #        if row[0] == poly_row:
         #           cursor.updateRow(tempfields_values)

    edit.stopOperation()
    edit.stopEditing(True)

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
