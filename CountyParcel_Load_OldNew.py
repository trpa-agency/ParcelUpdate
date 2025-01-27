#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
import pandas as pd
from time import strftime
import utils
import sys
import os

# environment settings
arcpy.env.workspace = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# set workspace and sde connections 
workspace = "F:/GIS/PARCELUPDATE/Workspace/Staging"

#Create database connection
# Create Local Database Connection
# Enterprise geodatabase connection parameters
server_name = "sql12"
database_name = "sde"
username = "sde"
password = "staff"


data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

server_name = "sql12"
database_name = "sde_tabular"
username = "sde"
password = "staff"

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

database_connection = 'db_connections/ConnectionFile.sde'
#old_fc = database_connection + "\\SDE.Parcels\\SDE.Parcel_master"
old_fc = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/parcel_master"
target_table = "db_connections/ConnectionFile_Tabular.sde/Parcel_APN_NewOld"
new_fc = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging"


prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')

df_parcel_changes = utils.make_old_new_dataframe(old_fc, new_fc, 'Yes', prefix_remove)
df_parcel_changes.to_csv(filepath+parcel_list_name, index=False)

inWorkspace = 'db_connections/ConnectionFile_Tabular.sde'
arcpy.env.workspace = inWorkspace

# Function to check for duplicate records
def record_exists(target, key_fields, key_values):
    """Checks if a record with specific key values exists in the target table."""
    where_clause = " AND ".join([f"{field} = '{value}'" for field, value in zip(key_fields, key_values)])
    with arcpy.da.SearchCursor(target, key_fields, where_clause) as cursor:
        for _ in cursor:
            return True  # Record found
    return False  # Record not found

try:
    #arcpy.management.Append(filepath+parcel_list_name, 'Parcel_APN_NewOld', schema_type="NO_TEST")

    # Define the unique key fields
    key_fields = ['APN', 'Status', 'DiscoveryDate']
    update_fields = ['APN', 'Status', 'DiscoveryDate']
    records_to_append = []

    print("Checking for duplicates in the target table...")
    for _, row in df_parcel_changes.iterrows():
        # Skip records with empty or null APN
        if not row['APN'] or pd.isna(row['APN']):
            print("Skipping record with empty or null APN.")
            continue
        # Extract key values from the current row
        key_values = [row[field] for field in key_fields]
        # Check if the record already exists in the target table
        if not record_exists(target_table, key_fields, key_values):
            records_to_append.append(key_values)
        else:
            print(f"Record {dict(zip(key_fields, key_values))} already exists. Skipping.")
    
    if records_to_append:
        print(f"Appending {len(records_to_append)} new records to the target table...")
        with arcpy.da.InsertCursor(target_table, update_fields) as insert_cursor:
            for record in records_to_append:
                #print(f"Inserting record {dict(zip(update_fields, record))}")
                insert_cursor.insertRow(record)
        print("Records successfully appended.")
    else:
        print("No new records to append.")    
except Exception:
    e = sys.exc_info()[1]
    print(e.args[0])