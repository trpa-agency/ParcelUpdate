import arcpy
import requests
import os
# import json
# network path to connection files
filePath   = "C:\\GIS\\DB_CONNECT"
sdeBase    = os.path.join(filePath, "Vector.sde")
parcelBase     = sdeBase + "\\sde.SDE.Parcels\\sde.SDE.Parcels_Base"
#  make feature layer from parcel base
feature_layer_name = arcpy.MakeFeatureLayer_management(parcelBase, "parcels_lyr")

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

def post_parcel_geom_update(featureLayer, url):
    # Use a SearchCursor to iterate through the features
    with arcpy.da.SearchCursor(featureLayer, ['SHAPE@WKT', 'APN']) as cursor:
        for row in cursor:
            feature_dict = {
                'APN': row[1],
                'WKT': row[0]
            }
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