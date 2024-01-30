# ParcelUpdate
Repository of scripts used to update parcel data at the Tahoe Regional Planning Agency

## Introduction
The TRPA maintains and updates a parcel dataset covering the Tahoe Basin. The data comes from the five county assessor's offices and gets transformed by the TRAP GIS Staff. Ultimately, ending up in the various TRPA information systems. 

## Extract Process
Parcel geometry and attributes are pulled via web services from the five county assessor's office that cover the Tahoe Basin. Each County maintains an authorattavie parcel layer that we consider the system of record for Tahoe parcels. The data is pulled around the 15th of each month, which aligns with the Placer County's update cycle. 

## Transform Process
The extracted county data is transformed into TRPA's standard schema. A series of string manipulations and spatial joins are used to do this tranformation. The TRPA standard schema can be viewed at this REST endpoint.

## Load Process
The load process moves the new geometries and attributes from the staged parcel layer (Parcel_Staging_Attributed) into our Enterprise Geodatabase using a branch versioned workflow.

## Current Enchancements
* Created a way to load a WKT dictionary as form data to LTinfo
* Updated the scripts metadata and structure
* Add Status field and make it 1 character long string always set to A
* Remove Littoral field from schema. Littoral defintion is not being met by spatial means.
* Added IPES and Estimated % Coverage Allowed to the Parcel_Master schema
  
## Future Enhancements
* Parcel_Master schema additions: Deed Restriction field as concatenated list. Add back in BMP_Status, add LCV Verified vs Estimated, and Verified Coverage Allowed, Verified % Coverage Allowed, VHR, Active_Permit, AccelaModDate
* Parcel_Point update in Transform and Load scripts
* Fix way LTinfo is getting Geometry from WKT_Export.py
* Create update of Parcel_County_Staging in Collection.sde using Load script
* Improve script metadata, error handling, and logging
* Create an automated way via email to notify staff of new and obsolete parcels
* Add QA/QC script
* Integrate verified address field
* Save copy of September update to yearly folder structure
* Script Parcel History based on september data
* Script Parcel Point update in Transform and Load script
* Update Parcel Point schema to mirror Parcel_Master
* Script Parcel_Development_History updates. TAX_SUM, CFA, RES, TAU, data engineering.
* Script Parcel History Polygon data append using September data
* Notify TRCD and CTC of parcel update and stand up shared update layer of expanded parcel (Olympic Valley AOI) data or them to pull

