"""
CountyParcel_Transform.py
Created: June 15th,2023
Last Updated: October 20th, 2023
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
sdeTabular = os.path.join(filePath, "Tabular.sde")

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
['ESTIMATED_PRCNT_COV_ALLOWED_TRPA', 'DOUBLE', "Estimated Percent Coverage Allowed (Bailey, sq.ft.)"],
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

##--------------------------------------------------------------------------------------------------------#
## SETUP SEND EMAIL WITH LOG FILE ##
##--------------------------------------------------------------------------------------------------------#
# path to text file
fileToSend = log_file_path
# email parameters
subject = "Parcel Transformation Log File"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "gis@trpa.gov"
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
                    
# combine duplicate records, creating multipart and dissolved polygons 
@timer
def CombineAPNs(fc, fld_dissolve):    
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
    logger.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

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
    in_features = "Parcel_CC_Extracted"
    parcel_out  = "Parcel_CC_Transformed"

    # in-memory feature class
    carsonParcel = r"in_memory/inMemoryFeatureClass"

    # copy feature class into in-memory feature class to work on
    arcpy.management.CopyFeatures(in_features, carsonParcel)

    # Add TRPA base fields
    arcpy.management.AddFields(carsonParcel, baseFields)

    # Do work.
    with arcpy.da.UpdateCursor(carsonParcel, [
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
                                            'APN',   # apn              #33
                                            'APN_NUM',   # ppno         #34
                                            'Phy_Addr', #full adr       #35
                                            'Loc1', # house number      #36
                                            'Dir',# street dir          #37
                                            'Street_Name',# street name #38
                                            'Unit',  # unite Number     #39
                                            'Legal_Owner',  # Owner     #40
                                            'Mail_Addr',# mail address1 #41
                                            'Mail2_Addr',#mail address2 #42
                                            'MCity', # Mailing City     #43
                                            'MZip',  # Mailing Zip      #44
                                            'Land_Value',# land value   #45
                                            'Improv_Val',# improvedvalue#46
                                            'LU',    # land use code    #47
                                            'Total_DWUnits',  # units   #48

    ]) as cursor:
        # loop through each record and transform the values
        for row in cursor:
            # Set APN
            apn = row[33]
            if not (apn is None or apn == "" or apn.isspace() == True):
                row[0] = (apn[:3] + "-" + apn[3:6] + "-" + apn[6:8])
            else:
                row[0] = ''
                
            #PPNO
            ppno = row[34]
            if not (ppno is None):
                row[1] = int(ppno)
            else:
                row[1] = ''
                
            # Jurisdiction
            row[2] = "CC"
            
            # APO Address
            full_address = row[35]
            if not (full_address is None or full_address=='' or full_address.isspace()==True):
                row[8] = full_address
            else:
                row[8] = ''
            
            # House Number
            house = row[36]
            if not (house is None):
                row[3] = str(house)
            else:
                row[3] = ''
            
            # Street Direction
            street_direction = row[37]
            if not (street_direction is None or street_direction=='' or street_direction.isspace()==True):
                row[4] = street_direction
            else:
                row[4] = ''
                
            # Street Name
            street_name = row[38]
            if not (street_name is None or street_name =='' or street_name.isspace()==True):
                row[5] = street_name.split(" ",-1)[0]
            else:
                row[5] = ''
                
            # Street Suffix
            street_suffix = row[38]
            if not (street_suffix is None or street_suffix =='' or street_suffix.isspace()==True):
                row[6] = street_suffix.split(" ")[-1]
            else:
                row[6] = ''
                
            # Unit Number
            unit= row[39]
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
            owner = row[40]
            if not (owner is None or owner == '' or owner.isspace()==True):
                row[12] = owner.strip()
            else:
                row[12] = ''

            # Mailing Address
            address1 = row[41]
            address2 = row[42]
            if not (address2 is None or address2 == '' or address2.isspace()==True):
                row[13] = str(address2).strip()
            elif (address2 is None or address2 == '' or address2.isspace()==True and address1 is None or address1 == '' or address1.isspace()==True):
                row[13] = str(address1).strip()
            else:
                row[13] = '' 
            
            # Mailing City
            mail_city = row[43]        
    #         mail_city.split(',',1)[0]
            if not (mail_city is None or mail_city=='' or mail_city.isspace()==True):
                row[14] = mail_city.strip().split(',',1)[0].strip()
            else:
                row[14] = ''
                
            # Mailing State
            mail_state = row[43]
            if not (mail_state is None or mail_state=='' or mail_state.isspace()==True):
                row[15] = mail_state.strip().rsplit(',')[-1].strip()
            else:
                row[15] = ''
            
            # Mailing Zipcode
            mail_zip = row[44] 
            if (mail_zip is not None and len(mail_zip)>=5):
                row[16] = mail_zip[:5]
            else:
                row[16] = ''
                
            # Assessed Land Value
            land_value = row[45]
            if not(land_value is None):
                row[17] = land_value
            else:
                row[17] = 0
            
            # Assessed Improved Value
            improved_value = row[46]
            if not (improved_value is None):
                row[18] = improved_value
            else:
                row[18] = 0
                    
            # Assessed Sum
            if not (land_value is None or improved_value is None):
                assessed_sum = improved_value + land_value
                row[19] = assessed_sum
            else:
                row[19] = None
            
            # Tax  Land Value
            taxland_value = row[45]
            if not(taxland_value is None):
                row[20] = taxland_value/0.35
            else:
                row[20] = None
            
            # Tax Improved Value
            taximproved_value = row[46]
            if not (taximproved_value is None):
                row[21] = taximproved_value/0.35
            else:
                row[21] = None
            
            # Tax Sum
            if not (land_value is None or improved_value is None):
                tax_sum = row[20]+row[21]
                row[22] = tax_sum
            else:
                row[22] = None
            
            # Tax Year
            tax_year =  datetime.datetime.now().year

            if not (tax_year is None):
                row[23] = tax_year
            else:
                row[23] = ''
                
            # County Land Use Code
            county_luc = row[47]
            if not (county_luc is None):
                row[24] = str(county_luc)
            else:
                row[24] = '' 
                
            # Units
            units = row[48]
            if not (units is None):
                row[27] = units
            else:
                row[27] = None
            
    #         Update the row.
            cursor.updateRow(row)
    del cursor

    #arcpy.management.CopyFeatures(carsonParcel, parcel_out)

    out_coordinate_system = arcpy.SpatialReference('NAD 1983 UTM Zone 10N') 
    arcpy.Project_management(carsonParcel, parcel_out, out_coordinate_system)

    print('New Carson Parcels transformed')
    logger.info('New Carson Parcels transformed')
    #-------------------------------------------------------------------------------------
    ## DOUGLAS TRANSFORM
    #-------------------------------------------------------------------------------------
    # get staging feature class and name output trnasformed feature class
    in_features = "Parcel_DG_Extracted"
    parcel_out  = "Parcel_DG_Transformed"

    # in-memory feature class
    douglasParcel = r"in_memory/inMemoryFeatureClass"

    # copy feature class into in-memory feature class to work on
    arcpy.management.CopyFeatures(in_features, douglasParcel)

    # Add TRPA base fields
    arcpy.management.AddFields(douglasParcel, baseFields)


    # Do work.
    with arcpy.da.UpdateCursor(douglasParcel, [
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
                                            'APN',   # apn,ppno         #33
                                            'PLOC_', # house number     #34
                                            'PLOCDR',# street dir       #35
                                            'PLOCNM',# street name      #36
                                            'PLOCTP',# street suffix    #37
                                            'PLOCU_',# unit number      #38
                                            'PANAME',# owner name       #39
                                            'PMADD1',# mailing addr1    #40
                                            'PMADD2',# mailing addr2    #41
                                            'PMCTST',# city,state       #42
                                            'PZIP',  # zip              #43
                                            'YYEAR', # tax year         #44
                                            'YLDUSE',# land use code    #45
                                            'YLANDV',# land value       #46
                                            'YIMPRV',# improved value   #47
                                            'YEXMP', # tax exempt value #48
                                            'YNETV', # tax net value    #49
                                            'PCONYR',# year built       #50
                                            'PBEDS', # bedrooms         #51
                                            'PBATHS',# bathrooms        #52

        ### These are missing from the new service
        #                                         'PBLDSF',# building sqft    #
        #                                         'STREETADDR', #full adr     #
        #                                         'P_DWEL',# units            #
        #                                         'VHR',   # vhr yes?         #
        #                                         'HOA',   # hoa name         #
    ]) as cursor:
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
            house            = str(row[34]).strip()
            street_direction = str(row[35]).strip()
            street_name      = str(row[36]).strip()
            street_suffix    = str(row[37]).strip()
            unit             = str(row[38]).strip()
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
            address1 = row[40].strip()
            address2 = row[41].strip()
            if not (address1 is None or address1=='' or address1.isspace()==True):
                row[13] = str(address1 + " " + address2)
            elif (address2 is None):
                row[13] = address1
            else:
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
                row[15] = mail_state
            else:
                row[15] = ''
            
            # Mailing Zipcode
            mail_zip = row[43].strip()
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
    countriesList = ['japan','canada', 'australia']

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
    #             print("Working on MAIL_ADDR4")
                if row[38] != 'UNKNOWN' and row[38].lower() not in countriesList:
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
                cityStateZip = re.search(cityStateZipRegex, str(row[37]))

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
                                            'ADR1',  # mailing addr1      #44
                                            'ADR2',  # mailing addr2      #45
                                            'CITY',  # city               #46 
                                            'STATE', # state              #47
                                            'ZIP',  # zip                 #48
                                            'USE_CD', # land use code     #49
                                            'USE_CD_N', # land use desc   #50
                                            'LANDVALUE',# land value      #51
                                            'STRUCTURE',# improved value  #52
                                            'EffectiveYr',# year built     #53
                                            'StructureSF'  # build sqft      #54
                                        
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
            
            if not (adr is None or adr=='' or adr.isspace()==True):
                row[8] = adr
            else:
                row[8] = ''
                
            # Postal Town - See TRPA ATTRIBUTION section
                
            # Postal State
            row[10] = 'CA'

            # Postal City - See TRPA ATTRIBUTION section
            
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
                row[17] = mail_state
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
                row[11] = ""

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
                row[11] = postal_zip
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
                row[17] = mail_state
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

    # owner name lists - this is a stupid way to figure this out
    fedOwnList = ("UNITED STATES OF AMERICA C/O USDA FOREST SERVICE","USA FOREST SERVICE", 
                "USDA FOREST SERVICE", "USDA - FOREST SERVICE", "UNITED STATES POSTAL", 
                "UNITED STATES OF AMERICA", "UNITED STATES FOREST SERVICE", "U S POSTAL SERVICE", "U S COAST GUARD",
                "U S A FOREST SERVICE``", "U S A FOREST SERVICE", "LAKE VALLEY RANGER STA", "DEPT OF VETRANS AFFAIRS%", 
                "DEPT OF VETERANS AFFAIRS%", "DEPT OF VETERANS AFFAIRS %", "BUREAU OF LAND MANAGEMENT", "U S FOREST SERVICE",
                "DEPT OF VETERANS AFFAIRS  & ERSKINE NEIL H TR", "DEPT OF VETERANS AFFAIRS  & MASTERS DANE C", 
                "DEPT OF VETERANS AFFAIRS  & SLEZAK FRANK J CO TR", "DEPT OF VETERANS AFFAIRS & RIVES DONALD E JR"
                "DEPT OF VETERANS AFFAIRS & WILLIAMS MATTHEW G DBA WILLIAMS VACATION HOME", "DEPT OF VETRANS AFFAIRS & WILSON VIVIAN M",
                "DEPARTMENT OF TRANSPORTATION", "USA FOREST SERVICE & OWNERSHIP UNVERIFIED", "U S A FOREST SERVICE & LAKE TAHOE BASIN MNGMT UNIT",
                "U S A FOREST SERVICE & OWNERSHIP UNVERIFIED", "U S D A FOREST SERVICE", "UNITED STATES & DEPT OF AGRICULTURE",
                "UNITED STATES OF AMERICA & ATTN RICHARD T FLYNN", "UNITED STATES OF AMERICA & DEPARTMENT OF AGRICULTU", "UNITED STATES OF AMERICA & F/S DEPT OF AGRICULTURE",
                "UNITED STATES OF AMERICA & FOREST SER. DEPT OF AG.", "UNITED STATES OF AMERICA & FOREST SERVICE", "UNITED STATES OF AMERICA & FOREST SERVICE (USDA)",
                "UNITED STATES OF AMERICA & FOREST SERVICE DEPT OF", "UNITED STATES OF AMERICA & FOREST SERVICE TAHOE BA", "UNITED STATES OF AMERICA & FOREST SERVICE USDA",
                "UNITED STATES OF AMERICA & FOREST SVC/DEPT OF AGRI", "UNITED STATES OF AMERICA & LAKE TAHOE BASIN MANAGM",
                "UNITED STATES OF AMERICA & LAKE TAHOE BASIN MGT UN", "UNITED STATES OF AMERICA & REGIONAL LAND ADJUSTMEN",
                "UNITED STATES OF AMERICA & U S FOREST SERVICE", "UNITED STATES OF AMERICA & U S FOREST SERVIE",
                "UNITED STATES OF AMERICA & USDA FOREST SER LAKE TA", "UNITED STATES OF AMERICA & USDA FOREST SERVICE",
                "USDA - FOREST SERVICE & LAKE TAHOE BASIN MGMT UNIT")

    stateOwnList = ("TAHOE CONSERVANCY", "STATE OF NEVADA FOREST SERVICE", "STATE OF NEVADA", "STATE OF CALIFORNIA THE", 
                    "STATE OF CALIFORNIA (EASEMENT)", "STATE OF CALIFORNIA", "STATE OF CA", "REGENTS OF UNIV OF CALIF",
                    "UNIVERSITY CALIFORNIA REGENTS", "UNIVERSITY OF NEVADA RENO", "NEVADA, STATE OF", "NEVADA STATE OF", 
                    "CALIFORNIA TAHOE CONSERVANCY ET AL", "CALIFORNIA TAHOE CONSERVANCY", "CALIFORNIA STATE OF THE", 
                    "CALIFORNIA STATE OF ET AL", "CALIFORNIA STATE OF", "CA STATE DEPT TRANSPORTATION", 
                    "CA TAHOE CONSERVANCY", "CALIFORNIA STATE OF TAHOE CONSERVANCY", "CALIFORNIA STATE OF THE", 
                    "NEVADA DEPT OF TRANSPORTATION", "STATE OF CALIFORNIA & CALIFORNIA TAHOE CONSERVANCY", "STATE OF CALIFORIA & CALIFORNIA TAHOE CONSERVANCY",
                    "STATE OF CALIFORNIA & CA TAHOE CONSERVANCY", "STATE OF CALIFORNIA & CALIFORNIA TAHOE CONSERVANCY CALIFORNIA TAHOE CONSERVANCY",
                    "STATE OF CALIFORNIA & CALIFORNIA TAHOE CONSEVANCY", "STATE OF CALIFORNIA & DEPART OF TRANSPORTATION", "STATE OF CALIFORNIA & DEPARTMENT OF GENERAL SERVIC", 
                    "STATE OF CALIFORNIA & DEPARTMENT OF TRANSPORTATION", "STATE OF CALIFORNIA & DEPT OF GEN SRVS R E DIV", "STATE OF CALIFORNIA & DEPT OF GENERAL SERVICES",
                    "STATE OF CALIFORNIA & DEPT OF PARKS & RECREATION", "STATE OF CALIFORNIA & DEPT OF TRANSPORTATION", "STATE OF CALIFORNIA & PARKS & RECREATION",
                    "STATE OF CALIFORNIA (EASEMENT) & CALIFORNIA TAHOE", "CALIFORNIA STATE PARKS AND RECREATION",
                    "CALIFORNIA STATE OF & DEPT GEN SERVICES REAL ESTAT")

    localOwnList = ("ZEPHYR COVE GENERAL IMP DIST", "WASHOE COUNTY SCHOOL DISTRICT BOARD", "WASHOE COUNTY", "WASHOE TRIBE OF NV & CA", 
                    "TALMONT RESORT IMPROVEMENT DISTRICT", "TALMONT RESORT IMPR DIST", "TALMONT RESORT IMP DISTRICT",
                    "TALMONT RESORT IMP DIST", "TAHOE PARADISE RESORT IMP DIST", "TAHOE PARADISE RES IMP DST",
                    "TAHOE FOREST HOSPITAL DISTRICT", "TAHOE TRUCKEE UNIFIED SCHOOL DISTRICT", "TAHOE TRUCKEE UNIFIED SCH DIST", 
                    "TAHOE DOUGLAS FIRE PROTECT DIST", "TAHOE DOUGLAS SEWER DIST", "TAHOE DOUGLAS DISTRICT", 
                    "TAHOE CITY PUBLIC UTILITY DISTRICT", "TAHOE CITY PUBLIC UTILITY DIST", "TAHOE CITY PUBLIC UTILDIST", 
                    "TAHOE CITY PUB UTILITY DST", "TAHOE CITY PUB UTILITY DIS", "TAHOE CITY P U D", "TAHOE CITY CEMETERY DIST", 
                    "SOUTH TAHOE REDEVELP AGENCY", "SOUTH TAHOE REFUSE CO", "SOUTH TAHOE PUD", "SOUTH TAHOE PUBLIC UTL DST",
                    "SOUTH TAHOE PUBLIC UTILITYDIST", "SOUTH TAHOE PUBLIC UTILITY DST", "SOUTH TAHOE PUBLIC UTILITY DIS", 
                    "SOUTH TAHOE PUBLIC UTILITY", "SOUTH TAHOE PUBLIC UTIL DT", "SOUTH TAHOE PUBLIC UTIL DIST", 
                    "SOUTH TAHOE PUBLIC", "SOUTH TAHOE PUB UTIL DIST", "SOUTH LAKE TAHOE CTYOF 1/3", "SOUTH LAKE TAHOE CITY OF", 
                    "SO TAHOE PUBLIC UTILITY DIST", "SO TAHOE PUB UTIL DIST", "SIERRA NEVADA COLLEGE", "ROUND HILL GEN IMP DIST",
                    "PLACER COUNTY REDEVELOPMENT AGENCY", "PLACER COUNTY OF", "PLACER COUNTY", "NORTH TAHOE PUBLIC UTL DIST",
                    "NORTH TAHOE PUBLIC UTILITY DISTRICT", "NORTH TAHOE PUBLIC UTILITY DIST", "NORTH TAHOE PUBLIC UTILITY DIS", 
                    "NORTH TAHOE PUBLIC UTILITIES DIST", "NORTH TAHOE PUBLIC UTILIITY DISTRICT", "NORTH TAHOE P U D",
                    "NORTH TAHOE FIRE PROTECTION DISTRICT", "NORTH TAHOE FIRE PROTECTION", "NORTH TAHOE FIRE DIST",
                    "NORTH LAKE TAHOE FIRE PROTECTION DIST", "N TAHOE FIRE PROTECTION DIST", "MEEKS BAY FIRE PROT DIST", 
                    "LAKERIDGE GENERAL IMP DIST", "LAKE VALLEY FIRE PROTECTION", "LAKE VALLEY FIRE PROT DST", "LAKE VALLEY FIRE PROT DIST", 
                    "LAKE VALLEY FIRE DISTRICT", "LAKE TAHOE UNIFIED SCHOOL DIST", "LAKE TAHOE SCHOOL", "LAKERIDGE GENERAL IMP DIST", 
                    "LAKE TAHOE FIRE PROTECTION DIST", "LAKE TAHOE FIRE PROTECT DIST", "LAKE TAHOE COMM COLLEGE DIST",
                    "LAKE TAHOE COMM COL DIST", "KINGSBURY GENERAL IMP DISTRICT", "KINGSBURY GENERAL IMP DIST",
                    "INCLINE VILLAGE GENERAL IMPROVEMENT DISTRICT", "INCLINE VILLAGE GENERAL IMPROVEMENT DIST", 
                    "DOUGLAS COUNTY SEWER DIST", "DOUGLAS COUNTY SCHOOL DIST", "DOUGLAS COUNTY", "DOUGLAS CO SEWER IMP DIST #1", 
                    "COUNTY OF EL DORADO", "CITY OF SOUTH LAKE TAHOE", "EL DORADO IRRIGATION DISTRICT", 
                    "HAPPY HOMESTEAD CEMETERY DIST", "WASHOE TRIBE", "SOUTHTAHOE PUBLIC UTILITY DIST", "DOUGLAS COUNTY TRUSTEE", 
                    "DOUGLAS COUNTY TRUSTEE (HOLD)", "WASHOE TRIBE OF NEVADA AND CALIFORNIA", "ALPINE SPRINGS CO WATER DIST", 
                    "ALPINE SPRINGS COUNTY WATER DISTRICT", "ALPINE SPRINGS WATER DISTRICT", "NORTHSTAR COMMUNITY SERVICE DISTRICT",
                    "SQUAW VALLEY CO WATER DIST", "SQUAW VALLEY PUBLIC SERVICE DISTRICT", "TRUCKEE TAHOE AIRPORT DISTRICT", 
                    "COUNTY OF EL DORADO & ATTEN: PAUL MCINTOSH", "COUNTY OF EL DORADO & BOARD OF SUPERVISORS", 
                    "COUNTY OF EL DORADO & BOARD OF SUPERVISORS", "COUNTY OF EL DORADO & C/O BOARD OF SUPERVISORS", "COUNTY OF EL DORADO & COUNSEL",
                    "COUNTY OF EL DORADO & COUNSEL'S OFFICE", "COUNTY OF EL DORADO & DEPARTMENT OF PUBLIC WORKS", "COUNTY OF EL DORADO & DEPARTMENT OF TRANSPORTATION",
                    "COUNTY OF EL DORADO & DEPT OF PUBLIC WORKS", "COUNTY OF EL DORADO & DEPT OF TRANSPORTATION", "COUNTY OF EL DORADO & GENERAL SERVICES DEPARTMENT",
                    "COUNTY OF EL DORADO & OF EL DORADO", "COUNTY OF EL DORADO & PUBLIC WORKS DEPARTMENT", "EL DORADO CO OFFICE EDUCATION", "EL DORADO COUNTY & SUPERINTENDENT OF SCHOOLS",
                    "EL DORADO COUNTY & BOARD OF SUPERVISORS", "LAKE TAHOE COMMUNITY COLLEGE DIST", "LAKE VALLEY RANGER STA & U S FOREST SERVICE",
                    "LAKE VALLEY FIRE PROTECTION & DISTRICT POLITICAL S", "SOUTH TAHOE PUBLIC & UTILITY DISTRICT",
                    "SOUTH TAHOE PUBLIC UTILITY &  DISTRIC", "SOUTH TAHOE PUBLIC UTIL DIST & CA MUNICIPAL CORP", "TAHOE CITY PUBLIC UTIL DST",
                    "TAHOE RESOURCE CONSERVATION &  DISTRIC", "TAHOE RESOURCE CONSERVATION DIST  C/O DISTRICT MANAGER", "FALLEN LEAF COMM SERVICES DIST",
                    "FALLEN LEAF LAKE COMM SERVDIST", "TAHOE DOUGLAS VISITORS AUTH", "KINGSBURY GENARAL IMP DIST", "ALPINE SPRINGS CO WTR DIST FIN CORP",
                    "COUNTY OF PLACER", "MCKINNEY WATER DISTRICT", "NORTHSTAR COMMUNITY SERVICES DISTRICT", "PLACER COUNTY PUBLIC WORKS",
                    "REDEVELOPMENT AGENCY OF THE COUNTY OF PL", "TRUCKEE DONNER PUBLIC UTILITY DISTRICT", "TRUCKEE SANITARY DISTRICT",
                    "TAHOE TRANSPORTATION DISTRICT") 

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
    fields = ("COUNTY_LANDUSE_CODE_TRPA",
            "COUNTY_LANDUSE_TRPA",  
            "EXISTING_LANDUSE_TRPA", 
            'JURISDICTION_TRPA')

    with arcpy.da.UpdateCursor(ParcelLayer, fields) as cursor:
        for row in cursor:
            ctyluc = str(row[0])
            cty = row[3]
            # set Washoe county land use
            # set TRPA Land Use Description
            if (row[0] != None or row[0] != "") and (row[3] == 'WA'):
                if ctyluc in ('400', '410', '440', '500', '510', '520', '630', '640', '670', '720'):
                    row[2] = "Commercial"
                elif ctyluc in ('210', '250'):
                    row[2] = "Condominium"
                elif ctyluc in ('240'):
                    row[2] = "Condominium Common Area"
                elif ctyluc in ('220', '230', '300', '310', '320', '330', '340', '350', '360'):
                    row[2] = "Multi-Family Residential"
                elif ctyluc in ('600', '620'):
                    row[2] = "Open Space"
                elif ctyluc in ('700', '710', 'PBRD'):
                    row[2] = "Public Service"
                elif ctyluc in ('190'):
                    row[2] = "Recreation"
                elif ctyluc in ('200'):
                    row[2] = "Single Family Residential"     
                elif ctyluc in ('420', '430'):
                    row[2] = "Tourist Accommodation"
                elif ctyluc in ('100', '110', '120', '130', '140', '150', '160', '170', '180'):
                    row[2] = "Vacant"            
                elif ctyluc is None:
                    row[2] == ''
            if (row[0] != None or row[0] != "") and (row[3] == 'WA'):
                if ctyluc in ('710'):
                    row[1] = "Intracounty public utility"
                elif ctyluc == '700':
                    row[1] = 'Centrally assessed public utility'
                elif ctyluc == '510':
                    row[1] = 'Commercial Industrial: retail or office with Indus'
                elif ctyluc == '500':
                    row[1] = 'General industrial: light indust, trucking, warehs'
                elif ctyluc == '440':
                    row[1] = 'Resort commercial: ski, golf, sports, etc.'
                elif ctyluc == '430':
                    row[1] = 'Commercial hotel or motel'
                elif ctyluc == '420':
                    row[1] = 'Casino or hotel casino'
                elif ctyluc == '410':
                    row[1] = 'Offices, professional and business, banks, etc.'
                elif ctyluc == '400':
                    row[1] = 'General Commercial: retail, mixed, parking, school'
                elif ctyluc == '340':
                    row[1] = 'Ten or more units'
                elif ctyluc == '330':
                    row[1] = 'Five to Nine Units'
                elif ctyluc == '320':
                    row[1] = 'Three or four Units'
                elif ctyluc == '310':
                    row[1] = 'Two Single Family Units'
                elif ctyluc == '300':
                    row[1] = 'Duplex'
                elif ctyluc == '250':
                    row[1] = 'Condo or Townhouse valued as apartment use'
                elif ctyluc == '240':
                    row[1] = 'Common Area'
                elif ctyluc == '210':
                    row[1] = 'Condominium or Townhouse'
                elif ctyluc == '200':
                    row[1] = 'Single Family Residence'
                elif ctyluc == '190':
                    row[1] = 'Public Parks: vacant or improved'
                elif ctyluc == '170':
                    row[1] = 'Other, unbuildable: roads, restrictions, terrain'
                elif ctyluc == '160':
                    row[1] = 'Splinter, unbuildable: small size or shape'
                elif ctyluc == '140':
                    row[1] = 'Vacant, commercial'
                elif ctyluc == '130':
                    row[1] = 'Vacant, multi-residential'
                elif ctyluc == '120':
                    row[1] = 'Vacant, single family'
                elif ctyluc == '110':
                    row[1] = 'Vacant, under development'
                elif ctyluc == '100':
                    row[1] = 'Vacant, other or unknown'            
                elif ctyluc is None:
                    row[1] == ''
                cursor.updateRow(row)
            # Set Carson City County Land Use Descriptions
            if (row[0] != None or row[0] != "") and (row[3] == 'CC'):
                if ctyluc in ('400', '401', '402', '403', '404', '408', '410', '411', 
                            '412', '440', '441', '460', '470', '480', '482', '490', 
                            '500', '501', '510', '511', '512', '513', '520', '521', 
                            '560', '570', '580', '582', '590', '624', '625', '694', 
                            '800', '820', '830', '840', '880', '882', '890', '920', 
                            '921', '930', '960', '980', '990'):
                    row[2] = "Commercial"
                elif ctyluc in ('210', '211'):
                    row[2] = "Condominium"
                elif ctyluc == '970':
                    row[2] = "Condominium Common Area"
                elif ctyluc in ('240', '241', '300', '301', '310', '311', '313', '320', 
                                '321', '330', '331', '333', '340', '341', '350', '360', 
                                '370', '380', '382', '390', '698'):
                    row[2] = "Multi-Family Residential"
                elif ctyluc in ('190', '600', '610', '612', '613', '614', '615', '616', 
                                '618', '620', '695', '696', '697', '810'):
                    row[2] = "Open Space"
                elif ctyluc in ('190', '700', '710', '711', '720', '731', '732', '733', '780', 
                                '790', '910', '922'):
                    row[2] = "Public Service"
                elif ctyluc in ('450', '900'):
                    row[2] = "Recreation"
                elif ctyluc in ('200', '201', '220', '222', '230', '231', '232', '260', 
                                '270', '280', '282', '290', '622', '692', '693'):
                    row[2] = "Single Family Residential"     
                elif ctyluc in ('420', '421', '430', '431', '432', '514'):
                    row[2] = "Tourist Accommodation"
                elif ctyluc in ('100', '108', '110', '117', '120', '130', '140', '150', '160'):
                    row[2] = "Vacant"
                elif ctyluc is None:
                    row[2] == ''
            if (row[0] != None or row[0] != "") and (row[3] == 'CC'):
                if ctyluc == '980':
                    row[1] = 'Special Purpose with Minor Improvements'
                elif ctyluc == '320':
                    row[1] = 'Three to Four Units'
                elif ctyluc == '280':
                    row[1] = 'Single Family Residential with Minor Improvements'
                elif ctyluc == '190':
                    row[1] = 'Vacant - Public Use Lands'
                elif ctyluc == '120':
                    row[1] = 'Vacant - Single Family Residential' 
                elif ctyluc is None:
                    row[1] == ''
                cursor.updateRow(row)           
            # update Douglas Land Use descriptions        
            if (row[0] != None or row[0] != "") and (row[3] == 'DG'):
                if ctyluc in ('400', '402', '410', '411', '412', 
                            '440', '460', '470', '480', '500', 
                            '510', '560', '580', '582'):
                    row[2] = "Commercial"
                elif ctyluc in ('210', '211'):
                    row[2] = "Condominium"
                elif ctyluc == '270':
                    row[2] = "Condominium Common Area"
                elif ctyluc in ('300', '310', '320', '330', '350', '390'):
                    row[2] = "Multi-Family Residential"
                elif ctyluc == '190':
                    row[2] = "Open Space"
                elif ctyluc in ('700', '710', '711', '910', '980', '970'):
                    row[2] = "Public Service"
                elif ctyluc in ('450', '900', '970'):
                    row[2] = "Recreation"
                elif ctyluc in ('200', '220', '230', '236', '240', '280', '282'):
                    row[2] = "Single Family Residential"     
                elif ctyluc in ('420', '430'):
                    row[2] = "Tourist Accommodation"
                elif ctyluc in ('100', '110', '117', '120', '130', '140'):
                    row[2] = "Vacant"
                elif ctyluc is None:
                    row[2] == ''
            if (row[0] != None or row[0] != "" or ctyluc.isspace() != True) and (row[3] == 'DG'):
                if ctyluc == '980':
                    row[1] = 'Special Purpose with Minor Improvements'
                elif ctyluc == '970':
                    row[1] = 'Special Purpose Common Area'
                elif ctyluc == '910':
                    row[1] = 'Cemeteries'
                elif ctyluc == '900':
                    row[1] = 'Parks for Public Use'
                elif ctyluc == '711':
                    row[1] = 'Communication, Transportation, and Utility Property of a Local Nature Under Construction'
                elif ctyluc == '710':
                    row[1] = 'Communication, Transportation, and Utility Property of a Local Nature'
                elif ctyluc == '700':
                    row[1] = 'Operating Communication, Transportation, and Utility Property of an Interstate or Intercounty Nature'
                elif ctyluc == '582':
                    row[1] = 'Industrial with Minor Improvements - with structures insufficient to determine intended use'
                elif ctyluc == '580':
                    row[1] = 'Industrial with Minor Improvements'
                elif ctyluc == '560':
                    row[1] = 'Industrial Auxiliary Area'
                elif ctyluc == '510':
                    row[1] = 'Commercial Industrial - retail or office use combined with Industrial use'
                elif ctyluc == '500':
                    row[1] = 'General Industrial - light industry, trucking and warehousing, service, repair, etc.'
                elif ctyluc == '480':
                    row[1] = 'Commercial with Minor Improvements'
                elif ctyluc == '470':
                    row[1] = 'Commercial Common Area'
                elif ctyluc == '460':
                    row[1] = 'Commercial Auxiliary Area'
                elif ctyluc == '450':
                    row[1] = 'Golf Course'
                elif ctyluc == '440':
                    row[1] = 'Commercial Recreation'
                elif ctyluc == '430':
                    row[1] = 'Commercial Living Accommodations'
                elif ctyluc == '420':
                    row[1] = 'Casino or Hotel Casino'
                elif ctyluc == '410':
                    row[1] = 'Offices, Professional and Business Services'
                elif ctyluc == '402':
                    row[1] = 'Parking and/or Parking Structures'
                elif ctyluc == '400':
                    row[1] = 'General Commercial'
                elif ctyluc == '390':
                    row[1] = 'Mixed Use with Multi-Family Residential as primary use'
                elif ctyluc == '382':
                    row[1] = 'Multi-Family Residential with Minor Improvements - No livable structures'
                elif ctyluc == '380':
                    row[1] = 'Multi-Family Residential with Minor Improvements'
                elif ctyluc == '370':
                    row[1] = 'Multi-Family Residential Common Area'
                elif ctyluc == '360':
                    row[1] = 'Multi-Family Residential Auxiliary Area'
                elif ctyluc == '350':
                    row[1] = 'Manufactured Home Park - Ten or More Manufactured Home Units'
                elif ctyluc == '341':
                    row[1] = 'Five or More Units - High Rise Under Construction'
                elif ctyluc == '340':
                    row[1] = 'Five or More Units - High Rise'
                elif ctyluc == '333':
                    row[1] = 'Exempt or Partially Exempt Apartment Building'
                elif ctyluc == '331':
                    row[1] = 'Five or More Units - Low Rise Under Construction'
                elif ctyluc == '330':
                    row[1] = 'Five or More Units - Low Rise'
                elif ctyluc == '321':
                    row[1] = 'Three to Four Units Under Construction'
                elif ctyluc == '320':
                    row[1] = 'Three to Four Units'
                elif ctyluc == '313':
                    row[1] = 'Multi-Family Residence with Manufactured Home Conversion'
                elif ctyluc == '311':
                    row[1] = 'Two Single Family Units Under Construction'
                elif ctyluc == '310':
                    row[1] = 'Two Single Family Units'
                elif ctyluc == '301':
                    row[1] = 'Duplex Under Construction'
                elif ctyluc == '300':
                    row[1] = 'Duplex'
                elif ctyluc == '290':
                    row[1] = 'Mixed Use with Single Family Residential as primary use'
                elif ctyluc == '282':
                    row[1] = 'Single Family Residential with Minor Improvements - No livable structures'
                elif ctyluc == '280':
                    row[1] = 'Single Family Residential with Minor Improvements'
                elif ctyluc == '270':
                    row[1] = 'Single Family Residential Common Area'
                elif ctyluc == '260':
                    row[1] = 'Single Family Residential Auxiliary Area'
                elif ctyluc == '240':
                    row[1] = 'Individual Residential Unit - Townhouse or Row House'
                elif ctyluc == '236':
                    row[1] = 'Personal Property Manufactured Home Secured'
                elif ctyluc == '233':
                    row[1] = 'Secured Manufactured Home with Site Built Additions (Not Converted)'
                elif ctyluc == '232':
                    row[1] = 'Manufactured Home - Unsecured with Site Built Additions'
                elif ctyluc == '231':
                    row[1] = 'Manufacture Home Conversions Pending'
                elif ctyluc == '230':
                    row[1] = 'Personal Property Manufactured Home on the Unsecured Roll'
                elif ctyluc == '222':
                    row[1] = 'Manufactured Home (Converted) with Site Built Additions'
                elif ctyluc == '220':
                    row[1] = 'Manufactured Home Converted to Real Property'
                elif ctyluc == '211':
                    row[1] = 'Individual Unit in a Multiple Unit Building Under Construction'
                elif ctyluc == '210':
                    row[1] = 'Individual Unit in a Multiple Unit Building'
                elif ctyluc == '201':
                    row[1] = 'Single Family Residence Under Construction'
                elif ctyluc == '200':
                    row[1] = 'Single Family Residence'
                elif ctyluc == '190':
                    row[1] = 'Vacant - Public Use Lands'
                elif ctyluc == '150':
                    row[1] = 'Vacant - Industrial'
                elif ctyluc == '140':
                    row[1] = 'Vacant - Commercial'
                elif ctyluc == '130':
                    row[1] = 'Vacant - Multi-Residential'
                elif ctyluc == '120':
                    row[1] = 'Vacant - Single Family Residential'
                elif ctyluc == '117':
                    row[1] = 'Vacant - Roads/Easements'
                elif ctyluc == '110':
                    row[1] = 'Vacant - Splinter and Other Unbuildable'
                elif ctyluc == '108':
                    row[1] = 'Vacant - Patented Mining Claim, Not Mined'
                elif ctyluc == '100':
                    row[1] = 'Vacant - Unknown/Other'
                elif ctyluc is None:
                    row[1] == ''
                cursor.updateRow(row)        
            # Set El Dorado County Land Use Description fields
            if (row[0] != None or row[0] != "") and (row[3] == 'EL'):
                if ctyluc in ('03', '29', '31', '32', '34', '36', '37', '38', '39', '41', '42', '43', '44', '45', '46', '47', '48', 
                            '65', '67', '68', '82', '91', '93'):
                    row[2] = "Commercial"
                elif ctyluc == '14':
                    row[2] = "Condominium"
                elif ctyluc == '89':
                    row[2] = "Condominium Common Area"
                elif ctyluc in ('01', '07', '12', '13', '16', '18', '19', '28', '35'):
                    row[2] = "Multi-Family Residential"
                elif ctyluc in ('25', '26', '50', '51', '52', '55', '56', '60', '70', '75', '79'):
                    row[2] = "Open Space"
                elif ctyluc in ('90', '92', '94', '96', '97', '98', '99'):
                    row[2] = "Public Service"
                elif ctyluc in ('61', '62', '63', '64'):
                    row[2] = "Recreation"
                elif ctyluc in ('06', '11', '15', '22', '23'):
                    row[2] = "Single Family Residential"     
                elif ctyluc in ('33', '80', '81'):
                    row[2] = "Tourist Accommodation"
                elif ctyluc in ('00', '02', '05', '17', '21', '24', '30', '40'):
                    row[2] = "Vacant"
                elif ctyluc is None:
                    row[2] == ''
            if (row[0] != None or row[0] != "") and (row[3] == 'EL'):
                if ctyluc == '98':
                    row[1] = 'DEV MSC FIRE SUPPRESSION FACILITIES'
                elif ctyluc == '96':
                    row[1] = 'DEV MSC CEMETERIES'
                elif ctyluc == '94':
                    row[1] = 'DEV MSC SCHOOLS - LARGE (101+ STUDENTS)'
                elif ctyluc == '93':
                    row[1] = 'DEV MSC SCHOOLS - MEDIUM (13-100 STUDENTS)'
                elif ctyluc == '92':
                    row[1] = 'DEV MSC SCHOOLS - SMALL (1-12 STUDENTS)'
                elif ctyluc == '90':
                    row[1] = 'UTL IND PUBLIC UTILITY (ON STATE ASSESSED ROLL)'
                elif ctyluc == '84':
                    row[1] = 'DEV MSC TEMPORARY USE CODE FOR PROJECT 184'
                elif ctyluc == '82':
                    row[1] = 'DEV COM PARKING LOT'
                elif ctyluc == '81':
                    row[1] = 'DEV MSC UNDERLYING INTEREST IN TIME SHARE PROJ'
                elif ctyluc == '79':
                    row[1] = 'RLU MSC ENV. SENSITIVE LAND - RESTRICTED USE'
                elif ctyluc == '68':
                    row[1] = 'DEV COM MARINAS'
                elif ctyluc == '65':
                    row[1] = 'DEV COM RESTAURANT'
                elif ctyluc == '64':
                    row[1] = 'DEV MSC SKI RESORTS'
                elif ctyluc == '63':
                    row[1] = 'DEV MSC CAMPGROUNDS'
                elif ctyluc == '62':
                    row[1] = 'DEV MSC COMMUNITY ORIENTED FACILITIES'
                elif ctyluc == '61':
                    row[1] = 'DEV MSC MISC. IMPROVED RECREATIONAL'
                elif ctyluc == '60':
                    row[1] = 'VAC MSC VACANT RECREATIONAL LAND'
                elif ctyluc == '50':
                    row[1] = 'TPZ MSC TIMBER PRESERVE ZONING - ACTIVE'
                elif ctyluc == '48':
                    row[1] = 'DEV IND OFFICES'
                elif ctyluc == '47':
                    row[1] = 'DEV IND HOSPITALS & CONVALESCENT HOSPITALS'
                elif ctyluc == '46':
                    row[1] = 'DEV IND MEDICAL/DENTAL/VET OFFICES'
                elif ctyluc == '45':
                    row[1] = 'DEV IND LIGHT MANUFACTURING'
                elif ctyluc == '43':
                    row[1] = 'DEV IND WAREHOUSES'
                elif ctyluc == '42':
                    row[1] = 'DEV IND MINI-WAREHOUSES (MINI-STORAGE)'
                elif ctyluc == '41':
                    row[1] = 'DEV IND MISC. IMPROVED INDUSTRIAL PROPERTY'
                elif ctyluc == '40':
                    row[1] = 'VAC IND VACANT INDUSTRIAL LAND'
                elif ctyluc == '39':
                    row[1] = 'DEV COM SUPERMARKETS'
                elif ctyluc == '38':
                    row[1] = 'DEV COM RETAIL STORES >15,000 SQ. FT.'
                elif ctyluc == '37':
                    row[1] = 'DEV COM RETAIL STORES 5,001-15,000 SQ. FT.'
                elif ctyluc == '36':
                    row[1] = 'DEV COM RETAIL STORES <=5,000 SQ. FT.'
                elif ctyluc == '35':
                    row[1] = 'DEV COM MOBILE HOME PARKS'
                elif ctyluc == '34':
                    row[1] = 'DEV COM SERVICE STATION'
                elif ctyluc == '33':
                    row[1] = 'DEV COM MOTEL, HOTEL'
                elif ctyluc == '31':
                    row[1] = 'DEV COM MISC. IMPROVED COMMERCIAL'
                elif ctyluc == '30':
                    row[1] = 'VAC COM VACANT COMMERCIAL LAND'
                elif ctyluc == '29':
                    row[1] = 'DEV MSC RURAL NON-RES. IMPROVEMENT 2.51-20.0 AC.'
                elif ctyluc == '26':
                    row[1] = 'AGP MSC RURAL RESTRICTIVE ZONING - NON-RENEWAL'
                elif ctyluc == '25':
                    row[1] = 'AGP MSC RURAL RESTRICTIVE ZONING - CLCA (ACTIVE)'
                elif ctyluc == '24':
                    row[1] = 'VAC RES RURAL RES. LAND 20+ MINOR NON-RES IMPR'
                elif ctyluc == '23':
                    row[1] = 'DEV RES RURAL RES. 20+ AC. 1 RES. UNIT'
                elif ctyluc == '22':
                    row[1] = 'DEV RES RURAL RES. 2.51-20.0 AC. 1 SF UNIT'
                elif ctyluc == '21':
                    row[1] = 'VAC RES VAC RURAL RES LAND 2.51-20.0 AC. 1 UNIT'
                elif ctyluc == '17':
                    row[1] = 'VAC MSC SUBJ. TO OPEN SPACE CONTRACT (NOT CLCA)'
                elif ctyluc == '16':
                    row[1] = 'DEV RES MOBILE HOME ON RENTED LAND'
                elif ctyluc == '15':
                    row[1] = 'DEV RES RESIDENCE ON LEASED LAND'
                elif ctyluc == '14':
                    row[1] = 'DEV MFR CONDOMINIUMS & TOWNHOUSES'
                elif ctyluc == '13':
                    row[1] = 'DEV MFR MULTI-RESIDENTIAL 4+ UNITS'
                elif ctyluc == '12':
                    row[1] = 'DEV MFR MULTI-RESIDENTIAL 2-3 UNITS'
                elif ctyluc == '11':
                    row[1] = 'DEV RES SINGLE FAM. RES. <=2.5 AC.(INC. MAN. HMS'
                elif ctyluc == '07':
                    row[1] = 'DEV MFR RETIREMENT HOUSING'
                elif ctyluc == '05':
                    row[1] = 'VAC MFR VACANT MULTI-RES. LAND 4+ UNITS ALLOWED'
                elif ctyluc == '03':
                    row[1] = 'DEV COM PLACE OF WORSHIP'
                elif ctyluc == '02':
                    row[1] = 'VAC RES NON-RES. IMPROVEMENTS <=2.5 AC.'
                elif ctyluc == '00':
                    row[1] = 'VAC RES VACANT RES. LAND <=2.5 AC. 1-3 UNITS'
                elif ctyluc is None:
                    row[1] == ''
                cursor.updateRow(row)
            # set Placer TRPA land use description
            if (row[0] != None or row[0] != "") and (row[3] == 'PL'):
                if ctyluc in ('07', '11', '12', '13', '14', '15', '17', '19', '21', '22', '23', 
                            '24', '25', '26', '27', '29', '31', '32', '36', '37', '38', 
                            '39', '62', '63', '71', '88'):
                    row[2] = "Commercial"
                elif ctyluc == ('04'):
                    row[2] = "Condominium"
                elif ctyluc == '89':
                    row[2] = "Condominium Common Area"
                elif ctyluc in ('02', '03', '04', '05', '09', '28'):
                    row[2] = "Multi-Family Residential"
                elif ctyluc in ('56', '55', '60', '61', '87', '90'):
                    row[2] = "Open Space"
                elif ctyluc in ('72', '76', '77', '81'):
                    row[2] = "Public Service"
                elif ctyluc in ('65', '66', '67', '68', '69'):
                    row[2] = "Recreation"
                elif ctyluc in ('01', '08', '16'):
                    row[2] = "Single Family Residential"     
                elif ctyluc in ('06', '18', '64'):
                    row[2] = "Tourist Accommodation"
                elif ctyluc in ('00', '10', '20', '30'):
                    row[2] = "Vacant"
                elif ctyluc is None:
                    row[2] == ''
            if (row[0] != None or row[0] != "") and (row[3] == 'PL'):
                if ctyluc == '90':
                    row[1] = 'GREENBELT'
                elif ctyluc == '89':
                    row[1] = 'COMMON AREA'
                elif ctyluc == '88':
                    row[1] = 'HIGHWAYS, ROADS, STREETS'
                elif ctyluc == '87':
                    row[1] = 'RIVERS, LAKES, RESERVOIR, CANAL'
                elif ctyluc == '81':
                    row[1] = 'UTILITIES, PUBLIC & PRIVATE'
                elif ctyluc == '77':
                    row[1] = 'CEMETERIES'
                elif ctyluc == '76':
                    row[1] = 'MISC. PUBLIC BUILDINGS'
                elif ctyluc == '72':
                    row[1] = 'SCHOOLS'
                elif ctyluc == '71':
                    row[1] = 'CHURCHES'
                elif ctyluc == '69':
                    row[1] = 'MISCELLANEOUS RECREATIONAL'
                elif ctyluc == '68':
                    row[1] = 'CAMPS & PARKS, GENERAL'
                elif ctyluc == '67':
                    row[1] = 'SKI FACILITY'
                elif ctyluc == '66':
                    row[1] = 'GOLF COURSE'
                elif ctyluc == '65':
                    row[1] = 'TENNIS, SWIMMING CLUBS'
                elif ctyluc == '64':
                    row[1] = 'LODGES, HALLS'
                elif ctyluc == '63':
                    row[1] = 'MARINA, PIER'
                elif ctyluc == '62':
                    row[1] = 'THEATER, BOWLING ALLEY'
                elif ctyluc == '61':
                    row[1] = 'NON-PROFIT CAMPS/PARKS'
                elif ctyluc == '60':
                    row[1] = 'CONSERVATION EASEMENT RESTRICTIONS'
                elif ctyluc == '56':
                    row[1] = 'TIMBERLAND, ZONED TPZ'
                elif ctyluc == '55':
                    row[1] = 'TIMBERLAND, UNRESTRICTED'
                elif ctyluc == '39':
                    row[1] = 'MISCELLANEOUS INDUSTRIAL'
                elif ctyluc == '38':
                    row[1] = 'WAREHOUSE'
                elif ctyluc == '37':
                    row[1] = 'MINI-STORAGE, COVERED STORAGE'
                elif ctyluc == '36':
                    row[1] = 'UNCOVERED STORAGE, WRECKING YARD'
                elif ctyluc == '32':
                    row[1] = 'HEAVY INDUSTRIAL'
                elif ctyluc == '31':
                    row[1] = 'LIGHT INDUSTRIAL'
                elif ctyluc == '30':
                    row[1] = 'VACANT INDUSTRIAL'
                elif ctyluc == '29':
                    row[1] = "MISCELLANEOUS COMM'L"
                elif ctyluc == '28':
                    row[1] = 'MOBILE HOME PARK'
                elif ctyluc == '27':
                    row[1] = 'PARKING LOTS'
                elif ctyluc == '26':
                    row[1] = 'AUTO SALES, REPAIR'
                elif ctyluc == '25':
                    row[1] = 'SERVICE STATION'
                elif ctyluc == '24':
                    row[1] = 'MINI-MARKET WITH GAS'
                elif ctyluc == '23':
                    row[1] = "BANKS, S&L'S, CREDIT UNION"
                elif ctyluc == '22':
                    row[1] = 'FAST FOOD RESTAURANT'
                elif ctyluc == '21':
                    row[1] = 'RESTAURANTS, COCKTAIL LOUNGES'
                elif ctyluc == '20':
                    row[1] = 'VACANT, COMMERCIAL'
                elif ctyluc == '19':
                    row[1] = 'OFFICE MEDICAL/DENTAL'
                elif ctyluc == '18':
                    row[1] = 'HOTELS, MOTELS, RESORTS'
                elif ctyluc == '17':
                    row[1] = 'OFFICE GENERAL'
                elif ctyluc == '16':
                    row[1] = 'RESIDENCE ON COMMERCIAL LAND'
                elif ctyluc == '15':
                    row[1] = 'SHOPPING CENTER'
                elif ctyluc == '14':
                    row[1] = 'OFFICE CONDO'
                elif ctyluc == '13':
                    row[1] = 'MINI-MARKETS, NO GAS'
                elif ctyluc == '12':
                    row[1] = 'SUBURBAN STORE'
                elif ctyluc == '11':
                    row[1] = 'COMMERCIAL STORE'
                elif ctyluc == '10':
                    row[1] = 'VACANT, SUBDIVIDED RESIDENTIAL'
                elif ctyluc == '09':
                    row[1] = 'MOBILE HOME IN M H PARK'
                elif ctyluc == '08':
                    row[1] = 'MOBILE HOME OUTSIDE OF PARK'
                elif ctyluc == '07':
                    row[1] = 'RESIDENTIAL, AUXILIARY IMP'
                elif ctyluc == '06':
                    row[1] = 'TIMESHARES'
                elif ctyluc == '05':
                    row[1] = 'APARTMENTS, 4 UNITS OR MORE'
                elif ctyluc == '04':
                    row[1] = 'SINGLE FAM RES, CONDO'
                elif ctyluc == '03':
                    row[1] = '3 SINGLE FAM RES, TRIPLEX'
                elif ctyluc == '02':
                    row[1] = '2 SINGLE FAM RES, DUPLEX'
                elif ctyluc == '01':
                    row[1] = 'SINGLE FAM RES, HALF PLEX'
                elif ctyluc == '00':
                    row[1] = 'VACANT, ALL TYPES-NOT ASGND'
                elif ctyluc is None:
                    row[1] == ''
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

    expression = f"{'APN_TRPA'} IS NULL OR {'COUNTY_TRPA'} IS NULL"

    # Use an UpdateCursor to delete records with null values
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
    arcpy.SpatialJoin_analysis(ParcelPoint, sde_Zip, ParcelPoint_PstlTown, 
                            "JOIN_ONE_TO_ONE", "KEEP_ALL", "", "HAVE_THEIR_CENTER_IN", "", "")
    print ("Finished the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))
    # log.info("Finished the Postal Town Spatial Join: " + strftime("%Y-%m-%d %H:%M:%S"))

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PSTL_TOWN_TRPA'], 
                ParcelPoint_PstlTown, ['APN_TRPA', 'COUNTY_TRPA'],['PO_NAME'])
    print ("The 'PSTL_TOWN' field in the parcel data has been updated")
    # log.info("The 'PSTL_TOWN' field in the parcel data has been updated")

    ### Postal ZIP ---------------------------------------------------------------------------------------------------###

    # transfer attributes to Parcel Layer
    fieldJoinCalc_multikey(ParcelLayer, ['APN_TRPA', 'COUNTY_TRPA'],['PSTL_ZIP5_TRPA'], 
                ParcelPoint_PstlTown, ['APN_TRPA', 'COUNTY_TRPA'],['ZIP_CODE'])
    print("The 'PSTL_ZIP5' field in the parcel data has been updated")
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
                sde_collect_IPES, ['APN', 'JURISDICTION'],['IPESScore'])
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
    
    # report how long it took to run the script
    runTime = datetime.datetime.now() - startTimer
    logger.info(f"\nTime it took to run this script: {runTime}")

    header = "SUCCESS - Parcel_County_Staging feature class updated."
    # send email with header based on try/except result
    send_mail(header)

# catch any arcpy errors
except arcpy.ExecuteError:
    logger.error(arcpy.GetMessages())

    header = "ERROR - Arcpy Exception - Check Log"
    # send email with header based on try/except result
    send_mail(header)

# catch system errors
except Exception:
    e = sys.exc_info()[1]
    logger.info(e.args[0])
    logger.error(e)
    header = "ERROR - System Error - Check Log"
    # send email with header based on try/except result
    send_mail(header)



