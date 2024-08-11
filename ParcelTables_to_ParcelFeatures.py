"""
ParcelTables_to_ParcelFeatures.py
Created: March 13th, 2020
Last Updated: 8/11/2024
Tahoe Regional Planning Agency
GIS Team, gis@trpa.gov

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

# ESRI packages
import arcpy
from arcgis.features import GeoAccessor
from arcgis.features import GeoSeriesAccessor
from arcgis.features import FeatureSet

# external connection packages
import requests
from boxsdk import Client, CCGAuth
import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy import create_engine

# email packages
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# set overwrite to true
arcpy.env.overwriteOutput = True
arcpy.env.workspace = "C:\GIS\Staging.gdb"

# in memory output file path
wk_memory = "memory" + "\\"
# set workspace and sde connections 
working_folder = "C:\GIS"
workspace      = "C:\GIS\Staging.gdb"

# network path to connection files
filePath = "C:\\GIS\\DB_CONNECT"
# database file path 
sdeBase = os.path.join(filePath, "Vector.sde")
sdeCollect = os.path.join(filePath, "Collection.sde")
sdeTabular = os.path.join(filePath, "Tabular.sde")

# Feature dataset to unversion and register as version
fdata = sdeCollect + "\\sde_collection.SDE.Parcel"
# string to use in updaetSDE function
sdeString  = fdata + "\\sde_collection.SDE."

# local path to stage csvs in
accelaFiles = "//trpa-fs01/GIS/Acella/Reports"

# Get database user and password from environment variables
db_user             = os.environ.get('DB_USER')
db_password         = os.environ.get('DB_PASSWORD')
#db_user             = 'sde'
#db_password         = 'staff'
driver              = 'ODBC Driver 17 for SQL Server'
tabular_database    = 'sde_tabular'
serverSQL12         = 'sql12'
bmp_database        = 'tahoebmpsde'
serverSQL14         = 'sql14'

# connect to BMP SQL dataabase
BMP_connection_string = f"DRIVER={driver};SERVER={serverSQL14};DATABASE={bmp_database};UID={db_user};PWD={db_password}"
BMP_connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": BMP_connection_string})
BMP_engine = create_engine(BMP_connection_url)

# connect to Tabular SQL dataabase
connection_string = f"DRIVER={driver};SERVER={serverSQL12};DATABASE={tabular_database};UID={db_user};PWD={db_password}"
connection_url = URL.create("mssql+pyodbc", query={"odbc_connect": connection_string})
Tab_engine = create_engine(connection_url)

# Box API credentials setup with CCGAuth
auth = CCGAuth(
  client_id     = "pusxamhqx4urav2lj847darrr1niydzp",
  client_secret = "tmnxqxp8sSY6i24OPX2bAYFrnIA3cerZ",
  user          = "21689880902"
)
# setup client for BOX connection
client = Client(auth)

##--------------------------------------------------------------------------------------#
## EMAIL and LOG FILE SETTINGS ##
##--------------------------------------------------------------------------------------#
## LOGGING SETUP
# Configure the logging
log_file_path = os.path.join(working_folder, "Logs\Parcel_Tables_to_Features.log")  
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
subject = "Parcel Tables to Parcel Features ETL"
sender_email = "infosys@trpa.org"
# password = ''
receiver_email = "gis@trpa.gov"

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

# Execute a query
def insert_into_sql(df, table, chunksize=1000):
    # add ObjectId column to the dataframe
    if 'OBJECTID' not in df.columns:
        df['OBJECTID'] = range(1, len(df) + 1)
    # create a connection to the database
    conn = Tab_engine.connect()
    # delete the existing rows from the table
    conn.execute(f"DELETE FROM {table}")
    # insert the rows into the table in chunks
    df.to_sql(table, conn, if_exists='append', index=False, schema= 'dbo',chunksize=chunksize)
    # log the number of rows inserted
    logger.info(f"{len(df)} rows inserted into {table} table")
    # close the connection
    conn.close()

            
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
            
# get box files
def getAccelaBOXfiles(fileDict):
    for fileName, fileID in fileDict.items():
        # Get the file object
        file = client.file(fileID).get()
        if file:
            # local file to overwrite
            local_file_path = os.path.join(accelaFiles, fileName)
            # Download and save the file
            with open(local_file_path, 'wb') as local_file:
                file.download_to(local_file)
                logger.info(f'File downloaded and saved as: {local_file_path}')
        else:
            logger.info(f'Error downloading file. File not found.')

# get the bigger accela report data via the API ESA setup on LTinfo
def getAccelaLTinfoFiles(xlsDict):
    for xlsName,api_url in xlsDict.items():
        # Send a GET request to the API
        response = requests.get(api_url)
        if response.status_code == 200:
            # If the request is successful, save the CSV content to a file
            with open(os.path.join(accelaFiles,xlsName), "wb") as xls_file:
                xls_file.write(response.content)
            logger.info(f"Excel file saved as {xlsName}")
        else:
            logger.info(f"Failed to fetch data from the API. Status code: {response.status_code}")

# replace the spaces in the column names with underscores
def clean_column_names(df):
    df.columns = df.columns.str.replace(" ", "_")
    return df

#---------------------------------------------------------------------------------------#
## GET DATA
#---------------------------------------------------------------------------------------#

# start timer for the get data requests
startTimer = datetime.datetime.now()

# dictionary of acella reports from ltinfo (check with ESA for updates or issues to their API)
ltinfoDict = {'Accela_Parcels.xlsx'         : 'https://laketahoeinfo.org/Api/GetAccelaParcelsExcel/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4',
              'Accela_Record_Details.xlsx'  : 'https://laketahoeinfo.org/Api/GetAccelaRecordDetailsExcel/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4',
            #   'Accela_Record_Documents.csv': 'https://laketahoeinfo.org/Api/GetAccelaRecordDocumentsExcel/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4'
             }

# dictionary of csv name and box file ID
boxDict = {'Land_Capable_Verifications.csv': "1342591986420",
           'Land_Capability_Challenge.csv' : "1342590467197",
           'Hydro_Soils.csv'              : "1342592456757",
           'Grading_Exception_Map.csv'      : "1337039879890",
           'Historic_Designations.csv'     : "1342590117002"
           }


# function to save Accela Reports from LTinfo API
getAccelaLTinfoFiles(ltinfoDict)

# function to save Accela Reports from Box
getAccelaBOXfiles(boxDict)

# make dataframes from exported accela views
dfLCV      = pd.read_csv(os.path.join(accelaFiles, 'Land_Capable_Verifications.csv'))
dfLCC      = pd.read_csv(os.path.join(accelaFiles, 'Land_Capability_Challenge.csv'))
dfSoil     = pd.read_csv(os.path.join(accelaFiles, 'Hydro_Soils.csv'))
dfHist     = pd.read_csv(os.path.join(accelaFiles, 'Historic_Designations.csv'))
dfGrade    = pd.read_csv(os.path.join(accelaFiles, 'Grading_Exception_Map.csv'))
# dfSecurity = pd.read_csv(os.path.join(accelaFiles, 'Accela_Security.csv'))
dfAParcel  = pd.read_excel(os.path.join(accelaFiles, 'Accela_Parcels.xlsx'))
dfAPermit  = pd.read_excel(os.path.join(accelaFiles, 'Accela_Record_Details.xlsx'))
# dfADoc     = pd.read_csv(os.path.join(accelaFiles, 'Accela_Record_Documents.xlsx'))

# get BMP Status data as dataframe from BMP SQL Database
with BMP_engine.begin() as bmpConnect:
    dfBMP      = pd.read_sql("SELECT * FROM tahoebmpsde.dbo.v_BMPStatus", bmpConnect)

# LTInfo - create dataframes from JSON found here: https://laketahoeinfo.org/WebServices/List
dfLTAPN    = pd.read_json("https://laketahoeinfo.org/WebServices/GetAllParcels/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfIPES     = pd.read_json("https://laketahoeinfo.org/WebServices/GetParcelIPESScores/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfLCVinfo  = pd.read_json("https://laketahoeinfo.org/WebServices/GetParcelsByLandCapability/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDRBank   = pd.read_json("https://laketahoeinfo.org/WebServices/GetBankedDevelopmentRights/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDRTrans  = pd.read_json("https://laketahoeinfo.org/WebServices/GetTransactedAndBankedDevelopmentRights/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDeed     = pd.read_json("https://laketahoeinfo.org/WebServices/GetDeedRestrictedParcels/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")

# create spatial dataframe from parcel master SDE
parcels = sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcel_Master"
sdfParcels = pd.DataFrame.spatial.from_featureclass(parcels)
       
# report how long it took to get the data
endTimer = datetime.datetime.now() - startTimer
print("\nTime it took to get the data: {}".format(endTimer))   
logger.info("\nTime it took to get the data: {}".format(endTimer)) 

#---------------------------------------------------------------------------------------#
## TRANSFORM TABLES INTO STAGING LAYERS
#---------------------------------------------------------------------------------------#

try:
    #---------------------------------------------------------------------------------------#
    # CREATE STAGING LAYERS ##
    #---------------------------------------------------------------------------------------#
    # start timer for the get data requests
    startTimer = datetime.datetime.now()
    #---------------------------------------------------------------------------------------#

    # Create BMP feature class
    # name of feature class
    name = "Parcel_BMP"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfBMP, on='APN', how='inner')
    
    # specify fields to keep
    fields = ['APN',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'CertificateIssued',
            'EvaluationComplete',
            'SourceCertIssued',
            'CertDate',
            'CertReissuedDate',
            'LandUse',
            'BMPStatus',
            'Catchment',
            'SourceCertDate',
            'SiteConstraint',
            'ParcelStreet',
            'CreditPercent',
            'AreaWide',
            'AreaWidePlanName',
            'CreditArea',
            'Rvkd',
            'TMDL_LandUse',
            'OwnerName',
            'SourceCertReissuedDate',
            'SourceCertNo',
            'CertNo',
            'SHAPE']

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of Land Capability Verifications
    # name of feature class
    name = "Parcel_Accela_LandCapabilityVerification"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCV, left_on='APN', right_on='GIS_ID', how='inner')
    # rename some of the fields
    df.rename(columns={"LABEL_FIELD": "Status"}, inplace=True)
    
    # specify fields to keep
    fields = ["APN", 
            "Status", 
            "SHAPE"]

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    # -----------------------------------------------------------------------------------#

    ## Create feature class of LCV Challenges
    # name of feature class
    name = "Parcel_Accela_LCV_Challenge"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCC, left_on='APN', right_on='GIS_ID', how='inner')
    # rename some of the fields
    df.rename(columns={"REC_DATE": "Date", "LABEL_FIELD": "Status"}, inplace=True)
    
    # specify fields to keep
    fields = ["APN", 
            "Date", 
            "Status", 
            "SHAPE"]

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    # -------------------------------------------------------------------------------------#

    ## Create feature class of SOILS/Hydro Project
    # name of feature class
    name = "Parcel_Accela_SoilsHydro"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfSoil, left_on='APN', right_on='GIS_ID', how='inner')
    # rename some of the fields
    df.rename(columns={"LABEL_FIELD": "Status"}, inplace=True)
    
    # specify fields to keep
    fields = ["APN",
            "Status", 
            "SHAPE"]

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    ##--------------------------------------------------------------------------------------#

    ## Create feature class of historic designations
    # name of feature class
    name = "Parcel_Accela_Historic"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfHist, left_on='APN', right_on='GIS_ID', how='inner')
    # rename some of the fields
    df.rename(columns={"REC_DATE": "Date", "LABEL_FIELD": "Status"}, inplace=True)
    
    fields = ['APN',
            'Status',
            'Date',
            'SHAPE']

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of historic designations
    # name of feature class
    name = "Parcel_Accela_GradingExceptions"
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

### The report fields changed so we renamed to match the feature class
    dfOut.rename(columns={
                'APN':'apn',
                'APO_ADDRESS':'property_address',
                'End_Date':'approved_ending_date',
                'Start_Date':'approved_beginning_date',
                'B1_ALT_ID':'file_number',
                'Description':'comment'}, 
                inplace=True)

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)
    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    # #---------------------------------------------------------------------------------------#

    ## Create feature class of LT Info parcels
    # name of feature class
    name = "Parcel_LTinfo"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLTAPN, on='APN', how='inner')
    
    # create fields list
    fields = ['APN',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'ParcelNickname',
            'ParcelSize',
            'Status',
            'RetiredFromDevelopment',
            'IsAutoImported',
            'OwnerName',
            'ParcelAddress',
            'Jurisdiction',
            'ParcelNotes',
            'LocalPlan',
            'FireDistrict',
            'ParcelWatershed',
            'BMPStatus',
            'HRA',
            'HasMooringRegistration',
            'SFRUU',
            'RBU',
            'TAU',
            'CFA',
            'RFA',
            'TFA',
            'PRUU',
            'MFRUU',
            'SHAPE']

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of LT Info parcels
    # name of feature class
    name = "Parcel_LTinfo_IPES"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfIPES, on='APN', how='inner')
    
    # create fields list
    fields = ['APN',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
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
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#

    # name of feature class
    name = "Parcel_LTinfo_LCV"
    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCVinfo, on='APN', how='inner')
    
    # specify fields to keep
    fields = ['APN',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'Status',
            'ParcelNickname',
            'TotalAreaSqFt',
            'UpdatedBy',
            'UpdatedOn',
            'DeterminationDate',
            'EstimatedOrVerified',
            'SitePlanUrl',
            'AccelaCAPRecord',
            'Bailey1aPresent',
            'Bailey1aSqFt',
            'Bailey1bPresent',
            'Bailey1bSqFt',
            'Bailey1cPresent',
            'Bailey1cSqFt',
            'Bailey2Present',
            'Bailey2SqFt',
            'Bailey3Present',
            'Bailey3SqFt',
            'Bailey4Present',
            'Bailey4SqFt',
            'Bailey5Present',
            'Bailey5SqFt',
            'Bailey6Present',
            'Bailey6SqFt',
            'Bailey7Present',
            'Bailey7SqFt',
            'IPESPresent',
            'IPESSqFt',
            'SHAPE']

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#
    
    # feature class to update
    name = "Parcel_LTinfo_DevelopmentRight_Banked"
    
    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDRBank, on='APN', how='inner')

    # specify fields to keep
    fields = ['APN',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'DevelopmentRight',
            'LandCapability',
            'IPESScore',
            'CumulativeBankedQuantity',
            'RemainingBankedQuantity',
            'Jurisdiction',
            'LocalPlan',
            'DateBankedOrApproved',
            'HRA',
            'LastUpdated',
            'SHAPE'] 

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)

    #---------------------------------------------------------------------------------------#
    # feature class to update
    name = "Parcel_LTinfo_DevelopmentRight_Transacted_Banked"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDRTrans, on='APN', how='left')
    
    # specify fields to keep
    fields = ['APN',
            'APO_ADDRESS',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'RecordType',
            'DevelopmentRight',
            'LandCapability',
            'IPESScore',
            'CumulativeBankedQuantity',
            'RemainingBankedQuantity',
            'Jurisdiction',
            'LocalPlan',
            'DateBankedOrApproved',
            'HRA',
            'LastUpdated',
            'TransactionNumber',
            'TransactionApprovalDate',
            'SendingParcel',
            'ReceivingParcel',
            'LandBank',
            'SHAPE']

    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)
    
    #---------------------------------------------------------------------------------------#
    
    # name of feature class
    name = "Parcel_LTinfo_DeedRestriction"

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDeed, on='APN', how='left')

    # specify fields to keep
    fields = ['APN',
            'APO_ADDRESS',
            'OWN_FULL',
            'MAIL_ADD1',
            'MAIL_ADD2',
            'MAIL_CITY',
            'MAIL_STATE',
            'MAIL_ZIP5',
            'JURISDICTION',
            'OWNERSHIP_TYPE',
            'EXISTING_LANDUSE',
            'RecordingNumber',
            'RecordingDate',
            'Description',
            'DeedRestrictionStatus',
            'DeedRestrictionType',
            'ProjectAreaFileNumber',
            'SHAPE']
            
    # update staging feature class from dataframe
    updateStagingLayer(name, df, fields)
    
    #---------------------------------------------------------------------------------------#
    # report how long it took to get the data
    endTimer = datetime.datetime.now() - startTimer
    print("\nTime it took to create staging layers: {}".format(endTimer))       
    #---------------------------------------------------------------------------------------#

    ##--------------------------------------------------------------------------------------------------------#
    ## BEGIN SDE UPDATES ##
    ##--------------------------------------------------------------------------------------------------------#

    # disconnect all users
    print("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    # unregister the sde feature class as versioned
    print ("\nUnregistering feature dataset as versioned...")
    arcpy.UnregisterAsVersioned_management(fdata,"NO_KEEP_EDIT","COMPRESS_DEFAULT")
    print ("\nFinished unregistering feature dataset as versioned.")

    # #---------------------------------------------------------------------------------------#

    # feature class list
    fcs =["Parcel_BMP",
        "Parcel_Accela_LandCapabilityVerification",
        "Parcel_Accela_LCV_Challenge",
        "Parcel_Accela_SoilsHydro",
        "Parcel_Accela_Historic",
        "Parcel_Accela_GradingExceptions",
        "Parcel_LTinfo",
        "Parcel_LTinfo_IPES",
        "Parcel_LTinfo_LCV",
        "Parcel_LTinfo_DevelopmentRight_Banked",
        "Parcel_LTinfo_DevelopmentRight_Transacted_Banked",
        "Parcel_LTinfo_DeedRestriction"
        ]

    # function to update all collection SDE feature classes in list
    updateSDECollectFC(fcs)

    #---------------------------------------------------------------------------------------#

    # clean the column names
    dfAParcel = clean_column_names(dfAParcel)
    dfAPermit = clean_column_names(dfAPermit)

    # # insert the dataframes into the SQL database
    insert_into_sql(dfAParcel, "Accela_Parcels")
    insert_into_sql(dfAPermit, "Accela_Record_Details")
    #---------------------------------------------------------------------------------------#

    # report how long it took to get the data
    endTimer = datetime.datetime.now() - startTimer 
    logger.info(f"\nTime it took to update Collection SDE feature classes: {endTimer}") 
    #---------------------------------------------------------------------------------------#

    ##--------------------------------------------------------------------------------------------------------#
    ## END OF UPDATES ##
    ##--------------------------------------------------------------------------------------------------------#

    # disconnect all users
    print("\nDisconnecting all users...")
    logger.info("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    print("\nRegistering feature dataset as versioned...")
    logger.info("\nRegistering feature dataset as versioned...")
    # register SDE feature class as versioned
    arcpy.RegisterAsVersioned_management(fdata, "NO_EDITS_TO_BASE")
    print("\nFinished registering feature dataset as versioned.")
    logger.info("\nFinished registering feature dataset as versioned.")
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
