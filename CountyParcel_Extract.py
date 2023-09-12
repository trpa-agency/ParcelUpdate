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
import logging

from datetime import datetime
import time
from zipfile import ZipFile
from io import BytesIO

import arcpy

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import pathlib
from time import strftime

# environment settings
arcpy.env.workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)

# set workspace and sde connections 
workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/Staging"

# network path to connection files
filePath = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/"

# portal signin
## TRPA_ADMIN credentials
portal_user = "TRPA_PORTAL_ADMIN"
portal_pwd = str(os.environ.get('Password'))
portal_url = "https://maps.trpa.org/portal/"
# sign in
arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)

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

# report how long it took to get the data
endTimer = datetime.datetime.now() - startTimer
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
    endTimer = datetime.datetime.now() - startTimer
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
    print("Done Saving Placer Features")

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
    print("Done saving Washoe Staging Features")
    ##--------------------------------------------------------------------------------------------------------#
    ## END OF EXTRACT ##
    ##--------------------------------------------------------------------------------------------------------#

    # report how long it took to run the script
    FINALendTimer = datetime.datetime.now() - FIRSTstartTimer
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
