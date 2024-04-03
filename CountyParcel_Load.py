#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
import pandas as pd
from time import strftime
import utils

# environment settings
arcpy.env.workspace = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# Get the current script's directory
#script_directory = os.path.dirname(os.path.abspath(__file__))

# set workspace and sde connections 
workspace = "F:/GIS/PARCELUPDATE/Workspace/Staging"

#Create database connection
inWorkspace = "F:\GIS\PARCELUPDATE\Workspace\Vector.sde"
arcpy.env.workspace = inWorkspace

#Make parcel points
arcpy.management.FeatureToPoint(
    in_features=r"F:\GIS\PARCELUPDATE\Workspace\ParcelStaging.gdb\Parcel_County_Staging",
    out_feature_class=r"F:\GIS\PARCELUPDATE\Workspace\ParcelStaging.gdb\Parcel_Points",
    point_location="INSIDE"
)

# prefixes to remove...these we keep or ignore
prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')

#New parcels (Parcel_County_Staging)
parcelNew = 'parcelNew'
arcpy.MakeFeatureLayer_management("F:\GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging", parcelNew)

parcelNew_points = 'parcelNew_points'
arcpy.MakeFeatureLayer_management("F:\GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_Points", parcelNew)

#Define special parcels that need to be ignored
df_special_parcels = pd.read_excel("F:\GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")


# Specify the name of the new version and the parent version
new_version_name = "Parcel_Update_" + strftime("%Y-%m-%d")
parent_version = "SDE.DEFAULT"
version_name_full = "SDE." + new_version_name
version_list = arcpy.da.ListVersions(inWorkspace)
version_exists = False

for version in version_list:
    if version.name == version_name_full:
        version_exists = True
        break

if version_exists:
    # Delete the version
    arcpy.management.DeleteVersion(inWorkspace, version_name_full)

# Create a new version
arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")

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

#Function parameters
new_fc = parcelNew
new_fc_points = parcelNew_points
master_fc_path = r'SDE.Parcels\SDE.Parcel_Master'
base_fc_path = r'SDE.Parcels\SDE.Parcels_Base'
points_fc_path = r'SDE.Parcels\SDE.ParcelPoints'
fields_to_exclude_master = ['SHAPE','OBJECTID', 'Shape']
fields_to_exclude_base = ['SHAPE']
fields_to_exclude_points = ['SHAPE', 'OBJECTID', 'Shape']
fields_to_ignore_master = ['PARCEL_SQFT', 'PPNO', 'ESTIMATED_COVERAGE_ALLOWED', 'IMPERVIOUS_SURFACE_SQFT', 
                    'LOCATION_TO_TOWNCENTER', 'UNITS', 'PARCEL_ACRES','YEAR_BUILT', 'BEDROOMS',
                   'BUILDING_SQFT', 'BATHROOMS']
fields_to_ignore_base = ['Shape', 'PARCEL_ACRES', 'PARCEL_SQFT', 'OBJECTID']
fields_to_ignore_points = ['Shape', 'PARCEL_ACRES', 'PARCEL_SQFT', 'OBJECTID']
master_difference_csv = "Differences_List.csv"
base_difference_csv = "Differences_List_Base.csv"
points_difference_csv = "Differences_List_Points.csv"
database_connection = 'db_connections/ConnectionFile.sde'

data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

#Update parcel master
utils.update_parcel_layer(parcelNew, master_fc_path,prefix_remove, data_type_mapping, fields_to_exclude_master, fields_to_ignore_master,
                          df_special_parcels,master_difference_csv, database_connection, version_name_full)
#Update Parcel Base
utils.update_parcel_layer(parcelNew, base_fc_path,prefix_remove, data_type_mapping, fields_to_exclude_base, fields_to_ignore_base,
                          df_special_parcels,base_difference_csv, database_connection, version_name_full)
#Update Parcel Points - maybe just generate parcel points? do we need to keep track of edit date for that
utils.update_parcel_layer(parcelNew_points, points_fc_path,prefix_remove, data_type_mapping, fields_to_exclude_points, fields_to_ignore_points,
                          df_special_parcels,points_difference_csv, database_connection, version_name_full)


#We need to create a connection to Base
server_name = "sql12"
database_name = "sde_tabular"
username = "sde"
password = "staff"
#change to include date dynamically
#version_name = "parcel_update_10182023"

# Create a new connection to the enterprise geodatabase in the script directory
#enterprise_connection = os.path.join(script_directory, "EnterpriseDBConnection.sde")

arcpy.CreateDatabaseConnection_management(
    out_folder_path='db_connections/',
    out_name="ConnectionFile_Tabular.sde",
    database_platform="SQL_SERVER",  # Replace with your DBMS type (e.g., ORACLE, SQL_SERVER, POSTGRESQL)
    instance=server_name,
    database=database_name,
    account_authentication="DATABASE_AUTH",  # Use "OPERATING_SYSTEM" for OS authentication
    username=username,
    password=password,
    version_type='TRANSACTIONAL'
)

filepath = "F:\GIS/PARCELUPDATE/Workspace/Parcel_Old_New/"
parcel_list_name = "Parcel_Old_New" + strftime("%Y-%m-%d")+".csv"
utils.df_parcel_changes.to_csv(filepath+parcel_list_name, index=False)

inWorkspace = 'db_connections/ConnectionFile_Tabular.sde'
arcpy.env.workspace = inWorkspace

try:
    arcpy.management.Append(filepath+parcel_list_name, 'Parcel_APN_NewOld', schema_type="NO_TEST")    
except Exception as e:
    print (f"Issue with updating list of new and old parcels: {e}")