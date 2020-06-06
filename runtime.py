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
from datetime import datetime

from importlib import reload

def import_model_and_upload_to_wordpress(cfg,**kwargs):
    
    
    
    arcpy.env.workspace = cfg['geodatabase']
    cfg['temp_env'] = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True
    """
    Initiatlisation of the different packages/classes:
    """
    SketchFab = SketchfabClient()
    WordPress = WordpressClient()
    Archive = AC()
    
    """
    Input standardisation 
    """
    
    def try_parsing_date(text):
        for fmt in ('%Y-%m-%d', '%d.%m.%Y', '%d/%m/%Y'):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                pass
        raise ValueError('no valid date format found')
        
    try: # fixing the acquisition date into a changable format
        cfg['metadata']['acquisition_date'] = \
            datetime.datetime.strptime(
                cfg['metadata']['acquisition_date'], '%d.%m.%Y %H:%M:%S')
    except:
        cfg['metadata']['acquisition_date'] = \
            try_parsing_date(cfg['metadata']['acquisition_date']) 
    
    
    
    with open(os.path.join(
                     cfg['data']['package_directory'],
                     cfg['data']['description_file']
                     ), 
            'r') as file:
        cfg['metadata']['description_text'] = file.read().replace('\n', '')
    
    
    if 'epsg_code' in kwargs: # embedding ArcGIS SpatialReference instead of EPSG code
        sr_in = arcpy.SpatialReference(kwargs['epsg_code'])
    elif cfg['data']['model_crs']:
        sr_in = arcpy.SpatialReference()
        sr_in.loadFromString(cfg['data']['model_crs'])
    cfg['data']['model_crs'] = sr_in
    
    if isinstance(cfg['metadata']['tag'], str):
        SketchFab_tags = [cfg['metadata']['tag'].split(';'),'Svalbox','Svalbard','UNIS']
    else:
        SketchFab_tags = cfg['metadata']['tag'].extend(['Svalbox','Svalbard','UNIS'])
    SF_data = {
        'name': cfg['model']['name'],
        'description': str(cfg['metadata']['description_text']),
        'tags': SketchFab_tags,
        # 'categories': model_category, incompatible with the Arcgis interface...
        'license': 'CC Attribution',
        'private': 0,
        # 'password': password,
        'isPublished': True,
        'isInspectable': True
    }
    
    """
    Creation of initial fields
    The following fields are needed at the very minimum:
    """    
    fields = {'name': [cfg['model']['name'], 'TEXT', False],
          'place':[cfg['model']['place'],'TEXT', False],
          'locality': [cfg['model']['region'], 'TEXT', False],
          'date': [cfg['metadata']['acquisition_date'], 'DATE', False],
          # 'svalbox_url': [None, 'TEXT', False],  # Will be updated later
          # 'url_pdf': [None, 'TEXT', False],  # Will be updated later
          'altitude_distance': [
              cfg['metadata']['acquisition_distance2outcrop'],
              'LONG', 
              False
              ],
          'resolution': [
              cfg['metadata']['processing_resolution'],
              'DOUBLE', 
              False
              ],
          'acquired_by': [cfg['metadata']['acquisition_user'], 'TEXT', False],
          'processed_by': [cfg['metadata']['processing_user'], 'TEXT', False],
          'reference': [cfg['metadata']['reference'], 'TEXT', False],
          'amount_images': [cfg['metadata']['processing_images'], 'LONG', False],
          'acquisition_type': [cfg['metadata']['acquisition_type'], 'TEXT', False],
          'spatial_calibration':[
              cfg['metadata']['processing_calibration'],
              'TEXT',
              False
              ],
          'quality':[cfg['metadata']['processing_quality'],'TEXT',False],
          'short_desc': [cfg['metadata']['description_text'], 'TEXT', True],
          'popup_html': [None, 'TEXT', False], # Will be updated later
          'tags': [cfg['metadata']['tag'], 'TEXT', False],
          'category': [cfg['metadata']['category'], 'TEXT', False],
          }
    
    """
    Checking whether the model is available on SketchFab, and, if not, starts
    the upload procedure (not recommended). Instead, upload your models from
    within Agisoft Metashape beforehand, and provide the SketchFab_id key.
    """
    
    if cfg['metadata']['sketchfab_id']:
        arcpy.AddMessage(f'Using user-specified SketchFab ID {cfg["metadata"]["sketchfab_id"]}.')
        try:
            SketchFab.check_upload(cfg['metadata']['sketchfab_id'], 1000, 750)
        except:
            raise AssertionError("Issue with SketchFab/ID.")
    else:
        SketchFab.response = SketchFab.post_model(
            SF_data, 
            os.path.join(
                cfg['data']['package_directory'],
                cfg['data']['sketchfab_upload_package']
                )
            ).json()
        arcpy.AddMessage('SketchFab has given this model ID {}.'.format(SketchFab.response['uid']))
        SketchFab.check_upload(SketchFab.response['uid'], 1000, 750)

    """
    Initialising Wordpress post with basic metadata.
    Category 22 is the category that belongs to virtual outcrop models. 
    Additional categories will be added in future.
    """
    WordPress.upload_worpress_media(file = os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['overview_img']
            ))

    post = {'title': cfg['model']['name'],
            # 'slug': 'rest-api-1',
            'status': 'publish',
            'author': '4',
            'excerpt': f"VOM featuring {cfg['model']['name']}",
            'format': 'standard',
            # 'portfolio_tag':model_tag_split,
            'portfolio_category': [22], # Category 22 is the 
            'content':'Updating...'
            }
    Svalbox_imID = WordPress.imID
    WordPress.create_wordpress_post(
        post, 
        featured_media = WordPress.imID,
        publish=False
        )
    cfg['metadata']['svalbox_post_id'] = WordPress.postresponse['id']
    Sketchfab_ID = SketchFab.response['uid']
    # TODO: cleaner way of getting nice url...


    """
    Initialising the classes that we will be writing the data to within ArcGIS.
    This also includes creating their shape outlines, and adding them to the gdb.
    In addition, we would also like to include extra fields that were generated
    by SketchFab and Wordpress. This allows for processing down the road.
    """
    
    classes = {'POINT': {'name': 'virtual_outcrops_point'},
               'POLYGON': {'name': 'virtual_outcrops_polygon'}
               }
    
    xtraFields = {'svalbox_postID':[cfg['metadata']['svalbox_post_id'], 'LONG', False],
                  'svalbox_imID':[Svalbox_imID, 'LONG', False],
                  'svalbox_url':[WordPress.postresponse['link'], 'TEXT', False],
                  'sketchfab_id':[Sketchfab_ID, 'TEXT', False],
                  # 'svalbox_img_url':['test', 'TEXT', False] #TODO
                  }
    # TODO: Add all important model IDs to the database dict.

    cfg['data']['model_long'], cfg['data']['model_lat'] = AGP.CreateGeometries(
        config=cfg,
        classes = classes,
        fields = fields,
        xtrafields = xtraFields,
        sr_in = cfg['data']['model_crs'])

    tempfields= {'coords_long': [cfg['data']['model_long'], 'DOUBLE', False],
                   'coords_lat': [cfg['data']['model_lat'], 'DOUBLE', False]}

    AGP.UpdateDatabaseFields(classes, tempfields,cfg['metadata']['svalbox_post_id'])

    """
    Updating the Wordpress post with the correct information
    """
    WordPress.generate_html(
        iframe= SketchFab.embed_modelSimple(SketchFab.response['uid'], 1000, 750),
        modelname=cfg['model']['name'],
        description=cfg['metadata']['description_text'],
        model_info={
            'Locality': cfg['model']['name'],
            'Area': cfg['model']['place'],
            'Region': cfg['model']['region'],
            'Northing/Longitude': round(cfg['data']['model_long'],2),
            'Easting/Latitude': round(cfg['data']['model_lat'],2),
            'Spatial reference': 'epsg:'+str(cfg['data']['model_crs']), # expand upon this...
        },
        model_specs={
            'Date acquired': cfg['metadata']['acquisition_date'],
            'Acquired by': cfg['model']['name'],
            'Acquisition method': cfg['metadata']['acquisition_type'],
            'Processed by': cfg['metadata']['processing_user'],
            '# images': cfg['metadata']['processing_images'],
            'Calibration': cfg['metadata']['processing_calibration'],
            'Average distance (m)': cfg['metadata']['acquisition_distance2outcrop'],
            'Resolution (cm/pix)': cfg['metadata']['processing_resolution'],
            'Operator': cfg['metadata']['operator'],
            'Reference': cfg['metadata']['reference']})

    post['content'] = WordPress.html

    WordPress.create_wordpress_post(post,featured_media=WordPress.imID,publish=True,update=True)

    """
    Archiving data onto the Svalbox
    """
    arcpy.AddMessage('Archiving data on the Box')
    Archive.createName(parameters=cfg,id_svalbox=cfg['metadata']['svalbox_post_id'])
    dir_archive = Archive.storeMetadata(
        folder_photo=os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['data_subdirectory']
            ),
        file_model=os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['model_file']
            ),
        file_modeltextures=os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['texture_zip']
            ),
        file_description=os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['description_file']
            ),
        file_imgoverview=os.path.join(
            cfg['data']['package_directory'],
            cfg['data']['overview_img']
            ),
        id_svalbox=cfg['metadata']['svalbox_post_id'],
        id_sketchfab=cfg['metadata']['sketchfab_id']
        )
    directory_field = {'dir_archive':[dir_archive.split(':')[1], 'TEXT', False]}
    AGP.UpdateDatabaseFields(classes, directory_field,cfg['metadata']['svalbox_post_id'])

if __name__ == '__main__':
    """
    The main file should only be run straight from within ArcGIS Pro. It relies
    on the parameters provided by the Toolbox GUI, and uses these to update the
    values of the empty configuration dictionary.
    """
    
    sys.path.insert(1,os.environ["HOMEDRIVE"]+os.environ["HOMEPATH"]+'/Documents/Github/Jupyter Notebooks/Metashape')
    import read_yaml as ryaml
    
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
        
    cfg = ryaml.read_yaml("empty_config.yml")
    cfg['geodatabase'] = gdb
    cfg['model']['name'] = model_name
    cfg['model']['place'] = model_place
    cfg['model']['region'] = model_locality
    cfg['data']['package_directory'] = model_image.split('/')

    # Workspace settings
    arcpy.env.workspace = gdb
    temp_env = os.environ.get('TEMP', 'TMP')
    arcpy.env.overwriteOutput = True  # dangerous, but convenient for TEMP dir

    model_description_text = open(model_desc).read()



    # SRID

    import_model_and_upload_to_wordpress(cfg)
    arcpy.AddMessage(f'Configuration has been loaded, model crs = {sr_in}.')
