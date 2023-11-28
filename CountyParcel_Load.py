#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
from datetime import datetime
import os
import sys
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
import sqlalchemy as sa
import pandas as pd
from arcgis.features import FeatureSet, GeoAccessor, GeoSeriesAccessor
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from time import strftime

# environment settings
arcpy.env.workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# Get the current script's directory
#script_directory = os.path.dirname(os.path.abspath(__file__))

# set workspace and sde connections 
workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/Staging"

# network path to connection files
#filePath = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/"


#This needs to be shifted over to SQL Table
df_special_parcels= pd.read_excel("//Trpa-fs01/GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")

""" #Create Local Database Connection
# Enterprise geodatabase connection parameters
server_name = "sql12"
database_name = "sde"
username = "sde"
password = "staff"
#change to include date dynamically
version_name = "parcel_update_10182023"

# Create a new connection to the enterprise geodatabase in the script directory
enterprise_connection = arcpy.CreateDatabaseConnection_management(
    script_directory, "EnterpriseDBConnection.sde", "SQL_SERVER", server_name, database_name,
    "DATABASE_AUTH", username, password, "SAVE_USERNAME"
)[0] """

### Functions ###
# time a function function
## use as decorator @timer
def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time} seconds to execute.")
        return result
    return wrapper

@timer           
def UpdateFieldFromDictionary(featureclass, field, update_dictionary):
    record_count = 0
    with arcpy.da.UpdateCursor(featureclass, field) as cursor:
        for row in cursor:
            key_field_value = row[0]
            if key_field_value in update_dictionary:
                row[0] = update_dictionary[key_field_value]
                cursor.updateRow(row)
                record_count+=record_count
    print(f"{record_count} rows were updated")


# moves attribute values from one feature class to the other using an aspatial join
@timer
def fieldJoinCalc(updateFC, updateFieldsList, sourceFC, sourceFieldsList):
    from time import strftime  
    print ("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
#     log.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Use list comprehension to build a dictionary from arcpy SearchCursor  
    valueDict = {r[0]:(r[1:]) for r in arcpy.da.SearchCursor(sourceFC, sourceFieldsList)}  
   
    with arcpy.da.UpdateCursor(updateFC, updateFieldsList) as updateRows:  
        for updateRow in updateRows:  
            # store the Join value of the row being updated in a keyValue variable  
            keyValue = updateRow[0]  
            # verify that the keyValue is in the Dictionary  
            if keyValue in valueDict:  
                # transfer the value stored under the keyValue from the dictionary to the updated field.  
                updateRow[1] = valueDict[keyValue][0]  
                updateRows.updateRow(updateRow)    
    del valueDict  
    print ("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
#     log.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

# transfer attributes frome one feature class field to another while using multiple fields to create the keys@timer
def fieldJoinCalc_multikey(updateFC, updateFieldsList_key, updateFieldsList_value, sourceFC, sourceFieldsList_key, sourceFieldsList_value, edit_session):
    from time import strftime  
    print ("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
#     log.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Use list comprehension to build a dictionary from arcpy SearchCursor  
    total_count=0
    valueDict = {(r[0]+r[1]):(r[2]) for r in arcpy.da.SearchCursor(sourceFC, (sourceFieldsList_key + sourceFieldsList_value))}  
    with arcpy.da.UpdateCursor(updateFC, (updateFieldsList_key+ updateFieldsList_value)) as updateRows:  
        for updateRow in updateRows:  
            # store the Join value of the row being updated in a keyValue variable  
            keyValue = updateRow[0]+updateRow[1]
            # verify that the keyValue is in the Dictionary  
            if keyValue in valueDict:
                total_count +=1
                if (total_count%1000)==0:
                    print (f"Updating row {total_count}")
                edit_session.startOperation()
                # transfer the value stored under the keyValue from the dictionary to the updated field.  
                updateRow[2] = valueDict[keyValue]  
                
                updateRows.updateRow(updateRow)
                edit_session.stopOperation()    
    del valueDict  
    print ("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    
#     log.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
#Gonna have to make this a compound key as well - need to handle duplicate APNs?
@timer
def differenceDictionary(df1, df2, key_field, fields_to_ignore):
    #Generate a list of columns in common
    common_columns = list(set(df1.columns) & set(df2.columns))
    # keep only the common columns in both dataframes
    df1 = df1[common_columns]
    df2 = df2[common_columns]
    #Trim spaces
    df1 = df1.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    df2 = df2.applymap(lambda x: x.strip() if isinstance(x, str) else x)
    
    #Force the column types to match
    for field in fields_to_ignore:
        df1 = df1.drop(field, axis=1)
        df2 = df2.drop(field, axis=1)
    for column in df2.columns:
        if df1[column].dtype != df2[column].dtype:
            print(column)
            print (df2[column].dtype)
            #This handles nulls
            if df1[column].dtype=='int64':
                df1[column]=df1[column].astype('Int64')
            df2.loc[:, column] = df2[column].astype(df1[column].dtype)
    #make an index from multiple fields    
    df1 = df1.set_index(key_field)
    df2 = df2.set_index(key_field)
    df1.sort_index(inplace=True)
    df2.sort_index(inplace=True)
    common_columns = list(set(df1.columns) & set(df2.columns))
    df1 = df1[common_columns]
    df2 = df2[common_columns]
    diff_df = df1.compare(df2)
    #
    if diff_df.empty:
        return {}
    new_values =diff_df.loc[:,pd.IndexSlice[:,'other']].droplevel(1,axis=1)
    #This wouldn't have to be modified
    dict_update = new_values.to_dict('index')
    #
    new_dict = {k: {a: b for a, b in v.items() if not pd.isnull(b)} 
                for k, v in dict_update.items()}
    # This portion gets rid of APNs with no changes to keep dictionary size managable
    keys_to_remove = []
    for outer_key, inner_dict in new_dict.items():
        inner_keys_to_remove = []
        for inner_key, value in inner_dict.items():
            if not value:
                inner_keys_to_remove.append(inner_key)
        for inner_key in inner_keys_to_remove:
            del inner_dict[inner_key]
        if not inner_dict:
            keys_to_remove.append(outer_key)

    for outer_key in keys_to_remove:
        del new_dict[outer_key]
    return new_dict

# use the differences dictionary to update attributes in feature service or feature class
@timer
def update_fc_from_dict(update_dict,key_field, fc,edit_session):
    #This gets our update cursor down to fields that need to be updated
    update_fields = set(field for values in update_dict.values() for field in values.keys())
    # create a SQL query to filter the feature class based on the key field values
    key_field_values = tuple(update_dict.keys())
    print("Updating Attributes started: " + strftime("%Y-%m-%d %H:%M:%S"))
    # update the attributes using the nested dictionary
    apn_issues =list()
    with arcpy.da.UpdateCursor(fc, [key_field] + list(update_fields)) as cursor:
        total_count=0
        for row in cursor:
            key_field_value = row[0]
            if key_field_value in update_dict:
                try:
                    update_values = update_dict[key_field_value]
                    total_count +=1
                    if (total_count%1000)==0:
                        print (f"Updating row {total_count} at "+ strftime("%Y-%m-%d %H:%M:%S"))
                    for field, value in update_values.items():
                        index = cursor.fields.index(field)
                        row[index] = value
                    edit_session.startOperation()
                    cursor.updateRow(row)
                    edit_session.stopOperation()
                        #print("Updated APN/Field: "+str(row[0])+" / "+str(field))
                except Exception as e:
                    apn_issues.append(key_field_value)
                    # Print the error message
                    print(f"Error updating {key_field_value}: {e}")
                    continue
    print("Updating Attributes Finished: " + strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Total updated{total_count}")
    return apn_issues

#Seperated out into two functions 
# so we can use this function to make old new table in SQL
@timer
def make_old_new_dataframe(old_feature_class, new_feature_class, TRPA_boundary, prefix_remove):
    df_old = pd.DataFrame.spatial.from_featureclass(old_feature_class)
    df_new = pd.DataFrame.spatial.from_featureclass(new_feature_class)
    df_merge = pd.merge(df_old, df_new,  how='outer', on=['APN'], indicator=True)
    df_merge.query('_merge!="both"', inplace=True)
    df_merge.loc[df_merge['_merge']=='right_only', 'Status']='New APN'
    # define Left Only as Old APNs
    df_merge.loc[df_merge['_merge']=='left_only', 'Status']='Old APN'
    df_merge.dropna(subset=['APN'], inplace=True) 
    df_merge = df_merge.loc[~df_merge['APN'].str.startswith(prefix_remove)]
    #
    date = time.strftime("%m%d%Y")
    df_merge['DiscoveryDate'] = date
    df_merge['DiscoveryDate'] = pd.to_datetime(df_merge['DiscoveryDate'], format='%m%d%Y')
    TRPA_BNDY_Fields = [col for col in df_merge.columns if 'WITHIN_TRPA_BNDY' in col]
    df_merge['TRPA_Boundary'] = df_merge[TRPA_BNDY_Fields].sum(axis=1)
    # final list of fields
    df_merge = df_merge[['APN','Status','DiscoveryDate','TRPA_Boundary']]
    if TRPA_boundary == 'Yes':
        df_merge = df_merge.loc[df_merge['TRPA_Boundary']>=1]
    return df_merge

# get the list of old and new parcels
#Think this through to handle duplicate APNs
@timer
def old_new_parcels_list(old_feature_class, 
                         new_feature_class, 
                         TRPA_boundary, 
                         prefix_remove, 
                         old_new):
    df_merge = make_old_new_dataframe(old_feature_class, new_feature_class, TRPA_boundary, prefix_remove)
    parcel_list = df_merge.loc[df_merge['Status']==old_new,'APN'].tolist()
    return parcel_list

#Identify differences between APNs that haven't changed
#MAKE A MULTI JOIN
@timer
def return_matching_apns(feature_class_old, 
                         feature_class_new, 
                         parcels_ignore):
    dfOld = pd.DataFrame.spatial.from_featureclass(feature_class_old)
    dfOld = dfOld[~dfOld['APN'].isin(parcels_ignore['APN'])]
    dfNew = pd.DataFrame.spatial.from_featureclass(feature_class_new)
    dfNew = dfNew.loc[dfNew['WITHIN_TRPA_BNDY']==1]
    matching_apns  = pd.merge(dfOld, dfNew,  how='inner', on=['APN'])
    matching_apns =pd.unique(matching_apns['APN'])
    return matching_apns

# deletes parcels
@timer
def delete_old_parcels(featureLayer, oldAPNs, edit_session):
    delete_count = 0
    with arcpy.da.UpdateCursor(featureLayer, ["APN"]) as cursor:
        for row in cursor:
            apn = row[0]
            if apn in oldAPNs:
                edit_session.startOperation()
                cursor.deleteRow()
                edit_session.stopOperation()
                delete_count +=1
    print(f"{delete_count} rows deleted from {featureLayer}.")

# inserts new parcels
@timer
def insert_new_parcels(featureLayer, new_APNs, new_parcels, fields, edit_session):
    new_count = 0
    where_clause = f"{arcpy.AddFieldDelimiters(featureLayer, 'APN')} IN "+str(tuple(new_APNs))
    print(where_clause)
    with arcpy.da.SearchCursor(new_parcels, fields, where_clause) as search_cursor:
    # Open an insert cursor to the destination feature class
        edit_session.startOperation()
        with arcpy.da.InsertCursor(featureLayer, fields) as insert_cursor:
            # insert the rows from the serach cursor
            for row in search_cursor:
                
                insert_cursor.insertRow(row)
                
                new_count +=1
                print(f"{new_count} rows inserted into {featureLayer}.")
        edit_session.stopOperation()
                
def generate_updated_shape_wkt(featureLayer, wkt_file_name):
    # Open the output text file for writing
    with open(wkt_file_name, "w") as wkt_file:
        # Write headers for your fields    
        field_names = ["APN"]  
        # Replace with your field names    
        wkt_file.write("\t".join(field_names) + "\tWKT\n")

            # Create a cursor to retrieve fields and geometry    
        fields = ["APN", "SHAPE@WKT"]  # Replace with your actual field names    
        cursor = arcpy.da.SearchCursor(featureLayer, fields)
        for row in cursor:
            field1_value,  wkt_geometry = row        
            row_data = [field1_value, wkt_geometry]
            wkt_file.write("\t".join(map(str, row_data)) + "\n")
        # Clean up by deleting the cursor
        del cursor

# updates @SHAPE that aren't identical to existing shapes
@timer
def update_parcel_geometry(featureLayer, new_parcels, edit_session):
    newShapes = arcpy.management.SelectLayerByLocation(
    in_layer=new_parcels,
    overlap_type="ARE_IDENTICAL_TO",
    select_features=featureLayer,
    search_distance=None,
    selection_type="NEW_SELECTION",
    invert_spatial_relationship="INVERT")
    # update SHAPE object with new value
    #Changed this to Jurisdiction to work with Parcel_Base
    updateFieldsList_key= ['APN', 'JURISDICTION']
    updateFieldsList_value = ['SHAPE@']
    sourceFieldsList_key = ['APN', 'JURISDICTION']
    sourceFieldsList_value = ['SHAPE@']
    fieldJoinCalc_multikey(featureLayer, updateFieldsList_key, updateFieldsList_value, newShapes, sourceFieldsList_key, sourceFieldsList_value, edit_session)

    # Get the count of selected features
    result = arcpy.management.GetCount(newShapes)
    count = int(result.getOutput(0))
    # number of shapes shifted
    print(f"{count} shapes shifted.")
    wkt_file_name = "Updated_Shapes_" + strftime("%Y-%m-%d")+".wkt"
    #Write to a wky file
    generate_updated_shape_wkt(newShapes, wkt_file_name)
    
@timer
def generate_spatial_dataframe(feature_class, data_type_mapping, fields_to_exclude): 
    # Get the field names and data types
    fields = arcpy.ListFields(feature_class)
    field_names = [field.name for field in fields if field.name not in fields_to_exclude]
    field_data_types = {field.name: field.type for field in fields if field.name not in fields_to_exclude}

    # Create a dictionary to store the data
    data = {}

    # Iterate through the rows and populate the dictionary
    with arcpy.da.SearchCursor(feature_class, field_names) as cursor:
        for row in cursor:
            for i, field_name in enumerate(field_names):
                if field_name not in data:
                    data[field_name] = []
                data_type = data_type_mapping.get(field_data_types[field_name], str)
                if row[i] is not None:
                    data[field_name].append(data_type(row[i]))
                else:
                    data[field_name].append(row[i])

    # Create a pandas DataFrame from the dictionary
    df = pd.DataFrame(data)

    return df

def get_text_fields(feature_class):
    field_list = []
    fields = arcpy.ListFields(feature_class)
    for field in fields:
        if field.type == 'String':
            field_list.append(field.name)
    return field_list

#Create database connection
inWorkspace = "//Trpa-fs01\GIS\PARCELUPDATE\Workspace\Vector.sde"
arcpy.env.workspace = inWorkspace
# Specify the name of the new version and the parent version
new_version_name = "Parcel_Update_" + strftime("%Y-%m-%d")
parent_version = "SDE.DEFAULT"
version_name_full = "SDE." + new_version_name
parcelMaster = 'parcelMasterVersion'
parcelBase = 'parcelBaseVersion'
arcpy.MakeFeatureLayer_management(r'SDE.Parcels\SDE.Parcel_Master',parcelMaster)
arcpy.MakeFeatureLayer_management(r'SDE.Parcels\SDE.Parcels_Base',parcelBase)

parcelNew = 'parcelNew'

arcpy.MakeFeatureLayer_management("//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging", parcelNew)

# Create a new version
arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")

# prefixes to remove...these we keep or ignore
prefix_remove = ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900')
# parcel master old/new
parcel_master_new_apn = old_new_parcels_list(parcelMaster, parcelNew, 'Yes', 
                                             prefix_remove,'New APN')
parcel_master_old_apn = old_new_parcels_list(parcelBase, parcelNew, 'No', 
                                             prefix_remove,'Old APN')
# parcel base old/new
parcel_base_new_apn   = old_new_parcels_list(parcelBase, parcelNew, 'Yes', 
                                           prefix_remove,'New APN')
parcel_base_old_apn   = old_new_parcels_list(parcelBase, parcelNew, 'No', 
                                           prefix_remove,'Old APN')

#Need to generate a list of new and old parcels and add it to TableNewOld_APN in sde_tabular
# Make the dataframe for eventual insert to new_old SQL table - wait to actually insert until process is complete

df_parcel_changes = make_old_new_dataframe(parcelMaster, parcelNew, 'Yes', prefix_remove)

# UPDATE PARCEL MASTER

#set up mapping for conversion from feature class to data frame

data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

fields_to_exclude = ['SHAPE','OBJECTID', 'Shape']

dfparcelNew = generate_spatial_dataframe(parcelNew, data_type_mapping, fields_to_exclude)
dfparcelMaster = generate_spatial_dataframe(parcelMaster, data_type_mapping, fields_to_exclude)

# filter to new parcels within TRPA boundary
dfparcelNew=dfparcelNew.loc[dfparcelNew['WITHIN_TRPA_BNDY']==1]
df_special_parcels = pd.read_excel("//Trpa-fs01/GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")
matching_apns_parcel_master = return_matching_apns(parcelMaster, parcelNew, df_special_parcels)

# filter parcel master to matching APNs
dfparcelMaster = dfparcelMaster[dfparcelMaster['APN'].isin(matching_apns_parcel_master)]
# filter staging data to matching APNs
dfparcelNew    = dfparcelNew[dfparcelNew['APN'].isin(matching_apns_parcel_master)]

#These fields won't be compared between existing and new parcels
fields_to_ignore = ['PARCEL_SQFT', 'PPNO', 'ESTIMATED_COVERAGE_ALLOWED', 'IMPERVIOUS_SURFACE_SQFT', 
                    'LOCATION_TO_TOWNCENTER', 'UNITS', 'PARCEL_ACRES','YEAR_BUILT', 'BEDROOMS',
                   'BUILDING_SQFT', 'BATHROOMS']

# get the differences as dictionaries
differences_master = differenceDictionary(dfparcelMaster, dfparcelNew, 'APN', fields_to_ignore)
dfDiff = pd.DataFrame(differences_master)
dfDiff.to_csv("Differences_List.csv")

# function to update attributes
# This can take a minute - CHANGE TO WRITE TO CSV?
#Create Local Database Connection
# Enterprise geodatabase connection parameters
server_name = "sql12"
database_name = "sde"
username = "sde"
password = "staff"
#change to include date dynamically
#version_name = "parcel_update_10182023"

# Create a new connection to the enterprise geodatabase in the script directory
#enterprise_connection = os.path.join(script_directory, "EnterpriseDBConnection.sde")

# If you want to create a connection file, you can use the following code:
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
# Create a new version
#arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")
arcpy.ChangeVersion_management(parcelMaster,'TRANSACTIONAL', version_name_full, '')
# Start an edit session
edit = arcpy.da.Editor('db_connections/ConnectionFile.sde')
edit.startEditing(False, True)
#Update Parcel_Master
#try:
    # Start an edit operation
#edit.startOperation()
apn_issues = update_fc_from_dict(differences_master, 'APN', parcelMaster,edit)
if len(apn_issues)==0:
    print ("No issues with executing updates")
else:
    print("There were issues with the following APNs")
    print(apn_issues)
edit.stopEditing(True)

edit.startEditing(False, True)

delete_old_parcels(parcelMaster, parcel_master_old_apn, edit)

fields = arcpy.ListFields(parcelMaster)
field_names_master = [field.name for field in fields ]
fields_new = arcpy.ListFields(parcelNew)
field_names_new = [field.name for field in fields_new ]

common_fields = list(set(field_names_master) & set(field_names_new))
insert_new_parcels(parcelMaster, parcel_master_new_apn, parcelNew, common_fields, edit)

#update_parcel_geometry(parcelMaster, parcelNew, edit)
edit.stopEditing(True)

edit = arcpy.da.Editor('db_connections/ConnectionFile.sde')
edit.startEditing(False, True)

update_parcel_geometry(parcelMaster, parcelNew, edit)
edit.stopEditing(True)
# UPDATE PARCEL BASE

# set up mapping for conversion from feature class to data frame
data_type_mapping = {
    "String": str,
    "Integer": int,
    "SmallInteger": int,
    "Single": float,
    "Double": float,
    "Date": pd.to_datetime
}

fields_to_exclude = ['SHAPE']
dfparcelNew = generate_spatial_dataframe(parcelNew, data_type_mapping, fields_to_exclude)
dfparcelBase = generate_spatial_dataframe(parcelBase, data_type_mapping, fields_to_exclude)

# filter to new parcels within TRPA boundary
dfparcelNew=dfparcelNew.loc[dfparcelNew['WITHIN_TRPA_BNDY']==1]
#df_special_parcels = pd.read_excel("//Trpa-fs01/GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")
matching_apns_parcel_base = return_matching_apns(parcelBase, parcelNew, df_special_parcels)

# filter parcel master to matching APNs
dfparcelBase = dfparcelBase[dfparcelBase['APN'].isin(matching_apns_parcel_base)]
# filter staging data to matching APNs
dfparcelNew    = dfparcelNew[dfparcelNew['APN'].isin(matching_apns_parcel_base)]


fields_to_ignore = ['Shape', 'PARCEL_ACRES', 'PARCEL_SQFT', 'OBJECTID']

# get the differences as dictionaries
differences_base = differenceDictionary(dfparcelBase, dfparcelNew, 'APN', fields_to_ignore)

print(len(differences_base))
df_dif=pd.DataFrame(differences_base)
df_dif.to_csv('base_differences.csv')

arcpy.ChangeVersion_management(parcelBase,'TRANSACTIONAL', version_name_full, '')
edit = arcpy.da.Editor('db_connections/ConnectionFile.sde')
edit.startEditing(False, True)

if len(differences_base)==0:
    print('No changes to base attributes')
else:
    apn_issues = update_fc_from_dict(differences_base, 'APN', parcelBase, edit)
    if len(apn_issues)==0:
        print ("No issues with executing updates")
    else:
        print("There were issues with the following APNs")
        print(apn_issues)

edit.stopEditing(True)
#Geometry Updates
fields = ['APN','PPNO','PARCEL_ACRES','PARCEL_SQFT','JURISDICTION','SHAPE@']

edit.startEditing(False, True)
delete_old_parcels(parcelBase, parcel_base_old_apn, edit)
insert_new_parcels(parcelBase, parcel_base_new_apn, parcelNew, fields, edit)
edit.stopEditing(True)

edit.startEditing(False, True)
update_parcel_geometry(parcelBase, parcelNew, edit)
# Stop the edit operation

# Save the edits and stop the edit session
edit.stopEditing(True)

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

filepath = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/Parcel_Old_New/"
parcel_list_name = "Parcel_Old_New" + strftime("%Y-%m-%d")+".csv"
df_parcel_changes.to_csv(filepath+parcel_list_name, index=False)

inWorkspace = 'db_connections/ConnectionFile_Tabular.sde'
arcpy.env.workspace = inWorkspace

try:
    arcpy.management.Append(filepath+parcel_list_name, 'Parcel_APN_NewOld', schema_type="NO_TEST")    
except Exception as e:
    print (f"Issue with updating list of new and old parcels: {e}")