"""
CountyParcel_Extract.py
Created: June 15th,2023
Last Updated: June 15th, 2023
Amy Fish, Tahoe Regional Planning Agency
Andy McClary, Tahoe Regional Planning Agency
Mason Bindl, Tahoe Regional Planning Agency

This python script was developed to get data from the five Tahoe Counties.
El Dorado, Carson, Douglas, Placer, and Washoe. 
The data is then staged for transformation. 

This script uses Python 3.x and was designed to be used with 
the default ArcGIS Pro python enivorment ""C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe"", with
no need for installing new libraries.

This script runs on the 16th of each month at 1am on Arc10 from scheduled task "CountyParcelExtract"
"""
#--------------------------------------------------------------------------------------------------------#
# import packages and modules
# import packages
import urllib
import json
import requests
import os
import shutil
import sys
import re
import logging

from datetime import datetime 
import time
from zipfile import ZipFile
from io import BytesIO

import pandas as pd
import pyodbc

import arcpy
from arcgis.features import GeoAccessor, GeoSeriesAccessor
from arcgis.gis import GIS

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# import traceback
# from pytz import timezone
# import pytz
import pathlib
# from IPython.display import display
# import getpass
from time import strftime
# import linecache
# import ssl

# environment settings
arcpy.env.workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# set workspace and sde connections 
workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/Staging"

# network path to connection files
filePath = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/"
# database file path 
sdeBase    = os.path.join(filePath, "Vector.sde/")
sdeCollect = os.path.join(filePath, "Collection.sde")
sdeTabular = os.path.join(filePath, "Tabular.sde")

# portal signin
## TRPA_ADMIN credentials 
portal_user = "TRPA_PORTAL_ADMIN"
portal_pwd = "@dmin6224"
portal_url = "https://maps.trpa.org/portal/"
# sign in
arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)

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

# set none to '' for all cells
@timer
def replace_null_values_with_blank(fc):
    field_list = get_text_fields(fc)
    with arcpy.da.UpdateCursor(fc, field_list) as cursor: 
        for row in cursor: 
            for i in range(len(row)): 
                if row[i] is None: 
                    row[i] = "" 
            cursor.updateRow(row)
            
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
                    
# combine duplicate records, creating multipart and dissolved polygons 
@timer
def CombineAPNs(fc, fld_dissolve):    
    from time import strftime  
    print ("Started combining APNs: " + strftime("%Y-%m-%d %H:%M:%S"))

    # get unique values from field
    value_list = [r[0] for r in arcpy.da.SearchCursor(fc, (fld_dissolve))]
    unique_vals = list(set(value_list))
    
    if len(value_list) !=len(unique_vals):
        seen = set()
        dup_vals = set()
        for x in value_list:
            if x in seen:
                dup_vals.add(x)
            else:
                seen.add(x)
        print(dup_vals)
        dup_vals.remove('')
        for unique_val in dup_vals:
            geoms = [r[0] for r in arcpy.da.SearchCursor(fc, ('SHAPE@', fld_dissolve)) if r[1] == unique_val]
            #Probably don't need this as there will always be more than one geometry
            if len(geoms) > 1:
                print(unique_val)    
                diss_geom = DissolveGeoms(geoms)

                # update the first feature with new geometry and delete the others
                where = "{} = '{}'".format(fld_dissolve, unique_val)
                cnt = 0
                with arcpy.da.UpdateCursor(fc, ('SHAPE@'), where) as curs:
                    for row in curs:
                        cnt += 1
                        if cnt == 1:
                            row[0] = diss_geom
                            curs.updateRow(row)
                        else:
                            curs.deleteRow()
    else:
        print("No duplicates!")
    print ("Finished combining APNs: " + strftime("%Y-%m-%d %H:%M:%S"))
    
# union all geometry inputs into one dissolved geometry
@timer
def DissolveGeoms(geoms):
    cnt = 0
    for geom in geoms:
        cnt += 1
        if cnt == 1:
            diss_geom = geom
        else:
            diss_geom = diss_geom.union(geom)
    return diss_geom

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

# transfer attributes frome one feature class field to another while using multiple fields to create the keys
@timer
def fieldJoinCalc_multikey(updateFC, updateFieldsList_key, updateFieldsList_value, sourceFC, sourceFieldsList_key, sourceFieldsList_value):
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
                # transfer the value stored under the keyValue from the dictionary to the updated field.  
                updateRow[2] = valueDict[keyValue]  
                updateRows.updateRow(updateRow)    
    del valueDict  
    print ("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
#     log.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

# find attribute level differences in two identical data frames
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
    new_values =diff_df.loc[:,pd.IndexSlice[:,'other']].droplevel(1,axis=1)
    #
    dict_update = new_values.to_dict('index')
    #
    new_dict = {k: {a: b for a, b in v.items() if not pd.isnull(b)} 
                for k, v in dict_update.items()}
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
def update_fc_from_dict(update_dict,key_field, fc):
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
                    cursor.updateRow(row)
                        #print("Updated APN/Field: "+str(row[0])+" / "+str(field))
                except Exception as e:
                    apn_issues.append(key_field_value)
                    # Print the error message
                    print(f"Error updating {key_field_value}: {e}")
                    continue
    print("Updating Attributes Finished: " + strftime("%Y-%m-%d %H:%M:%S"))
    print(f"Total updated{total_count}")
    return apn_issues

#Seperated out into two functions so we can use this function to make old new table in SQL
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
def delete_old_parcels(featureLayer, oldAPNs):
    delete_count = 0
    with arcpy.da.UpdateCursor(featureLayer, ["APN"]) as cursor:
        for row in cursor:
            apn = row[0]
            if apn in oldAPNs:
                cursor.deleteRow()
                delete_count +=1
    print(f"{delete_count} rows deleted from {featureLayer}.")

# inserts new parcels
@timer
def insert_new_parcels(featureLayer, new_APNs, new_parcels, fields):
    new_count = 0
    where_clause = f"{arcpy.AddFieldDelimiters(featureLayer, 'APN')} IN "+str(tuple(new_APNs))
    print(where_clause)
    with arcpy.da.SearchCursor(new_parcels, fields, where_clause) as search_cursor:
    # Open an insert cursor to the destination feature class
        with arcpy.da.InsertCursor(featureLayer, fields) as insert_cursor:
            # insert the rows from the serach cursor
            for row in search_cursor:
                insert_cursor.insertRow(row)
                new_count +=1
                print(f"{new_count} rows inserted into {featureLayer}.")
                
# updates @SHAPE that aren't identical to existing shapes
@timer
def update_parcel_geometry(featureLayer, new_parcels):
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
    fieldJoinCalc_multikey(featureLayer, updateFieldsList_key, updateFieldsList_value, newShapes, sourceFieldsList_key, sourceFieldsList_value)

    # Get the count of selected features
    result = arcpy.management.GetCount(newShapes)
    count = int(result.getOutput(0))
    # number of shapes shifted
    print(f"{count} shapes shifted.")
    
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

# Parcel AOI to select parcels to keep (includes TRPA Boundary and Olympic Valley Watershed)
parcelAOI = "Parcel_AOI"

#sde feature classes to use in attribution stage
sde_Impervious       = sdeBase + "\\sde.SDE.Impervious\\sde.SDE.Impervious_2019"
sde_Bailey           = sdeBase + "\\sde.SDE.Soils\sde.SDE.land_capability_Bailey_Soils"
sde_RegionalLandUse  = os.path.join(sdeBase,"sde.SDE.Planning/sde.SDE.RegionalLandUse")
sde_NRCSSoils1974    = sdeBase + "\\sde.SDE.Soils\\sde.SDE.NRCS_Soils_1974"
sde_NRCSSoils2003    = sdeBase + "\\sde.SDE.Soils\\sde.SDE.NRCS_Soils_2003"
sde_Catchment        = sdeBase + "\\sde.SDE.WaterQuality\\sde.SDE.TMDL_Catchment"
sde_HydroArea        = sdeBase + "\\sde.SDE.Water\\sde.SDE.Hydro_Areas"
sde_Watershed        = sdeBase + "\\sde.SDE.Water\\sde.SDE.Watershed"
sde_FireDistrict     = sdeBase + "\\sde.SDE.Jurisdictions\\sde.SDE.FireDistricts"
sde_LocalPlan        = sdeBase + "\\sde.SDE.Planning\\sde.SDE.LocalPlan"
sde_SpecialDistrict  = sdeBase + "\\sde.SDE.Planning\\sde.SDE.SpecialPlanningDistrict"
sde_CSLT             = sdeBase + "\\sde.SDE.Jurisdictions\\sde.SDE.CSLT"
sde_CurrentParcels   = sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcel_Master"
sde_Zoning           = sdeBase + "\\sde.SDE.Planning\\sde.SDE.District"
sde_TownCenter       = sdeBase + "\\sde.SDE.Planning\\sde.SDE.TownCenter"
sde_TownCenterBuffer = sdeBase + "\\sde.SDE.Planning\\sde.SDE.TownCenter_Buffer"
sde_Index1987        = sdeBase + "\\sde.SDE.Index\\sde.SDE.AssessorMapIndex_1987"
sde_TRPAboundary     = sdeBase + "\\sde.SDE.Jurisdictions\\sde.SDE.TRPA_bdy"
sde_BonusUnitboundary= sdeBase + "\\sde.SDE.Planning\\sde.SDE.Bonus_unit_boundary"
sde_UrbanArea        = sdeBase + "\\sde.SDE.Jurisdictions\\sde.SDE.UrbanAreas"
sde_Zip              = sdeBase + "\\sde.SDE.Jurisdictions\\sde.SDE.Postal_ZIP"
sde_TAZ              = sdeBase + "\\sde.SDE.Transportation\\sde.SDE.Transportation_Analysis_Zone"
sde_Littoral         = sdeBase + "\\sde.SDE.Shorezone\\sde.SDE.LittoralParcel"
sde_Tolerance        = sdeBase + "\\sde.SDE.Shorezone\\sde.SDE.Tolerance_District"

# in memory fcs to use in the attribution stage
memory = "memory" + "\\"
ParcelPoint_RegionalLandUse = memory + "ParcelPoint_RegionalLandUse"
ParcelPoint_Soils74         = memory + "ParcelPoint_Soils74"
ParcelPoint_Soils03         = memory + "ParcelPoint_Soils03"
ParcelPoint_Catchment       = memory + "ParcelPoint_Catchment"
ParcelPoint_HydroArea       = memory + "ParcelPoint_HydroArea"
ParcelPoint_Watershed       = memory + "ParcelPoint_Watershed"
ParcelPoint_FireDistrict    = memory + "ParcelPoint_FireDistrict"
ParcelPoint_LocalPlan       = memory + "ParcelPoint_LocalPlan"
ParcelPoint_TownCenter      = memory + "ParcelPoint_TownCenter"
ParcelPoint_TownCenterBuffer= memory + "ParcelPoint_TownCenterBuffer"
ParcelPoint_Zoning          = memory + "ParcelPoint_Zoning"
ParcelPoint_SpecialDistrict = memory + "ParcelPoint_SpecialDistrict"
ParcelPoint_Index1987       = memory + "ParcelPoint_Index1987"
ParcelPoint_PstlTown        = memory + "ParcelPoint_PstlTown"
ParcelPoint_PstlZip         = memory + "ParcelPoint_PstlZip"
ParcelPoint_CSLT            = memory + "ParcelPoint_CSLT"
ParcelPoint_TAZ             = memory + "ParcelPoint_TAZ"
ParcelPoint_Design          = memory + "ParcelPoint_Design"
ParcelPoint_Littoral        = memory + "ParcelPoint_Littoral"
ParcelPoint_Tolerance       = memory + "ParcelPoint_Tolerance"

# Set up fields to add to FGDB.
baseFields = [
# apn ppno
['APN_TRPA', 'TEXT', 'APN', 50],
['PPNO_TRPA', 'DOUBLE','PPNO'],
['JURISDICTION_TRPA', 'TEXT', 'Jurisdiction', 4],
['COUNTY_TRPA', 'TEXT', 'County', 2],
 # parcel address   
['HSE_NUMBR_TRPA', 'TEXT', 'House Number', 25],
['UNIT_NUMBR_TRPA', 'TEXT', 'Unit Number', 50],
['STR_DIR_TRPA', 'TEXT','Street Direction', 5],
['STR_NAME_TRPA', 'TEXT', 'Street Name', 100],
['STR_SUFFIX_TRPA', 'TEXT', 'Street Suffix', 6],
['APO_ADDRESS_TRPA', 'TEXT', 'Full Address', 100],
['PSTL_TOWN_TRPA', 'TEXT', 'Postal Town', 25],
['PSTL_STATE_TRPA', 'TEXT', 'Postal State', 2],
['PSTL_ZIP5_TRPA', 'TEXT', 'Postal Zip Code', 5],
# owner info
['OWN_FIRST_TRPA', 'TEXT', 'Owner First Name', 255],
['OWN_LAST_TRPA', 'TEXT', 'Owner Last Name', 255],
['OWN_FULL_TRPA', 'TEXT', 'Owner Name', 255],
    # swap this in soon
# ['OWNER_NAME_TRPA', 'TEXT', 'Owner Name', 255],
['MAIL_ADD1_TRPA', 'TEXT', 'Mailing Address', 100],
['MAIL_CITY_TRPA', 'TEXT', 'Mailing City', 50],
['MAIL_STATE_TRPA', 'TEXT', 'Mailing State', 25],
['MAIL_ZIP5_TRPA', 'TEXT', 'Mailing Zip Code', 5],
# value fields  
['AS_LANDVALUE_TRPA', 'LONG','Assessed Land Value'],
['AS_IMPROVALUE_TRPA', 'LONG','Assessed Improved Value'],
['AS_SUM_TRPA', 'LONG', 'Assessed Sum Value'],
['TAX_LANDVALUE_TRPA', 'LONG','Tax Land Value'],
['TAX_IMPROVALUE_TRPA', 'LONG','Tax Improved Value'],
['TAX_SUM_TRPA', 'LONG','Tax Sum'],
['TAX_YEAR_TRPA', 'TEXT','Tax Year', 5],
# jurisdiction land use fields
['COUNTY_LANDUSE_CODE_TRPA', 'TEXT', 'County Landuse Code', 50],
['COUNTY_LANDUSE_TRPA', 'TEXT', 'County Landuse', 250],
# Fields for building info
["YEAR_BUILT_TRPA", "SHORT", 'Year Built', 5],
['UNITS_TRPA', 'DOUBLE', 'Units', 5],
["BEDROOMS_TRPA", "DOUBLE",'Bedrooms'],
['BATHROOMS_TRPA', 'DOUBLE', 'Bathrooms'],
['BUILDING_SQFT_TRPA', 'DOUBLE', 'Building Size'],
# fields to add? 
["VHR_TRPA", "TEXT", "Vacation Home Rental", 3],
["HOA_TRPA", "TEXT", "Home Owners Association", 3]
]

trpaFields = [
# land use
['OWNERSHIP_TYPE_TRPA', 'TEXT', 'Ownership Type', 50],
['EXISTING_LANDUSE_TRPA', 'TEXT', 'Existing Landuse', 50],
['REGIONAL_LANDUSE_TRPA', 'TEXT', 'Regional Landuse', 50], 
# Fields for soil, watershed, etc...
['ESTIMATED_COVERAGE_ALLOWED_TRPA', 'DOUBLE', "Estimate of Coverage Allowed (Bailey, sq.ft.)"],
['IMPERVIOUS_SURFACE_SQFT_TRPA', 'DOUBLE', "Impervious Surface (Remote Sensing, sq.ft.)"],
['SOIL_1974_TRPA', 'TEXT','NRCS Soils 1974', 5],
["SOIL_2003_TRPA", "TEXT", "NRCS Soils 2003", 5],
["CATCHMENT_TRPA", "TEXT", "Catchment", 150],
["HRA_NAME_TRPA", "TEXT", "Hydrologic Resource Area", 30],
["WATERSHED_NUMBER_TRPA", "SHORT", "Watershed Number"],
["WATERSHED_NAME_TRPA", "TEXT", "Watershed Name", 30],
["PRIORITY_WATERSHED_TRPA", "TEXT", "Priority Watershed", 2],
["FIREPD_TRPA", "TEXT", "Fire Protection District", 25],
# Fields for Planning purposes
["PLAN_ID_TRPA", "TEXT", 'Plan ID',8],
["PLAN_NAME_TRPA", "TEXT", 'Plan Name', 40],
["PLAN_TYPE_TRPA", "TEXT", 'Plan Type', 40],
["ZONING_ID_TRPA", "TEXT", 'Zoning ID', 50],
["ZONING_DESCRIPTION_TRPA", "TEXT", 'Zoning Description',500],
["TOWN_CENTER_TRPA", "TEXT",'Town Center', 50],
["LOCATION_TO_TOWNCENTER_TRPA", "TEXT", 'Location Relative to Town Center', 50],
["TOLERANCE_ID_TRPA", "TEXT", 'Tolerance ID', 50],
["TAZ_TRPA", "DOUBLE",'Transportation Analysis Zone'],
["INDEX_1987_TRPA", "TEXT", "1987 Parcel Map Index",10],
["LITTORAL_TRPA", "SHORT", "Littoral"],
["WITHIN_TRPA_BNDY_TRPA", "SHORT","Within TRPA Boundary?"],
["WITHIN_BONUSUNIT_BNDY_TRPA", "SHORT", "Within Bonus Unit Boundary"],
["LOCAL_PLAN_HYPERLINK_TRPA", "TEXT", "Local Plan Hyperlink", 255],
["DESIGN_GUIDELINES_HYPERLINK_TRPA", "TEXT", "Design Guidelines", 255],
["LTINFO_HYPERLINK_TRPA", "TEXT", "LTinfo Parcel Details", 255],
["INDEX_1987_HYPERLINK_TRPA", "TEXT", "Index 1987 Hyperlink", 255],
# Fields for Parcel Size
["PARCEL_ACRES_TRPA", "DOUBLE", "Acres"],
["PARCEL_SQFT_TRPA", "DOUBLE", "Square Feet"] 
]



# start a timer for the entire script run
FIRSTstartTimer = datetime.now()

# Create and open log file.
complete_txt_path = os.path.join(working_folder, "CountyParcel_Extract_Log.txt")
print (complete_txt_path)
log = open(complete_txt_path, "w")

# Write results to txt file
log.write("Log: " + str(FIRSTstartTimer) + "\n")
log.write("\n")
log.write("Begin process:\n")
log.write("Process started at: " + str(FIRSTstartTimer) + "\n")
log.write("\n")

#---------------------------------------------------------------------------------------#
## GET DATA
#---------------------------------------------------------------------------------------#
# start timer for the get data requests
startTimer = datetime.now()


# report how long it took to get the data
endTimer = datetime.now() - startTimer
print("\nTime it took to get the data: {}".format(endTimer))   
log.write("\nTime it took to get the data: {}".format(endTimer)) 
#---------------------------------------------------------------------------------------#
## Define Functions ##
#---------------------------------------------------------------------------------------#
##--------------------------------------------------------------------------------------------------------#
## SEND EMAIL WITH LOG FILE ##
##--------------------------------------------------------------------------------------------------------#
# path to text file
fileToSend = complete_txt_path

# email parameters
subject = "County Parcel Extract Log File"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "gis@trpa.gov"


def send_mail(body):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    msgText = MIMEText('%s<br><br>Cheers,<br>GIS Team' % (body), 'html')
    msg.attach(msgText)

    attachment = MIMEText(open(fileToSend).read())
    attachment.add_header("Content-Disposition", "attachment", filename = os.path.basename(fileToSend))
    msg.attach(attachment)

    try:
        with smtplib.SMTP("mail.smtp2go.com", 25) as smtpObj:
            smtpObj.ehlo()
            smtpObj.starttls()
#             smtpObj.login(sender_email, password)
            smtpObj.sendmail(sender_email, receiver_email, msg.as_string())
    except Exception as e:
        print(e)


try:
    #---------------------------------------------------------------------------------------#
    ## Carson City County GET Data
    # parameters for get data from rest service
    params = {'where': '1=1', 'outFields': '*', 'f': 'pjson', 'returnGeometry': True}
    r = requests.get('https://gis.carson.org/arcgis/rest/services/CarsonCity/CarsonCityNV_OpenData/FeatureServer/36/query', params)
    data = r.json()

    # save JSON as a Feature class
    json_path = os.path.join(workspace,'CCtemp.json')

    # delete existing/old json file
    os.remove(json_path)

    # open and write data to json file
    with open(json_path, 'w') as f:
        json.dump(data, f)

    # delete the existing table
    arcpy.management.Delete('Parcel_CC_Features')
    print("Deleted existing table")

    # json object to table
    arcpy.JSONToFeatures_conversion(json_path, 'Parcel_CC_Features')
    print("Saved CC Staging Feature class")

    # get data from rest service
    params = {'where': '1=1', 'outFields': '*', 'f': 'pjson', 'returnGeometry': True}
    r = requests.get('https://gis.carson.org/arcgis/rest/services/CarsonCity/CarsonCityNV_OpenData/FeatureServer/42/query', params)
    data = r.json()

    # save JSON as a Feature class
    json_path = os.path.join(workspace,'CCtemp.json')

    # delete existing/old json file
    os.remove(json_path)

    # open and write data to json file
    with open(json_path, 'w') as f:
        json.dump(data, f)

    # delete the existing table
    arcpy.management.Delete('Parcel_CC_Table')
    print("Deleted existing table")

    # json object to table
    arcpy.JSONToFeatures_conversion(json_path, 'Parcel_CC_Table')
    print("Saved CC Staging Table")


    # The qualifiedFieldNames environment is used by Copy Features when persisting 
    # the join field names.
    arcpy.env.qualifiedFieldNames = False

    # Set local variables
    inFeatures = "Parcel_CC_Features"
    joinTable  = "Parcel_CC_Table"
    joinField  = "APN"
    outFeature = "Parcel_CC_Extracted"

    # Join the feature layer to a table
    cc_join = arcpy.management.AddJoin(inFeatures, 
                                            joinField, 
                                            joinTable, 
                                            joinField)

    # Copy the joined layer to a new permanent feature class
    arcpy.management.CopyFeatures(cc_join, outFeature)
    print("Carson Parcels Extracted")
    #---------------------------------------------------------------------------------------#
    # report how long it took to get the data
    endTimer = datetime.now() - startTimer
    print("\nTime it took to update Collection SDE feature classes: {}".format(endTimer)) 
    log.write("\nTime it took to update Collection SDE feature classes: {}".format(endTimer)) 

    #---------------------------------------------------------------------------------------#
    # DOUGLAS EXTRACT
    #---------------------------------------------------------------------------------------#

    baseURL = "https://gisservices.douglasnv.us/server/rest/services/TRPA_Parcels/FeatureServer/0"
    fields = "*"
    outfc = "Parcel_DG_Extracted"

    # Get record extract limit
    urlstring = baseURL + "?f=json"
    j = urllib.request.urlopen(urlstring)
    js = json.load(j)
    maxrc = int(js["maxRecordCount"])
    print("Record extract limit: %s" % maxrc)

    # Get object ids of features
    where = "1=1"
    urlstring = baseURL + "/query?where={}&returnIdsOnly=true&f=json".format(where)
    j = urllib.request.urlopen(urlstring)
    js = json.load(j)
    idfield = js["objectIdFieldName"]
    idlist = js["objectIds"]
    idlist.sort()
    numrec = len(idlist)
    print("Number of target records: %s" % numrec)

    # Gather features
    print ("Gathering records...")
    fs = dict()
    for i in range(0, numrec, maxrc):
        torec = i + (maxrc - 1)
        if torec > numrec:
            torec = numrec - 1
        fromid = idlist[i]
        toid = idlist[torec]
        where = "{} >= {} and {} <= {}".format(idfield, fromid, idfield, toid)
        print ("  {}".format(where))
        urlstring = baseURL + "/query?where={}&returnGeometry=true&outFields={}&f=json".format(where,fields)
        # build that feature set!
        fs[i] = arcpy.FeatureSet()
        fs[i].load(urlstring)

    # Save features
    print("Saving features...")
    fslist = []
    for key,value in fs.items():
        fslist.append(value)
    arcpy.Merge_management(fslist, outfc)

    print("Douglas Parcels Extracted")

    #---------------------------------------------------------------------------------------#
    # EL DORADO EXTRACT
    #---------------------------------------------------------------------------------------#
    # Set up Zip path.
    zipPath = workspace
    # setup output feature class
    outfc = "Parcel_EL_Extracted"

    # Check if zip from failed attempt still exists
    existingZip = pathlib.Path(zipPath + r"\zipfolder")
    if existingZip.exists():
        shutil.rmtree(zipPath + r"\zipfolder")
        logging.info('Previous zip folder deleted')

    # Setup the params for the extraction GP tool. The boundary is a polygon the grabs the whole county.
    payload = {'f': 'json', 'env:outSR': '6418', 'Layers_to_Clip': '["Parcels"]', 'Area_of_Interest': '{"geometryType":"esriGeometryPolygon","features":[{"geometry":{"rings":[[[-13490599.294393552,4646257.881632805],[-13490599.294393552,4735689.204726496],[-13336502.24537058,4735689.204726496],[-13336502.24537058,4646257.881632805],[-13490599.294393552,4646257.881632805]]],"spatialReference":{"wkid":102100}}}],"sr":{"wkid":102100}}', 'Feature_Format': 'File Geodatabase - GDB - .gdb'}

    # Make the request to the GP service.
    logging.info('Requesting parcels from EDC')
    job = requests.get(r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/submitJob",params=payload)
    jobJson = job.json()

    # Check to make sure the job was accepted and get the JobID.
    if 'jobId' in jobJson:
        jobID = jobJson['jobId']
        jobStatus = jobJson['jobStatus']
        jobURL = r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/jobs"
        if jobStatus == 'esriJobSubmitted' or jobStatus == 'esriJobExecuting':
            logging.info('EDC job submitted')

        # Check the status of the job, when done grab the resulting ZIP file link.
        while jobStatus == 'esriJobSubmitted' or jobStatus == 'esriJobExecuting':
            time.sleep(5)
            jobCheck = requests.get(jobURL+"/"+jobID+"?f=json")
            jobJson = jobCheck.json()
            if 'jobStatus' in jobJson:
                jobStatus = jobJson['jobStatus']
                if jobStatus == "esriJobSucceeded":
                    if 'results' in jobJson:
                        logging.info('EDC server job completed')
                        resultURL = jobJson['results']['Output_Zip_File']['paramUrl']

                        # Grab the ZIP link.
                        logging.info('Downloading ZIP from EDC')
                        jobResult = requests.get(jobURL+"/"+jobID+r"/"+resultURL+r"?f=json&returnType=data")
                if jobStatus == "esriJobFailed":
                    logging.error('EDC server job failure')
                    if 'messages' in jobJson:
                        logging.error(jobJson['messages'])
                    raise ValueError('EDC job failed!')

    # Get the ZIP file.
    parcelsZip = requests.get(jobResult.json()['value']['url'])
    logging.info('Downloaded ZIP from EDC')

    # Save the ZIP into memory.
    zipFile = ZipFile(BytesIO(parcelsZip.content))

    # Unzip the ZIP to the defined path.
    for each in zipFile.namelist():
        if not each.endswith('/'):
            root, name = os.path.split(each)
            directory = os.path.normpath(os.path.join(zipPath, root))
            if not os.path.isdir(directory):
                os.makedirs(directory)
            open(os.path.join(directory, name), 'wb').write(zipFile.read(each))
    logging.info('Unzipped files in ' + str(zipPath))

    # Setup env for parcel FGDB and set overwrite to true.
    zipFolder = zipPath + r"\zipfolder"
    # arcpy.env.overwriteOutput = True
    in_features = os.path.join(workspace, "zipfolder\data.gdb\Parcels")

    # Export to staging gdb
    arcpy.management.CopyFeatures(in_features, outfc)
    print("El Dorado Parcels Extracted")

    #---------------------------------------------------------------------------------------#
    # PLACER EXTRACT
    #---------------------------------------------------------------------------------------#
    #Parameters
    hostedFeatureService = 'true'
    agsService = 'false'

    # username and password to get the token via the AGOL shared group
    # username = 'mbindl'
    # password = getpass.getpass()
    username = 'TRPA_ADMIN'
    password = 'TRP@g1sT3am'

    baseURL = "https://services9.arcgis.com/NENkjkswKTzMfG3A/arcgis/rest/services/Parcels_with_Mega/FeatureServer/0"
    fields = "*"
    outdata = 'Parcel_PL_Extracted'
    token = ''

    # Disable warnings
    requests.packages.urllib3.disable_warnings()

    #Report error function
    def PrintException():
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        filename = f.f_code.co_filename
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        arcpy.AddError('Error:  Line {} -- "{}": {}'.format(lineno, line.strip(), exc_obj))
        sys.exit()

    #generate token for AGOL Hosted Feature Service

    if username and password:
        try:
            tokenURL = 'https://www.arcgis.com/sharing/rest/generateToken'
            params = {'f': 'pjson', 'username': username, 'password': password, 'referer': 'https://www.arcgis.com', 'expiration': str(21600)}
            response = requests.post(tokenURL, data = params, verify = False)
            token = response.json()['token']
        except:
            PrintException()
    else:
        token = ''

    print('Token: '+token)

    # Get record extract limit 
    urlstring = baseURL + "?token="+token+"&f=json" 
    j = requests.get(urlstring, verify=False)
    js = j.json() 
    maxrc = int(js["maxRecordCount"]) 
    print("Record extract limit: %s" % maxrc)

    # Get object ids of features
    where = "1%3D1"
    urlstring = baseURL + "/query?where=1%3D1&returnIdsOnly=true&f=json&token="+token
    j = requests.get(urlstring, verify=True)
    js = j.json() 
    idfield = js["objectIdFieldName"]
    idlist = js["objectIds"]
    idlist.sort()
    numrec = len(idlist)
    print("Number of target records: %s" % numrec)

    # Gather features
    print ("Gathering records...")
    fs = {}
    for i in range(0, numrec, maxrc):
        torec = i + (maxrc - 1)
        if torec > numrec:
            torec = numrec - 1
        fromid = idlist[i]
        toid = idlist[torec]
        where = "{} >= {} and {} <= {}".format(idfield, fromid, idfield, toid)
        print ("  {}".format(where))
        urlstring = baseURL + f'/query?where={where}&returnGeometry=true&outFields={fields}&f=json&token='+token
        fs[i] = arcpy.FeatureSet()
        fs[i].load(urlstring)

    # Save features
    print("Saving features...")
    fslist = []
    for key,value in fs.items():
        fslist.append(value)
    arcpy.Merge_management(fslist, outdata)
    print("Done")

    #---------------------------------------------------------------------------------------#
    # WASHOE EXTRACT
    #---------------------------------------------------------------------------------------#
    baseURL = "https://wcgisweb.washoecounty.us/arcgis/rest/services/OpenData/OpenData/FeatureServer/0"
    fields = "*"
    outfc = "Parcel_WA_Extracted"

    # Get record extract limit
    urlstring = baseURL + "?f=json"
    j = urllib.request.urlopen(urlstring)
    js = json.load(j)
    maxrc = int(js["maxRecordCount"])
    print("Record extract limit: %s" % maxrc)

    # Get object ids of features
    where = "1=1"
    urlstring = baseURL + "/query?where={}&returnIdsOnly=true&f=json".format(where)
    j = urllib.request.urlopen(urlstring)
    js = json.load(j)
    idfield = js["objectIdFieldName"]
    idlist = js["objectIds"]
    idlist.sort()
    numrec = len(idlist)
    print("Number of target records: %s" % numrec)

    # Gather features
    print ("Gathering records...")
    fs = dict()
    for i in range(0, numrec, maxrc):
        torec = i + (maxrc - 1)
        if torec > numrec:
            torec = numrec - 1
        fromid = idlist[i]
        toid = idlist[torec]
        where = "{} >= {} and {} <= {}".format(idfield, fromid, idfield, toid)
        print ("  {}".format(where))
        urlstring = baseURL + "/query?where={}&returnGeometry=true&outFields={}&f=json".format(where,fields)
        # build that feature set!
        fs[i] = arcpy.FeatureSet()
        fs[i].load(urlstring)

    # Save features
    print("Saving features...")
    fslist = []
    for key,value in fs.items():
        fslist.append(value)
    arcpy.Merge_management(fslist, outfc)
    print("Done")
    ##--------------------------------------------------------------------------------------------------------#
    ## END OF EXTRACT ##
    ##--------------------------------------------------------------------------------------------------------#


    # report how long it took to run the script
    FINALendTimer = datetime.now() - FIRSTstartTimer
    print ("\nTime it took to run this script: {}".format(FINALendTimer))

    log.write("\nTime it took to run this script: {}".format(FINALendTimer))
    log.close()
    
    header = "SUCCESS - Parcel feature classes were updated."
    # send email with header based on try/except result
    send_mail(header)
    print('Sending email...')

# catch any arcpy errors
except arcpy.ExecuteError:
    print(arcpy.GetMessages())
    log.write(arcpy.GetMessages())
    log.close()
    
    header = "ERROR - Arcpy Exception - Check Log"
    # send email with header based on try/except result
    send_mail(header)
    print('Sending email...')

# catch system errors
except Exception:
    e = sys.exc_info()[1]
    print(e.args[0])
    log.write(e)
    log.close()
    
    header = "ERROR - System Error - Check Log"
    # send email with header based on try/except result
    send_mail(header)
    print('Sending email...')
