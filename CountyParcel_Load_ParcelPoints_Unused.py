#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
import pandas as pd
from time import strftime
import utils

# environment settings
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

#Create database connection 
inWorkspace = "F:\GIS\PARCELUPDATE\Workspace\Vector.sde"
arcpy.env.workspace = inWorkspace

# Specify the name of the new version and the parent version
new_version_name = "Parcel_Point_Update_" + strftime("%Y-%m-%d")
new_version_name = "Parcel_Update_2025-12-05"
parent_version = "SDE.DEFAULT"
version_name_full = "SDE." + new_version_name
version_list = arcpy.da.ListVersions(inWorkspace)
version_exists = False


for version in version_list:
    if version.name == version_name_full:
        version_exists = True
        break

#if version_exists:
    # Change to the version
#    print("Changing version to " + version_name_full)
#    arcpy.ChangeVersion_management(inWorkspace, version_name_full, "TRANSACTIONAL")
    #arcpy.management.DeleteVersion(inWorkspace, version_name_full)
#else:
    # Create a new version
    #arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")


# Create Local Database Connection
# Enterprise geodatabase connection parameters
server_name = "sql12"
database_name = "sde"
username = "sde"
password = "staff"

arcpy.CreateDatabaseConnection_management(
    out_folder_path='db_connections/',
    out_name="ConnectionFile.sde",
    database_platform="SQL_SERVER",  # Replace with your DBMS type (e.g., ORACLE, SQL_SERVER, POSTGRESQL)
    instance=server_name,
    database=database_name,
    account_authentication="DATABASE_AUTH",  # Use "OPERATING_SYSTEM" for OS authentication
    username=username,
    password=password,
    version_type='TRANSACTIONAL',
    version=version_name_full
)

points_fc_path = r'SDE.Parcels\SDE.ParcelPoints'
new_points_fc = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_Points"
old_fc = 'Old_Feature_Class'

arcpy.MakeFeatureLayer_management(points_fc_path,old_fc)

database_connection = 'db_connections/ConnectionFile.sde'
arcpy.ChangeVersion_management(old_fc,'TRANSACTIONAL', version_name_full, '')
edit = arcpy.da.Editor(database_connection)
edit.startEditing(False, True)
    
#Delete all the rows in points_fc_path
arcpy.DeleteRows_management(old_fc)

# Selet the Parcel_points where Within_TRPA_BNDY = 1
temp_layer = arcpy.SelectLayerByAttribute_management(new_points_fc,"NEW_SELECTION", "Within_TRPA_BNDY = 1")

# Append the selected points to the ParcelPoints
arcpy.Append_management(temp_layer, old_fc, "NO_TEST")

#Save and stop the edit session
edit.stopOperation()
edit.stopEditing(True)
print("Parcel Points updated successfully")