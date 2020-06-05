import arcpy
import os
from API.RetrievePasswords import Passwords
from API.SketchFab import SketchfabClient
from API.Wordpress import WordpressClient
from API.Archive import ArchiveClient as AC
import API.ArcGISPro as AGP
import sys
from time import sleep

import numpy as np
import pandas as pd

from importlib import reload

def import_model_and_upload_to_wordpress(cfg,**kwargs):
    if 'epsg_code' in kwargs:
        sr_in = arcpy.SpatialReference(kwargs['epsg_code'])
    elif cfg['model_crs']:
        sr_in = arcpy.SpatialReference()
        sr_in.loadFromString(fields['model_crs'])

    model_popup_html = r'<span style="font-size: 1.2 rem; font-weight: bold">No model available!</span>'
    # TODO add proper model popup html

    # Uploading data to SketchFab first.
    SketchFab = SketchfabClient()

    if isinstance(cfg['model_tag'], str):
        SketchFab_tags = [cfg['model_tag'].split(';'),'Svalbox','Svalbard','UNIS']
    else:
        SketchFab_tags = cfg['model_tag'].extend(['Svalbox','Svalbard','UNIS'])
    SF_data = {
        'name': cfg['model_name'],
        'description': str(cfg['model_description_text']),
        'tags': SketchFab_tags,
        # 'categories': model_category, incompatible with the Arcgis interface...
        'license': 'CC Attribution',
        'private': 0,
        # 'password': password,
        'isPublished': True,
        'isInspectable': True
    }


    if len(cfg['sketchfab_id']) > 0:
        arcpy.AddMessage('Using user-specified SketchFab ID {}.'.format(cfg['sketchfab_id']))
        SketchFab.check_upload(cfg['sketchfab_id'], 1000, 750)
    else:
        SketchFab.response = SketchFab.post_model(SF_data, model_upload).json()
        arcpy.AddMessage('SketchFab has given this model ID {}.'.format(SketchFab.response['uid']))
        SketchFab.check_upload(SketchFab.response['uid'], 1000, 750)

    WordPress = WordpressClient()
    WordPress.upload_worpress_media(file = model_img)

    post = {'title': cfg['model_name'],
            # 'slug': 'rest-api-1',
            'status': 'publish',
            'author': '4',
            'excerpt': f'VOM featuring {cfg['model_name']}',
            'format': 'standard',
            # 'portfolio_tag':model_tag_split,
            'portfolio_category': [22],
            'content':'Updating...'
            }
    Svalbox_imID=WordPress.imID
    WordPress.create_wordpress_post(post, featured_media=WordPress.imID, publish=False)
    Svalbox_postID=WordPress.postresponse['id']
    Sketchfab_ID = SketchFab.response['uid']
    # TODO: cleaner way of getting nice url...


    classes = {'POINT': {'name': 'virtual_outcrops_point'},
               'POLYGON': {'name': 'virtual_outcrops_polygon'}
               }
    xtraFields = {'svalbox_postID':[Svalbox_postID, 'LONG', False],
                  'svalbox_imID':[Svalbox_imID, 'LONG', False],
                  'svalbox_url':[WordPress.postresponse['link'], 'TEXT', False],
                  'sketchfab_id':[Sketchfab_ID, 'TEXT', False],

                  # 'svalbox_img_url':['test', 'TEXT', False] #TODO
                  }
    # TODO: Add all important model IDs to the database dict.

    # WordPress.media_params = 'test'
fields = {'name': [model_name, 'TEXT', False],
          'place':[model_place,'TEXT', False],
          'locality': [model_locality, 'TEXT', False],
          'date': [model_date, 'DATE', False],
          # 'svalbox_url': [None, 'TEXT', False],  # Will be updated later
          # 'url_pdf': [None, 'TEXT', False],  # Will be updated later
          'altitude_distance': [model_distance2outcrop, 'LONG', False],
          'resolution': [model_resolution, 'DOUBLE', False],
          'acquired_by': [model_acq_by, 'TEXT', False],
          'processed_by': [model_proc_by, 'TEXT', False],
          'reference': [model_reference, 'TEXT', False],
          'amount_images': [model_images, 'LONG', False],
          'acquisition_type': [model_acq_type, 'TEXT', False],
          'spatial_calibration':[model_calibration,'TEXT',False],
          'quality':[model_quality,'TEXT',False],
          'short_desc': [model_description_text, 'TEXT', True],
          'popup_html': [None, 'TEXT', False], # Will be updated later
          'tags': [model_tag, 'TEXT', False],
          'category': [model_tag, 'TEXT', False],
          }

    coords_long, coords_lat = AGP.CreateGeometries(
        model_popup_html,
        classes = classes,
        fields = fields,
        xtrafields = xtraFields,
        sr_in = sr_in)

    tempfields= {'coords_long': [coords_long, 'DOUBLE', False],
                   'coords_lat': [coords_lat, 'DOUBLE', False]}

    AGP.UpdateDatabaseFields(classes, tempfields,Svalbox_postID)

    WordPress.generate_html(
        iframe= SketchFab.embed_modelSimple(SketchFab.response['uid'], 1000, 750),
        modelname=model_name,
        description=str(model_description_text),
        model_info={
            'Locality': model_name,
            'Area': model_place,
            'Region': model_locality,
            'UTM33x/Longitude': round(coords_long,2),
            'UTM33x/Latitude': round(coords_lat,2)  # expand upon this...
        },
        model_specs={
            'Date acquired': model_date,
            'Acquired by': model_acq_by,
            'Acquisition method': model_acq_type,
            'Processed by': model_proc_by,
            '# images': model_images,
            'Calibration': model_calibration,
            'Average distance (m)': model_distance2outcrop,
            'Resolution (cm/pix)': model_resolution,
            'Operator': model_operator,
            'Reference': model_reference})

    post['content'] = WordPress.html

    WordPress.create_wordpress_post(post,featured_media=WordPress.imID,publish=True,update=True)

    Archive = AC()
    arcpy.AddMessage('Archiving data on the Box')
    Archive.createName(parameters=Parameters,id_svalbox=Svalbox_postID)
    dir_archive = Archive.storeMetadata(folder_photo=Parameters['folder_photos'],
                          file_model=Parameters['model_model'],
                          file_modeltextures=Parameters['model_textures'],
                          file_description=Parameters['model_desc'],
                          file_imgoverview=Parameters['model_img'],
                          id_svalbox=Svalbox_postID,
                          id_sketchfab=Sketchfab_ID
        )
    directory_field = {'dir_archive':[dir_archive.split(':')[1], 'TEXT', False]}
    AGP.UpdateDatabaseFields(classes, directory_field,Svalbox_postID)

if __name__ == '__main__':
    # Parameters
    ParameterTextList = ['gdb',
                     'model_name',
                     'model_place',
                     'model_locality',
                     'model_img',
                     'model_model',
                     'model_textures',
                     'model_crs',
                     'folder_photos',
                     'model_upload',
                     'sketchfab_id',
                     'coords_long',
                     'coords_lat',
                     'model_desc',
                     'model_date',
                     'model_acq_type',
                     'model_acq_by',
                     'model_proc_by',
                     'model_distance2outcrop',
                     'model_images',
                     'model_resolution',
                     'model_calibration',
                     'model_operator',
                     'model_quality',
                     'model_reference',
                     'model_tag',
                     'model_category'
                    ]

    Parameters = dict()
    for c,key in enumerate(ParameterTextList):
        Parameters[key] = arcpy.GetParameterAsText(c)
        exec(key + " = arcpy.GetParameterAsText(c)")

    # Workspace settings
    arcpy.env.workspace = gdb
    temp_env = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True  # dangerous, but convenient for TEMP dir

    model_description_text = open(model_desc).read()



    # SRID

    import_model_and_upload_to_wordpress(cfg)
    arcpy.AddMessage(f'Configuration has been loaded, model crs = {sr_in}.')
