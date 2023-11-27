import pandas as pd
import numpy as np
import requests
from arcgis import GIS
import arcpy
from arcgis.features import FeatureLayer
from datetime import datetime
import os
import time
from time import strftime

# Connect to TRPA Enterprise GIS Portal
portal_user = "TRPA_PORTAL_ADMIN"
portal_pwd = "@dmin6224"
portal_url = "https://maps.trpa.org/portal/"
# sign in
#arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)
gis = GIS(portal_url, portal_user,portal_pwd)
arcpy.env.workspace = "F:\GIS\PROJECTS\ResearchAnalysis\VHR\Data\VHR_Staging.gdb"
workspace           = r"F:\GIS\PROJECTS\ResearchAnalysis\VHR\Data\VHR_Staging.gdb"
workspace_folder    = r"F:\GIS\PROJECTS\ResearchAnalysis\VHR\VHR"

service_url = 'https://maps.trpa.org/server/rest/services/Parcel_Master/FeatureServer/0'
feature_layer = FeatureLayer(service_url)
query_result = feature_layer.query()
# Convert the query result to a list of dictionaries
sdfParcels = query_result.sdf

def get_fs_data(service_url):
    
    feature_layer = FeatureLayer(service_url)
    query_result = feature_layer.query()
    # Convert the query result to a list of dictionaries
    feature_list = query_result.features

    # Create a pandas DataFrame from the list of dictionaries
    all_data = pd.DataFrame([feature.attributes for feature in feature_list])

    return all_data

def renamecolumns(df, column_mapping, county, jurisdiction):
    df = df.rename(columns=column_mapping).drop(columns=[col for col in df.columns if col not in column_mapping])
    df['county'] = county
    df['jurisdiction'] = jurisdiction
    return df
def download_sdf(service_url):
   
    feature_layer = FeatureLayer(service_url)
    query_result = feature_layer.query()
# Convert the query result to a list of dictionaries
    sdf = query_result.sdf
    return sdf

def before_or_after_today(date):
    today = datetime.now()
    if date < today:
        return 'expired'
    else:
        return 'active'

washoe_data_sdf = download_sdf('https://wcgisweb.washoecounty.us/arcgis/rest/services/OpenData/OpenData/MapServer/146')
eldorado_data_sdf = download_sdf('https://see-eldorado.edcgov.us/arcgis/rest/services/Vhr_App/VHR_PERMITS/MapServer/1')
placer_data_sdf = download_sdf('https://services6.arcgis.com/PArfeTGcwA9RGNzN/ArcGIS/rest/services/STR_Permits_231002_Parcels/FeatureServer/0')
CSLT_data_sdf = download_sdf('https://services2.arcgis.com/gWRYLIS16mKUskSO/ArcGIS/rest/services/VHR_Public/FeatureServer/0')
douglas_data_sdf = download_sdf('https://gisservices.douglasnv.us/server/rest/services/VHR_Occupancy/MapServer/67')
CSLT_Hosted_Rental_Data_sdf = download_sdf('https://services2.arcgis.com/gWRYLIS16mKUskSO/arcgis/rest/services/Hosted_Rentals_Public/FeatureServer/0')

washoe_data_sdf.spatial.to_featureclass(os.path.join(workspace, "VHR_Raw_WA"), sanitize_columns=False)
eldorado_data_sdf.spatial.to_featureclass(os.path.join(workspace, "VHR_Raw_EL"), sanitize_columns=False)
placer_data_sdf.spatial.to_featureclass(os.path.join(workspace, "VHR_Raw_PL"), sanitize_columns=False)
CSLT_data_sdf.spatial.to_featureclass(os.path.join(workspace, "VHR_Raw_CSLT"), sanitize_columns=False)
CSLT_Hosted_Rental_Data_sdf.spatial.to_featureclass(os.path.join(workspace, "Hosted_Raw_CSLT"), sanitize_columns=False)
douglas_data_sdf.spatial.to_featureclass(os.path.join(workspace, "VHR_Raw_DG"), sanitize_columns=False)

washoe_data = get_fs_data('https://wcgisweb.washoecounty.us/arcgis/rest/services/OpenData/OpenData/MapServer/146')
eldorado_data = get_fs_data('https://see-eldorado.edcgov.us/arcgis/rest/services/Vhr_App/VHR_PERMITS/MapServer/1')
placer_data = get_fs_data('https://services6.arcgis.com/PArfeTGcwA9RGNzN/ArcGIS/rest/services/STR_Permits_231002_Parcels/FeatureServer/0')
CSLT__VHR_data = get_fs_data('https://services2.arcgis.com/gWRYLIS16mKUskSO/ArcGIS/rest/services/VHR_Public/FeatureServer/0')
CSLT_Hosted_Rental_Data = get_fs_data('https://services2.arcgis.com/gWRYLIS16mKUskSO/arcgis/rest/services/Hosted_Rentals_Public/FeatureServer/0')
douglas_data = get_fs_data('https://gisservices.douglasnv.us/server/rest/services/VHR_Occupancy/MapServer/67')

#Can't figure out why field mapping is giving an error for this so I had to do a workaround
washoe_data['APN']=washoe_data['B1_PARCEL_NBR']

EL_Field_Mapping = {'APN' : 'APN', 
'License_Status' : 'Status', 
'Account_Number' : 'Permit_ID', 
'Number_of_Overnight_Guests' : 'Max_Occupancy'
}
PL_Field_Mapping = {
   'COPY_STRPermits_231002_ExcelT_4' : 'APN', 
'COPY_STRPermits_231002_ExcelT_2' : 'Status', 
'COPY_STRPermits_231002_ExcelT_1' : 'Permit_ID' 

}
WA_Field_Mapping = {
  'APN' : 'APN', 
'APPL_STATUS' : 'Status', 
'Record_ID' : 'Permit_ID', 
'MaxOccupancy' : 'Max_Occupancy'

}
DG_Field_Mapping = {
  'APN' : 'APN', 
'Permit_Status' : 'Status', 
'Accela_Permit__' : 'Permit_ID', 
'Max_Nighttime_Occupancy' : 'Max_Occupancy',
'Expire_Date': 'expiration_date'
}
CSLT_Field_Mapping = {
    'prcl_id' : 'APN', 

'bl_id' : 'Permit_ID', 
'occpy_max' : 'Max_Occupancy',
'expiration': 'expiration_date'
}
CSLT_Hosted_Mapping = {
    'prcl_id' : 'APN',
    'Permit' : 'Permit_ID',
    'permit_status': 'Status',
    'Max_Occupancy': 'Max_Occupancy'
}

EL_VHR = renamecolumns(eldorado_data, EL_Field_Mapping, 'EL', 'EL')
EL_VHR['APN'] = EL_VHR['APN'].str[:3]+'-'+EL_VHR['APN'].str[3:6]+'-'+EL_VHR['APN'].str[6:9]
PL_VHR = renamecolumns(placer_data, PL_Field_Mapping, 'PL', 'PL')
PL_VHR['APN']=PL_VHR['APN'].str[:11]
DG_VHR = renamecolumns(douglas_data, DG_Field_Mapping, 'DG', 'DG')
DG_VHR['APN']=DG_VHR['APN'].astype(str)
DG_VHR['APN'] = DG_VHR['APN'].str[:4]+'-'+DG_VHR['APN'].str[4:6]+'-'+DG_VHR['APN'].str[6:9]+'-'+DG_VHR['APN'].str[9:12]
DG_VHR['expiration_date']=pd.to_datetime(DG_VHR['expiration_date'], unit='ms')
WA_VHR = renamecolumns(washoe_data, WA_Field_Mapping, 'WA', 'WA')
WA_VHR['APN']=WA_VHR['APN']
CSLT_VHR = renamecolumns(CSLT__VHR_data, CSLT_Field_Mapping, 'EL', 'CSLT')
CSLT_VHR['APN'] = CSLT_VHR['APN']
CSLT_VHR['expiration_date']=pd.to_datetime(CSLT_VHR['expiration_date'], unit='ms')
CSLT_Hosted=renamecolumns(CSLT_Hosted_Rental_Data, CSLT_Hosted_Mapping, 'EL','CSLT')
CSLT_Hosted['Rental_Type']="Hosted Rental"
VHR_Data = pd.concat([EL_VHR, PL_VHR, DG_VHR, WA_VHR, CSLT_VHR, CSLT_Hosted])

VHR_Data['Rental_Type']=VHR_Data['Rental_Type'].fillna('VHR')
VHR_Data.loc[(VHR_Data['jurisdiction']=='CSLT')&(VHR_Data['Status'].isna()), 'Status'] = VHR_Data.loc[(VHR_Data['jurisdiction']=='CSLT')&(VHR_Data['Status'].isna()),'expiration_date'].apply(before_or_after_today)

status_lookup = {'VHR Permit- Waitlist' : 'Pending', 
'VHR Permit- Expired' : 'Inactive', 
'VHR Permit - Active' : 'Active', 
'VHR Permit- Submitted' : 'Pending', 
'VHR Permit- Approved for Payment' : 'Pending', 
'VHR Permit- Incomplete' : 'Pending', 
'VHR Permit - Inactive' : 'Inactive', 
'Inactive' : 'Inactive', 
'VHR Permit- Denied' : 'Inactive', 
'VHR Permit- Withdrawn' : 'Inactive', 
'VHR Permit- Complete' : 'Active', 
'VHR Permit- Closed' : 'Inactive', 
'VHR Permit- Revoked' : 'Inactive', 
'VHR Permit- Suspended' : 'Suspended',
'current' : 'Active', 
'Current' : 'Active', 
'Suspended' : 'Suspended', 
'Active' : 'Active', 
'About to Expire' : 'Active',
'active':'Active',
'denied': 'Inactive',
'expired': 'Inactive'
}
VHR_Data['Status'] = VHR_Data['Status'].str.strip()
VHR_Data['Status'] = VHR_Data['Status'].replace(status_lookup)
VHR_Data['Status'] = VHR_Data['Status'].fillna('Active')
VHR_Data['Rental_Type'] = VHR_Data['Rental_Type'].fillna('VHR')

merged_df = pd.merge(sdfParcels, VHR_Data,  left_on=['APN', 'JURISDICTION'], right_on=['APN', 'jurisdiction'], how='inner' )

drop_columns = ['OBJECTID',  'GlobalID', 'created_user', 'created_date', 'last_edited_user','last_edited_date']
merged_df.drop(columns=drop_columns, inplace=True)

merged_df.spatial.to_featureclass(os.path.join(workspace, "Parcel_VHR"), sanitize_columns=False)


## use as decorator @timer
def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time} seconds to execute.")
        return result
    return wrapper
#Difference dictionary and only make edits where things have changed?

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
    #    
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
    #
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

#Pull existing feature class and bring that in for comparison
# We also need to handle old new ones? 