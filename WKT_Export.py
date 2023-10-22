import arcpy
import requests
import os
import time

# import json
# network path to connection files
filePath   = "C:\\GIS\\DB_CONNECT"
sdeBase    = os.path.join(filePath, "Vector.sde")
parcelBase = os.path.join(sdeBase, 'SDE.Parcels\SDE.Parcels_Base')

#  make feature layer from parcel base
feature_layer_name = arcpy.management.MakeFeatureLayer(parcelBase, "Parcel_Layer")

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

# def get_parcel_wkt_list(featureLayer):    
#     # Define the list to store dictionaries
#     feature_list = []
#     # Use a SearchCursor to iterate through the features
#     with arcpy.da.SearchCursor(featureLayer, ['SHAPE@WKT', 'APN']) as cursor:
#         for row in cursor:
#             feature_dict = {
#                 'APN': row[1],
#                 'WKT': row[0]
#             }
#             feature_list.append(feature_dict)
#     return feature_list

@timer
def post_parcel_geom_update(featureLayer, url):
    # Use a SearchCursor to iterate through the features
    with arcpy.da.SearchCursor(featureLayer, ['SHAPE@WKT', 'APN']) as cursor:
        total_count = 0
        for row in cursor:
            total_count +=1
            if (total_count%1000)==0:
                print(f"Updating row {total_count}")
            feature_dict = {
                'APN': row[1],
                'WKT': row[0]
            }
            print(feature_dict)
            requests.post(url, feature_dict)

# feature_list = get_parcel_wkt_list(feature_layer_name)

# test_feature_list = feature_list[0:3]

# json_url = "https://qa.laketahoeinfo.org/api/UpdateParcelGeometries/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4"
# data={"parcelGeometriesToUpdate": test_feature_list}

# headers = {
#     "Content-Type": "application/json"
# }
# data_json = json.dumps(data)
# # note: not sure this post is the correct python code
# response = requests.post(json_url, data=json.dumps(data), headers=headers)

post_url = 'https://qa.laketahoeinfo.org/api/UpdateParcelGeometry/1A77D078-B83E-44E0-8CA5-8D7429E1A6B4'
post_parcel_geom_update(feature_layer_name, post_url)