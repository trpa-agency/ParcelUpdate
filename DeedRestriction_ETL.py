import pandas as pd
import sqlalchemy


dfDeed     = pd.read_json("https://laketahoeinfo.org/WebServices/GetDeedRestrictedParcels/JSON/e17aeb86-85e3-4260-83fd-a2b32501c476")


def checkCSVdiff(csv1, csv2):
    with open(csv1,csv2):
        import pandas as pd

        # Read the first CSV file into a DataFrame
        df1 = pd.read_csv('file1.csv')

        # Read the second CSV file into a DataFrame
        df2 = pd.read_csv('file2.csv')

        # Find the rows that are in df2 but not in df1
        new_records = df2[~df2.isin(df1.to_dict('list')).all(axis=1)]

        # Display the new records
        print("New Records:")
        print(new_records)
    if not new_records.empty:
        # Display and accumulate new records
        print("New Records:")
        print(new_records)
        
        # Append new records to the accumulated DataFrame
        accumulated_records = accumulated_records.append(new_records)

        # Optionally, save the accumulated records to a CSV file
        accumulated_records.to_csv('accumulated_records.csv', index=False)


# Define the paths to your geodatabase and feature classes
geodatabase_path = r'C:\path\to\your\geodatabase.gdb'
feature_class1 = 'FeatureClass1'
feature_class2 = 'FeatureClass2'

# Create a set to store the OBJECTID values of records in feature_class1
existing_records = set()

while True:
    # Open an update cursor on feature_class1
    with arcpy.da.UpdateCursor(
            arcpy.AddFieldDelimiters(geodatabase_path, feature_class1), ['OID@']) as cursor:
        for row in cursor:
            existing_records.add(row[0])

    # Open a search cursor on feature_class2
    with arcpy.da.SearchCursor(
            arcpy.AddFieldDelimiters(geodatabase_path, feature_class2), ['OID@']) as cursor:
        new_records = [row[0] for row in cursor if row[0] not in existing_records]

    if new_records:
        # Display and optionally append new records
        print("New Records in", feature_class2)
        print(new_records)

        # Optionally, append new records to feature_class1
        with arcpy.da.InsertCursor(
                arcpy.AddFieldDelimiters(geodatabase_path, feature_class1), ['SHAPE@']) as cursor:
            for oid in new_records:
                # Use a search cursor to get the geometry of the new record from feature_class2
                with arcpy.da.SearchCursor(
                        arcpy.AddFieldDelimiters(geodatabase_path, feature_class2), ['SHAPE@'],
                        where_clause="OID = " + str(oid)) as search_cursor:
                    for row in search_cursor:
                        cursor.insertRow(row)
        To Table
        To Email
        
    # Sleep for a while (e.g., 1 hour) before checking again
    time.sleep(3600)  # 3600 seconds = 1 hour