"""
ParcelTables_to_ParcelFeatures.py
Created: March 13th, 2020
Last Updated: June 14th, 2023
Mason Bindl, Tahoe Regional Planning Agency
Amy Fish, Tahoe Regional Planning Agency

This python script was developed to move data from 
Accela, LTinfo, and BMP databases to TRPA's dynamic Enterprise Geodatabase.
This ETL process updates parcel based feature classes for Development Rights, BMPs, LCVs, LCCs, 
Historic Parcels, Securities, Grading Exceptions, Deed Restrictions, and Soils Hydro Projects

This script uses Python 3.x and was designed to be used with 
the default ArcGIS Pro python enivorment ""C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe"", with
no need for installing new libraries.

This script runs nightly at 10pm on Arc10 from scheduled task "ParcelETL"
"""
#--------------------------------------------------------------------------------------------------------#
# import packages and modules
# base packages
import os
import sys
import logging
from datetime import datetime
import pandas as pd
import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy import create_engine
# ESRI packages
import arcpy
from arcgis.features import FeatureSet, GeoAccessor, GeoSeriesAccessor
# email packages
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# set overwrite to true
arcpy.env.overwriteOutput = True
arcpy.env.workspace = "C:\GIS\Scratch.gdb"

# in memory output file path
wk_memory = "memory" + "\\"
# set workspace and sde connections 
working_folder = "C:\GIS"
workspace      = "C:\GIS\Scratch.gdb"

# network path to connection files
filePath = "C:\\GIS\\DB_CONNECT"
# database file path 
sdeBase = os.path.join(filePath, "Vector.sde")
sdeCollect = os.path.join(filePath, "Collection.sde")
# Feature dataset to unversion and register as version
fdata = sdeCollect + "\\sde_collection.SDE.Parcel"
# string to use in updaetSDE function
sdeString  = fdata + "\\sde_collection.SDE."

# connect to bmp SQL dataabase
connection_string = "DRIVER={ODBC Driver 17 for SQL Server};SERVER=sql14;DATABASE=tahoebmpsde;UID=sde;PWD=staff"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
engine = create_engine(connection_url)

##--------------------------------------------------------------------------------------#
## EMAIL and LOG FILE SETTINGS ##
##--------------------------------------------------------------------------------------#
## LOGGING SETUP
# Configure the logging
log_file_path = os.path.join(working_folder, "Parcel_Development_ETL_Log.log")  
# setup basic logging configuration
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=log_file_path,  # Set the log file path
                    filemode='w')
# Create a logger
logger = logging.getLogger(__name__)
# Log start message
logger.info("Script Started: " + str(datetime.datetime.now()) + "\n")

## EMAIL SETUP
# path to text file
fileToSend = log_file_path
# email parameters
subject = "Parcel Development ETL"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "mbindl@trpa.gov"

#---------------------------------------------------------------------------------------#
## FUNCTIONS ##
#---------------------------------------------------------------------------------------#

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

# # update staging layers
def updateStagingLayer(name, df, fields):
    # copy fields to keep
    dfOut = df[fields].copy()
    # specify output feature class
    outFC = os.path.join(workspace, name)
    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)
    # confirm feature class was created
    print(f"\nUpdated staging layer:{outFC}")
    logger.info(f"\nUpdated staging layer:{outFC}")

# replaces features in outfc with exact same schema
def updateSDECollectFC(fcList):
    for fc in fcList:
        inputFC = os.path.join(workspace, fc)
        dsc = arcpy.Describe(inputFC)
        fields = dsc.fields
        out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
        fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]
        outfc = sdeString + fc
        # deletes all rows from the SDE feature class
        arcpy.TruncateTable_management(outfc)
        logger.info("\nDeleted all records in: {}\n".format(outfc))
        from time import strftime  
        logger.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
        # insert rows from Temporary feature class to SDE feature class
        with arcpy.da.InsertCursor(outfc, fieldnames) as oCursor:
            count = 0
            with arcpy.da.SearchCursor(inputFC, fieldnames) as iCursor:
                for row in iCursor:
                    oCursor.insertRow(row)
                    count += 1
                    if count % 100 == 0:
                        logger.info("Inserting record %d into %s SDE feature class" % (count, outfc))
                logger.info(f"\nDone updating: {outfc}")
            

#---------------------------------------------------------------------------------------#
## GET DATA
#---------------------------------------------------------------------------------------#

# start timer for the get data requests
startTimer = datetime.datetime.now()

# get feature classes from enterprise geodatabase
bonusBoundary= os.path.join(sdeBase, "sde.SDE.Planning\sde.SDE.Bonus_unit_boundary")
mfAllowed    = os.path.join(sdeBase, "sde.SDE.Planning\sde.SDE.Multifamily_Allowed_Zone")
parcelMaster = os.path.join(sdeBase, "sde.SDE.Parcels\\sde.SDE.Parcel_Master")
parcelIPES   = os.path.join(sdeCollect, fdata, "sde_collection.SDE.Parcel_LTinfo_IPES")
parcelDeed   = os.path.join(sdeCollect, fdata, "sde_collection.SDE.Parcel_LTinfo_DeedRestriction")

# create spatial dataframe from parcel master SDE
sdfParcels = pd.DataFrame.spatial.from_featureclass(parcelMaster)
sdfIPES    = pd.DataFrame.spatial.from_featureclass(parcelIPES)
sdfDeed    = pd.DataFrame.spatial.from_featureclass(parcelDeed)

# report how long it took to get the data
endTimer = datetime.datetime.now() - startTimer
print("\nTime it took to get the data: {}".format(endTimer))   
logger.info("\nTime it took to get the data: {}".format(endTimer)) 


#---------------------------------------------------------------------------------------#
## TRANSFORM TO STAGING LAYERS
#---------------------------------------------------------------------------------------#
# join IPES, join Deed, MF Allowed Spatial Join, field calc of % allowed

try:
    #---------------------------------------------------------------------------------------#
    # CREATE STAGING LAYERS ##
    #---------------------------------------------------------------------------------------#
    # start timer for the get data requests
    startTimer = datetime.datetime.now()
    #---------------------------------------------------------------------------------------#

    # name of feature class
    name = "Parcel_Development"

    # spatial join

    # List of DataFrames
    dfs = [sdfParcels, sdfDeed, sdfIPES]

    # Merge DataFrames horizontally
    combined_df = pd.merge(dfs[0], dfs[1], on='APN')
    for df in dfs[2:]:
        combined_df = pd.merge(combined_df, df, on='APN')

    # Print the combined DataFrame
    print(combined_df)
    # specify fields to keep
    fields = ['APN',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'ESTIMATED_COVERAGE_ALLOWED',
            'PARCEL_SQFT',
            'RecordingNumber',
            'RecordingDate',
            'Description',
            'DeedRestrictionStatus',
            'DeedRestrictionType',
            'ProjectAreaFileNumber',
            'ScoreSheetUrl',
            'Status',
            'ParcelNickname',
            'IPESScore',
            'IPESScoreType',
            'BaseAllowableCoveragePercent',
            'IPESTotalAllowableCoverageSqFt',
            'ParcelHasDOAC',
            'HistoricOrImportedIpesScore',
            'CalculationDate',
            'FieldEvaluationDate',
            'RelativeErosionHazardScore',
            'RunoffPotentialScore',
            'AccessScore',
            'UtilityInSEZScore',
            'ConditionOfWatershedScore',
            'AbilityToRevegetateScore',
            'WaterQualityImprovementsScore',
            'ProximityToLakeScore',
            'LimitedIncentivePoints',
            'TotalParcelArea',
            'IPESBuildingSiteArea',
            'SEZLandArea',
            'SEZSetbackArea',
            'InternalNotes',
            'PublicNotes',
            'SHAPE']
            
    # update staging feature class from dataframe
    updateStagingLayer(name, combined_df, fields)
    
    #---------------------------------------------------------------------------------------#
    # report how long it took to get the data
    endTimer = datetime.datetime.now() - startTimer
    print("\nTime it took to create staging layers: {}".format(endTimer))       
    #---------------------------------------------------------------------------------------#

    ##--------------------------------------------------------------------------------------------------------#
    ## BEGIN SDE UPDATES ##
    ##--------------------------------------------------------------------------------------------------------#

#     # disconnect all users
#     print("\nDisconnecting all users...")
#     arcpy.DisconnectUser(sdeCollect, "ALL")

#     # unregister the sde feature class as versioned
#     print ("\nUnregistering feature dataset as versioned...")
#     arcpy.UnregisterAsVersioned_management(fdata,"NO_KEEP_EDIT","COMPRESS_DEFAULT")
#     print ("\nFinished unregistering feature dataset as versioned.")

#     # #---------------------------------------------------------------------------------------#

#     # feature class list
#     fcs =["Parcel_Development"]

#     # function to update all collection SDE feature classes in list
#     updateSDECollectFC(fcs)

#     #---------------------------------------------------------------------------------------#
#     # report how long it took to get the data
#     endTimer = datetime.datetime.now() - startTimer 
#     logger.info(f"\nTime it took to update Collection SDE feature classes: {endTimer}") 
#     #---------------------------------------------------------------------------------------#

#     ##--------------------------------------------------------------------------------------------------------#
#     ## END OF UPDATES ##
#     ##--------------------------------------------------------------------------------------------------------#

#     # disconnect all users
#     print("\nDisconnecting all users...")
#     logger.info("\nDisconnecting all users...")
#     arcpy.DisconnectUser(sdeCollect, "ALL")

#     print("\nRegistering feature dataset as versioned...")
#     logger.info("\nRegistering feature dataset as versioned...")
#     # register SDE feature class as versioned
#     arcpy.RegisterAsVersioned_management(fdata, "NO_EDITS_TO_BASE")
#     print("\nFinished registering feature dataset as versioned.")
#     logger.info("\nFinished registering feature dataset as versioned.")
    
    # report how long it took to run the script
    runTime = datetime.datetime.now() - startTimer
    logger.info(f"\nTime it took to run this script: {runTime}")

    # send email with header based on try/except result
    header = "SUCCESS - Parcel feature classes were updated."
    send_mail(header)
    print('Sending email...')

# catch any arcpy errors
except arcpy.ExecuteError:
    print(arcpy.GetMessages())
    logger.debug(arcpy.GetMessages())
    # send email with header based on try/except result
    header = "ERROR - Arcpy Exception - Check Log"
    send_mail(header)
    print('Sending email...')

# catch system errors
except Exception:
    e = sys.exc_info()[1]
    print(e.args[0])
    logger.debug(e)
    # send email with header based on try/except result
    header = "ERROR - System Error - Check Log"
    send_mail(header)
    print('Sending email...')
