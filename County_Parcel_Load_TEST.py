import arcpy
import pandas as pd
import logging
from time import strftime
from pathlib import Path
import sys
import utils
import argparse

# Set up logging
LOG_FILE = Path("parcel_update_log.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

def parse_arguments():
    """Parse command-line arguments."""
    try:
        parser = argparse.ArgumentParser(description="Process GIS Parcel Update")
        parser.add_argument("mode", choices=["base", "master", "both"], help="Specify the update mode")
        return parser.parse_args()
    except Exception as e:
        logging.error(f"Error parsing arguments: {e}")
        sys.exit(1)

def setup_environment(workspace: Path):
    """Set up environment settings for arcpy."""
    try:
        arcpy.env.workspace = str(workspace)
        arcpy.env.overwriteOutput = True
        arcpy.env.outputCoordinateSystem = arcpy.SpatialReference(26910)
        logging.info("Environment setup completed successfully.")
    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy error in setup_environment: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error in setup_environment: {e}")
        sys.exit(1)

def delete_feature_class_if_exists(feature_class: Path):
    """Delete feature class if it exists."""
    try:
        if feature_class.exists():
            arcpy.management.Delete(str(feature_class))
            logging.info(f"Deleted feature class: {feature_class}")
    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy error deleting feature class {feature_class}: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error deleting feature class {feature_class}: {e}")
        sys.exit(1)

def create_parcel_points():
    """Create Parcel Points from Parcel_County_Staging."""
    try:
        staging_gdb = Path("F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb")
        parcel_staging = staging_gdb / "Parcel_County_Staging"
        parcel_points = staging_gdb / "Parcel_Points"

        delete_feature_class_if_exists(parcel_points)

        arcpy.management.FeatureToPoint(
            in_features=str(parcel_staging),
            out_feature_class=str(parcel_points),
            point_location="INSIDE"
        )
        logging.info("Parcel Points created successfully.")
    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy error creating parcel points: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error creating parcel points: {e}")
        sys.exit(1)

def create_version_if_needed(in_workspace: Path, version_name_full: str):
    """Create a new version if it doesn't exist."""
    try:
        version_list = arcpy.da.ListVersions(str(in_workspace))
        if any(version.name == version_name_full for version in version_list):
            arcpy.management.DeleteVersion(str(in_workspace), version_name_full)
            logging.info(f"Deleted existing version: {version_name_full}")
        
        arcpy.CreateVersion_management(str(in_workspace), "SDE.DEFAULT", version_name_full, "PUBLIC")
        logging.info(f"Version created: {version_name_full}")
    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy error creating version: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error creating version: {e}")
        sys.exit(1)

def create_database_connection(in_workspace: Path, version_name_full: str):
    """Create a database connection to the specified geodatabase."""
    try:
        arcpy.CreateDatabaseConnection_management(
            out_folder_path='db_connections/',
            out_name="ConnectionFile.sde",
            database_platform="SQL_SERVER",
            instance="sql12",
            database="sde",
            account_authentication="DATABASE_AUTH",
            username="sde",
            password="staff",
            version_type='TRANSACTIONAL',
            version=version_name_full
        )
        logging.info(f"Database connection created: {version_name_full}")
    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy error creating database connection: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error creating database connection: {e}")
        sys.exit(1)

def update_parcel_layer_if_needed(mode: str, parcel_new: Path, df_special_parcels: pd.DataFrame, version_name_full: str):
    """Call the update function based on the mode."""
    update_configs = {
        "master": ('SDE.Parcels.SDE.Parcel_Master', "Differences_List.csv", ['SHAPE', 'OBJECTID', 'Shape'], 
                   ['PARCEL_SQFT', 'PPNO', 'ESTIMATED_COVERAGE_ALLOWED', 'IMPERVIOUS_SURFACE_SQFT', 'LOCATION_TO_TOWNCENTER', 
                    'UNITS', 'PARCEL_ACRES', 'YEAR_BUILT', 'BEDROOMS', 'BUILDING_SQFT', 'BATHROOMS']),
        "base": ('SDE.Parcels.SDE.Parcels_Base', "Differences_List_Base.csv", ['SHAPE'], 
                 ['Shape', 'PARCEL_ACRES', 'PARCEL_SQFT', 'OBJECTID']),
    }
    fc_path, difference_csv, fields_to_exclude, fields_to_ignore = update_configs.get(mode, (None, None, None, None))

    if fc_path:
        utils.update_parcel_layer(
            str(parcel_new), 
            fc_path, 
            ('880','881','910','920','500', '510', '520', '530', '560', '570', '580', '590', '600', '700','800','900'),
            {"String": str, "Integer": int, "SmallInteger": int, "Single": float, "Double": float, "Date": pd.to_datetime}, 
            fields_to_exclude, 
            fields_to_ignore,
            df_special_parcels,
            difference_csv,
            'db_connections/ConnectionFile.sde',
            version_name_full
        )
        logging.info(f"{mode.capitalize()} update completed successfully.")
    else:
        logging.error(f"Invalid mode: {mode}. No update performed.")
        sys.exit(1)

def main():
    try:
        # Parse arguments
        args = parse_arguments()

        # Environment setup
        setup_environment(Path("F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"))

        # Create Parcel Points
        create_parcel_points()

        # Load special parcels DataFrame
        df_special_parcels = pd.read_excel("F:/GIS/PARCELUPDATE/Workspace/special_parcels.xlsx")
        
        # Workspace and Version Setup
        in_workspace = Path("F:/GIS/PARCELUPDATE/Workspace/Vector.sde")
        new_version_name = f"Parcel_Update_{strftime('%Y-%m-%d')}"
        version_name_full = f"SDE.{new_version_name}"

        create_version_if_needed(in_workspace, version_name_full)
        create_database_connection(in_workspace, version_name_full)

        # Update Parcel Layer based on the mode
        update_parcel_layer_if_needed(args.mode, Path("F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb/Parcel_County_Staging"), 
                                      df_special_parcels, version_name_full)

    except arcpy.ExecuteError as e:
        logging.error(f"ArcPy execution error: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
