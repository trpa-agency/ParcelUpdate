"""
Script Name: Parcel_History_Update.py

Purpose: Update the Parcel_History layer in the SDE databse
required for the Parcel History layer in the GIS database.  This script will
be run annually to update the Parcel History table with the new parcels and
inactive parcels.  
Requirements: The script requires the following labuild_years_activeyers and folder locations:
1. Parcel Master - The master parcel layer
2. Parcel History - The parcel history layer
3. C:\\temp\\gis\\Workspacbuild_years_activee.gdb - The workspace geodatabase
4. c:\\temp

Author: Amy Fish
Date: 3/28/2023

TODO: 1. Add the ability to email the results of the script
      2. Add the ability to create a new version in the SDE database
      3. Update PPNO
"""
import arcpy

# additional imports for logging and emailing the results
import sys 
import smtplib
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#Set the constants
working_folder = "C:\\temp\\"
subject = "Parcel History update"
sender_email = "infosys@trpa.org"
receiver_email = "afish@trpa.gov"

# Set the database connection
database_connection = "C:\\Users\\afish\\AppData\\Roaming\\Esri\\ArcGISPro\\Favorites\\SDE (SDE user).sde"

# Define the existing layers
Parcel_Poly_2023 = "C:\\temp\\gis\\workspace.gdb\\Parcels2023"
parcel_history = database_connection + "\\SDE.Parcels\\SDE.Parcel_History"
parcel_master = database_connection + "\\SDE.Parcels\\SDE.Parcel_Master"
parcel_base = database_connection + "\\SDE.Parcels\\SDE.Parcels_Base"

# Define the output layers
Parcels_toPoint = "c:\\temp\\gis\\Workspace.gdb\\Parcels_toPoint_2023"
new_output_layer = "c:\\temp\\gis\\Workspace.gdb\\New_Parcels"
inactive_output_layer = "c:\\temp\\gis\\Workspace.gdb\\Inactive_Parcels"
selection_layer_new = "c:\\temp\\gis\\Workspace.gdb\\Parcels2023joinedtoHistory_TEMP"  # This has all of the parcel 2023 joined to parcel history
selection_layer_inactive = "c:\\temp\\gis\\Workspace.gdb\\ParcelHistoryjoinedtoParcels2023_TEMP"  # This has all of the parcel 2023 joined to parcel history

# Configure the logging
log_file_path = os.path.join(working_folder, "parcel_history.log")  # Specify the path to your local directory
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename=log_file_path,  # Set the log file path
                    filemode='w')

# Create a logger
logger = logging.getLogger(__name__)
  
# Set the workspace environment
arcpy.env.overwriteOutput = True
arcpy.env.workspace = database_connection

#Convert Parcel Polygon features to centerpoints
arcpy.management.FeatureToPoint(in_features=Parcel_Poly_2023, out_feature_class=Parcels_toPoint, point_location="INSIDE")

# Replace these variables with your actual values
input_layer = Parcels_toPoint

# send email with attachments
def send_mail(body):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    msgText = MIMEText('%s<br><br>Cheers,<br>GIS Team' % (body), 'html')
    msg.attach(msgText)

    #attachment = MIMEText(open(fileToSend).read())
    #attachment.add_header("Content-Disposition", "attachment", filename = os.path.basename(fileToSend))
    #msg.attach(attachment)

    with smtplib.SMTP("mail.smtp2go.com", 25) as smtpObj:
            smtpObj.ehlo()
            smtpObj.starttls()
            smtpObj.sendmail(sender_email, receiver_email, msg.as_string())
    
# Function to remap the fields of an input layer
def remap_fields(output_layer):
    try:
        # Remove Parcels_toPoint_2023 from the field name
        arcpy.AlterField_management(output_layer, "Parcels_toPoint_2023_APN", "APN", "APN")
        arcpy.AlterField_management(output_layer, "Parcels_toPoint_2023_PPNO", "PPNO", "PPNO")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_Status", "Status", "Status")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_IsActive", "IsActive", "IsActive")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_APN_Current", "APN_Current", "APN_Current")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_APNS_CURRENT", "APNS_CURRENT", "APNS_CURRENT")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_Current_Address", "Current_Address", "Current_Address")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2006Active", "b2006Active", "b2006Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2007Active", "b2007Active", "b2007Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2008Active", "b2008Active", "b2008Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2009Active", "b2009Active", "b2009Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2010Active", "b2010Active", "b2010Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2011Active", "b2011Active", "b2011Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2012Active", "b2012Active", "b2012Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2013Active", "b2013Active", "b2013Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2014Active", "b2014Active", "b2014Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2015Active", "b2015Active", "b2015Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2016Active", "b2016Active", "b2016Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2017Active", "b2017Active", "b2017Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2018Active", "b2018Active", "b2018Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2019Active", "b2019Active", "b2019Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2020Active", "b2020Active", "b2020Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2021Active", "b2021Active", "b2021Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2022Active", "b2022Active", "b2022Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2023Active", "b2023Active", "b2023Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_Years_Active", "Years_Active", "Years_Active")       
        # Next year add arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2024Active", "b2024Active", "b2024Active")
    
        print("Field names changed")
        logger.info("Field names changed \n")
  

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        print(e)
        logger.info("Error: " + str(e) + "\n")

def create_new_version(new_version_name):
    try:
        # Create a new version
        parent_version = "SDE.DEFAULT"
        version_name_full = "SDE." + new_version_name

        version_list = arcpy.da.ListVersions(arcpy.env.workspace)
        version_exists = False

        for version in version_list:
            if version.name == version_name_full:
                version_exists = True
                break
        
        if version_exists:
            # Delete the version
            arcpy.management.DeleteVersion(arcpy.env.workspace, version_name_full)
            print("Deleted existing version")
            logger.info("Deleted existing version\n")

        # Create a new version
        arcpy.CreateVersion_management(arcpy.env.workspace, parent_version, new_version_name, "PUBLIC")

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        print(e)
        logger.info("Error: " + str(e) + "\n")

def add_missing_records(input_layer, target_layer, output_layer, join_field):
    try:
        # Set the workspace environment
        arcpy.env.workspace = arcpy.Describe(input_layer).path
        
        # Create a join layer
        # Specify the type of join - Options are KEEP_COMMON and KEEP_ALL
        join_type = 'KEEP_ALL' 
    
        # Join both layers
        Parcel_History_Layer_Joined = arcpy.management.AddJoin(input_layer, join_field, target_layer, join_field, join_type)

        # Copy the newly joined data and then remove the join 
        arcpy.management.CopyFeatures(Parcel_History_Layer_Joined, selection_layer_new)
        
        # Clean up
        arcpy.management.RemoveJoin(Parcel_History_Layer_Joined)
        
        # Select features where the join field in the target layer is null (which means there is a missing record)
        temp_layer = arcpy.SelectLayerByAttribute_management(selection_layer_new,"NEW_SELECTION", "SDE_Parcel_History_APN IS NULL")

        arcpy.env.workspace = database_connection

        # Copy the selected missing features to a new feature class
        # But first let's see how many features there are in parcel_history before we put in the new records
        count = int(arcpy.GetCount_management(temp_layer).getOutput(0))
        arcpy.CopyFeatures_management(temp_layer, output_layer)
        print(f"{count} missing records identified and saved to {output_layer}.")
        logger.info(f"{count} missing records identified and saved to {output_layer} \n")

        # Only do the following if count is greater than 0
        if count > 0:
            # Change the field name
            remap_fields(output_layer)
            # Set multiple values in output_layer to another field

            # ToDO: Populate the PPNO field and County field
            with arcpy.da.UpdateCursor(output_layer, ["IsActive", "APN_Current", "APNS_CURRENT", "APN","STATUS", "b2006Active","b2007Active","b2008Active","b2009Active","b2010Active",
                                                    "b2011Active","b2012Active","b2013Active","b2014Active","b2015Active","b2016Active","b2017Active","b2018Active","b2019Active",
                                                    "b2020Active","b2021Active","b2022Active","b2023Active", "Years_Active"
                                                    ]) as cursor:
                for row in cursor:
                    row[0] = "1"                #IsActive
                    row[1] = row[3]             #APN_Current
                    row[2] = row[3]             #APNS_Current
                    row[4] = "Active"           #Status
                    row[5] = "0"                #2006 Active
                    row[6] = "0"                #2007 Active
                    row[7] = "0"                #2008 Active
                    row[8] = "0"                #2009 Active
                    row[9] = "0"                #2010 Active
                    row[10] = "0"               #2011 Active
                    row[11] = "0"               #2012 Active
                    row[12] = "0"               #2013 Active
                    row[13] = "0"               #2014 Active
                    row[14] = "0"               #2015 Active
                    row[15] = "0"               #2016 Active
                    row[16] = "0"               #2017 Active
                    row[17] = "0"               #2018 Active
                    row[18] = "0"               #2019 Active
                    row[19] = "0"               #2020 Active
                    row[20] = "0"               #2021 Active
                    row[21] = "0"               #2022 Active
                    row[22] = "1"               #2023 Active
                    # Next year add #2024 Active and set 2023 active to 0
                    row[23] = ""                #Years Active    - Set this later in the script
                    cursor.updateRow(row)
           
            # Switch to the new version
            #old_fc = "parcel_history_fc"
            #arcpy.MakeFeatureLayer_management(target_layer,old_fc)
            #print("Created feature layer " + old_fc)

            # Creat a new version in the SDE database
            #new_version_name = "Parcel_History_Updates"
            #create_new_version(new_version_name)
        
            # Switch to the new version
            #arcpy.ChangeVersion_management(old_fc,'TRANSACTIONAL', "SDE." + new_version_name, '')
            #print("Switched to new version")
            
            # Get record count of the target layer
            count = int(arcpy.GetCount_management(target_layer).getOutput(0))
            print(f"Number of records in target layer: {count}")
            logger.info(f"Number of records in target layer: {count}\n")
            
            edit = arcpy.da.Editor(arcpy.env.workspace)
            edit.startEditing()
            edit.startOperation()
                            
            fields = ["SHAPE@", "APN","IsActive", "APN_Current", "APNS_CURRENT", "APN","STATUS", "b2006Active","b2007Active","b2008Active","b2009Active","b2010Active",
                                                    "b2011Active","b2012Active","b2013Active","b2014Active","b2015Active","b2016Active","b2017Active","b2018Active","b2019Active",
                                                    "b2020Active","b2021Active","b2022Active","b2023Active", "Years_Active"]
            values = [list(row) for row in arcpy.da.SearchCursor(output_layer, fields)]
                        
            #Create an insert cursor
            iCursor = arcpy.da.InsertCursor(target_layer, fields)           
            for row in values:
                iCursor.insertRow(row)

            # Stop the edit session
            edit.stopEditing(True)

            count = int(arcpy.GetCount_management(target_layer).getOutput(0))
            print(f"Number of records in target layer: {count}")
        
        else:
            print(f"No new parcels to add.")

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        print(e)
        logger.info("Error: " + str(e) + "\n")

# Create find_obsolete_records function
def find_obsolete_records(input_layer, target_layer, join_field):
    try:
        print("Finding obsolete records")
        # Set the workspace environment
        arcpy.env.workspace = arcpy.Describe(target_layer).path
        
        # Create a join layer
        inactive_selection_layer = arcpy.management.AddJoin(target_layer, join_field, input_layer, join_field, 'KEEP_ALL' )
        
        # Copy the newly joined data and then remove the join 
        arcpy.management.CopyFeatures(inactive_selection_layer, selection_layer_inactive)
        
        # Clean up
        arcpy.management.RemoveJoin(inactive_selection_layer)
                    
        temp_layer = arcpy.SelectLayerByAttribute_management(selection_layer_inactive,"SUBSET_SELECTION", "Parcels_toPoint_2023_APN IS NULL AND SDE_Parcel_History_IsActive = 1")
        arcpy.CopyFeatures_management(temp_layer, inactive_output_layer)
        
        # Get the count of parcels to update to inactive 
        count = int(arcpy.GetCount_management(temp_layer).getOutput(0))
        print(f"{count} obsolete records identified that need to be updated.")

        # Only do the following if count is greater than 0
        if count > 0:
            arcpy.env.workspace = database_connection
            edit = arcpy.da.Editor(arcpy.env.workspace)
            edit.startEditing()
            edit.startOperation()

            # Create a list of APNs to update
            update_list = [row[0] for row in arcpy.da.SearchCursor(temp_layer, "Parcels_toPoint_2023_APN")]
            print(f"List of APNs to update: {update_list}")

            # Update the IsActive field to 0 and b2023Active to 0 
            with arcpy.da.UpdateCursor(target_layer, ["APN", "IsActive", "b2023Active"]) as cursor:
                print("Updating records")
                for row in cursor:
                    apn_key = row[0]
                    # Check if the APN is in the list of inactive parcels
                    if row[0] in update_list:
                        row[1] = "0"                # IsActive
                        row[2] = "0"                # 2023 Active
                        print(f"Updating parcel {apn_key} to inactive.")
                        cursor.updateRow(row)        
                    
            # Stop the edit session
            edit.stopEditing(True)
            print("Stopped edit session")            

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        print(e)
        logger.info("Error: " + str(e) + "\n")

def populate_new_fields():
    try:
        arcpy.env.workspace = database_connection
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing()
        edit.startOperation()

        # Set b2023Active to true in parcel_master if the parcel is active
        print("Populating b2023Active and Active fields")

        # Create a dictionary of APNs and IsActive values from 2023Parcels
        apnDict = dict([(r[0], r[1]) for r in arcpy.da.SearchCursor(Parcel_Poly_2023, ["APN","APN"])])
        print("Created dictionary")
        
        with arcpy.da.UpdateCursor(parcel_history, ["APN", "b2023Active", "IsActive", "Status"]) as cursor:    
            # Get the APN from the row
            for row in cursor:
                apn = row[0]
                # Check if the APN is in the dictionary
                if apn in apnDict:
                    row[1] = 1
                    row[2] = 1
                    row[3] == "Active"
                else:
                    row[1] = 0
                    row[2] = 0
                    row[3] == "Inactive"
                cursor.updateRow(row)

        # Stop the edit session
        edit.stopEditing(True)
    
    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        logger.info("Error: " + str(e) + "\n")

def build_years_active():
    try:
        print("Building Years Active")
        arcpy.env.workspace = database_connection
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing()
        edit.startOperation()
        with arcpy.da.UpdateCursor(parcel_history, ["APN", "b2023Active", "Years_Active"]) as cursor:
            for row in cursor:
                years_active = ""
                if str(row[1]) == "1": #2023 Active
                    if row[2] == "":
                        years_active = "2023"
                    else:
                        years_active = "2023," + str(row[2])
                        
                    if years_active != row[2]:
                        row[2] = years_active
                        cursor.updateRow(row)
                
        # Stop the edit session
        edit.stopEditing(True)
        print("Finished building Years Active")

    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        logger.info("Error: " + str(e) + "\n")


def update_current_apn():
    try:
        # For inactive parcels, update the Current APN and Current APNs        
        print("Updating Current APN and Current APNs. Start time: : " + time.strftime("%Y-%m-%d %H:%M:%S"))
        arcpy.env.workspace = database_connection
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing()
        edit.startOperation()
        
        # Join Parcel_Poly_2023
        currentapns_join = "C:\\temp\\gis\\Workspace.gdb\\CurrentAPNs_Join"
        
        temp_layer = arcpy.SelectLayerByAttribute_management(parcel_history,"NEW_SELECTION", "IsActive = 0")
        
        # Buffer temp_layer - This is necessary because the point may not get an overlap of the new parcels
        temp_layer_buffer = "C:\\temp\\gis\\Workspace.gdb\\CurrentAPNs_Buffer"
        arcpy.analysis.Buffer(temp_layer, temp_layer_buffer, "1 Feet", "FULL", "ROUND", "NONE", None, "PLANAR")
        arcpy.analysis.SpatialJoin(temp_layer_buffer, parcel_master, currentapns_join, "JOIN_ONE_TO_MANY")
        i = 0
        print ("starting check at time: "+ time.strftime("%Y-%m-%d %H:%M:%S"))

        with arcpy.da.UpdateCursor(parcel_history, ["APN", "APN_Current", "APNS_CURRENT"], "IsActive = 0") as cursor:
            for row in cursor:
                new_currentapn_string = ""
                new_all_apns_string = ""
                old_currentapn_string = ""
                old_all_apns_string = ""
                apn = row[0]
                old_currentapn_string = str(row[1])
                old_all_apns_string = str(row[2])
                with arcpy.da.SearchCursor(currentapns_join, ["APN_1"], "APN = '" + apn + "'", sql_clause=(None, "ORDER BY APN_1 ASC")) as cur:
                    for r in cur:
                        new_currentapn_string = str(r[0])
                        if str(r[0]) != "None":
                            # Check to see if string already contains the value
                            if str(r[0]) not in new_all_apns_string:
                                new_all_apns_string += str(r[0]) + ", "


                    if new_all_apns_string.endswith(", "):
                        new_all_apns_string = new_all_apns_string[:-2]

                    # Update if value has changed and is not empty
                    if new_currentapn_string != old_currentapn_string:
                        row[1] = new_currentapn_string
                        cursor.updateRow(row)
                        i += 1

                    if (new_all_apns_string != old_all_apns_string) and (new_all_apns_string != ""):
                        row[2] = new_all_apns_string
                        cursor.updateRow(row)
                        i += 1

        print("Number of records updated: " + str(i))
        # Stop the edit session
        edit.stopEditing(True)
        print("Finished updating Current APN and Current APNs: : " + time.strftime("%Y-%m-%d %H:%M:%S"))

    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        logger.info("Error: " + str(e) + "\n")

def update_attributes():
    # Insert try and except blocks
    try:
        
        edit = arcpy.da.Editor(arcpy.env.workspace)
        edit.startEditing()
        edit.startOperation()
        print("Started edit session")
        
        luDict = dict([(r[0], (r[1],r[2])) for r in arcpy.da.SearchCursor(parcel_master, ["APN","APO_ADDRESS","EXISTING_LANDUSE"])])
        luCountyDict = dict([(r[0], (r[1],r[2])) for r in arcpy.da.SearchCursor(parcel_base, ["APN","JURISDICTION","PPNO"])])
        
        i = 0
        with arcpy.da.UpdateCursor(parcel_history, ["APN_Current","Current_Address", "LandUse_Description", "JURISDICTION", "PPNO"]) as cursor:    
            # print row count
            print("Row count: " + str(arcpy.GetCount_management(parcel_history).getOutput(0)))
            for row in cursor:
                i += 1
                if i < 250:
                    apn_current = row[0]   #joinFieldValue is populated with APN
                    # Set value to emtpy string if dictionary key does not exist
                    try:
                        master_address = luDict[apn_current][0].strip()
                    except KeyError:
                        master_address = "" 
                    try:
                        master_landuse =  luDict[apn_current][1].strip()
                    except KeyError:
                        master_landuse = ""
                    try:
                        master_county =  luCountyDict[apn_current][0].strip()
                    except KeyError:
                        master_county = ""
                    try:
                        master_ppno =  luCountyDict[apn_current][1]

                    except KeyError:
                        master_ppno = ""

                    history_address = row[1]
                    history_landuse = row[2]
                    history_county = row[3]
                    history_ppno = row[4]

                    # if master_address is not equal to the current address, update the current address
                    update = False
                    if master_address != history_address:
                        row[1] = master_address
                        update = True
                    if master_landuse != history_landuse:
                        row[2] = master_landuse
                        update = True
                    if master_county != history_county:
                        row[3] = master_county
                        update = True
                    #if master_ppno != history_ppno:
                    #    updateRow[4] = master_ppno
                    #    updateRows.updateRow(updateRow)
                        
                    if update:
                        print("Updating row")
                        cursor.updateRow(row)                        
                    

        # Stop the edit session
        edit.stopEditing(True)
        print("Stopped edit session")
    
    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        logger.info("Error: " + str(arcpy.GetMessages(2)) + "\n")

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        logger.info("Error: " + str(e) + "\n")


# Call the function to find missing records
add_missing_records(input_layer, parcel_history, new_output_layer, "APN")

# Call the function to find active parcels that are now obsolete
find_obsolete_records(input_layer, parcel_history, "APN")

# Set b2023Active for all active parcels (Replace with new field each year)
populate_new_fields()

# Update Current APN and Current APNs for Inactive parcels
update_current_apn()

# Build Years Active String
build_years_active()

#Update address and land use and jurisdiction. Run this after updating current parcel
update_attributes()