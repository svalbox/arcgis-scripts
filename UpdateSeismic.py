# coding=utf-8

import arcpy
import os
import AuxiliaryFunctions # Transform lines to WGS84
from collections import OrderedDict


gdb = arcpy.GetParameterAsText(0)
dir_root = r'\\Petrel-8\data\DATABASE\GEOPHYSICS\SEISMIC'
sr = arcpy.SpatialReference(32633)
seismic_dict = dict()

fld_names = ['Linename',
             'Company',
             'Survey',
             'Path']

fc_gdb = os.path.join(gdb, 'SEISMIC_2D')

if not arcpy.Exists(fc_gdb):
        arcpy.AddMessage("\nCreating master 2D Seismic feature class..")
        arcpy.CreateFeatureclass_management(gdb, os.path.basename(fc_gdb), "POLYLINE", spatial_reference=sr)
        for field in fld_names:
            arcpy.AddField_management(fc_gdb, field, "TEXT")

existing_line = set([row[0] for row in arcpy.da.SearchCursor(fc_gdb, ['Linename'])])
added_line = []

# Import shapefiles to master feature class
arcpy.AddMessage("\nIndexing filesystem... ")

for (path, dirs, files) in os.walk(dir_root):
    if path != dir_root:
        for filename in files:
            if filename.endswith('.sgy') or filename.endswith('.segy'):
                line_name = os.path.basename(filename).split('.')[0]
                if line_name in existing_line:
                    continue
                else:
                    added_line.append(line_name)
                seismic_dict[line_name] = OrderedDict()
                seismic_dict[line_name]['line_name'] = line_name
                seismic_dict[line_name]['company'] = os.path.basename(os.path.abspath(os.path.join(path, os.pardir))) #the parent dir
                seismic_dict[line_name]['survey'] = os.path.basename(path) #just the dir name of the segy, could also be year, depends...
                seismic_dict[line_name]['path'] = os.path.join(path, filename)

arcpy.AddMessage("\nImporting shapefiles to server feature class...")

for line in seismic_dict:
    shp_approx = '.'.join([line, 'shp'])
    for file_ in os.listdir(os.path.dirname(seismic_dict[line]['path'])):
        if file_.endswith(shp_approx):
            shp_path = os.path.join(os.path.dirname(seismic_dict[line]['path']), file_)
            shp_desc = arcpy.Describe(shp_path)
            shp_sr = shp_desc.spatialReference
            with arcpy.da.InsertCursor(fc_gdb, fld_names + ['SHAPE@']) as cursor:
                for row in arcpy.da.SearchCursor(shp_path, 'SHAPE@'):
                    line_shp = row[-1]
                    if shp_sr.GCS.GCSName != sr.GCS.GCSName:
                        projected_line = AuxiliaryFunctions.Transform(line_shp, shp_sr, sr, line)
                        seismic_dict[line]['line'] = projected_line
                    else:
                        seismic_dict[line]['line'] = line_shp
                    insert_row = [seismic_dict[line]['line_name'],
                                  seismic_dict[line]['company'],
                                  seismic_dict[line]['survey'],
                                  seismic_dict[line]['path'],
                                  seismic_dict[line]['line']]
                    cursor.insertRow(insert_row)
                    
arcpy.AddMessage("\nImported {} 2D lines...".format(len(added_line)))