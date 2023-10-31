"""
GradingExceptions_to_ParcelFeatures_ETL.py
Created: October 15th, 2023
Last Updated: October 20th, 2023
Mason Bindl, Tahoe Regional Planning Agency
Amy Fish, Tahoe Regional Planning Agency
Andy McClary, Tahoe Regional Planning Agency

This python script was developed to move data from 
Accela reprots to TRPA's dynamic Enterprise Geodatabase.
This ETL process updates parcel based feature classes for Grading Exceptions.

This script uses Python 3.x and was designed to be used with 
the default ArcGIS Pro python enivorment 
""C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe"", 
with no need for installing new libraries.

This script runs nightly at 10pm on Arc10 from scheduled task "Grading Exception ETL"
"""
#-------------------------------------------------------------------------------------------------------------------
# import packages
import pandas as pd
import arcpy
import os
import sys
import logging
from datetime import datetime
from arcgis.features import FeatureSet, GeoAccessor, GeoSeriesAccessor
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from boxsdk import OAuth2, Client, CCGAuth

# set overwrite to true
arcpy.env.overwriteOutput = True

# in memory output file path
memory = "memory" + "\\"

# set workspace and sde connections 
working_folder      = "C:\GIS"
workspace           = "C:\GIS\Scratch.gdb"
arcpy.env.workspace = "C:\GIS\Scratch.gdb"

# network path to connection files
filePath   = "C:\\GIS\\DB_CONNECT"
sdeBase    = os.path.join(filePath, "Vector.sde")
sdeCollect = os.path.join(filePath, "Collection.sde")

# Feature dataset to unversion and register as version
fdata = sdeCollect + "\\sde_collection.SDE.Parcel"

# Configure the logging
log_file_path = os.path.join(working_folder, "GradingException.log")  # Specify the path to your local directory
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=log_file_path,  # Set the log file path
                    filemode='w')

# Create a logger
logger = logging.getLogger(__name__)

# start a timer for the entire script run
FIRSTstartTimer = datetime.now()

# Log different types of messages
logger.info("Script Started: " + str(FIRSTstartTimer) + "\n")

#---------------------------------------------------------------------------------------#
## Define Functions ##
#---------------------------------------------------------------------------------------#
##--------------------------------------------------------------------------------------------------------#
## SEND EMAIL WITH LOG FILE ##
##--------------------------------------------------------------------------------------------------------#
# path to text file
fileToSend = log_file_path
# email parameters
subject = "Grading Exception ETL Log File"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "gis@trpa.gov"

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

# replaces features in outfc with exact same schema
def updateSDE(inputfc,outfc, fieldnames, log):
    # deletes all rows from the SDE feature class
    arcpy.TruncateTable_management(outfc)
    log.info("\nDeleted all records in: {}\n".format(outfc))
    from time import strftime  
    log.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    # insert rows from Temporary feature class to SDE feature class
    with arcpy.da.InsertCursor(outfc, fieldnames) as oCursor:
        count = 0
        with arcpy.da.SearchCursor(inputfc, fieldnames) as iCursor:
            for row in iCursor:
                oCursor.insertRow(row)
                count += 1
                if count % 100 == 0:
                    log.info("Inserting record %d into %s SDE feature class" % (count, outfc))
            log.info("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
            log.info("\nDone updating: %s"%(outfc))


#---------------------------------------------------------------------------------------#
# EXTRACT DATA FROM BOX
#---------------------------------------------------------------------------------------#
# Box API credentials

auth = CCGAuth(
  client_id="pusxamhqx4urav2lj847darrr1niydzp",
  client_secret="tmnxqxp8sSY6i24OPX2bAYFrnIA3cerZ",
  user="21689880902"
)
client = Client(auth)

# # setup box connection with oauth2
# clientId        = 'pusxamhqx4urav2lj847darrr1niydzp'
# clientSecret    = 'tmnxqxp8sSY6i24OPX2bAYFrnIA3cerZ'
# accessToken     = '0H8G8Pq1Ze8OAimuuHUFixvrHVvOWyU2'
# oauth2 = OAuth2(clientId, clientSecret, access_token=accessToken)
# client = Client(oauth2)

# grading exception BOX file id
fileID = '1337039879890'

# Get the file object
file = client.file(fileID).get()

if file:
    # local file to overwrite
    local_file_path = "//trpa-fs01/GIS/Acella/Reports/Grading_Exception_Map.csv"
    # Download and save the file
    with open(local_file_path, 'wb') as local_file:
        file.download_to(local_file)
    logger.info(f'File downloaded and saved as: {local_file_path}')
else:
    logger.info(f'Error downloading file. File not found.')

#---------------------------------------------------------------------------------------#
# TRANSFORM DATA
#---------------------------------------------------------------------------------------#
# start timer for the get data requests
startTimer = datetime.now()

# local csv file location
accelaFiles = "//trpa-fs01/GIS/Acella/Reports"
# make dataframes from exported accela views
dfGrade = pd.read_csv(os.path.join(accelaFiles, "Grading_Exception_Map.csv"))

# create spatial dataframe from parcel master in sde
parcels = sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcel_Master"
sdfParcels = pd.DataFrame.spatial.from_featureclass(parcels)
       
# report how long it took to get the data
endTimer = datetime.now() - startTimer

logger.info("\nTime it took to get the data: {}".format(endTimer))   
# creating staging data
try:
    #---------------------------------------------------------------------------------------#
    ## CREATE STAGING LAYER ##
    #---------------------------------------------------------------------------------------#
    # start timer for the get data requests
    startTimer = datetime.now()
    #---------------------------------------------------------------------------------------#
    #---------------------------------------------------------------------------------------#

    ## Create feature class of historic designations
    # name of feature class
    name = "Parcel_GradingExceptions"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfGrade, left_on='APN', right_on='PARCEL_NUMBER', how='left')

    #drop null parcels that dont have joined attributes
    df = df.dropna(subset=["PARCEL_NUMBER"])

    # # specify fields to keep
    dfOut = df[["APN", 
                "APO_ADDRESS", 
                'B1_ALT_ID',
                'Start_Date',
                'End_Date',
                'Description',
                "SHAPE"]].copy()

    dfOut = dfOut.rename(columns={'APN':'apn',
                                'APO_ADDRESS':'property_address',
                                'End_Date':'approved_ending_date',
                                'Start_Date':'approved_beginning_date',
                                'B1_ALT_ID':'file_number',
                                'Description':'comment'})

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    logger.info("\nUpdated staging layer: " + outFC)
    # report how long it took to get the data
    endTimer = datetime.now() - startTimer
    logger.info("\nTime it took to create staging layers: {}".format(endTimer))

    #--------------------------------------------------------------------------------------------------------#
    # LOAD DATA TO COLLECTION SDE
    #--------------------------------------------------------------------------------------------------------#
    
    # start timer for the get data requests
    startTimer = datetime.now()

    # disconnect all users
    logger.info("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    # unregister the sde feature class as versioned
    logger.info("\nUnregistering feature dataset as versioned...")
    arcpy.UnregisterAsVersioned_management(fdata,"NO_KEEP_EDIT","COMPRESS_DEFAULT")
    logger.info("\nFinished unregistering feature dataset as versioned.")
    # Update Parcel_GradingExceptions

    # input staging feature class
    inputFC = "Parcel_GradingExceptions"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_Accela_GradingExceptions"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update SDE function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames, logger)

    # disconnect all users
    logger.info("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    logger.info("\nRegistering feature dataset as versioned...")
    # register SDE feature class as versioned
    arcpy.RegisterAsVersioned_management(fdata, "NO_EDITS_TO_BASE")
    logger.info("\nFinished registering feature dataset as versioned.")

    # report how long it took to run the script
    FINALendTimer = datetime.now() - FIRSTstartTimer
    logger.info("\nTime it took to run this script: {}".format(FINALendTimer))
   
    header = "SUCCESS - The Grading Exception feature class was updated."
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

#--------------------------------------------------------------------------------------------------------#
# THE END
#--------------------------------------------------------------------------------------------------------#
