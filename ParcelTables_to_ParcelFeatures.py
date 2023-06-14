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
import arcpy
from datetime import datetime
import os
import sys
import pyodbc
import pandas as pd
from arcgis.features import FeatureSet, GeoAccessor, GeoSeriesAccessor
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# set overwrite to true
arcpy.env.overwriteOutput = True

# in memory output file path
wk_memory = "memory" + "\\"

# set workspace and sde connections 
working_folder = "C:\GIS"
workspace      = "C:\GIS\Scratch.gdb"
arcpy.env.workspace = "C:\GIS\Scratch.gdb"

# network path to connection files
filePath = "C:\\GIS\\DB_CONNECT"

# database file path 
sdeBase = os.path.join(filePath, "Vector.sde")
sdeCollect = os.path.join(filePath, "Collection.sde")

# Feature dataset to unversion and register as version
fdata = sdeCollect + "\\sde_collection.SDE.Parcel"

# start a timer for the entire script run
FIRSTstartTimer = datetime.now()

# Create and open log file.
complete_txt_path = os.path.join(working_folder, "Parcel_ETL_Log.txt")
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

# make sql database connection to BMP with pyodbc
bmpConnect = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=sql14;DATABASE=tahoebmpsde;UID=sde;PWD=staff')
# BMP - create dataframe from tahoebmpsde table
dfBMP      = pd.read_sql("SELECT * FROM tahoebmpsde.dbo.v_BMPStatus", bmpConnect)

# # make sql database connection to Accela with pyodbc
# accConnect = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=ASQL;DATABASE=Accela;UID=BMP_Update;PWD=BMP_update_123')
# # Accela - create dataframes from sql tables
# dfLCV      = pd.read_sql("SELECT * FROM Accela.dbo.v_LandCapabilityVerifications", accConnect)
# dfLCC      = pd.read_sql("SELECT * FROM Accela.dbo.v_LandCapabilityChallenges", accConnect)  
# dfSoil     = pd.read_sql("SELECT * FROM Accela.dbo.v_HydroSoilsProjects", accConnect)
# dfHist     = pd.read_sql("SELECT * FROM Accela.dbo.v_HistoricDeterminations", accConnect)
# dfGrade    = pd.read_sql("SELECT * FROM Accela.dbo.v_GradingExceptions", accConnect)

# make dataframes from exported accela views
accelaFiles = "//trpa-fs01/GIS/Acella/Reports"
dfLCV      = pd.read_csv(os.path.join(accelaFiles, "v_landcapabilityverifications.csv"))
dfLCC      = pd.read_csv(os.path.join(accelaFiles, "v_landcapabilityChallenges.csv"))
dfSoil     = pd.read_csv(os.path.join(accelaFiles, "v_hydrosoilsprojects.csv"))
dfHist     = pd.read_csv(os.path.join(accelaFiles, "v_historicdeterminations.csv"))
dfGrade    = pd.read_csv(os.path.join(accelaFiles, "v_gradingexceptions.csv"))

# LTInfo - create dataframes from JSON found here: https://laketahoeinfo.org/WebServices/List
dfLTAPN    = pd.read_json("https://laketahoeinfo.org/WebServices/GetAllParcels/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfIPES     = pd.read_json("https://laketahoeinfo.org/WebServices/GetParcelIPESScores/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfLCVinfo  = pd.read_json("https://laketahoeinfo.org/WebServices/GetParcelsByLandCapability/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDRBank   = pd.read_json("https://laketahoeinfo.org/WebServices/GetBankedDevelopmentRights/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDRTrans  = pd.read_json("https://laketahoeinfo.org/WebServices/GetTransactedAndBankedDevelopmentRights/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")
dfDeed     = pd.read_json("https://laketahoeinfo.org/WebServices/GetDeedRestrictedParcels/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")

# create spatial dataframe from parcel master in sde
parcels = sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcel_Master"
sdfParcels = pd.DataFrame.spatial.from_featureclass(parcels)
       
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
subject = "Parcel ETL Log File"
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

# replaces features in outfc with exact same schema
def updateSDE(inputfc,outfc, fieldnames):
    # deletes all rows from the SDE feature class
    arcpy.TruncateTable_management(outfc)
    print ("\nDeleted all records in: {}\n".format(outfc))
    from time import strftime  
    print ("Started data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
    # insert rows from Temporary feature class to SDE feature class
    with arcpy.da.InsertCursor(outfc, fieldnames) as oCursor:
        count = 0
        with arcpy.da.SearchCursor(inputfc, fieldnames) as iCursor:
            for row in iCursor:
                oCursor.insertRow(row)
                count += 1
                if count % 1000 == 0:
                    print("Inserting record %d into %s SDE feature class" % (count, outfc))
            print ("Finished data transfer: " + strftime("%Y-%m-%d %H:%M:%S"))
            print("Done updating: %s"%(outfc))
            log.write("\nDone updating: %s"%(outfc))

try:
    #---------------------------------------------------------------------------------------#
    ## CREATE STAGING LAYERS ##
    #---------------------------------------------------------------------------------------#
    # start timer for the get data requests
    startTimer = datetime.now()
    #---------------------------------------------------------------------------------------#

    # Create BMP feature class
    # name of feature class
    name = "Parcel_BMP"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfBMP, on='APN', how='inner')

    # specify fields to keep
    fields = list(df.columns)[:3]+list(df.columns)[76:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # rename some of the fields
    dfOut.rename(columns={"PPNO_x": "PPNO"}, inplace=True)

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of Land Capability Verifications
    # name of feature class
    name = "Parcel_LCV"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCV, left_on='APN', right_on='GIS_ID', how='inner')

    # rename some of the fields
    df.rename(columns={"LABEL_FIELD": "Status"}, inplace=True)

    # specify fields to keep
    dfOut = df[["OBJECTID","APN", "Status", "SHAPE"]].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    # -----------------------------------------------------------------------------------#

    ## Create feature class of LCV Challenges
    # name of feature class
    name = "Parcel_LCV_Challenge"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCC, left_on='APN', right_on='GIS_ID', how='inner')

    # rename some of the fields
    df.rename(columns={"REC_DATE": "Date", "LABEL_FIELD": "Status"}, inplace=True)

    # specify fields to keep
    dfOut = df[["APN", "Date", "Status", "SHAPE"]].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    # -------------------------------------------------------------------------------------#

    ## Create feature class of SOILS/Hydro Project
    # name of feature class
    name = "Parcel_SoilsHydro"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfSoil, left_on='APN', right_on='GIS_ID', how='inner')

    # rename some of the fields
    df.rename(columns={"REC_DATE": "Date", "LABEL_FIELD": "Status"}, inplace=True)

    # specify fields to keep
    dfOut = df[["APN", "Date", "Status", "SHAPE"]].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    ##--------------------------------------------------------------------------------------#

    ## Create feature class of historic designations
    # name of feature class
    name = "Parcel_Historic"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfHist, left_on='APN', right_on='GIS_ID', how='inner')

    # rename some of the fields
    df.rename(columns={"REC_DATE": "Date", "LABEL_FIELD": "Status"}, inplace=True)

    # specify fields to keep
    dfOut = df[["APN", "Date", "Status", "SHAPE"]].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

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

    # specify fields to keep
    dfOut = df[["APN", "PROPERTY_ADDRESS", "ApprovedEndingDate", "ApprovedBeginningDate", 
                "FileNumber", "Comment", "SHAPE"]].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of LT Info parcels
    # name of feature class
    name = "Parcel_LTinfo"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLTAPN, on='APN', how='inner')

    # create fields list
    fields = list(df.columns)[0:2]+[list(df.columns)[20]]+list(df.columns)[75:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of LT Info parcels
    # name of feature class
    name = "Parcel_LTinfo_IPES"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfIPES, on='APN', how='inner')

    # create fields list
    fields = list(df.columns)[0:2]+[list(df.columns)[20]]+list(df.columns)[75:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    ## Create feature class of LT Info LCV parcels
    # name of feature class
    name = "Parcel_LTinfo_LCV"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfLCVinfo, on='APN', how='inner')

    # specify fields to keep
    fields = list(df.columns)[0:2]+list(df.columns)[76:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    # name of feature class
    name = "Parcel_LTinfo_DevelopmentRight_Banked"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDRBank, on='APN', how='inner')

    # specify fields to keep
    fields = list(df.columns)[0:2]+list(df.columns)[75:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#

    # name of feature class
    name = "Parcel_LTinfo_DevelopmentRight_Transacted_Banked"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDRTrans, on='APN', how='left')

    # specify fields to keep
    fields = list(df.columns)[0:2]+list(df.columns)[75:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)
    #---------------------------------------------------------------------------------------#
    #---------------------------------------------------------------------------------------#
    # name of feature class
    name = "Parcel_LTinfo_DeedRestriction"

    # specify output feature class
    outFC = os.path.join(workspace, name)

    # create spatial data frame by merging parcels and sql table on APN
    df = pd.merge(sdfParcels, dfDeed, on='APN', how='left')

    # specify fields to keep
    fields = list(df.columns)[0:2]+list(df.columns)[75:]+[list(df.columns)[74]]

    # specify fields to keep
    dfOut = df[fields].copy()

    # spaital dataframe to feature class
    dfOut.spatial.to_featureclass(outFC, sanitize_columns=False)

    # confirm feature class was created
    print("\nUpdated staging layer: " + outFC)

    #---------------------------------------------------------------------------------------#
    # report how long it took to get the data
    endTimer = datetime.now() - startTimer
    print("\nTime it took to create staging layers: {}".format(endTimer))       
    #---------------------------------------------------------------------------------------#

    ##--------------------------------------------------------------------------------------------------------#
    ## BEGIN SDE UPDATES ##
    ##--------------------------------------------------------------------------------------------------------#

    #---------------------------------------------------------------------------------------#
    # start timer for the get data requests
    startTimer = datetime.now()
    #---------------------------------------------------------------------------------------#

    # disconnect all users
    print("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    # unregister the sde feature class as versioned
    print ("\nUnregistering feature dataset as versioned...")
    arcpy.UnregisterAsVersioned_management(fdata,"NO_KEEP_EDIT","COMPRESS_DEFAULT")
    print ("\nFinished unregistering feature dataset as versioned.")

    #---------------------------------------------------------------------------------------#
    # Update Parcel_BMP

    # input staging feature class
    inputFC = "Parcel_BMP"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_BMP"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_LCV

    # input staging feature class
    inputFC = "Parcel_LCV"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_Accela_LandCapabilityVerification"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_LCV_Challenge

    # input staging feature class
    inputFC = "Parcel_LCV_Challenge"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_Accela_LCV_Challenge"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_SoilsHydro

    # input staging feature class
    inputFC = "Parcel_SoilsHydro"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_Accela_SoilsHydro"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_Historic

    # input staging feature class
    inputFC = "Parcel_Historic"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_Accela_Historic"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#
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

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_LTInfo

    # input staging feature class
    inputFC = "Parcel_LTinfo"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_IPES

    # input staging feature class
    inputFC = "Parcel_LTinfo_IPES"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo_IPES"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_LTInfo_LCV

    # input staging feature class
    inputFC = "Parcel_LTinfo_LCV"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo_LCV"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # Update Parcel_

    # input staging feature class
    inputFC = "Parcel_LTinfo_DevelopmentRight_Banked"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo_DevelopmentRight_Banked"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # input staging feature class
    inputFC = "Parcel_LTinfo_DevelopmentRight_Transacted_Banked"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo_DevelopmentRight_Transacted_Banked"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#

    # input staging feature class
    inputFC = "Parcel_LTinfo_DeedRestriction"

    # path to output FC
    updateFC = sdeCollect + "\\sde_collection.SDE.Parcel\\sde_collection.SDE.Parcel_LTinfo_DeedRestriction"

    # Get field objects from inputFC
    dsc = arcpy.Describe(inputFC)
    fields = dsc.fields

    # List all field names except the OID field and geometry fields
    # Replace 'Shape' with 'SHAPE@'
    out_fields = [dsc.OIDFieldName, dsc.lengthFieldName, dsc.areaFieldName]
    fieldnames = [field.name if field.name != 'Shape' else 'SHAPE@' for field in fields if field.name not in out_fields]

    # update function (input, output, fields)
    updateSDE(inputFC, updateFC, fieldnames)

    #---------------------------------------------------------------------------------------#
    # report how long it took to get the data
    endTimer = datetime.now() - startTimer
    print("\nTime it took to update Collection SDE feature classes: {}".format(endTimer)) 
    log.write("\nTime it took to update Collection SDE feature classes: {}".format(endTimer)) 
    #---------------------------------------------------------------------------------------#

    ##--------------------------------------------------------------------------------------------------------#
    ## END OF UPDATES ##
    ##--------------------------------------------------------------------------------------------------------#

    # disconnect all users
    print("\nDisconnecting all users...")
    arcpy.DisconnectUser(sdeCollect, "ALL")

    print("\nRegistering feature dataset as versioned...")
    # register SDE feature class as versioned
    arcpy.RegisterAsVersioned_management(fdata, "NO_EDITS_TO_BASE")
    print("\nFinished registering feature dataset as versioned.")

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
