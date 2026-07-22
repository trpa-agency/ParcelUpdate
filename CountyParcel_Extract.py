"""
CountyParcel_Extract.py
Created: June 15th,2023
Last Updated: October 9th, 2024
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
import urllib.parse
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
import ssl
import traceback
import linecache

# environment settings
arcpy.env.workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
arcpy.env.overwriteOutput = True
arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)
    
# set workspace and sde connections 
workspace = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/Staging"
workspace = "f:/gis/parcelupdate/workspace/staging"

# network path to connection files
filePath = "//Trpa-fs01/GIS/PARCELUPDATE/Workspace/"
filePath = "f:/gis/parcelupdate/workspace/"

# portal signin
## TRPA_ADMIN credentials
portal_user = "TRPA_PORTAL_ADMIN"
portal_user="admin"
#portal_pwd = str(os.environ.get('Password'))
portal_pwd = "WelcomeArc1"
portal_url = "https://maps.trpa.org/portal/"
# sign in
arcpy.SignInToPortal(portal_url, portal_user, portal_pwd)

# Parcel AOI to select parcels to keep (includes TRPA Boundary and Olympic Valley Watershed)
parcelAOI = "Parcel_AOI"

FIRSTstartTimer = datetime.datetime.now()

counties_to_run = ['El Dorado', 'Placer', 'Douglas', 'Washoe', 'Carson City']

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

# Function to check if a county exists in the list of counties to run
def is_county_in_list(county, county_list):
    return county in county_list

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

    county_to_check = 'Carson City'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    
    if exists == 1:
        # delete the existing table
        arcpy.management.Delete('Parcel_CC_Features')
        print("Deleted existing Carson City County Feature Class")
        log.write("Deleted existing Carson City County Feature Class")

        baseURL = "https://portal.carsoncity.gov/server/rest/services/CarsonCity/CarsonCityNV_OpenData/MapServer/36"
        fields = "*"
        urlstring = baseURL + "?f=json"
        
        #j = urllib.request.urlopen(urlstring)
        #js = json.load(j)
        # Create an unverified SSL context (skips cert validation)
        ssl_context = ssl._create_unverified_context()

        with urllib.request.urlopen(urlstring, context=ssl_context) as j:
            js = json.load(j)
        
        maxrc = int(js["maxRecordCount"])
        print("Carson City Feature Service record extract limit: %s" % maxrc)
        log.write("Carson City Feature Service record extract limit: %s" % maxrc)
        
        # Get object ids of features
        where = "1=1"
        urlstring = baseURL + "/query?where={}&returnIdsOnly=true&f=json".format(where)
        #j = urllib.request.urlopen(urlstring)
        #js = json.load(j)
        with urllib.request.urlopen(urlstring, context=ssl_context) as j:
            js = json.load(j)

        idfield = js["objectIdFieldName"]
        idlist = js["objectIds"]
        idlist.sort()
        numrec = len(idlist)
        print("Number of target records: %s" % numrec)
        log.write("Number of target records: %s" % numrec)
        
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
            print("{}".format(where))
            log.write("{}".format(where))
            urlstring = baseURL + "/query?where={}&returnGeometry=true&outFields={}&f=json".format(where,fields)
            # build that feature set!
            fs[i] = arcpy.FeatureSet()
            fs[i].load(urlstring)
            
        # Save features
        print("Saving features...")
        fslist = []
        for key,value in fs.items():
            fslist.append(value)
        arcpy.Merge_management(fslist, 'Parcel_CC_Features')

        #The associated attributes in the table
        baseURL = "https://portal.carsoncity.gov/server/rest/services/CarsonCity/CarsonCityNV_OpenData/MapServer/42"
        fields = "*"
        urlstring = baseURL + "?f=json"
        j = urllib.request.urlopen(urlstring)
        js = json.load(j)
        maxrc = int(js["maxRecordCount"])
        print("Carson City associated table record extract limit: %s" % maxrc)

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
        log.write("Number of target records: %s" % numrec)

        
        # Associated records are stored in a table
        arcpy.management.Delete('Parcel_CC_Table')
        print("Deleted existing table")
        log.write("Deleted existing table")
        fs_table = dict()
        table_records = dict()
        
        for i in range(0, numrec, maxrc):
            torec = i + (maxrc - 1)
            if torec > numrec:
                torec = numrec - 1
            fromid = idlist[i]
            toid = idlist[torec]
            where = "{} >= {} and {} <= {}".format(idfield, fromid, idfield, toid)
            print("{}".format(where))
            log.write("{}".format(where))
            urlstring = baseURL + "/query?where={}&returnGeometry=false&outFields={}&f=json".format(where,fields)
            urlstring = urlstring.replace(" ", "%20")
            j = urllib.request.urlopen(urlstring)
            js = json.load(j)
            fs_table[i] = arcpy.AsShape(js, True) 
                 
        # Save features
        fslist = []
        for key,value in fs_table.items():
            fslist.append(value)

        arcpy.Merge_management(fslist, 'Parcel_CC_Table')
        print("Saved CC Staging Table")
        log.write("Saved CC Staging Table")

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
        log.write("Carson Parcel Extracted")
        #---------------------------------------------------------------------------------------#
        # report how long it took to get the data
        endTimer = datetime.datetime.now() - startTimer
        print("\nTime it took to update Carson feature classes: {}".format(endTimer)) 
        log.write("\nTime it took to update Carson feature classes: {}".format(endTimer)) 

    #---------------------------------------------------------------------------------------#
    # DOUGLAS EXTRACT
    #---------------------------------------------------------------------------------------#
    county_to_check = 'Douglas'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    if exists == 1:
        baseURL = "https://gisservices.douglasnv.us/server/rest/services/TRPA_Parcels/FeatureServer/0"
        fields = "*"
        outfc = "Parcel_DG_Extracted"

        # Get record extract limit
        urlstring = baseURL + "?f=json"
        j = urllib.request.urlopen(urlstring)
        js = json.load(j)
        maxrc = int(js["maxRecordCount"])
        print("Record extract limit: %s" % maxrc)
        log.write("Record extract limit: %s" % maxrc)

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
        log.write("Number of target records: %s" % numrec)

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
            print("{}".format(where))
            log.write("{}".format(where))
            urlstring = baseURL + "/query?where={}&returnGeometry=true&outFields={}&f=json".format(where,fields)
            # build that feature set!
            fs[i] = arcpy.FeatureSet()
            fs[i].load(urlstring)

        # Save features
        print("Saving features...")
        fslist = []
        for key,value in fs.items():
            fslist.append(value)
        
        if len(fslist) == 0:
            print("ERROR: No feature sets collected for Douglas")
            log.write("ERROR: No feature sets collected for Douglas\n")
        else:
            print(f"Merging {len(fslist)} feature sets...")
            log.write(f"Merging {len(fslist)} feature sets...\n")
            try:
                arcpy.Merge_management(fslist, outfc)
                
                # Verify the output was created
                if arcpy.Exists(outfc):
                    count = int(arcpy.management.GetCount(outfc)[0])
                    print(f"Douglas Parcels Extracted: {count} features")
                    log.write(f"Douglas Parcels Extracted: {count} features\n")
                else:
                    print("ERROR: Merge completed but output feature class does not exist")
                    log.write("ERROR: Merge completed but output feature class does not exist\n")
            except Exception as e:
                print(f"ERROR during Douglas merge: {str(e)}")
                log.write(f"ERROR during Douglas merge: {str(e)}\n")

    #---------------------------------------------------------------------------------------#
    # EL DORADO EXTRACT
    #---------------------------------------------------------------------------------------#
    county_to_check = 'El Dorado'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    if exists == 1:    
        # Set up output feature class
        outfc = "Parcel_EL_Extracted"

        # Delete existing output feature class if it exists
        try:
            arcpy.management.Delete(outfc)
            print("Deleted existing El Dorado County Feature Class")
            log.write("Deleted existing El Dorado County Feature Class\n")
        except:
            pass
        
        # Set up Zip path.
        zipPath = workspace

        # Check if zip from failed attempt still exists
        existingZip = pathlib.Path(zipPath + r"\zipfolder")
        if existingZip.exists():
            shutil.rmtree(zipPath + r"\zipfolder")
            log.write('Previous zip folder deleted')

        # Setup the params for the extraction GP tool. The boundary is a polygon the grabs the whole county.
        payload = {'f': 'json', 'env:outSR': '6418', 'Layers_to_Clip': '["Parcels"]', 'Area_of_Interest': '{"geometryType":"esriGeometryPolygon","features":[{"geometry":{"rings":[[[-13490599.294393552,4646257.881632805],[-13490599.294393552,4735689.204726496],[-13336502.24537058,4735689.204726496],[-13336502.24537058,4646257.881632805],[-13490599.294393552,4646257.881632805]]],"spatialReference":{"wkid":102100}}}],"sr":{"wkid":102100}}', 'Feature_Format': 'File Geodatabase - GDB - .gdb'}

        # Make the request to the GP service.
        print("Requesting parcels from EDC")
        log.write('Requesting parcels from EDC')
        job = requests.get(r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/submitJob",params=payload)
        jobJson = job.json()

        # Check to make sure the job was accepted and get the JobID.
        if 'jobId' in jobJson:
            jobID = jobJson['jobId']
            jobStatus = jobJson['jobStatus']
            jobURL = r"https://see-eldorado.edcgov.us/arcgis/rest/services/uGOTNETandEXTRACTS/geoservices/GPServer/Extract%20Data%20Task/jobs"
            if jobStatus == 'esriJobSubmitted' or jobStatus == 'esriJobExecuting':
                print("EDC job submitted")
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
                        print("EDC server job failure")
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
        in_features = os.path.join(workspace, "zipfolder", "data.gdb", "Parcels")

        # Export to staging gdb

        if not arcpy.Exists(in_features):
            raise FileNotFoundError(f"Input feature class not found: {in_features}")

        arcpy.management.CopyFeatures(in_features, outfc)
        print("El Dorado Parcels Extracted")

    #---------------------------------------------------------------------------------------#
    # PLACER EXTRACT
    #---------------------------------------------------------------------------------------#
    county_to_check = 'Placer'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    if exists == 1:
        #Parameters
        hostedFeatureService = 'true'
        agsService = 'false'

        # username and password to get the token via the AGOL shared group
        username = 'TRPA_ADMIN'
        password = 'TRP@g1sT3am'

        baseURL = "https://services9.arcgis.com/NENkjkswKTzMfG3A/arcgis/rest/services/County_Parcels/FeatureServer/0"

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

        print('Token: ' + token)

        def get_agol_token():
            try:
                tokenURL = 'https://www.arcgis.com/sharing/rest/generateToken'
                params = {
                    'f': 'pjson',
                    'username': username,
                    'password': password,
                    'referer': 'https://www.arcgis.com',
                    'expiration': str(21600)
                }
                response = requests.post(tokenURL, data=params, verify=False)
                response.raise_for_status()
                js = response.json()
                if 'token' not in js:
                    raise ValueError(f"Unable to generate token: {js}")
                return js['token']
            except Exception:
                PrintException()

        def build_query_url(where_clause, current_token):
            where_encoded = urllib.parse.quote(where_clause, safe='')
            token_encoded = urllib.parse.quote(current_token, safe='')
            fields_encoded = urllib.parse.quote(fields, safe='*')
            return baseURL + f'/query?where={where_encoded}&returnGeometry=true&outFields={fields_encoded}&f=json&token=' + token_encoded

        token = get_agol_token()
        token_expire = time.time() + 21000

        # Get record extract limit 
        urlstring = baseURL + "?token=" + urllib.parse.quote(token, safe='') + "&f=json"
        j = requests.get(urlstring, verify=False)
        js = j.json()
        maxrc = int(js["maxRecordCount"])
        print("Record extract limit: %s" % maxrc)

        # Get object ids of features
        urlstring = baseURL + "/query?where=1%3D1&returnIdsOnly=true&f=json&token=" + urllib.parse.quote(token, safe='')
        print(urlstring)
        j = requests.get(urlstring, verify=False)
        js = j.json()
        idfield = js["objectIdFieldName"]
        idlist = js["objectIds"]
        idlist.sort()
        numrec = len(idlist)
        print("Number of target records: %s" % numrec)

        # Gather features
        print("Gathering records...")
        batch_features = []
        for i in range(0, numrec, maxrc):
            if time.time() >= token_expire:
                token = get_agol_token()
                token_expire = time.time() + 21000

            torec = i + (maxrc - 1)
            if torec > numrec:
                torec = numrec - 1
            fromid = idlist[i]
            toid = idlist[torec]
            where = "{} >= {} and {} <= {}".format(idfield, fromid, idfield, toid)
            print("  {}".format(where))
            urlstring = build_query_url(where, token)

            response = requests.get(urlstring, verify=False)
            response.raise_for_status()
            js = response.json()
            if 'error' in js:
                error_text = json.dumps(js['error'])
                if 'token' in error_text.lower():
                    token = get_agol_token()
                    token_expire = time.time() + 21000
                    urlstring = build_query_url(where, token)
                    response = requests.get(urlstring, verify=False)
                    response.raise_for_status()
                    js = response.json()
                else:
                    raise ValueError(f"Placer query error: {js}")

            if 'features' not in js:
                raise ValueError(f"Unexpected Placer query response: {js}")

            temp_json = os.path.join(workspace, f"Parcel_PL_batch_{i}.json")
            with open(temp_json, 'w', encoding='utf-8') as temp_file:
                json.dump(js, temp_file)

            temp_fc = os.path.join('in_memory', f'Parcel_PL_batch_{i}')
            arcpy.JSONToFeatures_conversion(temp_json, temp_fc)
            batch_features.append(temp_fc)
            os.remove(temp_json)

        print("Saving features...")
        if arcpy.Exists(outdata):
            arcpy.management.Delete(outdata)
        arcpy.Merge_management(batch_features, outdata)
        for temp_fc in batch_features:
            if arcpy.Exists(temp_fc):
                arcpy.management.Delete(temp_fc)
        print("Done Saving Placer Features")

    #---------------------------------------------------------------------------------------#
    # WASHOE EXTRACT
    #---------------------------------------------------------------------------------------#
    county_to_check = 'Washoe'
    exists = is_county_in_list(county_to_check, counties_to_run)
    print(f"Is {county_to_check} in the list? {exists}")
    if exists == 1:
        
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

    ##--------------------------------------------------------------------------------------------------------#
    ## DELETE Parcels outside of the Tahoe Basin ##
    ##--------------------------------------------------------------------------------------------------------#
    # list of parcel staging layers to trim
    parcelLayers = ["Parcel_CC_Extracted",
                    "Parcel_DG_Extracted",
                    "Parcel_EL_Extracted",
                    "Parcel_PL_Extracted",
                    "Parcel_WA_Extracted"]

    # delete BS Parcels
    parcelDelete = "ParcelDelete"

    for parcel in parcelLayers:
        # Skip layers that weren't created during the extract
        if not arcpy.Exists(parcel):
            print(f"Skipping {parcel} - does not exist")
            log.write(f"Skipping {parcel} - does not exist\n")
            continue

        # Run MakeFeatureLayer
        arcpy.management.MakeFeatureLayer(parcel, parcelDelete)
        # select within clementini
        arcpy.management.SelectLayerByLocation(parcelDelete,
                                              "INTERSECT",
                                              # includes TRPA Boundary and Olympic Valley Wateshed
                                              parcelAOI, '0',
                                              "NEW_SELECTION", "INVERT")

        # Run GetCount and if some features have been selected, then
        # run DeleteFeatures to remove the selected features.
        deleteCount = int(arcpy.management.GetCount(parcelDelete)[0])
        if deleteCount > 0:
            arcpy.management.DeleteFeatures(parcelDelete)

        # delete feature layer
        arcpy.management.Delete(parcelDelete)
        print(f"{deleteCount} features deleted from {parcel}")
        log.write(f"{deleteCount} features deleted from {parcel}\n")
    ##--------------------------------------------------------------------------------------------------------#
    ## Send Email with Log ##
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
    import traceback
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    line_content = linecache.getline(filename, lineno, f.f_globals).strip()
    
    error_msg = f"\n{'='*80}\nARCPY ERROR on Line {lineno}:\n{line_content}\n{'='*80}\n{traceback.format_exc()}\n{arcpy.GetMessages()}"
    print(error_msg)
    log.write(error_msg)
    log.close()
    
    header = "ERROR - Arcpy Exception - Check Log"
    try:
        send_mail(header)
        print('Sending error email...')
    except Exception as mail_error:
        print(f"Failed to send email: {mail_error}")

# catch system errors
except Exception as e:
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    line_content = linecache.getline(filename, lineno, f.f_globals).strip()
    
    error_msg = f"\n{'='*80}\nSYSTEM ERROR on Line {lineno}:\n{line_content}\n{'='*80}\n{traceback.format_exc()}"
    print(error_msg)
    log.write(error_msg)
    log.close()
    
    header = "ERROR - System Error - Check Log"
    try:
        send_mail(header)
        print('Sending error email...')
    except Exception as mail_error:
        print(f"Failed to send email: {mail_error}")
