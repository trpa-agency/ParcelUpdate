# ParcelUpdate
Repository of scripts used to update parcel data at the Tahoe Regional Planning Agency

## Introduction
The TRPA maintains and updates a parcel dataset covering the Tahoe Basin. The data comes from the five county assessor's offices and gets transformed by the TRAP GIS Staff. Ultimately, ending up in the various TRPA information systems. 

## Extract Process
Parcel geometry and attributes are pulled via web services from the five county assessor's office that cover the Tahoe Basin. Each County maintains an authorattavie parcel layer that we consider the system of record for Tahoe parcels. The data is pulled around the 15th of each month, which aligns with the Placer County's update cycle. 

## Transform Process
The extracted county data is transformed into TRPA's standard schema. A series of string manipulations and spatial joins are used to do this tranformation. The TRPA standard schema can be viewed at this REST endpoint.

## Load Process
The load process moves the stage parcel layer (Parcel_Staging_Attributed) into our Enterprise Geodatabase using a branch versioned workflow.

## Current Enchancements
* Created a way to load a WKT dictionary as form data to LTinfo
* Updated the scripts metadata and structure
## Future Enhancements
* improve script metadata, error handling, and logging
* Create an automated way via email to notify staff of new and obsolete parcels
* Add QA/QC script
* Update Address table for BMP load
* Integrate varified address field
* Save copy of Sepetember Update to yearly folder structure

