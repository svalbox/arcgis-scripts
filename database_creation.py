# -*- coding: utf-8 -*-
"""
Created on Wed Sep 23 16:24:16 2020

@author: Peter
"""


"""
Name: create_enterprise_gdb.py
Description: Provide connection information to a DBMS instance and create an enterprise geodatabase.
Type  create_enterprise_gdb.py -h or create_enterprise_gdb.py --help for usage
"""

# Import system modules
import arcpy
import os
import optparse
import sys


# Define usage and version
parser = optparse.OptionParser(usage = "usage: %prog [Options]", version="%prog 1.0 for " + arcpy.GetInstallInfo()['Version'] )

#Define help and options
parser.add_option ("--DBMS", dest="Database_type", type="choice", choices=['SQL_SERVER', 'ORACLE', 'POSTGRESQL', ''], default="", help="Type of enterprise DBMS:  SQL_SERVER, ORACLE, or POSTGRESQL.")                   
parser.add_option ("-i", dest="Instance", type="string", default="", help="DBMS instance name")
parser.add_option ("-D", dest="Database", type="string", default="none", help="Database name:  Do not specify for Oracle")
parser.add_option ("--auth", dest="Account_authentication", type ="choice", choices=['DATABASE_AUTH', 'OPERATING_SYSTEM_AUTH'], default='DATABASE_AUTH', help="Authentication type options (case-sensitive):  DATABASE_AUTH, OPERATING_SYSTEM_AUTH.  Default=DATABASE_AUTH")
parser.add_option ("-U", dest="Dbms_admin", type="string", default="", help="DBMS administrator user")
parser.add_option ("-P", dest="Dbms_admin_pwd", type="string", default="", help="DBMS administrator password")
parser.add_option ("--schema", dest="Schema_type", type="choice", choices=['SDE_SCHEMA', 'DBO_SCHEMA'], default="SDE_SCHEMA", help="Schema type  applies to geodatabases in SQL Server only. Type SDE_SCHEMA to create geodatabase in SDE schema or type DBO_SCHEMA to create geodatabase in DBO schema. Default=SDE_SCHEMA")
parser.add_option ("-u", dest="Gdb_admin", type="string", default="", help="Geodatabase administrator user name; Must always be sde for PostgreSQL, sde-schema geodatabases in SQL Server, and master sde geodatabase in Oracle")
parser.add_option ("-p", dest="Gdb_admin_pwd", type="string", default="", help="Geodatabase administrator password")
parser.add_option ("-t", dest="Tablespace", type="string", default="", help="Tablespace name; For PostgreSQL, type name of existing tablespace in which to store database. If no tablespace name specified, pg_default is used. For Oracle, type name of existing tablespace, or, if tablespace with specified name does not exist, it will be created and set as the default tablespace for the sde user. If no tablespace name is specified, SDE_TBS tablespace is created and set as sde user default. Tablespace name not supported for SQL Server.")
parser.add_option ("-l", dest="Authorization_file", type="string", default="", help="Full path and name of authorization file; file created when ArcGIS Server Enterprise authorized, and stored in \\Program Files\ESRI\License<release#>\sysgen on Windows or /arcgis/server/framework/runtime/.wine/drive_c/Program Files/ESRI/License<release#>/sysgen on Linux")
# Check if value entered for option
try:
	(options, args) = parser.parse_args()

	
	#Check if no system arguments (options) entered
	if len(sys.argv) == 1:
		print("%s: error: %s\n" % (sys.argv[0], "No command options given"))
		parser.print_help()
		sys.exit(3)

	#Usage parameters for spatial database connection
	database_type = options.Database_type.upper()
	instance = options.Instance
	database = options.Database.lower()	
	account_authentication = options.Account_authentication.upper()
	dbms_admin = options.Dbms_admin
	dbms_admin_pwd = options.Dbms_admin_pwd
	schema_type = options.Schema_type.upper()
	gdb_admin = options.Gdb_admin
	gdb_admin_pwd = options.Gdb_admin_pwd	
	tablespace = options.Tablespace
	license = options.Authorization_file

	
	if( database_type ==""):	
		print(" \n%s: error: \n%s\n" % (sys.argv[0], "DBMS type (--DBMS) must be specified."))
		parser.print_help()
		sys.exit(3)		
		
	if (license == ""):
		print(" \n%s: error: \n%s\n" % (sys.argv[0], "Authorization file (-l) must be specified."))
		parser.print_help()
		sys.exit(3)			
	
	if(database_type == "SQL_SERVER"):
		if(schema_type == "SDE_SCHEMA" and gdb_admin.lower() != "sde"):
			print("\n%s: error: %s\n" % (sys.argv[0], "To create SDE schema on SQL Server, geodatabase administrator must be SDE."))
			sys.exit(3)
		if (schema_type == "DBO_SCHEMA" and gdb_admin != ""):
			print("\nWarning: %s\n" % ("Ignoring geodatabase administrator specified when creating DBO schema..."))
		if( account_authentication == "DATABASE_AUTH" and dbms_admin == ""):
			print("\n%s: error: %s\n" % (sys.argv[0], "DBMS administrator must be specified with database authentication"))
			sys.exit(3)
		if( account_authentication == "OPERATING_SYSTEM_AUTH" and dbms_admin != ""):
			print("\nWarning: %s\n" % ("Ignoring DBMS administrator specified when using operating system authentication..."))
	else:
		if (schema_type == "DBO_SCHEMA"):
			print("\nWarning: %s %s, %s\n" % ("Only SDE schema is supported on", database_type, "switching to SDE schema..." ))
			
		if( gdb_admin.lower() == ""):
			print("\n%s: error: %s\n" % (sys.argv[0], "Geodatabase administrator must be specified."))
			sys.exit(3)

		if( gdb_admin.lower() != "sde"):
			if (database_type == "ORACLE"):
				print("\nGeodatabase admin user is not SDE, creating user schema geodatabase on Oracle...\n")
			else:
				print("\n%s: error: %s for %s.\n" % (sys.argv[0], "Geodatabase administrator must be SDE", database_type))
				sys.exit(3)
			
		if( dbms_admin == ""):
			print("\n%s: error: %s\n" % (sys.argv[0], "DBMS administrator must be specified!"))
			sys.exit(3)

		if (account_authentication == "OPERATING_SYSTEM_AUTH"):
			print("Warning: %s %s, %s\n" % ("Only database authentication is supported on", database_type, "switching to database authentication..." ))

	# Get the current product license
	product_license=arcpy.ProductInfo()
	
	
	# Checks required license level
	if product_license.upper() == "ARCVIEW" or product_license.upper() == 'ENGINE':
		print("\n" + product_license + " license found!" + " Creating an enterprise geodatabase requires an ArcGIS Desktop Standard or Advanced, ArcGIS Engine with the Geodatabase Update extension, or ArcGIS Server license.")
		sys.exit("Re-authorize ArcGIS before creating enterprise geodatabase.")
	else:
		print("\n" + product_license + " license available!  Continuing to create...")
		arcpy.AddMessage("+++++++++")
	
	
	try:
		print("Creating enterprise geodatabase...\n")
		arcpy.CreateEnterpriseGeodatabase_management(database_platform=database_type,instance_name=instance, database_name=database, account_authentication=account_authentication, database_admin=dbms_admin, database_admin_password=dbms_admin_pwd, sde_schema=schema_type, gdb_admin_name=gdb_admin, gdb_admin_password=gdb_admin_pwd, tablespace_name=tablespace, authorization_file=license)
		for i in range(arcpy.GetMessageCount()):
			arcpy.AddReturnMessage(i)
		arcpy.AddMessage("+++++++++\n")
	except:
		for i in range(arcpy.GetMessageCount()):
			arcpy.AddReturnMessage(i)
			
#Check if no value entered for option	
except SystemExit as e:
	if e.code == 2:
		parser.usage = ""
		print("\n")
		parser.print_help()   
		parser.exit(2)