"""
ParcelTables_to_ParcelFeatures.py
Created: March 13th, 2020
Last Updated: 9/11/2026
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

The LT Info API was refactored in Sept 2026
"""
#--------------------------------------------------------------------------------------------------------#
# import packages and modules
# base packages
import os
import sys
import json
import logging
from datetime import datetime
from time import strftime
import numpy as np
import pandas as pd
import traceback

# ESRI packages
import arcpy
from arcgis.features import GeoAccessor
from arcgis.features import GeoSeriesAccessor
from arcgis.features import FeatureSet

# SQL, email, and box connections
import requests
from boxsdk import Client, CCGAuth
import sqlalchemy as sa
from sqlalchemy.engine import URL
from sqlalchemy import text
from sqlalchemy import create_engine
import smtplib
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# set overwrite to true
arcpy.env.overwriteOutput = True
arcpy.env.workspace = r"C:\GIS\Staging.gdb"

# set workspace and sde connections and memory paths
working_folder = r"C:\GIS"
workspace      = r"C:\GIS\Staging.gdb"
wk_memory = "memory" + "\\"

# network path to connection files
filePath = "C:\\GIS\\DB_CONNECT"
# database file path 
sdeBase = os.path.join(filePath, "Vector.sde")
sdeCollect = os.path.join(filePath, "Collection.sde")
sdeTabular = os.path.join(filePath, "Tabular.sde")

# Feature dataset to unversion and register as version
fdata = sdeCollect + "\\sde_collection.SDE.Parcel"
sdeString  = fdata + "\\sde_collection.SDE."

# local path to stage csvs in from BOX
accelaFiles = "//trpa-fs01/GIS/Acella/Reports"

# Get database user and password from environment variables
db_user             = os.environ.get('DB_USER')
db_password         = os.environ.get('DB_PASSWORD')

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
log_file_path = os.path.join(working_folder, r"Logs\Parcel_Tables_to_Features.log")  
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
fileToSend = log_file_path
# email parameters
subject = "Parcel Tables to Parcel Features ETL"
sender_email = "infosys@trpa.org"
receiver_email = "afish@trpa.gov"
updated_items = []
failed_items = []
current_item = None

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
            smtpObj.sendmail(sender_email, receiver_email, msg.as_string())
    except Exception as e:
        logger.error(e)

def email_uncaught_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    logger.exception("Unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
    send_mail(
        "ERROR - Unhandled exception - Check Log<br><br>"
        f"{status_summary()}<br><br>"
        f"<pre>{error_details}</pre>"
    )

sys.excepthook = email_uncaught_exception

def status_summary(include_current=True):
    updated = ', '.join(updated_items) or 'None'
    failed = ', '.join(failed_items) or (current_item if include_current else 'None') or 'None identified'
    return f"<b>Updated:</b> {escape(updated)}<br><b>Failed or in progress:</b> {escape(failed)}"

def write_featureclass_with_cursor(df, outFC, fields):
    if arcpy.Exists(outFC):
        actual_fields = {field.name.lower(): field.name for field in arcpy.ListFields(outFC)}
        missing_fields = [field for field in fields if field.lower() not in actual_fields and field != 'SHAPE']
        if missing_fields:
            logger.warning(
                f"Feature class exists but is missing required fields for {outFC}: {missing_fields}. Recreating it."
            )
            arcpy.management.Delete(outFC)

    if not arcpy.Exists(outFC):
        source = arcpy.Describe(sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcel_Master")
        arcpy.management.CreateFeatureclass(
            os.path.dirname(outFC),
            os.path.basename(outFC),
            source.shapeType,
            spatial_reference=source.spatialReference
        )
        pandas_to_arcgis_types = {
            "int64": "LONG",
            "float64": "DOUBLE",
            "bool": "SHORT",
            "datetime64[ns]": "DATE"
        }
        for field in fields:
            if field == 'SHAPE':
                continue
            dtype = str(df[field].dtype)
            field_type = pandas_to_arcgis_types.get(dtype, "TEXT")
            if field_type == "TEXT":
                arcpy.management.AddField(outFC, field, field_type, field_length=254)
            else:
                arcpy.management.AddField(outFC, field, field_type)

    actual_fields = {field.name.lower(): field.name for field in arcpy.ListFields(outFC)}
    missing_fields = [field for field in fields if field.lower() not in actual_fields and field != 'SHAPE']
    if missing_fields:
        raise RuntimeError(f"Missing fields in {outFC}: {missing_fields}")
    cursor_fields = [
        'SHAPE@' if field == 'SHAPE' else actual_fields[field.lower()]
        for field in fields
    ]
    arcpy.management.DeleteRows(outFC)
    with arcpy.da.InsertCursor(outFC, cursor_fields) as cursor:
        for row in df[fields].itertuples(index=False, name=None):
            values = []
            for field_name, value in zip(fields, row):
                if value is None or value is pd.NA:
                    values.append(None)
                    continue
                try:
                    missing = pd.isna(value)
                except (TypeError, ValueError):
                    missing = False
                if isinstance(missing, bool) and missing:
                    values.append(None)
                    continue
                if field_name == 'SHAPE':
                    geom = None
                    if isinstance(value, arcpy.Geometry):
                        geom = value
                    elif hasattr(value, 'as_arcpy'):
                        try:
                            geom = value.as_arcpy()
                        except Exception:
                            geom = None
                    elif hasattr(value, 'JSON'):
                        try:
                            geom = arcpy.AsShape(value.JSON, True)
                        except Exception:
                            geom = None
                    elif hasattr(value, 'WKT'):
                        try:
                            geom = arcpy.FromWKT(value.WKT)
                        except Exception:
                            geom = None
                    if geom is None and isinstance(value, dict):
                        try:
                            geom = arcpy.AsShape(value, True)
                        except Exception:
                            try:
                                geom = arcpy.AsShape(json.dumps(value), True)
                            except Exception:
                                geom = None
                    if geom is None and isinstance(value, str):
                        stripped = value.strip()
                        if stripped.startswith('{'):
                            try:
                                geom = arcpy.AsShape(json.loads(stripped), True)
                            except Exception:
                                geom = None
                        elif stripped.startswith('('):
                            try:
                                geom = arcpy.FromWKT(stripped)
                            except Exception:
                                geom = None
                        if geom is None:
                            try:
                                geom = arcpy.AsShape(stripped, True)
                            except Exception:
                                geom = None
                    if geom is None:
                        raise ValueError(
                            f"Could not convert SHAPE value to ArcGIS geometry: {type(value)}"
                        )
                    values.append(geom)
                    continue
                if hasattr(value, 'item') and not isinstance(value, (str, bytes)):
                    try:
                        value = value.item()
                    except ValueError:
                        pass
                if isinstance(value, np.generic):
                    value = value.item()
                if isinstance(value, (list, tuple, dict, set)):
                    value = None if len(value) == 0 else str(value)
                if isinstance(value, pd.Timestamp):
                    value = value.to_pydatetime()
                values.append(value)
            try:
                cursor.insertRow(values)
            except Exception as exc:
                logger.error(
                    f"Insert failed for {outFC}. Row values: {values}. Error: {exc}"
                )
                raise

# # update staging layers
def updateStagingLayer(name, df, fields):
    global current_item
    current_item = name
    try:
        # copy fields to keep
        dfOut = df[fields].copy().reset_index(drop=True)
        duplicate_fields = dfOut.columns[dfOut.columns.duplicated()].tolist()
        if duplicate_fields:
            raise ValueError(f"Duplicate output fields for {name}: {duplicate_fields}")
        # ArcGIS Pro's exporter cannot process pandas extension-backed string arrays.
        for field in dfOut.columns:
            if field != 'SHAPE' and dfOut[field].dtype.type is str:
                dfOut[field] = pd.Series(
                    dfOut[field].tolist(), index=dfOut.index, dtype=object
                )
        logger.debug(
            f"{name} export shape={dfOut.shape}, unique_index={dfOut.index.is_unique}, "
            f"dtypes={dfOut.dtypes.astype(str).to_dict()}"
        )
        # specify output feature class
        outFC = os.path.join(workspace, name)
        # spaital dataframe to feature class
        try:
            dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)
        except ValueError as export_error:
            if "Length of values" not in str(export_error):
                raise
            logger.warning(
                f"ArcGIS pandas export failed for {name}; using arcpy cursor fallback: {export_error}"
            )
            write_featureclass_with_cursor(dfOut, outFC, fields)
        # confirm feature class was created
        print(f"\nUpdated staging layer:{outFC}")
        logger.info(f"\nUpdated staging layer:{outFC}")
        updated_items.append(name)

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        lineno = tb.tb_lineno
        print(f"Error on line: {lineno}")
        print(f"General error: {e}")
        print(f"{exc_type} {os.path.basename(tb.tb_frame.f_code.co_filename)} {lineno}")
        failed_items.append(name)
        raise
    
# Execute a query
def insert_into_sql(df, table, chunksize=1000):
    global current_item
    current_item = f"dbo.{table}"
    # create a connection to the database
    conn = Tab_engine.connect()
    destination_columns = {
        column['name'] for column in sa.inspect(Tab_engine).get_columns(table, schema='dbo')
    }
    insert_columns = [column for column in df.columns if column in destination_columns]
    skipped_columns = [column for column in df.columns if column not in destination_columns]
    if not insert_columns:
        conn.close()
        raise ValueError(f"No matching columns found for dbo.{table}")
    if skipped_columns:
        logger.warning(
            f"Skipped columns not present in dbo.{table}: {', '.join(skipped_columns)}"
        )
    df_to_insert = df[insert_columns].copy()
    
    conn.execute(text(f"DELETE FROM {table}"))

    # insert the rows into the table in chunks
    df_to_insert.to_sql(table, conn, if_exists='append', index=False, schema='dbo', chunksize=chunksize)
    # log the number of rows inserted
    logger.info(f"{len(df_to_insert)} rows inserted into {table} table")
    updated_items.append(f"dbo.{table}")
    # close the connection
    conn.close()

            
# replaces features in outfc with exact same schema
def updateSDECollectFC(fcList):
    for fc in fcList:
        global current_item
        current_item = fc
        inputFC = os.path.join(workspace, fc)
        dsc = arcpy.Describe(inputFC)
        fields = dsc.fields
        out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
        fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]
        outfc = sdeString + fc

        # deletes all rows from the SDE feature class
        arcpy.TruncateTable_management(outfc)
        logger.info("\nDeleted all records in: {}\n".format(outfc))
        logger.info("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))

        # insert rows from Temporary feature class to SDE feature class
        with arcpy.da.InsertCursor(outfc, fieldnames) as oCursor:
            with arcpy.da.SearchCursor(inputFC, fieldnames) as iCursor:
                for row in iCursor:
                    oCursor.insertRow(row)
                logger.info(f"\nDone updating: {outfc}")
            updated_items.append(fc)

def update_collection_sde(fcList):
    print("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")
    print("\nUnregistering feature dataset as versioned...")
    arcpy.UnregisterAsVersioned_management(fdata, "NO_KEEP_EDIT", "COMPRESS_DEFAULT")
    print("\nFinished unregistering feature dataset as versioned.")
    updateSDECollectFC(fcList)
    print("\nRegistering feature dataset as versioned...")
    arcpy.RegisterAsVersioned_management(fdata, "NO_EDITS_TO_BASE")
    print("\nFinished registering feature dataset as versioned.")
            
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

# replace the spaces in the column names with underscores
def clean_column_names(df):
    df.columns = df.columns.str.replace(" ", "_")
    return df

#---------------------------------------------------------------------------------------#
## GET DATA
#---------------------------------------------------------------------------------------#

# Lake Tahoe Info Web Services API
ltinfo_api_url = "https://api.laketahoeinfo.org"
ltinfo_api_key = "ee44fc77-6602-4276-9a8b-1e4508104e9f"

def get_ltinfo_json(endpoint):
    response = requests.get(
        f"{ltinfo_api_url}/{endpoint}",
        headers={"x-api-key": ltinfo_api_key},
        params={"returnType": "JSON"}
    )
    response.raise_for_status()
    return pd.DataFrame(response.json())

# start timer for the get data requests
startTimer = datetime.datetime.now()

# dictionary of csv name and box file ID
boxDict = {'Land_Capable_Verifications.csv': "1342591986420",
           'Land_Capability_Challenge.csv' : "1342590467197",
           'Hydro_Soils.csv'              : "1342592456757",
           'Grading_Exception_Map.csv'      : "1337039879890",
           'Historic_Designations.csv'     : "1342590117002"
           }


# function to save Accela Reports from Box
getAccelaBOXfiles(boxDict)

# make dataframes from exported accela views
dfLCV      = pd.read_csv(os.path.join(accelaFiles, 'Land_Capable_Verifications.csv'))
dfLCC      = pd.read_csv(os.path.join(accelaFiles, 'Land_Capability_Challenge.csv'))
dfSoil     = pd.read_csv(os.path.join(accelaFiles, 'Hydro_Soils.csv'))
dfHist     = pd.read_csv(os.path.join(accelaFiles, 'Historic_Designations.csv'))
dfGrade    = pd.read_csv(os.path.join(accelaFiles, 'Grading_Exception_Map.csv'))
# dfSecurity = pd.read_csv(os.path.join(accelaFiles, 'Accela_Security.csv'))
# dfADoc     = pd.read_csv(os.path.join(accelaFiles, 'Accela_Record_Documents.xlsx'))

# get BMP Status data as dataframe from BMP SQL Database
with BMP_engine.begin() as bmpConnect:
    dfBMP      = pd.read_sql("SELECT * FROM tahoebmpsde.dbo.v_BMPStatus", bmpConnect)

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
    if 1 == 1:
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
        
        fields = ['APN','Status','Date','SHAPE']

        # update staging feature class from dataframe
        updateStagingLayer(name, df, fields)

        #---------------------------------------------------------------------------------------#

        ## Create feature class of grading exceptions
        # name of feature class
        name = "Parcel_Accela_GradingExceptions"
        # specify output feature class
        outFC = os.path.join(workspace, name)
        # create spatial data frame by merging parcels and sql table on APN
        df = pd.merge(sdfParcels, dfGrade, left_on='APN', right_on='PARCEL_NUMBER', how='left')
        #drop null parcels that dont have joined attributes
        df = df.dropna(subset=["PARCEL_NUMBER"])
        # # specify fields to keep
        dfOut = df[["APN", "APO_ADDRESS", 'B1_ALT_ID', 'Start_Date', 'End_Date', 'Description', "SHAPE"]].copy()

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

        csv_fcs = ["Parcel_BMP",
               "Parcel_Accela_LandCapabilityVerification",
               "Parcel_Accela_LCV_Challenge",
               "Parcel_Accela_SoilsHydro",
               "Parcel_Accela_Historic",
               "Parcel_Accela_GradingExceptions"]
        update_collection_sde(csv_fcs)

        # Load LT Info only after the CSV/BMP-derived staging layers are complete.
        dfLTAPN    = get_ltinfo_json("parcels")
        dfIPES     = get_ltinfo_json("parcel-ipes-scores")
        dfLCVinfo  = get_ltinfo_json("parcel-land-capabilities-accela")
        dfDRBank   = get_ltinfo_json("banked-development-rights")
        dfDeed     = get_ltinfo_json("deed-restricted-parcels")
        dfDRTrans  = get_ltinfo_json("transacted-and-banked-development-rights")
        
        dfAParcel  = dfLTAPN.copy()

        name = "Parcel_LTinfo_DevelopmentRight_Transacted_Banked"
        csv_path = os.path.join(workspace, f"{name}.csv")

        # Export the LT Info service data to CSV in the staging geodatabase first.
        dfDRTrans.to_csv(csv_path, index=False)
        logger.info(f"Exported LT Info transacted/banked development rights CSV to: {csv_path}")

        # Join the exported LT Info data back to the parcel feature class and retain geometry.
        df = pd.merge(sdfParcels, dfDRTrans, on='APN', how='left')
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

        dfOut = df[fields].copy().reset_index(drop=True)
        outFC = os.path.join(workspace, name)
        write_featureclass_with_cursor(dfOut, outFC, fields)
        print(f"\nUpdated staging layer:{outFC}")
        logger.info(f"\nUpdated staging layer:{outFC}")
        updated_items.append(name)

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

        # The current LCV API response no longer includes the legacy attributes
        # above. Keep the existing feature-class contract and populate absent
        # source fields with nulls.
        for field in fields:
            if field not in df.columns:
                df[field] = pd.NA

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
                'LocalPlan',
                'DateBankedOrApproved',
                'HRA',
                'LastUpdated',
                'SHAPE'] 

        # The banked-development-rights endpoint does not provide the
        # transacted-only cumulative quantity field. Preserve the existing
        # feature-class schema with nulls for that unavailable value.
        for field in fields:
            if field not in df.columns:
                df[field] = pd.NA

        outFC = os.path.join(workspace, name)
        write_featureclass_with_cursor(df[fields].copy().reset_index(drop=True), outFC, fields)
        print(f"\nUpdated staging layer:{outFC}")
        logger.info(f"\nUpdated staging layer:{outFC}")
        updated_items.append(name)

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
        ltinfo_fcs = ["Parcel_LTinfo",
            "Parcel_LTinfo_IPES",
            "Parcel_LTinfo_LCV",
            "Parcel_LTinfo_DevelopmentRight_Banked",
            "Parcel_LTinfo_DevelopmentRight_Transacted_Banked",
            "Parcel_LTinfo_DeedRestriction"
            ]

        # function to update all collection SDE feature classes in list
        update_collection_sde(ltinfo_fcs)
       
        # clean the column names
        dfAParcel = clean_column_names(dfAParcel)

        # insert the dataframes into the SQL database
        insert_into_sql(dfAParcel, "Accela_Parcels")

    # send email with header based on try/except result
    header = "SUCCESS - Parcel feature classes were updated."
    send_mail(f"{header}<br><br>{status_summary(include_current=False)}")
    print('Sending email...')

# catch any arcpy errors
except arcpy.ExecuteError:
    error_message = arcpy.GetMessages()
    error_number = arcpy.GetReturnCode()  # Gets the error number for ArcPy exceptions
    print(f"Error Number: {error_number}")
    print(error_message)
    logger.debug(f"Error Number: {error_number}")
    logger.debug(error_message)
    # send email with header based on try/except result
    header = "ERROR - Arcpy Exception - Check Log"
    send_mail(f"{header}<br><br>{status_summary()}<br><br><pre>{escape(error_message)}</pre>")
    print('Sending email...')

# catch system errors
except Exception as e:
    # Get line number of error
    exc_type, exc_obj, tb = sys.exc_info()
    lineno = tb.tb_lineno
    print(f"Error on line: {lineno}")
    print(f"General error: {e}")
    print(f"{exc_type} {os.path.basename(tb.tb_frame.f_code.co_filename)} {lineno}")
    logger.debug(f"Error on line: {lineno}")
    logger.debug(f"General error: {e}")
    # send email with header based on try/except result
    header = "ERROR - System Error - Check Log"
    error_details = ''.join(traceback.format_exception(exc_type, exc_obj, tb))
    send_mail(f"{header}<br><br>{status_summary()}<br><br><pre>{escape(error_details)}</pre>")
    print('Sending email...')
