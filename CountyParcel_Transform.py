"""
CountyParcel_Transform.py
Created: June 15th,2023
Last Updated: January 26, 2025 
Amy Fish, Tahoe Regional Planning Agency
Andy McClary, Tahoe Regional Planning Agency
Mason Bindl, Tahoe Regional Planning Agency

This python script was developed to get data from the five Tahoe Counties.
El Dorado, Carson, Douglas, Placer, and Washoe. 
The data is then staged for transformation. 

This script uses Python 3.x and was designed to be used with 
the default ArcGIS Pro python enivorment ""C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe"", with
no need for installing new libraries.

This script runs on the 16th of each month at 1am on Arc10 from scheduled task "CountyParcelTransform"
"""
#----------------------------------------------------------------------
# SETUP
#----------------------------------------------------------------------
# import packages
import os
import sys
import re
import logging
from datetime import datetime 
import time
import pandas as pd
import arcpy
from time import strftime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# environment settings
arcpy.env.workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# set workspace and sde connections 
workspace = "F:/GIS/PARCELUPDATE/Workspace/Staging"

# network path to connection files
filePath = "F:/GIS/PARCELUPDATE/Workspace/"
# database file path 
sdeBase    = os.path.join(filePath, "Vector.sde/")
sdeCollect = os.path.join(filePath, "Collection.sde")
sdeTabular = os.path.join(filePath, "Tabular.sde/")

# portal signin
## TRPA_ADMIN credentials 
# portal_user = "TRPA_PORTAL_ADMIN"
# portal_pwd = str(os.environ.get('Password'))
# portal_url = "https://maps.trpa.org/portal/"
# # sign in
# arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)

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

# sde Collect feature classes to use for attribution
sde_collect_IPES     = os.path.join(sdeCollect, 'SDE.Parcel\SDE.Parcel_LTinfo_IPES')
sde_collect_LCV      = os.path.join(sdeCollect, 'SDE.Parcel\SDE.Parcel_LTinfo_LCV')
sde_collect_BMP      = os.path.join(sdeCollect, 'SDE.Parcel\SDE.Parcel_BMP')
sde_collect_Deed     = os.path.join(sdeCollect, 'SDE.Parcel\SDE.Parcel_LTinfo_Deed_Restriction')  
sde_collect_VHR      = os.path.join(sdeCollect, 'SDE.Parcel\SDE.Parcel_VHR')

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

# Input data (feature class or shapefile)
in_features = sde_collect_IPES

where__clause_ipes = "IPESScoreType = 'Official'" 
# Name of the new layer
ipes_layer = "in_memory\\sde_collect_IPES_Official"
# Make the layer
arcpy.management.MakeFeatureLayer(in_features, ipes_layer, where__clause_ipes)
 


#read ownership csv to get federal state etc lists
ownership_df = pd.read_csv('ownership_lookup.csv')
localOwnList = ownership_df[ownership_df['Owner_Type'] == 'Local']['Owner_Name'].tolist()
stateOwnList = ownership_df[ownership_df['Owner_Type'] == 'State']['Owner_Name'].tolist()
fedOwnList = ownership_df[ownership_df['Owner_Type'] == 'Federal']['Owner_Name'].tolist()

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
#['MAIL_STATE_TRPA', 'TEXT', 'Mailing State', 25],
['MAIL_STATE_TRPA', 'TEXT', 'Mailing State', 2],
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
#['ESTIMATED_PRCNT_COV_ALLOWED_TRPA', 'DOUBLE', "Estimated Percent Coverage Allowed (Bailey, sq.ft.)"],
['ESTIMATED_PRCNT_COV_ALLOWED_TRPA', 'SHORT', "Estimated Percent Coverage Allowed (Bailey, sq.ft.)"],
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
["IPES_TRPA", "LONG", "IPES Score"],
["WITHIN_TRPA_BNDY_TRPA", "SHORT","Within TRPA Boundary?"],
["WITHIN_BONUSUNIT_BNDY_TRPA", "SHORT", "Within Bonus Unit Boundary"],
["LOCAL_PLAN_HYPERLINK_TRPA", "TEXT", "Local Plan Hyperlink", 255],
["DESIGN_GUIDELINES_HYPERLINK_TRPA", "TEXT", "Design Guidelines", 255],
["LTINFO_HYPERLINK_TRPA", "TEXT", "LTinfo Parcel Details", 255],
["INDEX_1987_HYPERLINK_TRPA", "TEXT", "Index 1987 Hyperlink", 255],
["STATUS_TRPA",'TEXT',"Status",1],
# Fields for Parcel Size
["PARCEL_ACRES_TRPA", "DOUBLE", "Acres"],
["PARCEL_SQFT_TRPA", "DOUBLE", "Square Feet"] 
]

#----------------------------------------------------------------------
# LOGGING
#----------------------------------------------------------------------
# Configure the logging
log_file_path = os.path.join(workspace, "ParcelTransformation.log")  # Specify the path to your local directory
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=log_file_path,  # Set the log file path
                    filemode='w')

# Create a logger
logger = logging.getLogger(__name__)
# start a timer for the entire script run
FIRSTstartTimer = datetime.datetime.now()
# Log different types of messages
logger.info("Script Started: " + str(FIRSTstartTimer) + "\n")

# Setup Counties to run
counties_to_run = ['El Dorado', 'Placer', 'Douglas', 'Washoe', 'Carson City']

##--------------------------------------------------------------------------------------------------------#
## SETUP SEND EMAIL WITH LOG FILE ##
##--------------------------------------------------------------------------------------------------------#
# path to text file
fileToSend = log_file_path
# email parameters
subject = "Parcel Transformation Log File"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "afish@trpa.gov"
#----------------------------------------------------------------------
# FUNCTIONS
#----------------------------------------------------------------------
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

def get_text_fields(feature_class):
    field_list = []
    fields = arcpy.ListFields(feature_class)
    for field in fields:
        if field.type == 'String':
            field_list.append(field.name)
    return field_list

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
    logger.info(f"{record_count} rows were updated")
    #record_count = 0
                    
# combine duplicate records, creating multipart and dissolved polygons 
@timer
def CombineAPNs(fc, fld_dissolve): 
    try:
        from time import strftime  
        print("Started combining APNs: " + strftime("%Y-%m-%d %H:%M:%S"))
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
    except Exception as e:
        exc_type, exc_obj, tb = sys.exc_info()
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print(str(lineno) + ": " + e.args[0])
        logger.error(e)    
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
    logger.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
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
    logger.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

# transfer attributes frome one feature class field to another while using multiple fields to create the keys
@timer
def fieldJoinCalc_multikey(updateFC, updateFieldsList_key, updateFieldsList_value, sourceFC, sourceFieldsList_key, sourceFieldsList_value):
    from time import strftime  
    print ("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Use list comprehension to build a dictionary from arcpy SearchCursor  
    total_count=0
    valueDict = {(r[0]+r[1]):(r[2]) for r in arcpy.da.SearchCursor(sourceFC, (sourceFieldsList_key + sourceFieldsList_value)) if r[0] is not None and r[1] is not None}  
    with arcpy.da.UpdateCursor(updateFC, (updateFieldsList_key+ updateFieldsList_value)) as updateRows:  
        for updateRow in updateRows:  
            # store the Join value of the row being updated in a keyValue variable  
            if updateRow[0] is not None and updateRow[1] is not None:
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
    #logger.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

# send email with attachments
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
        logger.error(e)

# Function to check if a county exists in the list of counties to run
def is_county_in_list(county, county_list):
    return county in county_list
#-----------------------------------------------------------------------
# START TRANSFORMATION
#-----------------------------------------------------------------------
try:
    # start timer for the get data requests
    startTimer = datetime.datetime.now()

    #-----------------------------------------------------------------------
    # CARSON COUNTY TRANSFORMATION
    #-----------------------------------------------------------------------
    # get staging feature class and name output transformed feature class
    county_to_check = 'Carson City'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        in_features = "Parcel_CC_Extracted"
        parcel_out  = "Parcel_CC_Transformed"

        # in-memory feature class
        carsonParcel = r"in_memory/inMemoryFeatureClass"

        # copy feature class into in-memory feature class to work on
        arcpy.management.CopyFeatures(in_features, carsonParcel)

        # Add TRPA base fields
        arcpy.management.AddFields(carsonParcel, baseFields)

        with arcpy.da.UpdateCursor(carsonParcel, [
            'APN_TRPA', 'PPNO_TRPA', 'JURISDICTION_TRPA', 'HSE_NUMBR_TRPA', 
            'STR_DIR_TRPA', 'STR_NAME_TRPA', 'STR_SUFFIX_TRPA', 'UNIT_NUMBR_TRPA', 
            'APO_ADDRESS_TRPA', 'PSTL_TOWN_TRPA', 'PSTL_STATE_TRPA', 'PSTL_ZIP5_TRPA',
            'OWN_FULL_TRPA', 'MAIL_ADD1_TRPA', 'MAIL_CITY_TRPA', 'MAIL_STATE_TRPA', 
            'MAIL_ZIP5_TRPA', 'AS_LANDVALUE_TRPA', 'AS_IMPROVALUE_TRPA', 'AS_SUM_TRPA', 
            'TAX_LANDVALUE_TRPA', 'TAX_IMPROVALUE_TRPA', 'TAX_SUM_TRPA', 'TAX_YEAR_TRPA', 
            'COUNTY_LANDUSE_CODE_TRPA', 'COUNTY_LANDUSE_TRPA', 'YEAR_BUILT_TRPA', 
            'UNITS_TRPA', 'BEDROOMS_TRPA', 'BATHROOMS_TRPA', 'BUILDING_SQFT_TRPA', 
            'VHR_TRPA', 'HOA_TRPA', 'APN', 'APN_NUM', 'Phy_Addr', 'Loc1', 'Dir', 
            'Street_Name', 'Unit', 'Legal_Owner', 'Mail_Addr', 'Mail2_Addr', 'MCity', 
            'MZip', 'Land_Value', 'Improv_Val', 'LU', 'Total_DWUnits'
        ]) as cursor:
            for row in cursor:
                # Set APN
                apn = row[cursor.fields.index('APN')]
                row[cursor.fields.index('APN_TRPA')] = (apn[:3] + "-" + apn[3:6] + "-" + apn[6:8]) if apn else ''

                # Set PPNO
                ppno = row[cursor.fields.index('APN_NUM')]
                row[cursor.fields.index('PPNO_TRPA')] = int(ppno) if ppno else ''

                # Jurisdiction
                row[cursor.fields.index('JURISDICTION_TRPA')] = "CC"

                # APO Address
                full_address = row[cursor.fields.index('Phy_Addr')]
                row[cursor.fields.index('APO_ADDRESS_TRPA')] = full_address if full_address else ''

                # House Number
                house = row[cursor.fields.index('Loc1')]
                row[cursor.fields.index('HSE_NUMBR_TRPA')] = str(house) if house else ''

                # Street Direction
                street_direction = row[cursor.fields.index('Dir')]
                row[cursor.fields.index('STR_DIR_TRPA')] = street_direction if street_direction else ''

                # Street Name and Suffix
                street_name = row[cursor.fields.index('Street_Name')]
                if street_name:
                    parts = street_name.split(" ")
                    row[cursor.fields.index('STR_NAME_TRPA')] = parts[0]
                    row[cursor.fields.index('STR_SUFFIX_TRPA')] = parts[-1]
                else:
                    row[cursor.fields.index('STR_NAME_TRPA')] = ''
                    row[cursor.fields.index('STR_SUFFIX_TRPA')] = ''

                # Unit Number
                unit = row[cursor.fields.index('Unit')]
                row[cursor.fields.index('UNIT_NUMBR_TRPA')] = unit if unit else ''

                # Postal State
                row[cursor.fields.index('PSTL_STATE_TRPA')] = 'NV'

                # Owner Name
                owner = row[cursor.fields.index('Legal_Owner')]
                row[cursor.fields.index('OWN_FULL_TRPA')] = owner.strip() if owner else ''

                # Mailing Address
                address1 = row[cursor.fields.index('Mail_Addr')]
                address2 = row[cursor.fields.index('Mail2_Addr')]
                row[cursor.fields.index('MAIL_ADD1_TRPA')] = address2.strip() if address2 else address1.strip() if address1 else ''

                # Mailing City
                mail_city = row[cursor.fields.index('MCity')]
                row[cursor.fields.index('MAIL_CITY_TRPA')] = mail_city.split(',', 1)[0].strip() if mail_city else ''

                # Mailing State
                mail_state = row[cursor.fields.index('MCity')]
                row[cursor.fields.index('MAIL_STATE_TRPA')] = mail_state.split(',')[-1].strip()[:2] if mail_state else ''

                # Mailing Zip
                mail_zip = row[cursor.fields.index('MZip')]
                row[cursor.fields.index('MAIL_ZIP5_TRPA')] = mail_zip[:5] if mail_zip and len(mail_zip) >= 5 else ''

                # Assessed Land Value
                land_value = row[cursor.fields.index('Land_Value')]
                row[cursor.fields.index('AS_LANDVALUE_TRPA')] = land_value if land_value else 0

                # Assessed Improved Value
                improved_value = row[cursor.fields.index('Improv_Val')]
                row[cursor.fields.index('AS_IMPROVALUE_TRPA')] = improved_value if improved_value else 0

                # Assessed Sum
                row[cursor.fields.index('AS_SUM_TRPA')] = (land_value or 0) + (improved_value or 0)

                # Tax Values
                row[cursor.fields.index('TAX_LANDVALUE_TRPA')] = (land_value / 0.35) if land_value else None
                row[cursor.fields.index('TAX_IMPROVALUE_TRPA')] = (improved_value / 0.35) if improved_value else None
                row[cursor.fields.index('TAX_SUM_TRPA')] = ((land_value or 0) / 0.35) + ((improved_value or 0) / 0.35)

                # Tax Year
                row[cursor.fields.index('TAX_YEAR_TRPA')] = datetime.datetime.now().year

                # County Land Use Code
                county_luc = row[cursor.fields.index('LU')]
                row[cursor.fields.index('COUNTY_LANDUSE_CODE_TRPA')] = str(county_luc) if county_luc else ''

                # Units
                units = row[cursor.fields.index('Total_DWUnits')]
                row[cursor.fields.index('UNITS_TRPA')] = units if units else None

                # Update the row
                cursor.updateRow(row)
        del cursor
    
        out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
        arcpy.Project_management(carsonParcel, parcel_out, out_coordinate_system)

        print('New Carson Parcels transformed')
        logger.info('New Carson Parcels transformed')
    #-------------------------------------------------------------------------------------
    ## DOUGLAS TRANSFORM
    #-------------------------------------------------------------------------------------
    # get staging feature class and name output trnasformed feature class
    county_to_check = 'Douglas'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        in_features = "Parcel_DG_Extracted"
        parcel_out  = "Parcel_DG_Transformed"

        # in-memory feature class
        douglasParcel = r"in_memory/inMemoryFeatureClass"

        # copy feature class into in-memory feature class to work on
        arcpy.management.CopyFeatures(in_features, douglasParcel)

        # Add TRPA base fields
        arcpy.management.AddFields(douglasParcel, baseFields)
        
        # Define the fields in a list variable
        fields = [
            ## TRPA base schema ##
            'APN_TRPA',                 #0
            'PPNO_TRPA',                #1
            'JURISDICTION_TRPA',        #2
            # parcel address   
            'HSE_NUMBR_TRPA',           #3
            'STR_DIR_TRPA',             #4
            'STR_NAME_TRPA',            #5
            'STR_SUFFIX_TRPA',          #6
            'UNIT_NUMBR_TRPA',          #7
            'APO_ADDRESS_TRPA',         #8
            'PSTL_TOWN_TRPA',           #9
            'PSTL_STATE_TRPA',          #10
            'PSTL_ZIP5_TRPA',           #11
            # owner fields
            # no own first and last for DG
            'OWN_FULL_TRPA',            #12
            'MAIL_ADD1_TRPA',           #13
            'MAIL_CITY_TRPA',           #14
            'MAIL_STATE_TRPA',          #15
            'MAIL_ZIP5_TRPA',           #16
            # value fields  
            'AS_LANDVALUE_TRPA',        #17
            'AS_IMPROVALUE_TRPA',       #18
            'AS_SUM_TRPA',              #19
            'TAX_LANDVALUE_TRPA',       #20 
            'TAX_IMPROVALUE_TRPA',      #21
            'TAX_SUM_TRPA',             #22
            'TAX_YEAR_TRPA',            #23
            # land use fields 
            'COUNTY_LANDUSE_CODE_TRPA', #24
            'COUNTY_LANDUSE_TRPA',      #25
            # Fields for building info
            "YEAR_BUILT_TRPA",          #26
            'UNITS_TRPA',               #27
            'BEDROOMS_TRPA',            #28
            'BATHROOMS_TRPA',           #29
            'BUILDING_SQFT_TRPA',       #30
            'VHR_TRPA',                 #31
            'HOA_TRPA',                 #32
            ###-------------------------###
            # County Fields to get data from
            'APN',                      #33
            'PLOC_',                    #34
            'PLOCDR',                   #35
            'PLOCNM',                   #36
            'PLOCTP',                   #37
            'PLOCU_',                   #38
            'PANAME',                   #39
            'PMADD1',                   #40
            'PMADD2',                   #41
            'PMCTST',                   #42
            'PZIP',                     #43
            'YYEAR',                    #44
            'YLDUSE',                   #45
            'YLANDV',                   #46
            'YIMPRV',                   #47
            'YEXMP',                    #48
            'YNETV',                    #49
            'PCONYR',                   #50
            'PBEDS',                    #51
            'PBATHS']                   #52

        with arcpy.da.UpdateCursor(douglasParcel, fields) as cursor:
            # loop through each record and transform the values
            for row in cursor:
                # APN field
                # Get County value
                apn = str(row[33])
                if not (apn is None or apn == ""):
                    row[0] =(apn[:4] + "-" + apn[4:6] + "-" + apn[6:9] + "-" + apn[9:12])
                else:
                    row[0] = ""
                    
                #PPNO
                ppno = row[33]
                if not (ppno is None):
                    row[1] = int(ppno)
                else:
                    row[1] = ''
                    
                # Jurisdiction
                row[2] = "DG"
                
                # APO Address
                house            = str(row[34]).strip() if row[34] is not None else ""
                street_direction = str(row[35]).strip() if row[35] is not None else ""
                street_name      = str(row[36]).strip() if row[36] is not None else ""
                street_suffix    = str(row[37]).strip() if row[37] is not None else ""
                unit             = str(row[38]).strip() if row[38] is not None else ""

                if not (street_name is None or street_name=='' or street_name.isspace()==True):
                    row[8] = re.sub(" +"," ", (house + " " + street_direction +" " + street_name+" " + street_suffix+" " + unit).strip())
                else:
                    row[8] = ''
                
                # House Number
                house = row[34]
                if not (house is None):
                    row[3] = str(house)
                else:
                    row[3] = ''
                
                # Street Direction
                street_direction = row[35]
                if not (street_direction is None or street_direction=='' or street_direction.isspace()==True):
                    row[4] = street_direction
                else:
                    row[4] = ''
                    
                # Street Name
                street_name = row[36]
                if not (street_name is None or street_name =='' or street_name.isspace()==True):
                    row[5] = street_name
                else:
                    row[5] = ''
                    
                # Street Suffix
                street_suffix = row[37]
                if not (street_suffix is None or street_suffix =='' or street_suffix.isspace()==True):
                    row[6] = street_suffix
                else:
                    row[6] = ''
                    
                # Unit Number
                unit= row[38]
                if not (unit is None or unit=='' or unit.isspace()==True):
                    row[7] = unit
                else:
                    row[7] = ''
                            
                # Postal Town - see Search/Update Cursor below
                
                # Postal State
                row[10] = 'NV'
                
                # Postal Zip - See Search/Update Cursor below
                row[11] = ''    
                
                # Owner Name
                owner = row[39]
                if not (owner is None or owner == '' or owner.isspace()==True):
                    row[12] = owner.strip()
                else:
                    row[12] = ""
            
                # Mailing Address
                address1 = row[40]
                address2 = row[41]
                if address1 and address2:  # Both values are non-empty and not None
                    row[13] = f"{address1} {address2}"
                elif address1:  # Only address1 is valid
                    row[13] = address1
                else:  # Neither address1 nor address2 is valid
                    row[13] = ''
                        
                # Mailing City
                mail_city = str(row[42]).split(',',1)[0].strip()
                
                if not (mail_city is None or mail_city=='' or mail_city.isspace()==True):
                    row[14] = mail_city
                else:
                    row[14] = ''
                    
                # Mailing State - Added logic to set anything that isn't 2 characters long to '' 
                mail_state = str(row[42]).rsplit(',')[-1].strip().split(' ',1)[0].strip()
                if not (mail_state is None or mail_state=='' or mail_state.isspace()==True or len(mail_state)!=2):
                    row[15] = mail_state[:2]
                else:
                    row[15] = ''
                
                # Mailing Zipcode
                #mail_zip = row[43].strip()
                mail_zip = row[43]
                if not (mail_zip is None or mail_zip=='' or mail_zip.isspace()==True):
                    row[16] = mail_zip[:5]
                else:
                    row[16] = ''
                    
                # Assessed Land Value
                land_value = row[46]
                if not(land_value is None):
                    row[17] = land_value
                else:
                    row[17] = ''
                
                # Assessed Improved Value
                improved_value = row[47]
                if not (improved_value is None):
                    row[18] = improved_value
                else:
                    row[18] = None
                        
                # Assessed Sum
                if not (land_value is None or improved_value is None):
                    assessed_sum = improved_value + land_value
                    row[19] = assessed_sum
                else:
                    row[19] = None
                
                # Tax  Land Value
                taxland_value = row[46]
                if not(taxland_value is None):
                    row[20] = taxland_value/0.35
                else:
                    row[20] = None
                
                # Tax Improved Value
                taximproved_value = row[47]
                if not (taximproved_value is None):
                    row[21] = taximproved_value/0.35
                else:
                    row[21] = None
                
                # Tax Sum
                if not (land_value is None or improved_value is None):
                    tax_sum = row[49]
                    row[22] = tax_sum
                else:
                    row[22] = None
                
                # Tax Year
                tax_year = row[44]
                if not (tax_year is None):
                    row[23] = tax_year
                else:
                    row[23] = ''
                    
                # County Land Use Code
                county_luc = row[45]
                if not (county_luc is None):
                    row[24] = str(county_luc)
                else:
                    row[24] = '' 
                
                # Year Built
                year_built = row[50]
                if not (year_built is None or year_built==''):
                    row[26] = year_built
                else:
                    row[26] = None
                
                # Bedrooms
                bedrooms = row[51]
                if not (bedrooms is None or bedrooms==''):
                    row[28] = bedrooms
                else:
                    row[28] = None
                # Bathrooms
                baths = row[52]
                if not (baths is None or baths==''):
                    row[29] = baths
                else:
                    row[29] = None
                    
        #         Update the row.
                cursor.updateRow(row)
        del cursor

        out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
        arcpy.Project_management(douglasParcel, parcel_out, out_coordinate_system)

        print('New Douglas Parcels transformed')
        logger.info('New Douglas Parcels Transformed')
    #-------------------------------------------------------------------------------------------
    # ELDORADO TRANSFORM
    #-------------------------------------------------------------------------------------------
    # get staging feature class to transform
    county_to_check = 'El Dorado'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        in_features = "Parcel_EL_Extracted"
        parcel_out  = "Parcel_EL_Transformed"

        # in-memory feature class
        eldoradoParcel = r"in_memory/inMemoryFeatureClass"

        # copy feature class into in-memory feature class to work on
        arcpy.management.CopyFeatures(in_features, eldoradoParcel)

        # Add TRPA base fields
        arcpy.management.AddFields(eldoradoParcel, baseFields)

        # Set up the regex queries for the data.
        # cityStateZipRegex = r'(.+?)\s([A-Z]{1,2})\s(.+?)$' - Keep in case new one doesn't work out long term.
        cityStateZipRegex = r'(.+?)\s([A-Z]{1,2})\s(?=\d)(.*)'
        poBoxRegex = r'([^x]+)\W(P\s*O BOX\W*[0-9]{1,6})'
        addressRegex = r'(\d{1,5}\D+.+)'
        canadaRegex = r'(.+?)\s([A-Z]{1,2})\s(CANADA)\s(.*)'
        brazilRegex = r'(.+?)\s(BRAZIL)\s(.*)'

        # Set up list for addresses with a country name in the mail_addr4 column.
        countriesList = ['japan','canada', 'australia', 'brazil', 'mexico', 'germany', 'france', 'england', 'united kingdom', 'uk', 'china', 'russia', 'india', 'south africa', 'nigeria', 'egypt', 'italy', 'spain', 'argentina', 'peru', 'chile', 'colombia', 'venezuela', 'ecuador', 'bolivia', 'paraguay', 'uruguay', 'panama', 'costa rica', 'nicaragua', 'honduras', 'el salvador', 'guatemala', 'belize', 'jamaica', 'haiti', 'dominican republic', 'cuba', 'bahamas', 'bermuda', 'puerto rico', 'us virgin islands', 'british virgin islands', 'anguilla', 'saint kitts and nevis', 'antigua and barbuda', 'saint lucia', 'saint vincent and the grenadines', 'grenada', 'barbados', 'trinidad and tobago', 'guyana', 'suriname', 'french guiana', 'martinique', 'guadeloupe', 'saint barthelemy', 'saint martin', 'sint maarten', 'aruba', 'curacao', 'bonaire', 'saba', 'sint eustatius', 'turks and caicos islands', 'cayman islands', 'anguilla', 'montserrat', 'bermuda', 'saint pierre and miquelon', 'greenland', 'iceland', 'faroe islands', 'norway', 'sweden', 'finland', 'denmark', 'estonia', 'latvia', 'lithuania', 'belarus', 'ukraine', 'moldova', 'romania', 'bulgaria', 'serbia', 'croatia', 'bosnia and herzegovina', 'slovenia', 'hungary', 'slovakia', 'czech republic', 'poland', 'austria', 'switzerland', 'liechtenstein', 'luxembourg', 'netherlands', 'belgium', 'ireland', 'portugal', 'spain', 'andorra', 'monaco', 'france', 'italy']
        
        # Transform County data to TRPA Schema
        with arcpy.da.UpdateCursor(eldoradoParcel, [
                                                ## TRPA base schema ##
                                                'APN_TRPA',                 #0
                                                'PPNO_TRPA',                #1
                                                'JURISDICTION_TRPA',        #2
                                                # parcel address   
                                                'HSE_NUMBR_TRPA',           #3
                                                'STR_DIR_TRPA',             #4
                                                'STR_NAME_TRPA',            #5
                                                'STR_SUFFIX_TRPA',          #6
                                                'UNIT_NUMBR_TRPA',          #7
                                                'APO_ADDRESS_TRPA',         #8
                                                'PSTL_TOWN_TRPA',           #9
                                                'PSTL_STATE_TRPA',          #10
                                                'PSTL_ZIP5_TRPA',           #11
                                                # owner fields
                                                    # no first and last fields
                                                'OWN_FULL_TRPA',            #12
                                                'MAIL_ADD1_TRPA',           #13
                                                'MAIL_CITY_TRPA',           #14
                                                'MAIL_STATE_TRPA',          #15
                                                'MAIL_ZIP5_TRPA',           #16
                                                # value fields  
                                                'AS_LANDVALUE_TRPA',        #17
                                                'AS_IMPROVALUE_TRPA',       #18
                                                'AS_SUM_TRPA',              #19
                                                'TAX_LANDVALUE_TRPA',       #20 
                                                'TAX_IMPROVALUE_TRPA',      #21
                                                'TAX_SUM_TRPA',             #22
                                                'TAX_YEAR_TRPA',            #23
                                                # land use fields 
                                                'COUNTY_LANDUSE_CODE_TRPA', #24
                                                'COUNTY_LANDUSE_TRPA',      #25
                                                # Fields for building info
                                                "YEAR_BUILT_TRPA",          #26
                                                'UNITS_TRPA',               #27
                                                'BEDROOMS_TRPA',            #28
                                                'BATHROOMS_TRPA',           #29
                                                'BUILDING_SQFT_TRPA',       #30
                                                'VHR_TRPA',                 #31
                                                'HOA_TRPA',                 #32
                                                ###-------------------------###
                                                # County Fields to get data from
                                                'PRCL_ID',                  #33
                                                'OWNER_NAME',               #34
                                                'MAIL_ADDR1',               #35
                                                'MAIL_ADDR2',               #36
                                                'MAIL_ADDR3',               #37
                                                'MAIL_ADDR4',               #38
                                                'ADDRSTNBR',                #39
                                                'ADDRSTDIR',                #40
                                                'ADDRSTNAME',               #41
                                                'ADDRSTTYPE',               #42
                                                'ADDRUNITNB',               #43
                                                'PRCL_ADDR',                #44
                                                'USECD_1',                  #45
                                                'USECDLIT_1',               #46
                                                'STRUCT_VAL',               #47
                                                'LAND_VAL',                 #48
                                                'YR_BUILT',                 #49
                                                'DWELLUNITS',               #50
                                                'BEDROOMS',                 #51
                                                'ADDRSTPRFX'                 #52
        ]) as cursor:
            # transform each row
            for row in cursor:   
                # Set APN
                apn = row[33]
                if not (apn is None or apn == "" or apn.isspace() == True or 'UN' in apn):
                    row[0] = (apn[:3] + "-" + apn[3:6] + "-" + apn[6:9])
                else:
                    row[0] = ''
                    
                # Set PPNO
                ppno = row[33]
                if not (apn is None or apn == "" or apn.isspace() == True or 'UN' in apn or 'NP' in apn):
                    try:
                        row[1] = float(ppno)
                    except ValueError:
                        row[1] = 0
                else:
                    row[1] = 0
                # Set County
                row[2] = 'EL'
                
                # APO Address
                full_address = row[44]
                if not (full_address is None or full_address=='' or full_address.isspace()==True):
                    
                    row[8] = full_address
                else:
                    row[8] = ''
                
                # House Number
                house = row[39]
                if not (house is None):
                    # convert house number to integer type
                    row[3] = str(int(house))
                else:
                    row[3] = ''
                
                # Street Direction
                street_direction = row[40]
                if not (street_direction is None or street_direction=='' or street_direction.isspace()==True
                        or street_direction == 'UNASSIGNED'):
                    # get the first character
                    row[4] = street_direction[0]
                else:
                    row[4] = ''
                    
                # Street Name
                street_name = row[41]
                street_prefix = row[52]
                if not (street_name is None or street_name =='' or street_name.isspace()==True):
                    if not (street_prefix is None or street_prefix =='' or street_prefix.isspace()==True
                        or street_prefix == 'UNASSIGNED'):
                        row[5]= street_prefix + ' ' + street_name
                    else:
                        row[5] = street_name
                else:
                    row[5] = ''
                    
                # Street Suffix
                street_suffix = row[42]
                if not (street_suffix is None or street_suffix =='' or street_suffix.isspace()==True               
                        or street_direction == 'UNASSIGNED'):
                    row[6] = street_suffix
                else:
                    row[6] = ''
                    
                # Unit Number
                unit= row[43]
                if not (unit is None or unit=='' or unit.isspace()==True):
                    row[7] = ("#" + str(unit))
                else:
                    row[7] = ''
                            
                # Postal Town - see Search/Update Cursor below
                row[9] = ''
                
                # Postal State
                row[10] = 'CA'
                
                # Postal Zip - See Search/Update Cursor below
                row[11] = ''    
                
                # Set Mailing Owner, Address, City, State, Zip
                if row[38] != ' ':
                    #Check MailAddr3 or MailAddr4 for country name
                    if row[38] != 'UNKNOWN' and row[38].lower() not in countriesList and row[37].lower() not in countriesList:
                        # Parse out city, state, and zip code and assign variables.
                        cityStateZip = re.search(cityStateZipRegex, str(row[38]))
                        if cityStateZip is not None:
                            city = cityStateZip.group(1)
                            state = cityStateZip.group(2)
                            zipCode = cityStateZip.group(3)
                            country = ''
                        else:
                            continue
                        # Check to see if address starts with PO Box and assign variable.
                        if str(row[37]).startswith('PO') or str(row[37]).startswith('P O'):
                            address = str(row[37])
                        elif "PO BOX" in str(row[37]) or "P O BOX" in str(row[37]) or "P.O. BOX" in str(row[37]):
                            address = str(row[37])

                        # Parse out address that doesn't have PO Box and assign variable.
                        else:
                            add = re.search(addressRegex,str(row[37]))
                            address = add.group(1)

                        # Assign owner variable.
                        owner = str(row[34])+' '+str(row[35])+' '+str(row[36])
                    elif row[38].lower() in countriesList:
                        country = str(row[38])
                        state = str(row[37])
                        city = str(row[36])
                        address = str(row[35])
                        owner = str(row[34])
                        zipCode = ''
                    elif row[38] == "CANADA": # temporary patch for incorrectly entered Canadian address
                        canadaZip = re.search(r'[ABCEGHJKLMNPRSTVXY][0-9][ABCEGHJKLMNPRSTVWXYZ] ?[0-9][ABCEGHJKLMNPRSTVWXYZ][0-9]', str(row[3]))
                        canadaProvZip = re.search(r'(.*?)\s(N[BLSTU]|[AMN]B|[BQ]C|ON|PE|SK)',str(row[36]))
                        if canadaZip != None:
                            zipCode = str(canadaZip.group(0))
                        else:
                            zipCode =''
                            address = str(row[35])
                            city = str(canadaProvZip.group(1))
                            state = str(canadaProvZip.group(2))
                            country = str(row[38])
                    else:
                        owner = str(row[34])
                        address = ''
                        city = ''
                        state = ''
                        zipCode = ''
                        country = ''

                # If mail_addr4 is "empty".
                elif row[37] != ' ':
        #             print("Working on MAIL_ADDR3")
                    # Parse out city, state, and zip code.
                    # Foreign addresses won't parse so assign country, owner, address, and city variables. Set state and zip to blanks.
                    if cityStateZip is None:
                        country = str(row[37])
                        owner = str(row[34])
                        address = str(row[35])
                        city = str(row[36])
                        state = ''
                        zipCode = ''
                    else:
                        country = ''
                        row2 = str(row[2])

                        # Sanitize rows that start with a space.
                        if str(row[36]).startswith(' '):
                            row2 = str(row[36])[1:]

                        # Parse out city, state, and zip code and assign variables.
                        city = cityStateZip.group(1)
                        state = cityStateZip.group(2)
                        zipCode = cityStateZip.group(3)

                        # Check to see if address starts with PO Box and assign variable.
                        if row2.startswith('PO') or row2.startswith('P O') or row2.startswith('P.O.'):
                            address = row2

                        # Sometimes there may be a word in front of PO Box and parse that out and assign variable.
                        elif "PO BOX" in row2 or "P O BOX" in row2 or row2.startswith('ONE ') or row2.startswith('TWO '):
                            address = row2
                        else:
                            # Parse out address that doesn't have PO Box and assign variable, sometimes there no address so set variable to None.
                            add = re.search(addressRegex,row2)
                            if add is None:
                                address = 'None'
                            else:
                                address = add.group(1)

                        # Assign owner variable.
                        owner = str(row[34])+' '+str(row[35])

                # Before moving to mail_addr2 must capture "blanks" and USA owned parcels and insert blanks.
                elif row[0] == 'UNITED STATES OF AMERICA':
                    cityStateZip = re.search(cityStateZipRegex, str(row[36]))
                    owner = str(row[34])
                    address = str(row[35])
                    if cityStateZip is None:
                        city = ''
                        state = ''
                        zipCode = ''
                    else:
                        city = cityStateZip.group(1)
                        state = cityStateZip.group(2)
                        zipCode = cityStateZip.group(3)
                    country = ''
                elif row[34] == ' ':
                    owner = ''
                    address = ''
                    city = ''
                    state = ''
                    zipCode = ''
                    country = ''
                elif row[35] == ' ':
                    owner = str(row[34])
                    address = ''
                    city = ''
                    state = ''
                    zipCode = ''
                    country = ''

                # Parse the rest of the address info.
                else:
        #             print("Working on MAIL_ADDR2")
                    if str(row[36]) == ' ':
                        owner = str(row[34])
                        address = str(row[35])
                        city = ''
                        state = ''
                        zipCode = ''
                        country = ''
                    else:
                        row2 = str(row[36])

                        # Parse out city, state, and zip code and assign variables.
                        cityStateZip = re.search(cityStateZipRegex, row2)

                        # if it can't parse it's a foreign address and assign country variable.
                        if cityStateZip is None:
                            if "CANADA" in row2:
                                cityStateZip = re.search(canadaRegex, row2)
                                city = cityStateZip.group(1)
                                state = cityStateZip.group(2)
                                zipCode = cityStateZip.group(4)
                                country = cityStateZip.group(3)
                            if "BRAZIL" in row2:
                                cityStateZip = re.search(brazilRegex, row2)
                                city = cityStateZip.group(1)
                                state = ''
                                zipCode = cityStateZip.group(3)
                                country = cityStateZip.group(2)
                        else:
                            row1 = str(row[35])
                            country = ''
                            city = cityStateZip.group(1)
                            state = cityStateZip.group(2)
                            zipCode = cityStateZip.group(3)

                            # Sanitize rows that start with a space.
                            if row1.startswith(' '):
                                row1 = row1[1:]

                            # Check to see if address starts with PO Box and assign variable.
                            if row1.startswith('PO') or row1.startswith('P.O.') or row1.startswith('P O') or row1.startswith('P  O'):
                                address = str(row[35])

                            # Sometimes there may be a word in front of PO Box and parse that out and assign variable.
                            elif "PO BOX" in row1 or "P O BOX" in row1:
                                poBox = re.search(poBoxRegex,row1)

                                # If it can't be parsed assign variable.
                                if poBox is None:
                                    address = row1
                                else:
                                    address = poBox.group(2)
                            else:
                                # Parse out address that doesn't have PO Box and assign variable, sometimes there no address so set variable to None.
                                add = re.search(addressRegex,row1)

                                # Have exception for addresses that spell out 'one' instead of '1'.
                                if add is None or row1.startswith('ONE'):
                                    address = row1
                                else:
                                    address = add.group(1)

                        # Set owner variable.
                        owner = str(row[34])

                # Set Owner
                row[12] = owner
                
                # Set Mailing Address
                row[13] = address
                
                # Set Mailing City
                row[14] = city
                
                # Set Mailing State
                row[15] = state
                
                # Set Mailing ZIP
                row[16] = zipCode[:5]
        #         row[10] = country

                # Assessed Land Value
                land_value = row[48]
                if not(land_value is None):
                    row[17] = land_value
                else:
                    row[17] = ''
                
                # Assessed Improved Value
                improved_value = row[47]
                if not (improved_value is None):
                    row[18] = improved_value
                else:
                    row[18] = None
                        
                # Assessed Sum
                if not (land_value is None or improved_value is None):
                    assessed_sum = improved_value + land_value
                    row[19] = assessed_sum
                else:
                    row[19] = None
                
                # Tax  Land Value
                taxland_value = row[48]
                if not(taxland_value is None):
                    row[20] = taxland_value
                else:
                    row[20] = None
                
                # Tax Improved Value
                taximproved_value = row[47]
                if not (taximproved_value is None):
                    row[21] = taximproved_value
                else:
                    row[21] = None
                
                # Tax Sum
                if not (land_value is None or improved_value is None):
                    tax_sum = taximproved_value + taxland_value
                    row[22] = tax_sum
                else:
                    row[22] = None
                
                # Tax Year
                row[23] = datetime.datetime.now().year # get current year
                    
                # County Land Use Code
                county_luc = row[45]
                if not (county_luc is None):
                    row[24] = str(county_luc)
                else:
                    row[24] = '' 
                
                # County Land Use - See Search/Update Cursor Below
                county_landuse = row[46]
                if not (county_landuse is None or county_landuse=='' or county_landuse.isspace()==True):
                    row[25] = county_landuse
                else:
                    row[25] = '' 
                
                # Year Built
                year_built = row[49]
                if not (year_built is None):
                    row[26] = year_built
                else:
                    row[26] = None
                    
                # Units
                units = row[50]
                if not (units is None):
                    row[27] = units
                else:
                    row[27] = None
                
                # Bedrooms
                bedrooms = row[51]
                if not (bedrooms is None):
                    row[28] = bedrooms
                else:
                    row[28] = None

                # Update the row.
                cursor.updateRow(row)
        del cursor

        out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
        CombineAPNs(eldoradoParcel, 'APN_TRPA')
        arcpy.Project_management(eldoradoParcel, parcel_out, out_coordinate_system)
        print('New El Dorado Parcels transformed')
        logger.info("New El Dorado Parcels Transformed")
    #---------------------------------------------------------------------------------
    # PLACER COUNTY TRANSFORM
    #---------------------------------------------------------------------------------
    county_to_check = 'Placer'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        in_features = "Parcel_PL_Extracted"
        parcel_out  = "Parcel_PL_Transformed"

        # in-memory feature class
        placerParcel = r"in_memory/inMemoryFeatureClass"

        # copy feature class into in-memory feature class to work on
        arcpy.management.CopyFeatures(in_features, placerParcel)

        # Add TRPA base fields
        arcpy.management.AddFields(placerParcel, baseFields)

        # Transform County data to TRPA data.
        with arcpy.da.UpdateCursor(placerParcel, ['APN_TRPA',               #0
                                                'PPNO_TRPA',                #1
                                                'JURISDICTION_TRPA',        #2
                                                # parcel address   
                                                'HSE_NUMBR_TRPA',           #3
                                                'STR_DIR_TRPA',             #4
                                                'STR_NAME_TRPA',            #5
                                                'STR_SUFFIX_TRPA',          #6
                                                'UNIT_NUMBR_TRPA',          #7
                                                'APO_ADDRESS_TRPA',         #8
                                                'PSTL_TOWN_TRPA',           #9
                                                'PSTL_STATE_TRPA',          #10
                                                'PSTL_ZIP5_TRPA',           #11
                                                # owner fields
                                                'OWN_FIRST_TRPA',           #12
                                                'OWN_LAST_TRPA',            #13
                                                'OWN_FULL_TRPA',            #14
                                                'MAIL_ADD1_TRPA',           #15
                                                'MAIL_CITY_TRPA',           #16
                                                'MAIL_STATE_TRPA',          #17
                                                'MAIL_ZIP5_TRPA',           #18
                                                # value fields  
                                                'AS_LANDVALUE_TRPA',        #19
                                                'AS_IMPROVALUE_TRPA',       #20
                                                'AS_SUM_TRPA',              #21
                                                'TAX_LANDVALUE_TRPA',       #22 
                                                'TAX_IMPROVALUE_TRPA',      #23
                                                'TAX_SUM_TRPA',             #24
                                                'TAX_YEAR_TRPA',            #25
                                                # land use fields 
                                                'COUNTY_LANDUSE_CODE_TRPA', #26
                                                'COUNTY_LANDUSE_TRPA',      #27
                                                # Fields for building info
                                                "YEAR_BUILT_TRPA",          #28
                                                'UNITS_TRPA',               #29
                                                'BEDROOMS_TRPA',            #30
                                                'BATHROOMS_TRPA',           #31
                                                'BUILDING_SQFT_TRPA',       #32
                                                'VHR_TRPA',                 #33
                                                'HOA_TRPA',                 #34
                                                ###-------------------------###
                                                # County Fields to get data from
                                                'APN',   # apn                #35
                                                'FEEPARCEL',   # ppno            #36
                                                'STREETNUM', # house number   #37
                                                'STREETDIR',# street dir      #38
                                                'STREETNAME',# street name    #39
                                                'STREETTYPE',# street suffix  #40
                                                'SP_APT',  # unit number      #41
                                                'OWNER1',# owner name         #42
                                                'OWNER2',# owner 2            #43
                                                'MailingAdr1',  # mailing addr1      #44
                                                'MailingAdr2',  # mailing addr2      #45
                                                'MailingCity',  # city               #46 
                                                'MailingState', # state              #47
                                                'MailingZip',  # zip                 #48
                                                'USE_CD', # land use code     #49
                                                'USE_CD_N', # land use desc   #50
                                                'LANDVALUE',# land value      #51
                                                'STRUCTURE',# improved value  #52
                                                'EffectiveYr',# year built     #53
                                                'StructureSF',  # build sqft      #54
                                                'SitusZip'      # Parcel zip      #55
                                            
        ]) as cursor:   
            # loop through each record to transform values to TRPA schema values
            for row in cursor:
                # set APN
                apn = row[35]
                if not (apn is None or apn == "" or apn.isspace() == True or "ROW" in apn or len(apn) < 8):
                    row[0] =apn[:11]
                else:
                    row[0] = ""
                    
                # set PPNO
                # Changed it to 9 rather than 8
                ppno = row[36]
                if not (ppno is None or ppno == "" or "ROW" in ppno or len(ppno) < 8):
                    row[1] = ppno[:9]
                else:
                    row[1] = 0
                    
                # Jurisdiction
                row[2] = "PL"
                
                # House Number
                house = row[37]
                if not (house is None or house=='' or house.isspace()==True):
                    row[3] = house
                else:
                    row[3] = ''
                
                # Street Direction
                street_direction = row[38]
                if not (street_direction is None or street_direction=='' or street_direction.isspace()==True):
                    row[4] = street_direction
                else:
                    row[4] = ''
                    
                # Street Name
                street_name = row[39]
                if not (street_name is None or street_name =='' or street_name.isspace()==True):
                    row[5] = street_name
                else:
                    row[5] = ''
                    
                # Street Suffix
                street_suffix = row[40]
                if not (street_suffix is None or street_suffix =='' or street_suffix.isspace()==True):
                    row[6] = street_suffix
                else:
                    row[6] = ''
                    
                # Unit Number
                unit= row[41]
                if not (unit is None or unit=='' or unit.isspace()==True):
                    row[7] = str(unit)
                else:
                    row[7] = ''
                
                # APO Address
                full_address = [house, street_direction, street_name, street_suffix, unit]
                adr = str(' '.join(filter(None, full_address))).strip()
                adr = re.sub(r"\s+", " ", adr).strip()

                if not (adr is None or adr=='' or adr.isspace()==True):
                    row[8] = adr
                else:
                    row[8] = ''
                    
                # Postal Town - See TRPA ATTRIBUTION section
                    
                # Postal State
                row[10] = 'CA'
                
                # Owner Name
                owner1 = row[42]
                owner2 = row[43]
                # own first
                if not (owner1 is None or owner1 == "" or owner1.isspace() == True):
                    row[12] = owner1.strip()
                else:
                    row[12] = ''
                # own last
                if not (owner2 is None or owner2 == "" or owner2.isspace() == True):
                    row[13] = owner2.strip()
                else:
                    row[13] = ''    
                # own full
                if not (owner2 is None or owner2 == "" or owner2.isspace() == True):
                    row[14] = (owner1+" " + owner2).strip()
                elif not (owner1 is None or owner1 == ""):
                    row[14] = owner1.strip()
                else:
                    row[14] = ''
                    
                # Mailing Address
                address1 = row[44]
                address2 = row[45]
                if not (address1 is None or address1=='' or address1.isspace()==True):
                    row[15] = str(address1).strip()
                else:
                    row[15] = ''
                
                # Mailing City
                mail_city = row[46]
                
                if not (mail_city is None or mail_city=='' or mail_city.isspace()==True):
                    row[16] = mail_city
                else:
                    row[16] = ''
                    
                # Mailing State
                mail_state = row[47]
                if not (mail_state is None or mail_state=='' or mail_state.isspace()==True):
                    #row[17] = mail_state
                    row[17] = mail_state[:2]
                else:
                    row[17] = ''
                
                # Mailing Zipcode
                mail_zip = row[48]
                if not (mail_zip is None or mail_zip=='' or mail_zip.isspace()==True):
                    row[18] = mail_zip[:5]
                else:
                    row[18] = ''
                    
                # Assessed Land Value
                land_value = row[51]
                if not(land_value is None or land_value==''):
                    row[19] = int(land_value)
                else:
                    row[19] = None
            
                # Assessed Improved Value    
                improved_value = row[52]
                if not (improved_value is None or improved_value==''):
                    row[20] = int(improved_value)
                else:
                    row[20] = None

                # Assessed Sum
                if not (row[19] is None and row[20] is None):
                    assessed_sum = improved_value + land_value
                    row[21] = assessed_sum
                else:
                    row[21] = None
                
                # Tax Land Value
                taxland_value = row[51]
                if not(taxland_value is None):
                    row[22] = int(taxland_value)
                else:
                    row[22] = None
                
                # Tax Improved Value
                taximproved_value = row[52]
                if not (taximproved_value is None):
                    row[23] = int(taximproved_value)
                else:
                    row[23] = None
                
                # Tax Sum
                if not (row[22] is None and row[23] is None):
                    tax_sum = taximproved_value + taxland_value
                    row[24] = tax_sum
                else:
                    row[24] = None
                
                # Tax Year
                row[25] = datetime.datetime.now().year # get current year
                    
                # County Land Use Code
                county_luc = row[49]
                if not (county_luc is None or county_luc=='' or county_luc.isspace()==True):
                    row[26] = county_luc
                else:
                    row[26] = '' 
                
                # County Land Use
                county_landuse = row[50]
                if not (county_landuse is None or county_landuse=='' or county_landuse.isspace()==True):
                    row[27] = county_landuse
                else:
                    row[27] = ''
                    
                # Year Built
                year_built = row[53]
                if not (year_built is None):
                    row[28] = year_built
                else:
                    row[28] = None
                    
                # Building SQFT
                bldsqft = row[54]
                if not (bldsqft is None):
                    row[32] = bldsqft
                else:
                    row[32] = None

                # Postal Zip
                parcelzip = row[55]
                if not (parcelzip is None):
                    row[11] = parcelzip[:5]
                else:
                    row[11] = None
                    
                # Update the row.
                cursor.updateRow(row)
        del cursor

        # combine duplicate APNs 
        ### some shoreline parcels are split by the highway and have two features for the same APN
        CombineAPNs(placerParcel, 'APN_TRPA')

        # project to our projected coordinate system
        out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
        arcpy.Project_management(placerParcel, parcel_out, out_coordinate_system)

        # done with the transormations for Placer
        print('New Placer Parcels transformed')
        logger.info('New Placer Parcels Transformed')
    #-------------------------------------------------------------------------------------------
    # WASHOE COUNTY TRANSFORM
    #-------------------------------------------------------------------------------------------
    county_to_check = 'Washoe'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        # input/output
        in_features = "Parcel_WA_Extracted"
        parcel_out  = "Parcel_WA_Transformed"

        # in-memory feature class
        washoeParcels = r"in_memory/inMemoryFeatureClass"

        # copy features to in-memory feature class
        arcpy.CopyFeatures_management(in_features, washoeParcels)

        # Add TRPA base fields
        arcpy.management.AddFields(washoeParcels,baseFields)

        # Tansform County Data to TRPA Data.
        with arcpy.da.UpdateCursor(washoeParcels, ['APN_TRPA',              #row[0]
                                                'PPNO_TRPA',                #row[1]
                                                'JURISDICTION_TRPA',        #row[2]
                                                # parcel address   
                                                'HSE_NUMBR_TRPA',           #3
                                                'STR_DIR_TRPA',             #4
                                                'STR_NAME_TRPA',            #5
                                                'STR_SUFFIX_TRPA',          #6
                                                'UNIT_NUMBR_TRPA',          #7
                                                'APO_ADDRESS_TRPA',         #8
                                                'PSTL_TOWN_TRPA',           #9
                                                'PSTL_STATE_TRPA',          #10
                                                'PSTL_ZIP5_TRPA',           #11
                                                # owner fields
                                                'OWN_FIRST_TRPA',           #12
                                                'OWN_LAST_TRPA',            #13
                                                'OWN_FULL_TRPA',            #14
                                                'MAIL_ADD1_TRPA',           #15
                                                'MAIL_CITY_TRPA',           #16
                                                'MAIL_STATE_TRPA',          #17
                                                'MAIL_ZIP5_TRPA',           #18
                                                # value fields  
                                                'AS_LANDVALUE_TRPA',        #19
                                                'AS_IMPROVALUE_TRPA',       #20
                                                'AS_SUM_TRPA',              #21
                                                'TAX_LANDVALUE_TRPA',       #22 
                                                'TAX_IMPROVALUE_TRPA',      #23
                                                'TAX_SUM_TRPA',             #24
                                                'TAX_YEAR_TRPA',            #25
                                                # land use fields 
                                                'COUNTY_LANDUSE_CODE_TRPA', #26
                                                'COUNTY_LANDUSE_TRPA',      #27
                                                # Fields for building info
                                                "YEAR_BUILT_TRPA",          #28
                                                'UNITS_TRPA',               #29
                                                'BEDROOMS_TRPA',            #30
                                                'BATHROOMS_TRPA',           #31
                                                'BUILDING_SQFT_TRPA',       #32
                                                'VHR_TRPA',                 #33
                                                'HOA_TRPA',                 #34
                                                ###-------------------------###
                                                # County Fields to get data from
                                                'PIN',   # apn              #35
                                                'APN',   # ppno             #36
                                                'FullAddress',#full adrress #37
                                                'STREETNUM', # house number #38
                                                'STREETDIR',# street dir    #39
                                                'STREET',# street name      #40
                                                'CITY',    # postal town    #41
                                                'SITUSZIP', # postal zip    #42
                                                'SQFEET',# building sqft    #43
                                                'FIRSTNAME',# first name    #44
                                                'LASTNAME', # last name     #45
                                                'MAILING1',# mailing addr1  #46
                                                'MAILING2',# mailing addr2  #47
                                                'MAILCITY',# city           #48
                                                'MAILSTATE', # mailing state#49
                                                'MAILZIP',  # zip           #50
                                                'TAXYEAR', # tax year       #51
                                                'LAND_USE',# land use code  #52
                                                'LANDASS',# land value      #53
                                                'BUILDASS',# improved value #54
                                                'TOTALASS', # total assesed #55
                                                'LANDAPR',  # land apr      #56
                                                'BUILDAPR', # building apr  #57
                                                'TOTALAPR', # total apr     #58
                                                'YEARBLT',# year built      #59
                                                'STORIES',# stories         #60
                                                'BEDROOMS', # bedrooms      #61      
                                                'BATHS',# bathrooms         #62
                                                'UNITS'   # units           #63
        ]) as cursor:
            # loop through each record and transform the values
            for row in cursor:
                # APN field
                # Get County value
                apn  = row[35]
                if not (apn is None or apn == "" or apn.isspace() == True):
                    # set TRPA value
                    row[0] = apn
                else:
                    row[0] = ''
                    
                #PPNO
                ppno = row[36]
                if not (ppno is None or ppno == ""):
                    row[1] = int(ppno)
                else:
                    row[1] = None
                    
                # Jurisdiction
                row[2] = "WA"
                        
                # APO Address
                fulladdress = row[37]
                if not (fulladdress is None or fulladdress=='' or fulladdress.isspace()==True):
                    row[8] = fulladdress
                else:
                    row[8] = ''
                
                # House Number
                house = row[38]
                if not (house is None or house=='' or house.isspace()==True):
                    row[3] = house
                else:
                    row[3] = ''
                    
                
                # Unit Number
                if not (fulladdress is None or fulladdress == ""):
                    if fulladdress.strip()[-1].isdigit():
                        if not ('STATE ROUTE 28' in fulladdress):
                            row[7] = (fulladdress.rsplit(' ')[-1].strip())
                        else:
                            if not (fulladdress.strip().rsplit(' ')[-1] == '28'):
                                row[7] = (fulladdress.rsplit(' ')[-1].strip())
                            else:
                                if not ('STATE ROUTE 28 28' in fulladdress): 
                                    row[7] = ""
                                else:
                                    row[7] = (fulladdress.rsplit(' ')[-1].strip())
                    else:
                        if not ('US HIGHWAY 395' in fulladdress):
                            if len(fulladdress.rsplit(' ')[-1]) == 1:
                                row[7] = (fulladdress.rsplit(' ')[-1].strip())
                            elif not (len(fulladdress.rsplit(' ')[-1]) == 1):
                                if fulladdress[-2].isdigit():
                                    row[7] = (fulladdress.rsplit(' ')[-1].strip())
                                else:
                                    row[7] = ""
                            else:
                                row[7] = ""
                        else:
                            row[7] = ""
                else:
                    row[7] = ""
                    
                # Street Direction
                stdir = row[39]
                if not (stdir is None):
                    row[4] = (stdir.strip())
                else:
                    row[4] = ""
                    
                # Street Name    
                stname = row[40]
                if not (stname is None or stname in ('CROSS BOW', 'ENTERPRISE', 'STATE ROUTE 28', 'UNSPECIFIED', 'US HIGHWAY 395', '')):
                    if stname[:2] in ('N ', 'S ', 'E ', 'W '):
                        row[5] = stname.rsplit(' ',1)[0].strip().split(' ',1)[1].strip()
                    elif not (stname is None or stname == "" or stname.isspace() == True):
                        row[5] = (stname.rsplit(' ',1)[0].strip())
                    #Currently the only example of this is two blanks in Incline Village with no info
                    elif stname is None or stname == "" or stname.isspace() == True:
                        if fulladdress[0].isdigit():
                            row[5] = (fulladdress.rsplit(' ')[-1].strip())
                        else:
                            row[5] = ""
                    else:
                        logging.info("Error parsing washoe street name")
                elif stname in ('CROSS BOW', 'ENTERPRISE', 'STATE ROUTE 28', 'UNSPECIFIED', ''):
                        row[5] = (stname.strip())
                else:
                    row[5] = ""
                    
                # Street Suffix
                if not stname in ('CROSS BOW', 'ENTERPRISE', 'STATE ROUTE 28', 'UNSPECIFIED', 'US HIGHWAY 395', ''):
                    if not (stname is None or stname == "" or stname.isspace() == True):
                        row[6] = (stname.rsplit(' ')[-1].strip())
                    elif stname is None or stname == "" or stname.isspace() == True:
                        if not (fulladdress is None or fulladdress[0].isdigit()):
                            row[6] = (fulladdress.rsplit(' ')[-1].strip())
                        else:
                            row[6] = ""
                    else:
                        logging.info("Error parsing washoe street suffix")
                else:
                    row[6] = ""

                # Postal Town
                postal_town = row[41]
                if not (postal_town is None or postal_town == '' or postal_town.isspace()==True):
                    row[9] = postal_town
                else:
                    row[9] = ''
                    
                # Postal State
                row[10] = 'NV'
                
                # Postal Zip
                postal_zip = row[42]
                if not (postal_zip is None or postal_zip == '' or postal_zip.isspace()==True):
                    row[11] = postal_zip[:5]
                else:
                    row[11] = ''
                    
                # Owner Name
                # set owner first name
                ownfirst = row[44]
                if not (ownfirst is None or ownfirst.isspace() == True):
                    row[12] = ownfirst
                else:
                    row[12] = ""
                
                # own last
                ownlast = row[45]
                if not (ownlast is None or ownlast.isspace() == True):
                    row[13] = ownlast
                else:
                    row[13] = ""
                
                # own full
                if not (ownfirst is None and ownlast is None):
                    row[14] = (ownfirst + " " + ownlast).strip()
                else:
                    row[14] = ""
                    
                # Mailing Address
                if not (row[46] is None):  
                    address1 = row[46].strip()
                if not (row[47] is None):
                    address2 = row[47].strip()
                if not (address1 is None or address1=='' or address1.isspace()==True):
                    row[15] = str((address1 + " " + address2).strip())
                elif (address2 is None):
                    row[15] = address1
                else:
                    row[15] = ''
                
                # Mailing City
                mail_city = row[48]
                if not (mail_city is None or mail_city=='' or mail_city.isspace()==True):
                    row[16] = mail_city
                else:
                    row[16] = ''
                    
                # Mailing State
                mail_state = row[49]
                if not (mail_state is None or mail_state=='' or mail_state.isspace()==True):
                    #row[17] = mail_state
                    row[17] = mail_state[:2]
                else:
                    row[17] = ''
                
                # Mailing Zipcode
                if not (row[50] is None):
                    mail_zip = row[50].strip()
                if not (mail_zip is None or mail_zip=='' or mail_zip.isspace()==True):
                    row[18] = mail_zip[:5]
                else:
                    row[18] = ''
                    
                # Assessement Value
                land_value = row[53]
                if not(land_value is None or land_value==''):
                    row[19] = land_value
                else:
                    row[19] = None
                
                improved_value = row[54]
                if not (improved_value is None or improved_value==''):
                    row[20] = improved_value
                else:
                    row[20] = None
                        
                assessed_sum = row[55]
                if not (assessed_sum is None or assessed_sum==''):
                    row[21] = assessed_sum
                else:
                    row[21] = None
                
                # Tax Value
                taxland_value = row[56]
                if not(taxland_value is None or taxland_value==''):
                    row[22] = taxland_value
                else:
                    row[22] = None
                
                taximproved_value = row[57]
                if not (taximproved_value is None or taximproved_value==''):
                    row[23] = taximproved_value
                else:
                    row[23] = None
                
                tax_sum = row[58]
                if not (tax_sum is None or tax_sum==''):
                    row[24] = tax_sum
                else:
                    row[24] = None
                
                # Tax Year
                tax_year = row[51]
                if not (tax_year is None or tax_year=='' or tax_year.isspace()==True):
                    row[25] = tax_year
                else:
                    row[25] = None
                    
                # County Land Use Code
                county_luc = row[52]
                if not (county_luc is None or county_luc=='' or county_luc.isspace()==True):
                    row[26] = int(county_luc.split(",",1)[0].strip())
                else:
                    row[26] = None 
                
                # Year Built
                year_built = row[59]
                if not (year_built is None or year_built==''):
                    row[28] = year_built
                else:
                    row[28] = None
                    
                # Units
                units = row[63]
                if not (units is None or units==''):
                    row[29] = int(units)
                else:
                    row[29] = None
                
                # Bedrooms
                bedrooms = row[61]
                if not (bedrooms is None or bedrooms==''):
                    row[30] = bedrooms
                else:
                    row[30] = None
                
                # Bathrooms
                bathrooms = row[62]
                if not (bathrooms is None or bathrooms==''):
                    row[31] = bathrooms
                else:
                    row[31] = None
                    
                # Building Square Feet
                building_sqft = row[43]
                if not (building_sqft is None or building_sqft==''):
                    row[32] = building_sqft
                else:
                    row[32] = None

                # Update the row.
                cursor.updateRow(row)
        del cursor

        # create a spatial reference object for the output coordinate system 
        out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
        arcpy.Project_management(washoeParcels, parcel_out, out_coordinate_system)

        print('New Washoe Parcels transformed')
        logger.info('New Washoe Parcels Transformed')
    #--------------------------------------
    # MERGE
    #--------------------------------------
    # delete in-memory
    arcpy.Delete_management("memory")
    print("Deleted Memory Workspace: " + strftime("%Y-%m-%d %H:%M:%S"))
    logger.info('Deleted Memory Workspace')
    # out merge fc
    parcel_out = "Parcel_Staging"

    # input feature classes
    ccParcel = "Parcel_CC_Transformed"
    dgParcel = "Parcel_DG_Transformed"
    elParcel = "Parcel_EL_Transformed"
    plParcel = "Parcel_PL_Transformed"
    waParcel = "Parcel_WA_Transformed"

    # Create FieldMappings object to manage merge output fields
    fieldMappings = arcpy.FieldMappings()
    # Add all fields from all parcel staging layers
    fieldMappings.addTable(ccParcel)
    fieldMappings.addTable(dgParcel)
    fieldMappings.addTable(elParcel)
    fieldMappings.addTable(plParcel)
    fieldMappings.addTable(waParcel)

    # Remove all output fields from the field mappings, except fields in field_master list
    for field in fieldMappings.fields:
        if field.name not in [  'OBJECTID',
                                'APN_TRPA',                 #0
                                'PPNO_TRPA',                #1
                                'JURISDICTION_TRPA',        #2
                                'COUNTY_TRPA',
                                # parcel address   
                                'HSE_NUMBR_TRPA',           #3
                                'STR_DIR_TRPA',             #4
                                'STR_NAME_TRPA',            #5
                                'STR_SUFFIX_TRPA',          #6
                                'UNIT_NUMBR_TRPA',          #7
                                'APO_ADDRESS_TRPA',         #8
                                'PSTL_TOWN_TRPA',           #9
                                'PSTL_STATE_TRPA',          #10
                                'PSTL_ZIP5_TRPA',           #11
                                # owner fields
                                'OWN_FIRST_TRPA',           #12
                                'OWN_LAST_TRPA',            #13
                                'OWN_FULL_TRPA',            #14
                                'MAIL_ADD1_TRPA',           #15
                                'MAIL_CITY_TRPA',           #16
                                'MAIL_STATE_TRPA',          #17
                                'MAIL_ZIP5_TRPA',           #18
                                # value fields  
                                'AS_LANDVALUE_TRPA',        #19
                                'AS_IMPROVALUE_TRPA',       #20
                                'AS_SUM_TRPA',              #21
                                'TAX_LANDVALUE_TRPA',       #22 
                                'TAX_IMPROVALUE_TRPA',      #23
                                'TAX_SUM_TRPA',             #24
                                'TAX_YEAR_TRPA',            #25
                                # land use fields 
                                'COUNTY_LANDUSE_CODE_TRPA', #26
                                'COUNTY_LANDUSE_TRPA',      #27
                                # Fields for building info
                                "YEAR_BUILT_TRPA",          #28
                                'UNITS_TRPA',               #29
                                'BEDROOMS_TRPA',            #30
                                'BATHROOMS_TRPA',           #31
                                'BUILDING_SQFT_TRPA',       #32
                                'VHR_TRPA',                 #33
                                'HOA_TRPA',                 #34
                                'SHAPE@']:
            # remove everything else
            fieldMappings.removeFieldMap(fieldMappings.findFieldMapIndex(field.name)) 
        
    # Use Merge tool to move features into single dataset
    arcpy.management.Merge([ccParcel, dgParcel, elParcel, plParcel, waParcel ], parcel_out, fieldMappings)
    print("Transformed Parcel Datasets Merged")
    logger.info("Transformed Parcel Datasets Merged")
    # out merge fc
    parcel_out = "Parcel_Staging"
    result = arcpy.GetCount_management(parcel_out)
    print('{} has {} records'.format(parcel_out, result[0]))
    logger.info(f'{parcel_out} has {result[0]} records')
    # out merge fc
    parcel_out = "Parcel_Staging"

    # delete unneccesary parcels
    parcelDelete = "ParcelDelete"

    # Run MakeFeatureLayer
    arcpy.management.MakeFeatureLayer(parcel_out, parcelDelete)
    
    arcpy.management.SelectLayerByAttribute(parcelDelete, 'NEW_SELECTION', 
                                            "APN_TRPA = '' Or APN_TRPA LIKE '920%' Or APN_TRPA LIKE '910%' OR APN_TRPA LIKE '%NP%' OR APN_TRPA LIKE '%ROW%' OR APN_TRPA LIKE '%UN%'")

    # Run GetCount and if some features have been selected, then 
    #  run DeleteFeatures to remove the selected features.
    deleteCount = arcpy.management.GetCount(parcelDelete)[0]
    if int(deleteCount) > 0:
        arcpy.management.DeleteFeatures(parcelDelete)
        print('{} records deleted'.format(deleteCount))
        logger.info(f'{deleteCount} records deleted')
    result = arcpy.GetCount_management(parcel_out)
    print('{} has {} records now.'.format(parcel_out, result[0]))
    logger.info(f'{parcel_out} has {result[0]} records now')
    #------------------------------------------------------
    # ADDITIONAL TRANSFORMATION
    #------------------------------------------------------


    suffix_dict = {
        'CI':'CIR',
        'BL':'BLVD',
        'TR':'TRL',
        'WY':'WAY',
        'E': '',
        'L':'',
        'AV':'AVE',
        'LP':'LOOP',
        'HY':'HWY',
        'PY':'PKWY',
        'PKY':'PKWY',
        'DRIVE': 'DR'
    }

    suffix_field = ['STR_SUFFIX_TRPA']

    UpdateFieldFromDictionary('Parcel_Staging', suffix_field, suffix_dict)

    replacement_values = ['UNIT','SUITE','SPACE','NULL']
    set_to_blank_values = ['0', '0 NULL']

    with arcpy.da.UpdateCursor('Parcel_Staging', ["STR_NAME_TRPA"]) as cursor:
        for row in cursor:
            if not row[0] is None:
                row[0]=row[0].upper()
            else:
                row[0] = ''      
            for replacement_value in replacement_values:
                row[0] = row[0].replace(replacement_value, '')
            row[0] = row[0].replace('  ', ' ')
            if row[0] in set_to_blank_values:
                row[0]=''
            if row[0].startswith('0 '):
                row[0]=row[0][2:]
            if (row[0] == '0 NO ADDRESS ON FILE')| (row[0] == 'NO ADDRESS ON FILE'):
                NewStreet='NO ADDRESS ON FILE'
                
            cursor.updateRow(row)

    #----------------------------------------------------------------------------------
    # TRPA ATTRIBUTION
    #----------------------------------------------------------------------------------
    print("Starting TRPA Attribution: " + strftime("%Y-%m-%d %H:%M:%S"))
    logger.info("Starting TRPA Attribution")
    # log.info("Starting TRPA Attribution: " + strftime("%Y-%m-%d %H:%M:%S"))

    # in and out with the same name overwrite == True
    ParcelStaging = "Parcel_Staging"
    ParcelPoint   = "Parcel_Point"
    ParcelNew     = 'Parcel_Staging_Attributed'

    # copy data into an in_memory feature class for warp speed.
    ParcelLayer = r"memory/ParcelLayer"
    arcpy.CopyFeatures_management(ParcelStaging, ParcelLayer)

    # Add TRPA fields.
    arcpy.management.AddFields(ParcelLayer,trpaFields)

    # ### County Atribute Update -------------------------------------------------------------------------------------###

    print("Starting the County attribute update: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the County attribute update: " + strftime("%Y-%m-%d %H:%M:%S"))

    with arcpy.da.UpdateCursor(ParcelLayer, ["JURISDICTION_TRPA", "COUNTY_TRPA"]) as cursor:
        for row in cursor:
            # set county field before changing EL to CSLT in Jurisdiction field
            row[1] = row[0] 
            cursor.updateRow(row)
    del cursor
    print("County Attribute Updated")

    #### Featurs to Points to use in speedy spatial joins
    # copy shapes to points in new parcel point layer
    arcpy.FeatureToPoint_management(ParcelLayer, ParcelPoint, "INSIDE")
    print("Copied features to points: "+ strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Copied features to points: "+ strftime("%Y-%m-%d %H:%M:%S"))

    ### Ownership Type Attribute Update ------------------------------------------------------------------------------###
    print("Starting the Ownership Type attribute update: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Ownership Type attribute update: " + strftime("%Y-%m-%d %H:%M:%S"))


    with arcpy.da.UpdateCursor(ParcelLayer, ["OWN_FULL_TRPA", "OWNERSHIP_TYPE_TRPA"]) as cursor:
        for row in cursor:
            # set ownership type
            own = row[0]
            if not (own is None or own == "" or own.isspace() == True):
                if own in fedOwnList:
                    row[1] = "Federal"
                elif own in localOwnList:
                    row[1] = "Local"
                elif own in stateOwnList:
                    row[1] = "State"
                elif not own in (fedOwnList, localOwnList, stateOwnList):
                    row[1] = "Private" 
                cursor.updateRow(row)
    del cursor
    print ("The 'OWNERSHIP_TYPE' field in the parcel data has been updated")
    # log.info("The 'Owernshipe Type' field in the parcel data has been updated")

    ### Existing Landuse Attribute Update ----------------------------------------------------------------------------###
    fields = ("COUNTY_LANDUSE_CODE_TRPA", "COUNTY_LANDUSE_TRPA", "EXISTING_LANDUSE_TRPA", "JURISDICTION_TRPA")

    # Define dictionaries for mapping land use codes
    washoe_landuse = {
        ('400', '410', '440', '500', '510', '520', '630', '640', '670', '720'): "Commercial",
        ('210', '250'): "Condominium",
        ('240',): "Condominium Common Area",
        ('220', '230', '300', '310', '320', '330', '340', '350', '360'): "Multi-Family Residential",
        ('600', '620'): "Open Space",
        ('700', '710', 'PBRD'): "Public Service",
        ('190',): "Recreation",
        ('200',): "Single Family Residential",
        ('420', '430'): "Tourist Accommodation",
        ('100', '110', '120', '130', '140', '150', '160', '170', '180'): "Vacant",}
    washoe_desc = {
        '710': "Intracounty public utility",
        '700': "Centrally assessed public utility",
        '510': "Commercial Industrial: retail or office with Indus",
        '500': "General industrial: light indust, trucking, warehs",
        '440': "Resort commercial: ski, golf, sports, etc.",
        '430': "Commercial hotel or motel",
        '420': "Casino or hotel casino",
        '410': "Offices, professional and business, banks, etc.",
        '400': "General Commercial: retail, mixed, parking, school",
        '340': "Ten or more units",
        '330': "Five to Nine Units",
        '320': "Three or four Units",
        '310': "Two Single Family Units",
        '300': "Duplex",
        '250': "Condo or Townhouse valued as apartment use",
        '240': "Common Area",
        '210': "Condominium or Townhouse",
        '200': "Single Family Residence",
        '190': "Public Parks: vacant or improved",
        '170': "Other, unbuildable: roads, restrictions, terrain",
        '160': "Splinter, unbuildable: small size or shape",
        '140': "Vacant, commercial",
        '130': "Vacant, multi-residential",
        '120': "Vacant, single family",
        '110': "Vacant, under development",
        '100': "Vacant, other or unknown" }
    carson_city_landuse = {
        ('400', '410', '420', '430', '440', '450', '460', '470'): "Commercial",
        ('210', '220', '230', '240', '250'): "Condominium",
        ('300', '310', '320', '330', '340', '350', '360', '370'): "Multi-Family Residential",
        ('600', '610', '620', '630', '640'): "Open Space",
        ('700', '710', '720', '730', '740'): "Public Service",
        ('800', '810', '820', '830'): "Recreation",
        ('200', '201', '202', '203', '204'): "Single Family Residential",
        ('500', '510', '520', '530'): "Industrial",
        ('100', '110', '120', '130', '140', '150', '160', '170', '180'): "Vacant",
    }
    carson_city_desc = {
        '700': "Government buildings and public service facilities",
        '720': "Educational institutions",
        '740': "Public safety and emergency services",
        '510': "Light industrial, warehouses",
        '500': "General industrial",
        '450': "Retail and mixed-use commercial",
        '440': "Hotels and motels",
        '420': "Casinos and entertainment venues",
        '410': "Office spaces and business centers",
        '400': "General commercial",
        '340': "Ten or more residential units",
        '330': "Five to nine residential units",
        '320': "Three or four residential units",
        '310': "Two single-family residences",
        '300': "Duplex",
        '250': "Condominium or townhouse",
        '210': "Single-family condominium",
        '200': "Single-family residence",
        '800': "Public parks and recreational spaces",
        '170': "Unbuildable land due to terrain restrictions",
        '160': "Splinter parcels, unbuildable",
        '140': "Vacant commercial land",
        '130': "Vacant multi-residential land",
        '120': "Vacant single-family land",
        '100': "Other or unknown vacant land"
    }
    douglas_landuse = {
        ('400', '402', '410', '411', '412', '440', '460', '470', '480', '500', '510', '560', '580', '582'): "Commercial",
        ('210', '211'): "Condominium",
        ('270',): "Condominium Common Area",
        ('300', '310', '320', '330', '350', '390'): "Multi-Family Residential",
        ('190',): "Open Space",
        ('700', '710', '711', '910', '980', '970'): "Public Service",
        ('450', '900', '970'): "Recreation",
        ('200', '220', '230', '236', '240', '280', '282'): "Single Family Residential",
        ('420', '430'): "Tourist Accommodation",
        ('100', '110', '117', '120', '130', '140'): "Vacant"}
    douglas_desc = {
        '980': 'Special Purpose with Minor Improvements', '970': 'Special Purpose Common Area', '910': 'Cemeteries',
        '900': 'Parks for Public Use', '711': 'Communication, Transportation, and Utility Property of a Local Nature Under Construction',
        '710': 'Communication, Transportation, and Utility Property of a Local Nature', '700': 'Operating Communication, Transportation, and Utility Property of an Interstate or Intercounty Nature',
        '582': 'Industrial with Minor Improvements - with structures insufficient to determine intended use',
        '580': 'Industrial with Minor Improvements', '560': 'Industrial Auxiliary Area', '510': 'Commercial Industrial - retail or office use combined with Industrial use',
        '500': 'General Industrial - light industry, trucking and warehousing, service, repair, etc.', '480': 'Commercial with Minor Improvements',
        '470': 'Commercial Common Area', '460': 'Commercial Auxiliary Area', '450': 'Golf Course', '440': 'Commercial Recreation',
        '430': 'Commercial Living Accommodations', '420': 'Casino or Hotel Casino', '410': 'Offices, Professional and Business Services',
        '402': 'Parking and/or Parking Structures', '400': 'General Commercial', '390': 'Mixed Use with Multi-Family Residential as primary use',
        '382': 'Multi-Family Residential with Minor Improvements - No livable structures', '380': 'Multi-Family Residential with Minor Improvements',
        '370': 'Multi-Family Residential Common Area', '360': 'Multi-Family Residential Auxiliary Area', '350': 'Manufactured Home Park - Ten or More Manufactured Home Units',
        '341': 'Five or More Units - High Rise Under Construction', '340': 'Five or More Units - High Rise', '333': 'Exempt or Partially Exempt Apartment Building',
        '331': 'Five or More Units - Low Rise Under Construction', '330': 'Five or More Units - Low Rise', '321': 'Three to Four Units Under Construction',
        '320': 'Three to Four Units', '313': 'Multi-Family Residence with Manufactured Home Conversion', '311': 'Two Single Family Units Under Construction',
        '310': 'Two Single Family Units', '301': 'Duplex Under Construction', '300': 'Duplex', '290': 'Mixed Use with Single Family Residential as primary use',
        '282': 'Single Family Residential with Minor Improvements - No livable structures', '280': 'Single Family Residential with Minor Improvements',
        '270': 'Single Family Residential Common Area', '260': 'Single Family Residential Auxiliary Area', '240': 'Individual Residential Unit - Townhouse or Row House',
        '236': 'Personal Property Manufactured Home Secured', '233': 'Secured Manufactured Home with Site Built Additions (Not Converted)',
        '232': 'Manufactured Home - Unsecured with Site Built Additions', '231': 'Manufacture Home Conversions Pending', '230': 'Personal Property Manufactured Home on the Unsecured Roll',
        '222': 'Manufactured Home (Converted) with Site Built Additions', '220': 'Manufactured Home Converted to Real Property', '211': 'Individual Unit in a Multiple Unit Building Under Construction',
        '210': 'Individual Unit in a Multiple Unit Building', '201': 'Single Family Residence Under Construction', '200': 'Single Family Residence',
        '190': 'Vacant - Public Use Lands', '150': 'Vacant - Industrial', '140': 'Vacant - Commercial', '130': 'Vacant - Multi-Residential',
        '120': 'Vacant - Single Family Residential', '117': 'Vacant - Roads/Easements', '110': 'Vacant - Splinter and Other Unbuildable',
        '108': 'Vacant - Patented Mining Claim, Not Mined', '100': 'Vacant - Unknown/Other'}
    eldo_landuse = {
        ('03', '29', '31', '32', '34', '36', '37', '38', '39', '41', '42', '43', '44', '45', '46', '47', '48', '65', '67', '68', '82', '91', '93'): "Commercial",
        ('14',): "Condominium",
        ('89',): "Condominium Common Area",
        ('01', '07', '12', '13', '16', '18', '19', '28', '35'): "Multi-Family Residential",
        ('25', '26', '50', '51', '52', '55', '56', '60', '70', '75', '79'): "Open Space",
        ('90', '92', '94', '96', '97', '98', '99'): "Public Service",
        ('61', '62', '63', '64'): "Recreation",
        ('06', '11', '15', '22', '23'): "Single Family Residential",
        ('33', '80', '81'): "Tourist Accommodation",
        ('00', '02', '05', '17', '21', '24', '30', '40'): "Vacant"}
    eldo_desc = {
        '98': 'DEV MSC FIRE SUPPRESSION FACILITIES',
        '96': 'DEV MSC CEMETERIES',
        '94': 'DEV MSC SCHOOLS - LARGE (101+ STUDENTS)',
        '93': 'DEV MSC SCHOOLS - MEDIUM (13-100 STUDENTS)',
        '92': 'DEV MSC SCHOOLS - SMALL (1-12 STUDENTS)',
        '90': 'UTL IND PUBLIC UTILITY (ON STATE ASSESSED ROLL)',
        '84': 'DEV MSC TEMPORARY USE CODE FOR PROJECT 184',
        '82': 'DEV COM PARKING LOT',
        '81': 'DEV MSC UNDERLYING INTEREST IN TIME SHARE PROJ',
        '79': 'RLU MSC ENV. SENSITIVE LAND - RESTRICTED USE',
        '68': 'DEV COM MARINAS',
        '65': 'DEV COM RESTAURANT',
        '64': 'DEV MSC SKI RESORTS',
        '63': 'DEV MSC CAMPGROUNDS',
        '62': 'DEV MSC COMMUNITY ORIENTED FACILITIES',
        '61': 'DEV MSC MISC. IMPROVED RECREATIONAL',
        '60': 'VAC MSC VACANT RECREATIONAL LAND',
        '50': 'TPZ MSC TIMBER PRESERVE ZONING - ACTIVE',
        '48': 'DEV IND OFFICES',
        '47': 'DEV IND HOSPITALS & CONVALESCENT HOSPITALS',
        '46': 'DEV IND MEDICAL/DENTAL/VET OFFICES',
        '45': 'DEV IND LIGHT MANUFACTURING',
        '43': 'DEV IND WAREHOUSES',
        '42': 'DEV IND MINI-WAREHOUSES (MINI-STORAGE)',
        '41': 'DEV IND MISC. IMPROVED INDUSTRIAL PROPERTY',
        '40': 'VAC IND VACANT INDUSTRIAL LAND',
        '39': 'DEV COM SUPERMARKETS',
        '38': 'DEV COM RETAIL STORES >15,000 SQ. FT.',
        '37': 'DEV COM RETAIL STORES 5,001-15,000 SQ. FT.',
        '36': 'DEV COM RETAIL STORES <=5,000 SQ. FT.',
        '35': 'DEV COM MOBILE HOME PARKS',
        '34': 'DEV COM SERVICE STATION',
        '33': 'DEV COM MOTEL, HOTEL',
        '31': 'DEV COM MISC. IMPROVED COMMERCIAL',
        '30': 'VAC COM VACANT COMMERCIAL LAND',
        '29': 'DEV MSC RURAL NON-RES. IMPROVEMENT 2.51-20.0 AC.',
        '26': 'AGP MSC RURAL RESTRICTIVE ZONING - NON-RENEWAL',
        '25': 'AGP MSC RURAL RESTRICTIVE ZONING - CLCA (ACTIVE)',
        '24': 'VAC RES RURAL RES. LAND 20+ MINOR NON-RES IMPR',
        '23': 'DEV RES RURAL RES. 20+ AC. 1 RES. UNIT',
        '22': 'DEV RES RURAL RES. 2.51-20.0 AC. 1 SF UNIT',
        '21': 'VAC RES VAC RURAL RES LAND 2.51-20.0 AC. 1 UNIT',
        '17': 'VAC MSC SUBJ. TO OPEN SPACE CONTRACT (NOT CLCA)',
        '16': 'DEV RES MOBILE HOME ON RENTED LAND',
        '15': 'DEV RES RESIDENCE ON LEASED LAND',
        '14': 'DEV MFR CONDOMINIUMS & TOWNHOUSES',
        '13': 'DEV MFR MULTI-RESIDENTIAL 4+ UNITS',
        '12': 'DEV MFR MULTI-RESIDENTIAL 2-3 UNITS',
        '11': 'DEV RES SINGLE FAM. RES. <=2.5 AC.(INC. MAN. HMS',
        '07': 'DEV MFR RETIREMENT HOUSING',
        '05': 'VAC MFR VACANT MULTI-RES. LAND 4+ UNITS ALLOWED',
        '03': 'DEV COM PLACE OF WORSHIP',
        '02': 'VAC RES NON-RES. IMPROVEMENTS <=2.5 AC.',
        '00': 'VAC RES VACANT RES. LAND <=2.5 AC. 1-3 UNITS'}
    placer_landuse = {
        ('07', '11', '12', '13', '14', '15', '17', '19', '21', '22', '23', '24', '25', '26', '27', '29', '31', '32', '36', '37', '38', '39', '62', '63', '71', '88'): "Commercial",
        '04': "Condominium",
        '89': "Condominium Common Area",
        ('02', '03', '05', '09', '28'): "Multi-Family Residential",
        ('56', '55', '60', '61', '87', '90'): "Open Space",
        ('72', '76', '77', '81'): "Public Service",
        ('65', '66', '67', '68', '69'): "Recreation",
        ('01', '08', '16'): "Single Family Residential",
        ('06', '18', '64'): "Tourist Accommodation",
        ('00', '10', '20', '30'): "Vacant"}
    placer_desc = {'90': 'GREENBELT',
        '89': 'COMMON AREA',
        '88': 'HIGHWAYS, ROADS, STREETS',
        '87': 'RIVERS, LAKES, RESERVOIR, CANAL',
        '81': 'UTILITIES, PUBLIC & PRIVATE',
        '77': 'CEMETERIES',
        '76': 'MISC. PUBLIC BUILDINGS',
        '72': 'SCHOOLS',
        '71': 'CHURCHES',
        '69': 'MISCELLANEOUS RECREATIONAL',
        '68': 'CAMPS & PARKS, GENERAL',
        '67': 'SKI FACILITY',
        '66': 'GOLF COURSE',
        '65': 'TENNIS, SWIMMING CLUBS',
        '64': 'LODGES, HALLS',
        '63': 'MARINA, PIER',
        '62': 'THEATER, BOWLING ALLEY',
        '61': 'NON-PROFIT CAMPS/PARKS',
        '60': 'CONSERVATION EASEMENT RESTRICTIONS',
        '56': 'TIMBERLAND, ZONED TPZ',
        '55': 'TIMBERLAND, UNRESTRICTED',
        '39': 'MISCELLANEOUS INDUSTRIAL',
        '38': 'WAREHOUSE',
        '37': 'MINI-STORAGE, COVERED STORAGE',
        '36': 'UNCOVERED STORAGE, WRECKING YARD',
        '32': 'HEAVY INDUSTRIAL',
        '31': 'LIGHT INDUSTRIAL',
        '30': 'VACANT INDUSTRIAL',
        '29': "MISCELLANEOUS COMM'L",
        '28': 'MOBILE HOME PARK',
        '27': 'PARKING LOTS',
        '26': 'AUTO SALES, REPAIR',
        '25': 'SERVICE STATION',
        '24': 'MINI-MARKET WITH GAS',
        '23': "BANKS, S&L'S, CREDIT UNION",
        '22': 'FAST FOOD RESTAURANT',
        '21': 'RESTAURANTS, COCKTAIL LOUNGES',
        '20': 'VACANT, COMMERCIAL',
        '19': 'OFFICE MEDICAL/DENTAL',
        '18': 'HOTELS, MOTELS, RESORTS',
        '17': 'OFFICE GENERAL',
        '16': 'RESIDENCE ON COMMERCIAL LAND',
        '15': 'SHOPPING CENTER',
        '14': 'OFFICE CONDO',
        '13': 'MINI-MARKETS, NO GAS',
        '12': 'SUBURBAN STORE',
        '11': 'COMMERCIAL STORE',
        '10': 'VACANT, SUBDIVIDED RESIDENTIAL',
        '09': 'MOBILE HOME IN M H PARK',
        '08': 'MOBILE HOME OUTSIDE OF PARK',
        '07': 'RESIDENTIAL, AUXILIARY IMP',
        '06': 'TIMESHARES',
        '05': 'APARTMENTS, 4 UNITS OR MORE',
        '04': 'SINGLE FAM RES, CONDO',
        '03': '3 SINGLE FAM RES, TRIPLEX',
        '02': '2 SINGLE FAM RES, DUPLEX',
        '01': 'SINGLE FAM RES, HALF PLEX',
        '00': 'VACANT, ALL TYPES-NOT ASGND'}

    with arcpy.da.UpdateCursor(ParcelLayer, fields) as cursor:
        for row in cursor:
            ctyluc = str(row[0]).strip() if row[0] else None
            cty = row[3]
            
            if ctyluc and cty == 'CC':  # Carson City
                # Set EXISTING_LANDUSE_TRPA
                for codes, landuse in carson_city_landuse.items():
                    if ctyluc in codes:
                        row[2] = landuse
                # Set COUNTY_LANDUSE_TRPA
                row[1] = carson_city_desc.get(ctyluc, '')
            elif ctyluc and cty == 'WA':  # Washoe County
                # Set EXISTING_LANDUSE_TRPA
                for codes, landuse in washoe_landuse.items():
                    if ctyluc in codes:
                        row[2] = landuse
                # Set COUNTY_LANDUSE_TRPA
                row[1] = washoe_desc.get(ctyluc, '')
            elif ctyluc and cty == 'DG':  # Douglas County
                # Set EXISTING_LANDUSE_TRPA
                for codes, landuse in douglas_landuse.items():
                    if ctyluc in codes:
                        row[2] = landuse
                # Set COUNTY_LANDUSE_TRPA
                row[1] = douglas_desc.get(ctyluc, '')
            elif ctyluc and cty == 'PL':  # Placer County
                # Set EXISTING_LANDUSE_TRPA
                for codes, landuse in placer_landuse.items():
                    if ctyluc in codes:
                        row[2] = landuse
                # Set COUNTY_LANDUSE_TRPA
                row[1] = placer_desc.get(ctyluc, '')
            elif ctyluc and cty == 'EL':  # El Dorado County
                # Set EXISTING_LANDUSE_TRPA
                for codes, landuse in eldo_landuse.items():
                    if ctyluc in codes:
                        row[2] = landuse
                # Set COUNTY_LANDUSE_TRPA
                row[1] = eldo_desc.get(ctyluc, '')
            cursor.updateRow(row)

    # delete cursor
    del cursor
    print ("The 'EXISTING_LANDUSE' field in the parcel data has been updated")
    # log.info("The 'EXISTING_LANDUSE' field in the parcel data has been updated")
    result = arcpy.GetCount_management(ParcelLayer)
    print('{} has {} records now.'.format(ParcelLayer, result[0]))

    ### Regional Landuse Update --------------------------------------------------------------------------------------###
    print("Starting the Regional Land Use Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Regional Land Use Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_RegionalLandUse, ParcelPoint_RegionalLandUse, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Regional Land Use Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Regional Land Use Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
        # Create an expression to find records with null values in either field
    print('Checking For Nulls')

    #expression = "{'APN_TRPA'} IS NULL OR {'COUNTY_TRPA'} IS NULL"
    expression = "'APN_TRPA' IS NULL OR 'COUNTY_TRPA' IS NULL"
    # Use an UpdateCursor to delete records with null values
    # Failing Create cursor has failed
    with arcpy.da.UpdateCursor(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'], where_clause=expression) as cursor:
        for row in cursor:
            cursor.deleteRow()
            print("One row dropped from tHE PARCEL LAYER")

    with arcpy.da.UpdateCursor(ParcelPoint_RegionalLandUse, ['APN_TRPA', 'COUNTY_TRPA'], where_clause=expression) as cursor:
        for row in cursor:
            cursor.deleteRow()
            print("One row dropped from regional Land Use")
    

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['REGIONAL_LANDUSE_TRPA'], 
                ParcelPoint_RegionalLandUse, ['APN_TRPA', 'COUNTY_TRPA'],['Description'])
    print ("The 'REGIONAL_LANDUSE' field in the parcel data has been updated")
    # log.info("The 'REGIONAL_LANDUSE' field in the parcel data has been updated")

    ## Estimated Coverage Allowed Attirbute Update ------------------------------------------------------------------###
    print("Starting the Estimated Coverage Allowed Identity Overlay: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Estimated Coverage Allowed Identity Overlay: " + strftime("%Y-%m-%d %H:%M:%S"))

    # create out table for the stats sum
    outTable =  memory + "id_Parcel_Bailey_Table"

    # Create Identity Output Layer
    id_ParcelLyr_BaileyLyr = memory + "id_Parcel_Bailey"

    # Create Impervious Layer
    Bailey_lyr = memory + "Bailey_lyr"

    # Create Identity Layer
    identity_layer = memory + "bailey_identity_layer"

    # Make a layer from the feature class Impervious that only passes Ftype = 'building' and 'other'
    arcpy.MakeFeatureLayer_management(sde_Bailey, Bailey_lyr)
    print ("Created feature layer of Bailey Soils")

    # Process: Use the Identity function
    print ("Starting Identity: "+ strftime("%Y-%m-%d %H:%M:%S"))
    arcpy.Identity_analysis (ParcelLayer, Bailey_lyr, id_ParcelLyr_BaileyLyr)
    print ("Finished Identity: "+ strftime("%Y-%m-%d %H:%M:%S"))

    # Add SqFt field
    arcpy.management.AddField(id_ParcelLyr_BaileyLyr, "SqFt", "DOUBLE", "", "", "", 
                            "Square Feet", "NULLABLE", "NON_REQUIRED", "")

    # Make a layer from the feature class Impervious that only passes Ftype = 'building' and 'other'
    arcpy.MakeFeatureLayer_management(id_ParcelLyr_BaileyLyr, identity_layer, 
                                    where_clause = "NOT CAPABILITY in ('WB', '-1', '0')")

    # calculate geometry of output identity
    arcpy.CalculateField_management(identity_layer, "SqFt", "!shape.area@SQUAREFEET!", "PYTHON3", "")

    # multiply square footage by bailey coefficents
    with arcpy.da.UpdateCursor(identity_layer, ['CAPABILITY', 'SqFt', 'PERCENT_COVERAGE_ALLOWED']) as cur:
        for row in cur:
            if row[0] != ('','WB'):
                row[1] = row[1]*row[2]
            else:
                row[1] == 0
            cur.updateRow(row)
    del cur    
    # Sum the square footage
    arcpy.Statistics_analysis(identity_layer, outTable, [["SqFt", "SUM"]], ["APN_TRPA","COUNTY_TRPA"])

    print("Finsished the Estimated Coverage Allowed Identity Overlay: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finsished the Estimated Coverage Allowed Identity Overlay: " + strftime("%Y-%m-%d %H:%M:%S"))

    ## Join parcel sums back to parcel layer and calculate field

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['ESTIMATED_COVERAGE_ALLOWED_TRPA'], 
                outTable, ['APN_TRPA', 'COUNTY_TRPA'],['SUM_SqFt'])
    print ("The 'ESTIMATED_COVERAGE_ALLOWED' field in the parcel data has been updated")

    ### Impervious Surface Attrigute Update --------------------------------------------------------------------------###
    # create out table for the stats sum
    outTable =  memory +"id_Parcel_Imp_Table"

    # Create Identity Output Layer
    id_ParcelLyr_ImperviousLyr = memory + "id_Parcel_Impervious"

    # Create Impervious Layer
    Impervious_lyr = memory + "Impervious_lyr"

    # Create Identity Layer
    identity_layer = memory + "identity_layer"
        
    # Make a layer from the feature class Impervious that only passes Ftype = 'building' and 'other'
    arcpy.MakeFeatureLayer_management(sde_Impervious, Impervious_lyr)

    # Process: Use the Identity function
    print ("Starting Identity of Imperviuos Surface by parcel: "+ strftime("%Y-%m-%d %H:%M:%S"))
    arcpy.Identity_analysis (ParcelLayer, Impervious_lyr, id_ParcelLyr_ImperviousLyr)
    print ("Finished Identity of Imperviuos Surface by parcel:: "+ strftime("%Y-%m-%d %H:%M:%S"))

    # Add SqFt field
    arcpy.management.AddField(id_ParcelLyr_ImperviousLyr, 
                            "SqFt", "DOUBLE", "", "", "", "Square Feet", "NULLABLE", "NON_REQUIRED", "")

    # Make a layer from the feature class Impervious that only passes Ftype = 'building' and 'other'
    arcpy.MakeFeatureLayer_management(id_ParcelLyr_ImperviousLyr, identity_layer, 
                                    where_clause = "Feature IN ('Building', 'Road', 'Other', 'Driveway')")

    # calculate geometry of output identity
    arcpy.CalculateField_management(identity_layer, "SqFt", "!shape.area@SQUAREFEET!", "PYTHON3", "")
                                                            
    # Sum the square footage of buildings and other by APN
    arcpy.Statistics_analysis(identity_layer, outTable, [["SqFt", "SUM"]], ["APN_TRPA","COUNTY_TRPA"])

    # Join parcel sums back to parcel layer and calculate field "Impervious Surface Sq Ft"
    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['IMPERVIOUS_SURFACE_SQFT_TRPA'], 
                outTable, ['APN_TRPA', 'COUNTY_TRPA'],['SUM_SqFt'])
    print ("The 'ImperviousCoverage_SqFt' field in the parcel data has been updated")

    ### Fire District Attribute Update -------------------------------------------------------------------------------###
    print("Starting the Fire District Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Fire District Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Process Fire District Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_FireDistrict, ParcelPoint_FireDistrict, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Fire District Spatial Join: "  + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Fire District Spatial Join: "  + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['FIREPD_TRPA'], 
                ParcelPoint_FireDistrict, ['APN_TRPA', 'COUNTY_TRPA'],['DISTRICT'])
    print ("The 'FIRE_PD' field has been updated")
    # log.info("The 'FIRE_PD' field has been updated")

    ### Soil 1974 Attribute Update ------------------------------------------------------------------------------------### 
    print("Starting the SOIL_1974 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the SOIL_1974 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_NRCSSoils1974, ParcelPoint_Soils74, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the SOIL_1974 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the SOIL_1974 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['SOIL_1974_TRPA'], 
                ParcelPoint_Soils74, ['APN_TRPA', 'COUNTY_TRPA'],['MUSYM_74'])
    print ("The 'SOIL_1974' field in the parcel data has been updated")
    # log.info("The 'SOIL_1974' field in the parcel data has been updated")

    ### Soil 2003 Attribute Update -----------------------------------------------------------------------------------###
    print("Starting the SOIL_2003 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the SOIL_2003 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_NRCSSoils2003, ParcelPoint_Soils03, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the SOIL_2003 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the SOIL_2003 Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['SOIL_2003_TRPA'], 
                ParcelPoint_Soils03, ['APN_TRPA', 'COUNTY_TRPA'],['MUSYM_03'])
    print ("The 'SOIL_2003' field in the parcel data has been updated.")
    # log.info("The 'SOIL_2003' field in the parcel data has been updated: "  + strftime("%Y-%m-%d %H:%M:%S"))

    ### HRA Attribute Upate -------------------------------------------------------------------------------------###
    print("Starting the Hydrologic Area Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Hydrologic Area Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_HydroArea, ParcelPoint_HydroArea, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Hydrologic Area Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Hydrologic Area Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['HRA_NAME_TRPA'], 
                ParcelPoint_HydroArea, ['APN_TRPA', 'COUNTY_TRPA'],['HRA_NAME'])
    print ("The 'HRA_NAME' field in the parcel data has been updated")
    # log.info("The 'HRA_NAME' field in the parcel data has been updated")

    ### Watshed Attribute Update -------------------------------------------------------------------------------###
    print("Starting the Watershed Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Watershed Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Watershed, ParcelPoint_Watershed, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Watershed Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Watershed Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['WATERSHED_NUMBER_TRPA'], 
                ParcelPoint_Watershed, ['APN_TRPA', 'COUNTY_TRPA'],['NUMBER'])
    # replace null with 0
    with arcpy.da.UpdateCursor(ParcelLayer, ['WATERSHED_NUMBER_TRPA']) as cursor:
        for row in cursor:
            if row[0] is None:
                # If the value is null, replace it with 0
                row[0] = 0
                cursor.updateRow(row)
    del cursor   
    print ("The 'WATERSHED_NUMBER' field in the parcel data has been updated")
    # log.info("The 'WATERSHED_NUMBER' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['WATERSHED_NAME_TRPA'], 
                ParcelPoint_Watershed, ['APN_TRPA', 'COUNTY_TRPA'],['NAME'])
    print ("The 'WATERSHED_NAME' field in the parcel data has been updated")
    # log.info("The 'WATERSHED_NAME' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PRIORITY_WATERSHED_TRPA'], 
                ParcelPoint_Watershed, ['APN_TRPA', 'COUNTY_TRPA'],['PRIORITY'])
    # replace null with 0
    with arcpy.da.UpdateCursor(ParcelLayer, ['PRIORITY_WATERSHED_TRPA']) as cursor:
        for row in cursor:
            if row[0] is None:
                # If the value is null, replace it with 0
                row[0] = 0
                cursor.updateRow(row)
    del cursor
    print ("The 'PRIORITY_WATERSHED' field in the parcel data has been updated")
    # log.info("The 'PRIORITY_WATERSHED' field in the parcel data has been updated")

    ### Local Plan Attribute Update -----------------------------------------------------------------------------###
    print("Starting the Local Plan Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Local Plan Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_LocalPlan, ParcelPoint_LocalPlan, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Local Plan Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Local Plan Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_ID_TRPA'], 
                ParcelPoint_LocalPlan, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_ID'])
    print ("The 'PLAN_ID' field in the parcel data has been updated")
    # log.info("The 'PLAN_ID' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_NAME_TRPA'], 
                ParcelPoint_LocalPlan, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_NAME'])
    print ("The 'PLAN_NAME' field in the parcel data has been updated")
    # log.info("The 'PLAN_NAME' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_TYPE_TRPA'], 
                ParcelPoint_LocalPlan, ['APN_TRPA', 'COUNTY_TRPA'],['PLAN_TYPE'])
    print ("The 'PLAN_TYPE' field in the parcel data has been updated")
    # log.info("The 'PLAN_NAME' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['LOCAL_PLAN_HYPERLINK_TRPA'], 
                ParcelPoint_LocalPlan, ['APN_TRPA', 'COUNTY_TRPA'],['File_URL'])
    print ("The 'LOCAL_PLAN_HYPERLINK' field in the parcel data has been updated")
    # log.info("The 'LOCAL_PLAN_HYPERLINK' field in the parcel data has been updated")

    ### Town Center Attribute Update --------------------------------------------------------------------------------### 
    print("Starting the Town Center Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Town Center Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_TownCenter, ParcelPoint_TownCenter, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")

    print("Finished the Town Center Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Town Center Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['TOWN_CENTER_TRPA'], 
                ParcelPoint_TownCenter, ['APN_TRPA', 'COUNTY_TRPA'],['NAME'])
    print("The 'TOWN_CENTER' field in the parcel data has been updated")
    # log.info("The 'TOWN_CENTER' field in the parcel data has been updated")

    ### Town Center Buffer Attribute Update --------------------------------------------------------------------------###
    print("Starting the Town Center Buffer Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Town Center Buffer Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_TownCenterBuffer, ParcelPoint_TownCenterBuffer, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Town Center Buffer Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Town Center Buffer Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['LOCATION_TO_TOWNCENTER_TRPA'], 
                ParcelPoint_TownCenterBuffer, ['APN_TRPA', 'COUNTY_TRPA'],['BUFFER_NAME'])
    print ("The 'LOCATION_TO_TOWNCENTER' field in the parcel data has been updated")
    # log.info("The 'LOCATION_TO_TOWNCENTER' field in the parcel data has been updated")
    
    ### Catchment Attribute Update ------------------------------------------------------------------------------------### 
    print("Starting the Catchment Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Catchment Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Catchment, ParcelPoint_Catchment, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print("Finished the Catchment Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Catchment Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['CATCHMENT_TRPA'], 
                ParcelPoint_Catchment, ['APN_TRPA', 'COUNTY_TRPA'],['Name'])
    print ("The 'Catchment' field in the parcel data has been updated")
    # log.info("The 'Catchment' field in the parcel data has been updated")

    ### Tolerance ID -------------------------------------------------------------------------------------------------###
    print("Starting the Tolerance District Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Tolerance, ParcelPoint_Tolerance, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "INTERSECT", "", "")
    print ("Finished the Tolerance District Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['TOLERANCE_ID_TRPA'], 
                ParcelPoint_Tolerance, ['APN_TRPA', 'COUNTY_TRPA'],['DISTRICT'])
    print ("The Tolerance ID field in the parcel data has been updated")

    ### Index 1987 Attribute Update ----------------------------------------------------------------------------------###
    print("Starting the 1987 Index Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the 1987 Index Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Index1987, ParcelPoint_Index1987, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the 1987 Index Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the 1987 Index Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['INDEX_1987_TRPA'], 
                ParcelPoint_Index1987, ['APN_TRPA', 'COUNTY_TRPA'],['MAP_NUMBER'])
    print("The 'INDEX_1987' field in the parcel data has been updated")
    # log.info("The 'INDEX_1987' field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['INDEX_1987_HYPERLINK_TRPA'], 
                ParcelPoint_Index1987, ['APN_TRPA', 'COUNTY_TRPA'],['URL'])
    print ("The 'INDEX_1987_HYPERLINK' field in the parcel data has been updated")
    # log.info("The 'INDEX_1987_HYPERLINK' field in the parcel data has been updated")

    ### Postal Town Field --------------------------------------------------------------------------------------------### 
    print("Starting the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Spatial Join
    #arcpy.SpatialJoin_analysis(ParcelPoint, sde_Zip, ParcelPoint_PstlTown, 
    #                        "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    #print ("Finished the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_UrbanArea, ParcelPoint_PstlTown, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    
    # log.info("Finished the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    #fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PSTL_TOWN_TRPA'], 
    #            ParcelPoint_PstlTown, ['APN_TRPA', 'COUNTY_TRPA'],['PO_NAME'])
    #print ("The 'PSTL_TOWN' field in the parcel data has been updated")
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PSTL_TOWN_TRPA'], 
                ParcelPoint_PstlTown, ['APN_TRPA', 'COUNTY_TRPA'],['NAME'])
    #print ("The 'PSTL_TOWN' field in the parcel data has been updated")
    # log.info("The 'PSTL_TOWN' field in the parcel data has been updated")

    ### Postal ZIP ---------------------------------------------------------------------------------------------------###

    # transfer attributes to Parcel Layer
    #fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PSTL_ZIP5_TRPA'], 
    #            ParcelPoint_PstlTown, ['APN_TRPA', 'COUNTY_TRPA'],['ZIP_CODE'])
    #print("The 'PSTL_ZIP5' field in the parcel data has been updated")
    # log.info("The 'PSTL_ZIP5' field in the parcel data has been updated")

    ### CSLT Jurisdiction Update -------------------------------------------------------------------------------------###
    print("Starting to select parcels within City of South Lake Tahoe: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting to select parcels within City of South Lake Tahoe: " + strftime("%Y-%m-%d %H:%M:%S"))

    # select by location
    csltParcels = arcpy.SelectLayerByLocation_management(ParcelLayer, "HAVE_THEIR_CENTER_IN", sde_CSLT, 0,   
                                                        "NEW_SELECTION")
    # update jurisdcition field
    with arcpy.da.UpdateCursor(csltParcels, ["JURISDICTION_TRPA"]) as cursor:
        for row in cursor:
            row[0] = "CSLT"
            # update all rows
            cursor.updateRow(row)
    del cursor 
    print("Finished updating parcels within City of South Lake Tahoe: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished updating parcels within City of South Lake Tahoe:  " + strftime("%Y-%m-%d %H:%M:%S"))
    print("JURISDCITION field update with 'CSLT' values ")
    # log.info("JURISDCITION field update with 'CSLT' values ")

    ### Zoning Attribute Update --------------------------------------------------------------------------------------###
    # Spatial Join
    print("Starting the Zoning Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the Zoning Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Zoning, ParcelPoint_Zoning, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print("Finished the Zoning Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Zoning Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['ZONING_ID_TRPA'], 
                ParcelPoint_Zoning, ['APN_TRPA', 'COUNTY_TRPA'],['ZONING_ID'])
    print("The Zoning ID field in the parcel data has been updated")
    # log.info("The Zoning ID field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['ZONING_DESCRIPTION_TRPA'], 
                ParcelPoint_Zoning, ['APN_TRPA', 'COUNTY_TRPA'],['ZONING_DESCRIPTION'])
    print("The Zoning Description field in the parcel data has been updated")
    # log.info("The Zoning Description field in the parcel data has been updated")

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],["DESIGN_GUIDELINES_HYPERLINK_TRPA"], 
                ParcelPoint_Zoning, ['APN_TRPA', 'COUNTY_TRPA'],["DESIGN_GUIDELINES_HYPERLINK"])
    print("The DESIGN_GUIDELINES_HYPERLINK field in the parcel data has been updated")
    # log.info("The DESIGN_GUIDELINES_HYPERLINK_TRPA field in the parcel data has been updated")

    ### TAZ Attirbute Update --------------------------------------------------------------------------------------###
    # Spatial Join
    print("Starting the TAZ Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Starting the TAZ Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_TAZ, ParcelPoint_TAZ, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print("Finished the TAZ Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the TAZ Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['TAZ_TRPA'], 
                ParcelPoint_TAZ, ['APN_TRPA', 'COUNTY_TRPA'],["TAZ"])
    print("The TAZ field in the parcel data has been updated")

    ### LTinfo Parcel Details Hyperlink Attribute Update -------------------------------------------------------------###
    print("Creating LTinfo Hyperlinks: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Creating LTinfo Hyperlinks: " + strftime("%Y-%m-%d %H:%M:%S"))

    # create ltinfo hyper link
    with arcpy.da.UpdateCursor(ParcelLayer, ["APN_TRPA","LTINFO_HYPERLINK_TRPA"]) as cursor:
        for row in cursor:
            if not (row[0] == None):
                row[1] = 'https://parcels.laketahoeinfo.org/Parcel/Detail/'+ row[0]
            else:
                row[1] = ''
            cursor.updateRow(row)
    del cursor
    print("The LTINFO_HYPERLINK field in the parcel data has been updated")

    ### set within TRPA boundary -------------------------------------------------------------------------------------###
    print("Identifying parcels within TRPA Boundary: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info('Identifying parcels within TRPA Boundary: ' + strftime("%Y-%m-%d %H:%M:%S"))

    # Select all new parcels that have their center within
    parcelSelect = arcpy.SelectLayerByLocation_management(ParcelLayer, 
                                                            'INTERSECT', 
                                                            sde_TRPAboundary, 
                                                            0, 
                                                            'NEW_SELECTION')

    # Update field 1= yes 0 = no
    with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_TRPA_BNDY_TRPA']) as cursor:
        for row in cursor:
            row[0] = '1'
            cursor.updateRow(row) 
    del cursor        
    # switch the selection
    parcelSelect = arcpy.SelectLayerByAttribute_management(parcelSelect,'SWITCH_SELECTION')

    # update other parcels
    with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_TRPA_BNDY_TRPA']) as cursor:
        for row in cursor:
            row[0] = '0'
            cursor.updateRow(row)
    del cursor
    print("Within TRPA Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Within TRPA Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))

    ### set within Bonus Unit Boundary -------------------------------------------------------------------------------###
    print("Identifying parcels within bonus unit boundary: "  + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Identifying parcels within bonus unit boundary: " + strftime("%Y-%m-%d %H:%M:%S"))

    # Select all new parcels that have their center within
    parcelSelect = arcpy.SelectLayerByLocation_management(ParcelLayer, 
                                                            'HAVE_THEIR_CENTER_IN', 
                                                            sde_BonusUnitboundary, 
                                                            0, 
                                                            'NEW_SELECTION')

    with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_BONUSUNIT_BNDY_TRPA']) as cursor:
        for row in cursor:
            row[0] = '1'
            cursor.updateRow(row) 
    del cursor   
    # switch the selection
    parcelSelect = arcpy.SelectLayerByAttribute_management(parcelSelect,'SWITCH_SELECTION')

    with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_BONUSUNIT_BNDY_TRPA']) as cursor:
        for row in cursor:
            row[0] = '0'
            cursor.updateRow(row)
    del cursor     
    print("Bonus Unit Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Bonus Unit Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))
    result = arcpy.GetCount_management(ParcelLayer)
    print('{} has {} records now.'.format(ParcelLayer, result[0]))

    ### Calculate Area Field------------------------------------------------------------------------------------------###
    print("Calculating Acres..." + strftime("%Y-%m-%d %H:%M:%S"))
    with arcpy.da.UpdateCursor(ParcelLayer, ['PARCEL_ACRES_TRPA', 'SHAPE@']) as cursor:
        for row in cursor:
            row[0] = row[1].getArea('PLANAR', 'ACRES')
            cursor.updateRow(row)
    del cursor

    # calculate square feet
    print("Calculating Square Feet..." + strftime("%Y-%m-%d %H:%M:%S"))
    with arcpy.da.UpdateCursor(ParcelLayer, ['PARCEL_SQFT_TRPA', 'SHAPE@']) as cursor:
        for row in cursor:
            row[0] = row[1].getArea('PLANAR', 'SquareFeetUS')
            cursor.updateRow(row)
    del cursor
    ### Set Status to Active--------------------------------------------------------------------------------------------------------###
    with arcpy.da.UpdateCursor(ParcelLayer, ['STATUS_TRPA']) as cursor:
        for row in cursor:
            row[0] = 'A'
            cursor.updateRow(row) 
    del cursor
    print("The 'STATUS_TRPA' field in the parcel data has been updated")
    
    ### Estimated Percent Coverage Allowed Update---------------------------------------------------------------------###
    with arcpy.da.UpdateCursor(ParcelLayer, ['ESTIMATED_PRCNT_COV_ALLOWED_TRPA', "ESTIMATED_COVERAGE_ALLOWED_TRPA", "PARCEL_SQFT_TRPA"]) as cursor:
        for row in cursor:
            if not row[1] is None:
                row[0] = (row[1] / row[2]) * 100
            else:
                row[0] = None
            cursor.updateRow(row) 
    del cursor  
    print("The 'ESTIMATED_PRCNT_COV_ALLOWED_TRPA' field in the parcel data has been updated")

    ### IPES Score Update --------------------------------------------------------------------------------------------###
    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'JURISDICTION_TRPA'],['IPES_TRPA'], 
                ipes_layer, ['APN', 'JURISDICTION'],['IPESScore'])
    print("The 'IPES_TRPA' field in the parcel data has been updated")

    ### Set Status to Active--------------------------------------------------------------------------------------------------------###
    with arcpy.da.UpdateCursor(ParcelLayer, ['STATUS_TRPA']) as cursor:
        for row in cursor:
            row[0] = 'A'
            cursor.updateRow(row) 
    del cursor
    print("The 'STATUS_TRPA' field in the parcel data has been updated")
    
    ### Copy to Feature Class ----------------------------------------------------------------------------------------###
    # copy in-memory features to staging feature class
    arcpy.CopyFeatures_management(ParcelLayer, ParcelNew)
    print("Copied in-memory features, parcel staging new is set: " + strftime("%Y-%m-%d %H:%M:%S"))

    arcpy.Delete_management("memory")
    print("Deleted Memory Workspace: " + strftime("%Y-%m-%d %H:%M:%S"))

    #---------------------------------
    # REPLACE NULL
    #---------------------------------
    # replace null with ''
    replace_null_values_with_blank(ParcelNew)
    result = arcpy.GetCount_management(ParcelNew)
    print('{} has {} records.'.format(ParcelNew, result[0]))
    logger.info(f'{ParcelNew} has {result[0]} now')
    #---------------------------------
    # GET COUNT
    #---------------------------------
    result = arcpy.GetCount_management("Parcel_Staging")
    print('{} has {} records'.format("Parcel_Staging", result[0]))
    result = arcpy.GetCount_management("Parcel_Staging_Attributed")
    print('{} has {} records'.format("Parcel_Staging_Attributed", result[0]))

    #----------------------------------
    # ATTRIBUTED TO STAGING FC
    #----------------------------------
    staging_fc     = "Parcel_Staging_Attributed"
    new_fc         = "Parcel_County_Staging" 

    # Create FieldMappings object to manage merge output fields
    fieldMappings = arcpy.FieldMappings()
    # # Add all fields from all parcel staging layers
    # fieldMappings.addTable(fc)

    for field in arcpy.ListFields(staging_fc):
        if not field.name == "OBJECTID" and not field.name == "Shape":
            old_name = field.name

            #Rename if necessary
            if old_name.endswith("_TRPA"):
                new_name = old_name[:-5]
            else:
                new_name = old_name

            #Create new FieldMap object    
            new_f = arcpy.FieldMap()
            new_f.addInputField(staging_fc, old_name) # Specify the input field to use

            #Rename output field
            new_f_name = new_f.outputField
            new_f_name.name = new_name
            new_f_name.aliasName = new_name
            new_f.outputField = new_f_name

            #Add field to FieldMappings object
            fieldMappings.addFieldMap(new_f)

    #Convert fc using new field names
    arcpy.FeatureClassToFeatureClass_conversion(staging_fc, 
                                                os.path.dirname(new_fc), 
                                                os.path.basename(new_fc), 
                                                field_mapping=fieldMappings)

    arcpy.DeleteField_management("Parcel_County_Staging", 
                                ["OBJECTID_1"])

    print("Parcel_County_Staging is good to go")
    logger.info("Parcel County Staging is good to go")

    #Delete the feature class from sde_tabular called Parcel_County_Staging
    old_fc = sdeTabular + "SDE.Parcel_County_Staging"
    arcpy.DeleteRows_management(old_fc)
    temp_layer = arcpy.SelectLayerByAttribute_management("Parcel_County_Staging","NEW_SELECTION", "Within_TRPA_BNDY = 1")
    arcpy.Append_management(temp_layer, old_fc, "NO_TEST")

    
    # report how long it took to run the script
    runTime = datetime.datetime.now() - startTimer
    logger.info(f"\nTime it took to run this script: {runTime}")

    header = "SUCCESS - Parcel_County_Staging feature class updated."
    # send email with header based on try/except result
    send_mail(header)

# catch any arcpy errors
except arcpy.ExecuteError:
    logger.error(arcpy.GetMessages())
    print(arcpy.GetMessages())
    header = "ERROR - Arcpy Exception - Check Log"
    # send email with header based on try/except result
    send_mail(header)

# catch system errors
except Exception:
    e = sys.exc_info()[1]
    logger.info(e.args[0])
    logger.error(e)
    # print line number error is on
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    print("line: " + str(lineno) + ", Error: " + e.args[0])
    header = "ERROR - System Error - Check Log"
    # send email with header based on try/except result
    send_mail(header)