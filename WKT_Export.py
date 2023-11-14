import arcpy
import requests
import os
import time

# setup
arcpy.env.workspace = "C:\GIS\Scratch.gdb"
arcpy.env.overwriteOutput = True

# network path to connection files
filePath   = "C:\\GIS\\DB_CONNECT"
sdeBase    = os.path.join(filePath, "Vector.sde")
parcelBase = os.path.join(sdeBase, 'SDE.Parcels\SDE.Parcels_Base')

#output projected in-memory feature class
parcelLayerProjected = "ParcelLayerProjected"

# Set output coordinate system to be WGS 1984
outCS = arcpy.SpatialReference(4326)

# run project tool
arcpy.Project_management(parcelBase, parcelLayerProjected, outCS)

# where clause to limit parcels
where = "APN IN ('029-041-009', '016-091-020', '090-225-018')"

# #  make feature layer from parcel base
# parcelLayer = arcpy.management.MakeFeatureLayer("ParcelLayerProjected", "Parcel_Layer", where_clause=where)

parcelLayer = arcpy.management.MakeFeatureLayer("ParcelLayerProjected", "Parcel_Layer")

# time a function function
## use as decorator @timer
def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"Function {func.__name__} took {end_time - start_time} seconds to execute.")
        return result
    return wrapper

# create dictionary and post
@timer
def post_parcel_geom_update(featureLayer, url):
    # Use a SearchCursor to iterate through the features
    with arcpy.da.SearchCursor(featureLayer, ['SHAPE@WKT', 'APN']) as cursor:
        total_count = 0
        for row in cursor:
            total_count +=1
            if (total_count%1000)==0:
                print(f"Updating row {total_count}")
            # setup dictionary
            feature_dict = {
                'APN': row[1],
                'WKT': row[0]
            }
            print(feature_dict)
            requests.post(url, feature_dict)

# post geometries
post_url = 'https://laketahoeinfo.org/api/UpdateParcelGeometry/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4'
post_parcel_geom_update(parcelLayer, post_url)