import arcpy
import logging
import pathlib

# Ensure the log file directory exists
log_file = r"C:\GIS\Logs\Parcel_Update_Annual.log"
pathlib.Path(log_file).parent.mkdir(parents=True, exist_ok=True)
# Set up logging
logging.basicConfig(filename=log_file, level=logging.INFO)

# env settings
arcpy.env.workspace = "C:\GIS\Scratch.gdb"
arcpy.env.overwriteOutput = True
# in memory fcs to use in the attribution stage
memory = "memory" + "\\"
# Define paths
sdeEdit = "F:\GIS\DB_CONNECT\Edit.sde"
sdeBase = "F:\GIS\DB_CONNECT\Vector.sde"

# feature classes
parcel_master_fc  = sdeBase + "\\SDE.Parcel\SDE.Parcel_Master"
parcel_history_fc = sdeEdit + "\\SDE.Parcel\SDE.Parcel_History_Attributed"
zoning_fc         = sdeBase + "\\SDE.Planning\SDE.District"
outfc             = "SpatialJoin_Parcel_History_District"

# function to update attributes
def update_attributes(parcels, join_fc, outfc, key, fields_to_update, join_fields):
    try:
        logging.info("Starting spatial join.")
        arcpy.analysis.SpatialJoin(
                    target_features=parcels,
                    join_features=join_fc,
                    out_feature_class=outfc,
                    join_operation="JOIN_ONE_TO_ONE",
                    join_type="KEEP_ALL",
                    field_mapping=None,
                    match_option="HAVE_THEIR_CENTER_IN",
                    search_radius=None,
                    distance_field_name="",
                    match_fields=None
                )
        # create a dictionary of joined attributes
        logging.info("Creating dictionary of joined attributes.")
        valueDict = {r[0]: r[1:] for r in arcpy.da.SearchCursor(outfc, [key] + join_fields)}
        # update the fields
        logging.info("Updating parcels with joined attributes.")
        with arcpy.da.UpdateCursor(parcels, [key] + fields_to_update) as updateRows:
            for updateRow in updateRows:
                keyValue = updateRow[0]
                if keyValue in valueDict:
                    for i in range(len(fields_to_update)):
                        updateRow[i + 1] = valueDict[keyValue][i]
                    updateRows.updateRow(updateRow)
        
        logging.info("Field join calculations complete.")
        arcpy.Delete_management(outfc)
    except arcpy.ExecuteError:
        logging.error(arcpy.GetMessages(2))
        raise
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise


import arcpy
from time import strftime

def update_parcel_boundary_size(parcel_history_fc, sde_TRPAboundary, sde_BonusUnitboundary):
    """
    Function to update parcel data with TRPA and Bonus Unit Boundary status, and calculate areas in acres and square feet.
    
    :param parcel_history_fc: Feature class containing the parcel history
    :param sde_TRPAboundary: TRPA boundary feature class
    :param sde_BonusUnitboundary: Bonus unit boundary feature class
    """
    
    # Start an edit session and operation
    edit = arcpy.da.Editor(arcpy.env.workspace)
    edit.startEditing(False, True)  # Start editing with undo/redo
    edit.startOperation()  # Start a new operation

    try:
        ParcelLayer = parcel_history_fc

        # set within TRPA boundary
        print("Identifying parcels within TRPA Boundary: " + strftime("%Y-%m-%d %H:%M:%S"))
        # log.info('Identifying parcels within TRPA Boundary: ' + strftime("%Y-%m-%d %H:%M:%S"))

        # Select all new parcels that have their center within
        parcelSelect = arcpy.SelectLayerByLocation_management(ParcelLayer, 
                                                                'INTERSECT', 
                                                                sde_TRPAboundary, 
                                                                0, 
                                                                'NEW_SELECTION')

        # Update field 1= yes 0 = no
        with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_TRPA_BNDY_TRPA']) as cursor:
            for row in cursor:
                row[0] = '1'
                cursor.updateRow(row) 
        del cursor

        # Switch the selection
        parcelSelect = arcpy.SelectLayerByAttribute_management(parcelSelect,'SWITCH_SELECTION')

        # Update other parcels
        with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_TRPA_BNDY_TRPA']) as cursor:
            for row in cursor:
                row[0] = '0'
                cursor.updateRow(row)
        del cursor

        print("Within TRPA Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))
        # log.info("Within TRPA Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))

        # set within Bonus Unit Boundary
        print("Identifying parcels within bonus unit boundary: " + strftime("%Y-%m-%d %H:%M:%S"))
        # log.info("Identifying parcels within bonus unit boundary: " + strftime("%Y-%m-%d %H:%M:%S"))

        # Select all new parcels that have their center within
        parcelSelect = arcpy.SelectLayerByLocation_management(ParcelLayer, 
                                                                'HAVE_THEIR_CENTER_IN', 
                                                                sde_BonusUnitboundary, 
                                                                0, 
                                                                'NEW_SELECTION')

        with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_BONUSUNIT_BNDY_TRPA']) as cursor:
            for row in cursor:
                row[0] = '1'
                cursor.updateRow(row) 
        del cursor

        # Switch the selection
        parcelSelect = arcpy.SelectLayerByAttribute_management(parcelSelect,'SWITCH_SELECTION')

        with arcpy.da.UpdateCursor(parcelSelect, ['WITHIN_BONUSUNIT_BNDY_TRPA']) as cursor:
            for row in cursor:
                row[0] = '0'
                cursor.updateRow(row)
        del cursor

        print("Bonus Unit Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))
        # log.info("Bonus Unit Boundary Updated: " + strftime("%Y-%m-%d %H:%M:%S"))

        # Get record count
        result = arcpy.GetCount_management(ParcelLayer)
        print('{} has {} records now.'.format(ParcelLayer, result[0]))

        # Calculate Area Field (Acres)
        print("Calculating Acres..." + strftime("%Y-%m-%d %H:%M:%S"))
        with arcpy.da.UpdateCursor(ParcelLayer, ['PARCEL_ACRES_TRPA', 'SHAPE@']) as cursor:
            for row in cursor:
                row[0] = row[1].getArea('PLANAR', 'ACRES')
                cursor.updateRow(row)
        del cursor

        # Calculate Square Feet
        print("Calculating Square Feet..." + strftime("%Y-%m-%d %H:%M:%S"))
        with arcpy.da.UpdateCursor(ParcelLayer, ['PARCEL_SQFT_TRPA', 'SHAPE@']) as cursor:
            for row in cursor:
                row[0] = row[1].getArea('PLANAR', 'SquareFeetUS')
                cursor.updateRow(row)
        del cursor

        # Successfully completed the updates
        print("Area calculations completed.")
        
    except Exception as e:
        print(f"Error occurred: {e}")
        # Log or handle the error if necessary
    finally:
        # Stop the edit operation and session
        edit.stopOperation()
        edit.stopEditing(True)  # Save the changes


# function to truncate and append with edit session
def truncate_and_append_with_edit_session(parcel_history_fc, target_sde_fc):
    """
    Truncate the target parcel_history SDE feature class and append data from the source parcel_history_fc within an edit session.

    :param parcel_history_fc: The source feature class (e.g., parcel_history_fc).
    :param target_sde_fc: The target feature class in the SDE database (e.g., parcel_history_sde).
    """
    # Set up the edit session
    edit = arcpy.da.Editor(arcpy.env.workspace)
    try:
        # Start an edit session and operation
        edit.startEditing(False, True)  # False for no versioning, True for multi-user editing
        edit.startOperation()  # Start a new operation for undo/redo functionality

        # Truncate the target feature class to remove all existing records
        print(f"Truncating the target feature class: {target_sde_fc}")
        arcpy.management.TruncateTable(target_sde_fc)
        print(f"Target feature class {target_sde_fc} truncated successfully.")

        # Append the data from the source feature class to the target
        print(f"Appending data from {parcel_history_fc} to {target_sde_fc}")
        arcpy.management.Append(parcel_history_fc, target_sde_fc, "TEST")
        print(f"Data from {parcel_history_fc} successfully appended to {target_sde_fc}.")

        # Stop the edit operation and session, saving the changes
        edit.stopOperation()
        edit.stopEditing(True)  # Commit the changes

    except arcpy.ExecuteError:
        # Catch ArcPy-specific errors
        print(f"ArcPy Error: {arcpy.GetMessages()}")
        edit.stopOperation()  # Ensure the operation is stopped even on error
        edit.stopEditing(False)  # Discard changes if an error occurs
    except Exception as e:
        # Catch any general Python exceptions
        print(f"Error occurred: {e}")
        edit.stopOperation()  # Ensure the operation is stopped even on error
        edit.stopEditing(False)  # Discard changes if an error occurs

# Example usage of the function
parcel_history_fc = r"C:\path\to\parcel_history.shp"  # Source feature class
target_sde_fc = r"Database Connections\Your_SDE.sde\path\to\parcel_history_sde"  # Target SDE feature class

truncate_and_append_with_edit_session(parcel_history_fc, target_sde_fc)