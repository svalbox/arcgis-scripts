import arcpy
import os
#import AuxiliaryFunctions # Transform lines to WGS84
from collections import OrderedDict
import glob
import sys

#reload(sys)
#sys.setdefaultencoding('utf8')

dir_root = r'\\srv21\flybilder'
#table_path = r'\\Petrel-8\data\NILS\AerialPhotoLinkingDoc.txt'
table_path = arcpy.GetParameterAsText(0)
gdb = arcpy.GetParameterAsText(1)
shp = os.path.join(gdb, 'IMAGERY_LOCATIONS')
sr = arcpy.SpatialReference(32633)
enc_set = 'iso-8859-1' # Norwegian character encoding set

table_dict = dict()
dir_dict = dict()
fld_names = ['Location',
             'Years',
             'Path',
             'ID'
             ]

path_list = [name.decode(enc_set) for name in glob.glob(os.path.join(dir_root, 4*'[0-9]' + '_*_*'))]

with open(table_path, 'r') as f:
    for line in f.readlines():
        table_columns = line.split('\t')[:3]
        if unicode(table_columns[0]).isnumeric():
            table_dict[table_columns[0]] = (table_columns[1], table_columns[2])

for path in path_list:
    param_tuple = os.path.basename(path).split('_')
    dir_dict[param_tuple[0]] = dict()
    dir_dict[param_tuple[0]]['id'] = param_tuple[0]
    dir_dict[param_tuple[0]]['path'] = path
    dir_dict[param_tuple[0]]['location'] = param_tuple[1]
    dir_dict[param_tuple[0]]['years'] = ', '.join(['19' + year if len(year) == 2 else year for year in param_tuple[2:]])

if not arcpy.Exists(shp):
        arcpy.AddMessage("\nCreating feature class..")
        arcpy.CreateFeatureclass_management(gdb, os.path.basename(shp), "POINT", spatial_reference=sr)
        for field in fld_names:
            arcpy.AddField_management(shp, field, "TEXT")

existing_entries = [row[0] for row in arcpy.da.SearchCursor(shp, 'ID')]

for key in table_dict:
    if key in existing_entries:
        continue
    shp_point = arcpy.Point(table_dict[key][0], table_dict[key][1])
    try:
        insert_row = [dir_dict[key]['location'],
                       dir_dict[key]['years'],
                       dir_dict[key]['path'],
                       dir_dict[key]['id'],
                       shp_point
                       ]
    except KeyError:
        arcpy.AddMessage('\nKey {} was not found in {}\n'.format(key, dir_root))
        raise
    with arcpy.da.InsertCursor(shp, fld_names + ['SHAPE@XY']) as cursor:
        cursor.insertRow(insert_row)