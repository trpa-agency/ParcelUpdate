import arcpy
import pandas as pd

# Define the path to the spreadsheet and read it
spreadsheet_path = r"F:\GIS\DOCUMENTATION\metadata_updates.xlsx"
metadata_df = pd.read_excel(spreadsheet_path)

# Define the workspace or root folder where the datasets are stored
workspace = r"F:\GIS\PARCELUPDATE\Workspace\Vector.sde"

# Loop through each row in the spreadsheet
for index, row in metadata_df.iterrows():
    dataset_name = row['Dataset Name']  
    description = row['Description']
    summary = row['Summary']
    title = row['Title']
    tags = row['Tags']
    credits = row['Credits']
    uselimitations = row['Use Limitations']


    # Path to the dataset within the workspace
    dataset_path = f"{workspace}\\{dataset_name}"

    # Check if the dataset exists
    if arcpy.Exists(dataset_path):
        # Access the metadata for the dataset
        metadata = arcpy.metadata.Metadata(dataset_path)

        # Update metadata fields from spreadsheet values
        metadata.title = dataset_name
        metadata.summary = summary
        metadata.description = description
        metadata.tags = tags
        metadata.accessConstraints = uselimitations
        metadata.credits = credits

        # Save the changes to the metadata
        metadata.save()
        print(f"Metadata updated for {dataset_name}")
    else:
        print(f"Dataset {dataset_name} not found in sde database.")

print("Metadata update process complete.")
