"""
Script Name: Parcel_History_Update.py

Purpose: Update the Parcel_History layer in the SDE databse
required for the Parcel History layer in the GIS database.  This script will
be run annually to update the Parcel History table with the new parcels and
inactive parcels.  
Requirements: The script requires the following layers and folder locations:
1. Parcel Master - The master parcel layer
2. Parcel History - The parcel history layer
3. Parcels_toPoint - The parcel points layer
4. C:\\temp\\gis\\Workspace.gdb - The workspace geodatabase


Author: Amy Fish
Date: 11/5/24

TODO: 1. add county and ppno when inserting new records
      
"""
import arcpy
import sys 
import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from time import strftime

#Change this year with each update
current_year = "2024"

#Set the constants
subject = "Parcel History update"
sender_email = "infosys@trpa.org"
receiver_email = "afish@trpa.gov"

year_to_update = f"b{current_year}Active"

# Set the database connection. Versioned edits require the creation of a connection file
server_name = "sql12"
database_name = "sde"
username = "sde"
password = "staff"
database_connection = 'db_connections/HistoryConnectionFile.sde'

# Define the existing layers

parcel_master = f"F:\\GIS\\PARCELUPDATE\\Workspace\\Vector.sde\\SDE.Parcels\\SDE.Parcel_Master"
parcel_history = database_connection + "\\SDE.Parcels\\SDE.Parcel_History"
Parcels_toPoint_Path = f"F:\\GIS\\PARCELUPDATE\\Workspace\\Vector.sde\\SDE.Parcels\\SDE.ParcelPoints"

# Define the output layers
new_output_layer = "c:\\temp\\gis\\Workspace.gdb\\New_Parcels"
inactive_output_layer = "c:\\temp\\gis\\Workspace.gdb\\Inactive_Parcels"
selection_layer_new = f"c:\\temp\\gis\\Workspace.gdb\\Parcels{current_year}joinedtoHistory_TEMP"  # This has all of the parcel 2024 joined to parcel history
selection_layer_inactive = "c:\\temp\\gis\\Workspace.gdb\\ParcelHistoryjoinedtoParcels" + current_year + "_TEMP"  # This has all of the parcel 2024 joined to parcel history

# Function to remap the fields of an input layer
def remap_fields(output_layer):
    try:
        # Remove Parcels_toPoint_2023 from the field name
        arcpy.AlterField_management(output_layer, "Parcels_toPoint_" + current_year + "_APN", "APN", "APN")
        arcpy.AlterField_management(output_layer, "Parcels_toPoint_" + current_year + "_PPNO", "PPNO", "PPNO")
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
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2024Active", "b2024Active", "b2024Active")
        arcpy.AlterField_management(output_layer, "SDE_Parcel_History_Years_Active", "Years_Active", "Years_Active")       
        # Next year add arcpy.AlterField_management(output_layer, "SDE_Parcel_History_b2025Active", "b2025Active", "b2025Active")
    
        print("Field names changed")
        
  

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        sys.exit()

    except Exception as e:
        print(e)
        sys.exit()

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
        
        # Only do the following if count is greater than 0
        if count > 0:
            # Change the field name
            remap_fields(output_layer)
            # Set multiple values in output_layer to another field

            # ToDO: Populate the PPNO field and County field
            with arcpy.da.UpdateCursor(output_layer, ["IsActive", "APN_Current", "APNS_CURRENT", "APN","STATUS", "b2006Active","b2007Active","b2008Active","b2009Active","b2010Active",
                                                    "b2011Active","b2012Active","b2013Active","b2014Active","b2015Active","b2016Active","b2017Active","b2018Active","b2019Active",
                                                    "b2020Active","b2021Active","b2022Active","b2023Active", "Years_Active","b2024Active"
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
                    row[22] = "0"               #2023 Active
                    # Next year add #2025 Active and set 2024 active to 0
                    row[23] = ""                #Years Active    - Set this later in the script
                    row[24] = "1"               #2024 Active
                    cursor.updateRow(row)

            
            # Get record count of the target layer
            count = int(arcpy.GetCount_management(target_layer).getOutput(0))
            print(f"Number of records in target layer: {count}")
            fields = ["SHAPE@", "APN","IsActive", "APN_Current", "APNS_CURRENT", "APN","STATUS", "b2006Active","b2007Active","b2008Active","b2009Active","b2010Active",
                                                    "b2011Active","b2012Active","b2013Active","b2014Active","b2015Active","b2016Active","b2017Active","b2018Active","b2019Active",
                                                    "b2020Active","b2021Active","b2022Active","b2023Active","b2024Active", "Years_Active"]

            values = [list(row) for row in arcpy.da.SearchCursor(output_layer, fields)]
                        

            arcpy.ChangeVersion_management(target_layer,'TRANSACTIONAL', version_name_full, '')
            edit = arcpy.da.Editor(database_connection)
            edit.startEditing(False, True)
            edit.startOperation()
            iCursor = arcpy.da.InsertCursor(target_layer, fields)   
            for row in values:
                iCursor.insertRow(row)
            # Save the changes
            edit.stopOperation()
            count = int(arcpy.GetCount_management(target_layer).getOutput(0))
            print(f"Number of records in target layer: {count}")
        
        else:
            print(f"No new parcels to add.")

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        sys.exit()

    except Exception as e:
        print(e)
        sys.exit()

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
                    
        temp_layer = arcpy.SelectLayerByAttribute_management(selection_layer_inactive,"SUBSET_SELECTION", "Parcels_toPoint_" +  current_year + "_APN IS NULL AND SDE_Parcel_History_IsActive = 1")
        arcpy.CopyFeatures_management(temp_layer, inactive_output_layer)
        
        # Get the count of parcels to update to inactive 
        count = int(arcpy.GetCount_management(temp_layer).getOutput(0))
        print(f"{count} obsolete records identified that need to be updated.")

        # Only do the following if count is greater than 0
        if count > 0:
            #arcpy.env.workspace = database_connection
            update_list = [row[0] for row in arcpy.da.SearchCursor(temp_layer, "SDE_Parcel_History_APN")]        
            # Update the IsActive field to 0 and b2023Active to 0 
            with arcpy.da.UpdateCursor(target_layer, ["APN", "IsActive", year_to_update, "Status"]) as cursor:
                print("Updating records")
                for row in cursor:
                    apn_key = row[0]
                    # Check if the APN is in the list of inactive parcels
                    if row[0] in update_list:
                        row[1] = "0"                # IsActive
                        row[2] = "0"                # Current Year Active
                        row[3] = "Inactive"         # Status
                        cursor.updateRow(row)        
                    
            # Stop the edit session to save the changes
            edit.stopOperation()

    except arcpy.ExecuteError:
        print(arcpy.GetMessages(2))
        sys.exit()

    except Exception as e:
        print(e)
        sys.exit()

def populate_new_fields():
    try:
        arcpy.env.workspace = database_connection

        # Set b2023Active to true in parcel_master if the parcel is active
        print(f"Populating Active fields")

        # Create a dictionary of APNs and IsActive values from 2024 Parcels
        Parcel_Poly_Current = "Parcel_Poly_Current"
        arcpy.MakeFeatureLayer_management(parcel_master,Parcel_Poly_Current)
        apnDict = dict([(r[0], r[1]) for r in arcpy.da.SearchCursor(Parcel_Poly_Current, ["APN","APN"])])
        print("Created dictionary")
        
        with arcpy.da.UpdateCursor(parcel_history, ["APN", "IsActive", "Status"]) as cursor:    
            # Get the APN from the row
            for row in cursor:
                apn = row[0]
                # Check if the APN is in the dictionary
                if apn in apnDict:
                    row[1] = 1
                    row[2] == "Active"
                else:
                    row[1] = 0
                    row[2] == "Inactive"
                cursor.updateRow(row)
        
        edit.stopOperation()
        del Parcel_Poly_Current
    
    except arcpy.ExecuteError:
        print(f"Arcpy error: {arcpy.GetMessages(2)}")
        sys.exit()

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print(f"Error on line: {lineno}")
        print(f"General error: {e}")
        print(f"{exc_type} {fname} {tb.tb_lineno}")
        sys.exit()

def build_years_active():
    try:
        with arcpy.da.UpdateCursor(parcel_history, ["APN", "IsActive", "Years_Active", "Status", "b2024Active"]) as cursor:
            for row in cursor:
                years_active = ""
                if str(row[1]) == "1": #Is Active
                    row[3] = "Active"
                    row[4] = 1
                    
                    if row[2] == "":
                        years_active = current_year
                    else:
                        years_active = f"{current_year},{row[2]}"
                    
                    if years_active != row[2]:
                        row[2] = years_active
                    
                    
                cursor.updateRow(row)

        edit.stopOperation()
        print ("Finished building Years Active: "+ time.strftime("%Y-%m-%d %H:%M:%S"))

    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)

def update_current_apn():
    try:
        # For inactive parcels, update the Current APN and Current APNs        
        print("Updating Current APN and Current APNs. Start time: : " + time.strftime("%Y-%m-%d %H:%M:%S"))
        
        # Join Parcel_Poly_2023
        currentapns_join = "C:\\temp\\gis\\Workspace.gdb\\CurrentAPNs_Join"
        temp_layer = arcpy.SelectLayerByAttribute_management(parcel_history,"NEW_SELECTION", "IsActive = 0")
        
        # Buffer temp_layer - This is necessary because the point may not get an overlap of the new parcels
        temp_layer_buffer = "C:\\temp\\gis\\Workspace.gdb\\CurrentAPNs_Buffer"
        arcpy.analysis.Buffer(temp_layer, temp_layer_buffer, "1 Feet", "FULL", "ROUND", "NONE", None, "PLANAR")
        arcpy.analysis.SpatialJoin(temp_layer_buffer, parcel_master, currentapns_join, "JOIN_ONE_TO_MANY")
        i = 0
        print ("starting check at time: "+ time.strftime("%Y-%m-%d %H:%M:%S"))

        #with arcpy.da.UpdateCursor(parcel_history, ["APN", "APN_Current", "APNS_CURRENT"], "IsActive = 0") as cursor:
        with arcpy.da.UpdateCursor(parcel_history, ["APN", "APN_Current", "APNS_CURRENT", "IsActive", "Status", "b2024Active"]) as cursor:
            for row in cursor:
                new_currentapn_string = ""
                new_all_apns_string = ""
                old_currentapn_string = ""
                old_all_apns_string = ""

                # If Active, update the Current APN and Current APNs
                if row[3] == 1:
                    row[1] = row[0]     # Current APN
                    row[2] = row[0]     # Current APNs
                    row[4] = "Active"   # Status              

                else:
                    apn = row[0]
                    row[4] = "Inactive"     # Status
                    row[5] = 0              # 2024 Active for inactive parcels
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

                        if (new_all_apns_string != old_all_apns_string) and (new_all_apns_string != ""):
                            row[2] = new_all_apns_string

                cursor.updateRow(row)

        edit.stopOperation()
        del temp_layer
        del temp_layer_buffer
        del currentapns_join
        print("Number of records updated: " + str(i))
        print("Finished updating Current APN and Current APNs: : " + time.strftime("%Y-%m-%d %H:%M:%S"))

    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        sys.exit()

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        sys.exit()

def update_attributes():
    try:      
        luDict = dict([(r[0], (r[1],r[2])) for r in arcpy.da.SearchCursor(parcel_master, ["APN","APO_ADDRESS","EXISTING_LANDUSE"])])
        luCountyDict = dict([(r[0], (r[1],r[2])) for r in arcpy.da.SearchCursor(parcel_master, ["APN","JURISDICTION","PPNO"])])
        
        i = 0
        with arcpy.da.UpdateCursor(parcel_history, ["APN_Current","Current_Address", "LandUse_Description", "JURISDICTION", "PPNO"]) as cursor:    
            
            for row in cursor:
                i += 1
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
                if master_ppno != history_ppno:
                    # CHECK TO SEE IF MASTER_PPNO IS NOT NULL OR EMPTY
                    if master_ppno != "" and master_ppno is not None:
                        row[4] = master_ppno
                        update = True                       
                    
                    if update:
                        cursor.updateRow(row)                        
        edit.stopOperation()            

    except arcpy.ExecuteError:
        print("Arcpy error:" + str(arcpy.GetMessages(2)))
        sys.exit()

    except Exception as e:
        # Get line number of error
        exc_type, exc_obj, tb = sys.exc_info()
        fname = os.path.split(tb.tb_frame.f_code.co_filename)[1]
        f = tb.tb_frame
        lineno = tb.tb_lineno
        print("Error on line: " + str(lineno))
        print ("General error:" + str(e))
        print(exc_type, fname, tb.tb_lineno)
        sys.exit()

#1. Set the workspace environment
print ("Process started: "+ time.strftime("%Y-%m-%d %H:%M:%S"))
arcpy.env.overwriteOutput = True
inWorkspace = "F:\GIS\PARCELUPDATE\Workspace\Vector.sde"
arcpy.env.workspace = inWorkspace

Parcels_toPoint = "Parcels_toPoint"
arcpy.MakeFeatureLayer_management(Parcels_toPoint_Path,Parcels_toPoint)

#make a copy of the layer
ParcelPoints = arcpy.CopyFeatures_management(Parcels_toPoint, f"c:\\temp\\gis\\Workspace.gdb\\Parcels_toPoint_{current_year}")

# Replace these variables with your actual values
input_layer = ParcelPoints

# Set up version and connection
new_version_name = "Parcel_History_" + strftime("%Y-%m-%d")
parent_version = "SDE.DEFAULT"
version_name_full = "SDE." + new_version_name
version_list = arcpy.da.ListVersions(inWorkspace)
version_exists = False

for version in version_list:
    if version.name == version_name_full:
        version_exists = True
        break

if version_exists:
    # Delete the version
    arcpy.management.DeleteVersion(inWorkspace, version_name_full)

# Create a new version
arcpy.CreateVersion_management(inWorkspace, parent_version, new_version_name, "PUBLIC")

arcpy.CreateDatabaseConnection_management(
    out_folder_path='db_connections/',
    out_name="HistoryConnectionFile.sde",
    database_platform="SQL_SERVER",  # Replace with your DBMS type (e.g., ORACLE, SQL_SERVER, POSTGRESQL)
    instance=server_name,
    database=database_name,
    account_authentication="DATABASE_AUTH",  # Use "OPERATING_SYSTEM" for OS authentication
    username=username,
    password=password,
    version_type='TRANSACTIONAL',
    version=version_name_full
)

history_fc = 'History_Feature_Class'
arcpy.MakeFeatureLayer_management(parcel_history,history_fc)
arcpy.ChangeVersion_management(history_fc,'TRANSACTIONAL', version_name_full, '')
edit = arcpy.da.Editor(database_connection)
edit.startEditing(False, True)

# Find missing records
add_missing_records(input_layer, history_fc, new_output_layer, "APN")

# Find active parcels that are now obsolete
find_obsolete_records(input_layer, parcel_history, "APN")

# Set b2024Active for all active parcels (Replace with new field each year)
populate_new_fields()

# Update Current APN and Current APNs for Inactive parcels
update_current_apn()

# Build Years Active String
build_years_active()

# Update address and land use and jurisdiction. Run this after updating current parcel
update_attributes()

#All done! Clean up and save
edit.stopEditing(True)
del Parcels_toPoint
del history_fc

header = "SUCCESS - Parcel_History feature class updated."
print ("Process completed: "+ time.strftime("%Y-%m-%d %H:%M:%S"))