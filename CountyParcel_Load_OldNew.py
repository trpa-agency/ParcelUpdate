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

#Create database connection
# Create Local Database Connection
# Enterprise geodatabase connection parameters
server_name = "sql12"
database_name = "sde"
username = _creds["sde_username"]
password = _creds["sde_password"]


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
username = _creds["sde_username"]
password = _creds["sde_password"]

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
old_fc = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/parcel_master"
target_table = "db_connections/ConnectionFile_Tabular.sde/Parcel_APN_NewOld"
new_fc = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging"


prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')

df_parcel_changes = utils.make_old_new_dataframe(old_fc, new_fc, 'Yes', prefix_remove)
df_parcel_changes.to_csv(filepath+parcel_list_name, index=False)

inWorkspace = 'db_connections/ConnectionFile_Tabular.sde'
arcpy.env.workspace = inWorkspace

# Function to check for duplicate records
# Function to check if APN+Status exists in the latest record for that APN
def latest_record_has_status(target, apn, status):
    """Returns True if the latest record for this APN already has this status."""
    # Get the latest DiscoveryDate for this APN
    where_clause = f"APN = '{apn}'"
    fields = ['Status', 'DiscoveryDate']
    latest_date = None
    latest_status = None

    with arcpy.da.SearchCursor(target, fields, where_clause, sql_clause=(None, "ORDER BY DiscoveryDate DESC")) as cursor:
        for row in cursor:
            latest_status = row[0]
            latest_date = row[1]
            break  # Only need the first row (latest)
    
    if latest_status is not None and latest_status == status:
        return True  # Status already exists for the latest record
    
    return False

try:
    update_fields = ['APN', 'Status', 'DiscoveryDate']
    records_to_append = []

    print("Checking for duplicates in the target table based on latest record...")

    for _, row in df_parcel_changes.iterrows():
        # Skip records with empty or null APN
        if not row['APN'] or pd.isna(row['APN']):
            print("Skipping record with empty or null APN.")
            continue
        
        apn = row['APN']
        status = row['Status']
        discovery_date = row['DiscoveryDate']

        if not latest_record_has_status(target_table, apn, status):
            records_to_append.append([apn, status, discovery_date])
        else:
            print(f"Latest record for APN {apn} already has Status '{status}'. Skipping.")

    if records_to_append:
        print(f"Appending {len(records_to_append)} new records to the target table...")
        with arcpy.da.InsertCursor(target_table, update_fields) as insert_cursor:
            for record in records_to_append:
                insert_cursor.insertRow(record)
        print("Records successfully appended.")
    else:
        print("No new records to append.")

except Exception:
    e = sys.exc_info()[1]
    print(e.args[0])
