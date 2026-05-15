"""
compare_parcel_master_versions.py
---------------------------------
Compares the attributes of sde.parcels\\parcel_master between SDE.DEFAULT and
another transactional version, joining on APN, and writes the differences to
a wide-format CSV.

Output CSV columns:
    APN, NumChangedFields, ChangedFields,
    <field1>_DEFAULT, <field1>_VERSION,
    <field2>_DEFAULT, <field2>_VERSION,
    ...

Only fields that differ for at least one APN get columns. For records that
did not change a particular field, those two cells are left blank.

Only APNs that exist in BOTH versions are reported (per the requested
configuration). System / geometry / version-tracking fields are skipped.

"""

import arcpy
import csv
import os
import sys
from datetime import datetime, date

# ============================================================================
# CONFIGURATION  
# ============================================================================
SDE_CONNECTION = r"F:\GIS\DB_CONNECT\vector.sde"

# Feature class inside the SDE (feature-dataset\feature-class).
FC_RELATIVE_PATH = r"sde.parcels\parcel_master"
APN_FIELD = "APN"
COMPARE_VERSION = "SDE.Parcel_Update_2026-04-29"
DEFAULT_VERSION = "SDE.DEFAULT"

# Where to write the CSV. The directory will be created if it does not exist.
OUTPUT_DIR = r"c:\temp\Output"

# Floating-point tolerance for considering two numbers equal.
FLOAT_TOLERANCE = 1e-6

# Field names (UPPER-CASE) to always skip in the comparison.
SYSTEM_FIELDS = {
    "OBJECTID", "OBJECTID_1", "FID",
    "SHAPE", "SHAPE_LENGTH", "SHAPE_AREA", "SHAPE.STLENGTH()", "SHAPE.STAREA()",
    "GLOBALID", "GDB_GEOMATTR_DATA",
    "CREATED_USER", "CREATED_DATE",
    "LAST_EDITED_USER", "LAST_EDITED_DATE",
    "SDE_STATE_ID", "GDB_FROM_DATE", "GDB_TO_DATE", "GDB_ARCHIVE_OID",
}

# ============================================================================


def log(msg):
    """Print a message and send it to the ArcGIS geoprocessing window too."""
    print(msg)
    try:
        arcpy.AddMessage(msg)
    except Exception:
        pass


def get_compare_fields(fc):
    """Return a list of editable, non-system, non-geometry field names."""
    fields = []
    for f in arcpy.ListFields(fc):
        if f.type in ("Geometry", "OID", "GlobalID", "Raster", "Blob"):
            continue
        if f.name.upper() in SYSTEM_FIELDS:
            continue
        fields.append(f.name)
    return fields


def values_equal(a, b):
    """Tolerant equality check for the values returned by a SearchCursor."""
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Numeric: compare with tolerance to absorb float jitter.
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= FLOAT_TOLERANCE
        except (TypeError, ValueError):
            pass
    # Strings: trim trailing whitespace before compare (common in legacy data).
    if isinstance(a, str) and isinstance(b, str):
        return a.rstrip() == b.rstrip()
    # Datetime / date: direct compare.
    if isinstance(a, (datetime, date)) and isinstance(b, (datetime, date)):
        return a == b
    return a == b


def fmt_value(v):
    """Format a value for CSV output. None becomes empty string."""
    if v is None:
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def build_records(layer, apn_field, fields):
    """Return dict {apn: {field: value}} for every row in the layer."""
    records = {}
    cursor_fields = [apn_field] + fields
    dup_count = 0
    null_apn_count = 0
    with arcpy.da.SearchCursor(layer, cursor_fields) as cur:
        for row in cur:
            apn = row[0]
            if apn is None or (isinstance(apn, str) and not apn.strip()):
                null_apn_count += 1
                continue
            if apn in records:
                dup_count += 1
                # Keep the first occurrence; warn at the end.
                continue
            records[apn] = dict(zip(fields, row[1:]))
    if null_apn_count:
        log("  WARNING: skipped {} record(s) with null/blank APN.".format(null_apn_count))
    if dup_count:
        log("  WARNING: encountered {} duplicate APN(s); kept first occurrence.".format(dup_count))
    return records


def make_versioned_layer(fc_path, layer_name, version_name):
    """Create an in-memory feature layer pinned to a specific version."""
    if arcpy.Exists(layer_name):
        arcpy.Delete_management(layer_name)
    arcpy.MakeFeatureLayer_management(fc_path, layer_name)
    arcpy.ChangeVersion_management(layer_name, "TRANSACTIONAL", version_name)
    return layer_name


def main():
    log("=" * 70)
    log("parcel_master version comparison")
    log("  DEFAULT version : {}".format(DEFAULT_VERSION))
    log("  Compare version : {}".format(COMPARE_VERSION))
    log("=" * 70)

    if COMPARE_VERSION.strip().upper() in ("", "SDE.YOURVERSIONNAME"):
        raise RuntimeError(
            "Please set COMPARE_VERSION at the top of the script to the "
            "name of the version you want to compare (e.g., 'SDE.QC_Edits')."
        )

    fc_path = os.path.join(SDE_CONNECTION, FC_RELATIVE_PATH)
    if not arcpy.Exists(fc_path):
        raise RuntimeError("Feature class not found: {}".format(fc_path))

    # Discover comparison fields from the source feature class.
    compare_fields = get_compare_fields(fc_path)
    if APN_FIELD in compare_fields:
        compare_fields.remove(APN_FIELD)  # APN is the join key, not a compared field.
    log("Comparing {} field(s): {}".format(len(compare_fields), ", ".join(compare_fields)))

    # Build version-pinned layers.
    log("Creating versioned layers...")
    default_lyr = make_versioned_layer(fc_path, "parcel_master_default", DEFAULT_VERSION)
    version_lyr = make_versioned_layer(fc_path, "parcel_master_version", COMPARE_VERSION)

    # Read both sides into memory keyed by APN.
    log("Reading rows from {} ...".format(DEFAULT_VERSION))
    default_records = build_records(default_lyr, APN_FIELD, compare_fields)
    log("  {:,} record(s).".format(len(default_records)))

    log("Reading rows from {} ...".format(COMPARE_VERSION))
    version_records = build_records(version_lyr, APN_FIELD, compare_fields)
    log("  {:,} record(s).".format(len(version_records)))

    # Compare on APNs present in both.
    common_apns = set(default_records.keys()) & set(version_records.keys())
    only_default = len(default_records) - len(common_apns)
    only_version = len(version_records) - len(common_apns)
    log("{:,} APN(s) present in both versions.".format(len(common_apns)))
    log("  ({:,} only in DEFAULT, {:,} only in {} -- not reported)"
        .format(only_default, only_version, COMPARE_VERSION))

    diff_rows = []           # list of (apn, {field: (default_val, version_val)})
    fields_with_changes = set()

    for apn in common_apns:
        d = default_records[apn]
        v = version_records[apn]
        changes = {}
        for f in compare_fields:
            dv = d.get(f)
            vv = v.get(f)
            if not values_equal(dv, vv):
                changes[f] = (dv, vv)
                fields_with_changes.add(f)
        if changes:
            diff_rows.append((apn, changes))

    log("{:,} APN(s) have one or more attribute differences.".format(len(diff_rows)))
    log("{:,} field(s) had a difference somewhere in the data.".format(len(fields_with_changes)))

    if not diff_rows:
        log("No differences to write. Done.")
        return

    # Build output path.
    if not os.path.isdir(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ver = COMPARE_VERSION.replace(".", "_").replace(" ", "_")
    out_csv = os.path.join(
        OUTPUT_DIR, "parcel_master_diff_{}_{}.csv".format(safe_ver, stamp)
    )

    # Wide-format header.
    sorted_fields = sorted(fields_with_changes)
    header = ["APN", "NumChangedFields", "ChangedFields"]
    for f in sorted_fields:
        header.append("{}_DEFAULT".format(f))
        header.append("{}_{}".format(f, safe_ver))

    # Write the CSV.
    # The 'newline=""' kwarg is Python 3; on Python 2 fall back to "wb".
    if sys.version_info[0] >= 3:
        out_fh = open(out_csv, "w", newline="", encoding="utf-8")
    else:
        out_fh = open(out_csv, "wb")

    try:
        writer = csv.writer(out_fh)
        writer.writerow(header)
        for apn, changes in sorted(diff_rows, key=lambda x: str(x[0])):
            changed_list = sorted(changes.keys())
            row = [apn, len(changed_list), "; ".join(changed_list)]
            for f in sorted_fields:
                if f in changes:
                    dv, vv = changes[f]
                    row.append(fmt_value(dv))
                    row.append(fmt_value(vv))
                else:
                    row.append("")
                    row.append("")
            writer.writerow(row)
    finally:
        out_fh.close()

    log("Wrote: {}".format(out_csv))
    log("Done.")


if __name__ == "__main__":
    main()
