import arcpy
import os
from API.RetrievePasswords import Passwords
from API.SketchFab import SketchfabClient
from API.Wordpress import WordpressClient
import sys
from time import sleep

# Parameters
ParameterTextList = ['gdb',
                 'model_name',
                 'model_locality',
                 'model_pdf',
                 'model_img',
                 'model_model',
                 'model_upload',
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
                 'model_reference',
                 'model_tag',
                 'model_category'
                ]

for c,key in enumerate(ParameterTextList):
    exec(key + " = arcpy.GetParameterAsText(c)")

model_tag_split = model_tag.split(';')
if len(model_tag_split ) == 1:
    model_tag_split = model_tag_split [0]

model_category_split  = model_category.split(';')
if len(model_category_split ) == 1:
    model_category_split  = model_category_split [0]

# Workspace settings
arcpy.env.workspace = gdb
temp_env = os.environ.get('TEMP', 'TMP')
arcpy.env.overwriteOutput = True  # dangerous, but convenient for TEMP dir

# SRID
sr_in = arcpy.SpatialReference(4326)
sr_out = arcpy.SpatialReference(32633)

model_description_text = open(model_desc).read()

fields = {'name': [model_name, 'TEXT', False],
          'locality': [model_locality, 'TEXT', False],
          'date': [model_date, 'DATE', False],
          'svalbox_url': [None, 'TEXT', False],  # Will be updated later
          # 'url_pdf': [None, 'TEXT', False],  # Will be updated later
          'altitude_distance': [model_distance2outcrop, 'LONG', False],
          'resolution': [model_resolution, 'DOUBLE', False],
          'acquired_by': [model_acq_by, 'TEXT', False],
          'processed_by': [model_proc_by, 'TEXT', False],
          'reference': [model_reference, 'TEXT', False],
          'amount_images': [model_images, 'LONG', False],
          'acquisition_type': [model_acq_type, 'TEXT', False],
          'short_desc': [model_description_text, 'TEXT', True],
          'popup_html': [None, 'TEXT', False], # Will be updated later
          'tags': [model_tag, 'TEXT', False],
          'category': [model_tag, 'TEXT', False],
          }

def CreateFields(fc):
    for field in fields:
        if fields[field][2]:
            arcpy.AddField_management(fc, field, fields[field][1], field_length=fields[field][2])
        else:
            arcpy.AddField_management(fc, field, fields[field][1])

def AddFields(fc):
    for field in fields:
        if not (len(arcpy.ListFields(fc,field))>0):
            arcpy.AddMessage('{} did not exist and has been created...'.format(field))
            arcpy.AddField_management(fc, field, fields[field][1])

            # if fields[field][2]:
            #     arcpy.AddField_management(fc, field, fields[field][1], field_length=fields[field][3])
            # else:
            #     arcpy.AddField_management(fc, field, fields[field][1])
            # arcpy.AddMessage('Added field {}'.format(field))



def CreateGeometries(model_html,**kwargs):
    """Create geometries based on the model file provided or get center coordinates
       from dialog"""

    if 'fields' in kwargs:
        fields.update(kwargs['fields'])

    arcpy.AddMessage('Starting to create geometries...')

    classes = {'POINT': {'name': 'virtual_outcrops_point'},
               'POLYGON': {'name': 'virtual_outcrops_polygon'}
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
        else:
            AddFields(fc_path)

    #     for some reason it wants an editing session, probably because it´s versioned and must be locked
    edit = arcpy.da.Editor(gdb)
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

            cursor_poly.insertRow(fields_values + [row[0]])

            coords_long = centroid_point[0]
            coords_lat = centroid_point[1]
            arcpy.AddMessage(centroid_point)


    elif model_model == "":
        #
        arcpy.AddMessage('No model.\nTaking coordinates from dialog...')
        centroid_coords = arcpy.Point(coords_long, coords_lat)

        centroid_geom = arcpy.PointGeometry(centroid_coords, sr_in)
        centroid_proj = centroid_geom.projectAs(sr_out)
        centroid_point = centroid_proj.firstPoint

    with arcpy.da.InsertCursor(classes['POINT']['path'], fields_keys + ["SHAPE@"]) as cursor_pnt:
        cursor_pnt.insertRow(fields_values + [centroid_point])
        arcpy.AddMessage('Created centre point.')
    edit.stopOperation()
    edit.stopEditing(True)

    return coords_long, coords_lat

if __name__ == '__main__':
    model_popup_html = r'<span style="font-size: 1.2 rem; font-weight: bold">No model available!</span>'
    # TODO add proper model popup html

    # Uploading data to SketchFab first.
    SketchFab = SketchfabClient()
    SF_data = {
        'name': model_name,
        'description': str(model_description_text),
        'tags': model_tag_split,
        # 'categories': model_category, incompatible with the Arcgis interface...
        'license': 'CC Attribution',
        'private': 0,
        # 'password': password,
        'isPublished': True,
        'isInspectable': True
    }

    SketchFab.response = SketchFab.post_model(SF_data, model_upload).json()

    arcpy.AddMessage('SketchFab has given this model ID {}.'.format(SketchFab.response['uid']))

    SketchFab.check_upload(SketchFab.response['uid'], 1000, 750)

    WordPress = WordpressClient()
    WordPress.upload_worpress_media(file = model_img)

    post = {'title': model_name,
            # 'slug': 'rest-api-1',
            'status': 'publish',
            'author': '4',
            'excerpt': f'VOM featuring {model_name}',
            'format': 'standard',
            # 'portfolio_tag':model_tag_split,
            'portfolio_category': [22],
            'content':'Updating...'
            }
    WordPress.create_wordpress_post(post, featured_media=WordPress.imID, publish=False)
    WordPress.create_wordpress_post(post, featured_media=WordPress.imID, publish=False, update=True)
    # TODO: cleaner way of getting nice url...

    xtraFields = {'svalbox_postID':WordPress.postresponse['id'],
                  'svalbox_url':WordPress.postresponse['link'],
                  # 'svalbox_img_url':WordPress.media_params['url'] #TODO
                  }
    # TODO: Add all important model IDs to the database dict.

    # WordPress.media_params = 'test'
    coords_long, coords_lat = CreateGeometries(model_popup_html,fields=xtraFields)

    WordPress.generate_html(
        iframe= SketchFab.embed_modelSimple(SketchFab.response['uid'], 1000, 750),
        modelname=model_name,
        description=str(model_description_text),
        model_info={
            'Locality': model_locality,
            'UTM33x/Longitude': coords_long,
            'UTM33x/Latitude': coords_lat  # expand upon this...
        },
        model_specs={
            'Date acquired': model_date,
            'Acquired by': model_acq_by,
            'Acquisition method': model_acq_type,
            'Processed by': model_proc_by,
            '# images': model_images,
            'Average distance': model_distance2outcrop,
            'Resolution': model_resolution,
            'Reference': model_reference})

    post['content'] = WordPress.html

    WordPress.create_wordpress_post(post,featured_media=WordPress.imID,publish=True,update=True)
