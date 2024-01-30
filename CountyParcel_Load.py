#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
import pandas as pd
from time import strftime
import utils

# environment settings
arcpy.env.workspace = "F:\GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# Get the current script's directory
#script_directory = os.path.dirname(os.path.abspath(__file__))

# set workspace and sde connections 
workspace = "F:\GIS/PARCELUPDATE/Workspace/Staging"

#Create database connection
inWorkspace = "F:\GIS\PARCELUPDATE\Workspace\Vector.sde"
arcpy.env.workspace = inWorkspace


# prefixes to remove...these we keep or ignore
prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')

#New parcels (Parcel_County_Staging)
parcelNew = 'parcelNew'
arcpy.MakeFeatureLayer_management("F:\GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging", parcelNew)

#Define special parcels that need to be ignored
df_special_parcels = pd.read_excel("F:\GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")


# Specify the name of the new version and the parent version
new_version_name = "Parcel_Update_" + strftime("%Y-%m-%d")
parent_version = "SDE.DEFAULT"
version_name_full = "SDE." + new_version_name

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
master_fc_path = r'SDE.Parcels\SDE.Parcel_Master'
base_fc_path = r'SDE.Parcels\SDE.Parcels_Base'
points_fc_path = r'SDE.Parcels\SDE.ParcelPoints'


data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

utils.update_parcel_layer


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
df_parcel_changes.to_csv(filepath+parcel_list_name, index=False)

inWorkspace = 'db_connections/ConnectionFile_Tabular.sde'
arcpy.env.workspace = inWorkspace

try:
    arcpy.management.Append(filepath+parcel_list_name, 'Parcel_APN_NewOld', schema_type="NO_TEST")    
except Exception as e:
    print (f"Issue with updating list of new and old parcels: {e}")