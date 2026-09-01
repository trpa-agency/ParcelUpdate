#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
import pandas as pd
from time import strftime
import utils
import argparse
import sys
import os

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

# prefixes to remove...these we keep or ignore
prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')

#New parcels (Parcel_County_Staging)
parcelNew = 'parcelNew'
arcpy.MakeFeatureLayer_management("F:\GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging", parcelNew)

#Define special parcels that need to be ignored
df_special_parcels = pd.read_excel("F:\GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")

# Specify the name of the new version and the parent version
new_version_name = "Parcel_Update_" + strftime("%Y-%m-%d")
new_version_name = "Parcel_Update_2026-04-20"
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
#    arcpy.ChangeVersion_management(inWorkspace, version_name_full, "TRANSACTIONAL")
    #arcpy.management.DeleteVersion(inWorkspace, version_name_full)
#else:
    # Create a new version
#    arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")

# Create Local Database Connection
# Enterprise geodatabase connection parameters
def load_credentials(path):
    creds = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            creds[key.strip()] = value.strip()
    return creds


_creds = load_credentials(os.path.join(os.path.dirname(os.path.abspath(__file__)), "passwords.txt"))

server_name = "sql12"
database_name = "sde"
username = _creds["sde_username"]
password = _creds["sde_password"]

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

base_fc_path = r'SDE.Parcels\SDE.Parcels_Base'

fields_to_exclude_base = ['SHAPE']
fields_to_ignore_base = ['Shape', 'PARCEL_ACRES', 'PARCEL_SQFT', 'OBJECTID']

base_difference_csv = "Differences_List_Base.csv"
database_connection = 'db_connections/ConnectionFile.sde'

data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

#Update Parcel Base
utils.update_parcel_layer(parcelNew, base_fc_path,prefix_remove, data_type_mapping, fields_to_exclude_base, fields_to_ignore_base,
                        df_special_parcels,base_difference_csv, database_connection, version_name_full)