#--------------------------------------------------------------------------------------------------------#
# import packages and modules
import arcpy
from collections import Counter
import pandas as pd
from time import strftime

try:
    # environment settings
    arcpy.env.workspace = "F:/GIS/PARCELUPDATE/Workspace/ParcelStaging.gdb"
    arcpy.env.overwriteOutput = True

    # vars
    layer_name = "parcel_county_staging"
    expected_counties = {"PL", "EL", "DG", "WA", "CC"}


    # Get the feature count
    feature_count = int(arcpy.GetCount_management(layer_name)[0])

    # Validate feature count.
    if not (63000 <= feature_count <= 65500):
        print(f"Warning: Unexpected feature count: {feature_count}")

    # Extract unique county names from the dataset
    apn_list = []
    ppno_list = []
    missing_apns = []
    missing_ppnos = []
    missing_counties = []
    missing_jurisdiction = []
    missing_landuse = []
    invalid_county_records = []
    found_counties = set()
    invalid_apo_addresses = []

    with arcpy.da.SearchCursor(layer_name, ["APN", "County", "PPNO", "Jurisdiction", "Existing_LandUse", "APO_Address"], "Within_TRPA_BNDY = 1") as cursor:
        for row in cursor:
            apn, county, ppno, jurisdiction, existing_landuse, apo_address = row
            ppno = int(ppno)
            
            # Check for missing APNs
            if not apn or apn.strip() == "":
                missing_apns.append(apn)
            else:
                apn_list.append(apn)
            
            if not ppno:
                missing_ppnos.append(ppno)
            else:
                ppno_list.append(ppno)

            # Normalize to lowercase and count occurrences of "none"
            if apo_address and apo_address.lower().count("none") > 1:
                invalid_apo_addresses.append((apn, apo_address))

            # Check if county is valid
            if county not in expected_counties:
                invalid_county_records.append((apn, county))
            
            if not county:
                missing_counties.append(apn)
            
            if not existing_landuse:
                missing_landuse.append(apn)
            
            if not jurisdiction:
                missing_jurisdiction.append(apn)
            
            found_counties.add(row[1])

            #Check for missing counties or jurisdictions
            

    # Identify duplicate APNs and PPNOs
    duplicate_apns = [apn for apn, count in Counter(apn_list).items() if count > 1]
    
    # Identify duplicate PPNOs, excluding PPNO = 13040002
    duplicate_ppnos = [ppno for ppno, count in Counter(ppno_list).items() if count > 1 and ppno != 13040002]

    # Check for missing counties
    missing_counties = expected_counties - found_counties
    if missing_counties:
        print(f"Missing counties: {missing_counties}")
    else:
        print("All expected counties are present.")

    if missing_jurisdiction:
        print(f"Missing jurisdictions for parcels: {missing_jurisdiction}")

    if missing_landuse:
        #print just the number of missing land use
        print(f"Number of parcels missing land use: {len(missing_landuse)}")

    if missing_apns:
        print("Missing APNs found!")
    
    if missing_ppnos:
        print("Missing PPNOs found!")

    if duplicate_apns:
        print("Duplicate APNs found:")
        for apn in duplicate_apns[:5]:  # only the first 5 (for readability)
            print(apn)
    
    if duplicate_ppnos:
        # we already know that PPNO 13040002 is duplicated in both EL and WA
        print("Duplicate PPNOs found (excluding PPNO 13040002):")
        for ppno in duplicate_ppnos[:5]:
            print(ppno)

    if invalid_county_records:
        print("Parcels with invalid counties found:")
        for apn, county in invalid_county_records[:5]:  # only the first 5 (for readability)
            print(f"APN: {apn}, County: {county}")

    if invalid_apo_addresses:
        print("Warning: The following records have 'none' appearing more than once in apo_address:")
        for apn, address in invalid_apo_addresses[:5]:  # only the first 5 (for readability)
            print(f"APN: {apn}, Address: {address}")
    
    print("Validation complete.")

except arcpy.ExecuteError:
    print(f"ArcPy error: {arcpy.GetMessages(2)}")
except ValueError as ve:
    print(f"ValueError: {ve}")
except Exception as e:
    print(f"Unexpected error: {e}")