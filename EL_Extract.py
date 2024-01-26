
#--------------------------------------------------------------------------------------------------------#
# import packages and modules
# import packages
import urllib
import json
import requests
import os
import shutil
import sys
import logging
from datetime import datetime
import time
from zipfile import ZipFile
from io import BytesIO
import arcpy
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import pathlib
from time import strftime

# environment settings
arcpy.env.workspace = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# set workspace and sde connections 
workspace = "F:/GIS/PARCELUPDATE/Workspace/Staging"

# network path to connection files
filePath = "F:/GIS/PARCELUPDATE/Workspace/"

# portal signin
## TRPA_ADMIN credentials
# portal_user = "TRPA_PORTAL_ADMIN"
# portal_pwd = str(os.environ.get('Password'))
# portal_url = "https://maps.trpa.org/portal/"
# # sign in
# arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)

# Parcel AOI to select parcels to keep (includes TRPA Boundary and Olympic Valley Watershed)
parcelAOI = "Parcel_AOI"

FIRSTstartTimer = datetime.datetime.now()

# Create and open log file.
complete_txt_path = os.path.join(workspace, "CountyParcel_Extract_Log.txt")
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
startTimer = datetime.datetime.now()


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
        log.write('Previous zip folder deleted')

    # Setup the params for the extraction GP tool. The boundary is a polygon the grabs the whole county.
    payload = {'f': 'json', 'env:outSR': '6418', 'Layers_to_Clip': '["Parcels"]', 'Area_of_Interest': '{"geometryType":"esriGeometryPolygon","features":[{"geometry":{"rings":[[[-13490599.294393552,4646257.881632805],[-13490599.294393552,4735689.204726496],[-13336502.24537058,4735689.204726496],[-13336502.24537058,4646257.881632805],[-13490599.294393552,4646257.881632805]]],"spatialReference":{"wkid":102100}}}],"sr":{"wkid":102100}}', 'Feature_Format': 'File Geodatabase - GDB - .gdb'}

    # Make the request to the GP service.
    log.write('Requesting parcels from EDC')
    job = requests.get(r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/submitJob",params=payload)
    jobJson = job.json()

    # Check to make sure the job was accepted and get the JobID.
    if 'jobId' in jobJson:
        jobID = jobJson['jobId']
        jobStatus = jobJson['jobStatus']
        jobURL = r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/jobs"
        if jobStatus == 'esriJobSubmitted' or jobStatus == 'esriJobExecuting':
            log.write('EDC job submitted')

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
    log.write(e.args[0])
    log.close()
    
    header = "ERROR - System Error - Check Log"
    # send email with header based on try/except result
    send_mail(header)
    print('Sending email...')
