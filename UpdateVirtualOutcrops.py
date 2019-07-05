# -*- coding: utf8 -*-
import arcpy
import os
import json
import base64
import urllib2
import requests
from time import sleep

# Parameters
gdb = arcpy.GetParameterAsText(0)
model_name = arcpy.GetParameterAsText(1)
model_locality = arcpy.GetParameterAsText(2)
model_pdf = arcpy.GetParameterAsText(3)
model_img = arcpy.GetParameterAsText(4)
model_model = arcpy.GetParameterAsText(5)
model_upload = arcpy.GetParameterAsText(6)
model_token = arcpy.GetParameterAsText(7)
coords_use = arcpy.GetParameter(8)
coords_long = arcpy.GetParameterAsText(9)
coords_lat = arcpy.GetParameterAsText(10)
model_desc = arcpy.GetParameterAsText(11)
model_date = arcpy.GetParameter(12)
model_acq_type = arcpy.GetParameter(13)
model_acq_by = arcpy.GetParameter(14)
model_proc_by = arcpy.GetParameter(15)
model_altitude = arcpy.GetParameterAsText(16)
model_images = arcpy.GetParameterAsText(17)
model_resolution = arcpy.GetParameterAsText(18)

# Workspace settings
arcpy.env.workspace = gdb
temp_env = os.environ.get('TEMP', 'TMP')
arcpy.env.overwriteOutput = True # dangerous, but convenient for TEMP dir

# SRID
sr_in = arcpy.SpatialReference(4326)
sr_out = arcpy.SpatialReference(32633)

fields = {'name': [model_name, 'TEXT', False],
         'locality': [model_locality, 'TEXT', False],
         'date': [model_date, 'DATE', False],
         'url_img': [None, 'TEXT', False], # Will be updated later
         'url_pdf': [None, 'TEXT', False], # Will be updated later
         'altitude_distance': [model_altitude, 'LONG', False],
         'resolution': [model_resolution, 'DOUBLE', False],
         'acquired_by': [model_acq_by, 'TEXT', False],
         'processed_by': [model_proc_by, 'TEXT', False],
         'amount_images': [model_images, 'LONG', False],
         'acquisition_type': [model_acq_type, 'TEXT', False],
         'short_desc': [open(model_desc).read(), 'TEXT', True],
         'popup_html': [None, 'TEXT', False]} # Will be updated later

model_html_default = r'<span style="font-size: 1.2 rem; font-weight: bold">No model available!</span>'


def CreateFields(fc):
    for field in fields:
        if fields[field][2]:
            arcpy.AddField_management(fc, field, fields[field][1], field_length=fields[field][3])
        else:
            arcpy.AddField_management(fc, field, fields[field][1])
    

def CreateGeometries(media_params, model_html=model_html_default):
    """Create geometries based on the model file provided or get center coordinates
       from dialog"""
       
    arcpy.AddMessage('Starting to create geometries...')
    
    classes = {'POINT': {'name': 'virtual_outcrops_point'},
               'POLYGON': {'name':'virtual_outcrops_polygon'}
               }
    
    # Construct feature classes
    for fc in classes:
        fc_path = classes[fc]['path'] = os.path.join(gdb, classes[fc]['name'])
        
        # Check if feature classes exist
        if not arcpy.Exists(classes[fc]['path']):
            arcpy.AddMessage('\nCreating {} feature class...'.format(fc))
            arcpy.CreateFeatureclass_management(gdb, os.path.basename(fc_path), fc,
                                                spatial_reference=sr_out)
            CreateFields(fc_path)
        
#     for some reason it wants an editing session, probably because it´s versioned and must be locked
    edit = arcpy.da.Editor(gdb)
    edit.startEditing(False, True)
    edit.startOperation()
    
    # Update urls for PDF and image, html for popup
    fields['url_img'][0] = media_params['Image']['url']
    fields['url_pdf'][0] = media_params['PDF']['url']
    fields['popup_html'][0] = model_html
    fields_list = fields.items()
    fields_keys = [x[0] for x in fields_list]
    fields_values = [x[1][0] for x in fields_list]
    
    if not model_model == "":
        arcpy.AddMessage('Model was specified.\nAttempting to fetch coordinates for footprint and centroid...')
        model_path = os.path.join('in_memory', '3D')
        footprint_path = os.path.join('in_memory', 'footprint')
        footprint_proj_path = os.path.join(temp_env, 'simple.shp') # Env for Project can't be in_memory
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
        
        cursor_poly = arcpy.da.InsertCursor(classes['POLYGON']['path'], fields_keys+["SHAPE@"])  
        
        for row in arcpy.da.SearchCursor(simplify_path, ['SHAPE@', 'SHAPE@XY']):
            # Create centroid point
            centroid_point = row[1]
            
            cursor_poly.insertRow(fields_values + [row[0]])
    
    elif model_model == "":
        # 
        arcpy.AddMessage('No model.\nTaking coordinates from dialog...')
        centroid_coords = arcpy.Point(coords_long, coords_lat)
        
        centroid_geom = arcpy.PointGeometry(centroid_coords, sr_in)
        centroid_proj = centroid_geom.projectAs(sr_out)
        centroid_point = centroid_proj.firstPoint

    with arcpy.da.InsertCursor(classes['POINT']['path'], fields_keys+["SHAPE@"]) as cursor_pnt:
        cursor_pnt.insertRow(fields_values + [centroid_point])
    
    edit.stopOperation()
    edit.stopEditing(True)
    
    
def UploadMedia():
    """Uploads PDF and image to WordPress and extracts the URLs to be set as 
    shape attributes"""

    arcpy.AddMessage('Starting to upload to WordPress...')
    # File parameters
    media_params = {'PDF': 
                       {'path': model_pdf,
                        'type': 'application/pdf',
                        'name': os.path.basename(model_pdf),
                        },
                     'Image': 
                        {'path': model_img,
                         'type': 'image/jpeg',
                         'name': os.path.basename(model_img)}
                     }

    
    url_wp = 'http://www.svalbox.no/wp-json/wp/v2'
    
    # Credentials
    user = 'nilsnolde'
    pythonapp = 'VeD9 G0fL dfC3 YJfZ w24Z oV6l'
    token = base64.standard_b64encode(user + ':' + pythonapp)
    
    # PDF - HTTP params
    for f in media_params:
        headers = {'authorization': 'Basic ' + token,
                   'content-type': media_params[f]['type'],
                   'content-transfer-encoding': 'base64',
                   'content-disposition': 'form-data; filename="{}"'.format(media_params[f]['name'])}
        data = open(media_params[f]['path'], 'rb').read()
        
        request = urllib2.Request(url_wp + '/media', data, headers)
        
        request_count = 0
        
        while request_count < 20:
            try:
                response = urllib2.urlopen(request)
                break
            except urllib2.HTTPError as e:
                arcpy.AddMessage('Error in uploading: {}\nTrying again..\n'.format(e))
                
                sleep(5)
            finally:
                request_count += 1
        
        request_count = 0
            
        media_params[f]['url'] = json.load(response)['guid']['raw']
        
        arcpy.AddMessage('Uploaded {} to {}\n'.format(f,
                                                    media_params[f]['url']))

    return media_params


def UploadModel():
    
    arcpy.AddMessage('Starting to upload model to Sketchfab. This may take while...')
    
    base_url = r'https://api.sketchfab.com/v3/models/'
    headers = {'Authorization': 'Token {}'.format(model_token)}
    
    parameters = {
            'name': model_name,
            'isInspectable': True,
            'license': 'by',
            'tags': 'virtual outcrop',
            'isPublished': True,
            'description': "let's try this",
            }
    
    f = open(model_upload, 'rb')
    files = {'modelFile': f}
    
    try:
        session = requests.Session()
        response = session.post(base_url,
                                 data=parameters,
                                 files=files,
                                 headers=headers)
        response_dict = response.json()
    except requests.exceptions.RequestException as e:
        arcpy.AddMessage(u'An error occured: {}'.format(e))
        raise
        
    finally:
        f.close()
    
    if response.status_code not in [200, 201, 202]:
        raise requests.exceptions.HTTPError(str(response_dict))
    
    arcpy.AddMessage('Upload succeeded. Your model is being processed...')
    arcpy.AddMessage('After Sketchfab processing it will be available at {}'.format('https://sketchfab.com/models/' + response_dict['uid']))
    
    return response_dict['uid']


def EmbedModel(model_uid):
    
    params = {
            'url': r'https://sketchfab.com/models/' + model_uid,
            'maxwidth': 280,
            'maxheight': 300
            }
    
    request_count = 0
    
    while request_count < 20:
        try:
            response = requests.get(r'https://sketchfab.com/oembed',
                                    params=params)
            arcpy.AddMessage(response.json())
            
            request_count += 1
            if '__all__' in response.json().get('detail', 'none'):
                arcpy.AddMessage("Not ready yet, trying again...")
                sleep(60)
                continue
            
            break
            
        except requests.exceptions.RequestException as e:
            arcpy.AddMessage(u'An error occured: {}'.format(e))
            raise
    request_count = 0
    
    response_dict = response.json()
    
    if int(response.status_code) not in [200, 201, 202]:
        raise requests.exceptions.HTTPError(str(response_dict))
        
    arcpy.AddMessage('Built embedded model viewer for popup.')
    
    return response_dict['html']
    
if __name__ == "__main__":
    model_html = model_html_default
    
    media_params = UploadMedia()
    if model_upload != '':
        model_uid = UploadModel()
        model_html = EmbedModel(model_uid)
    CreateGeometries(media_params, model_html)
    