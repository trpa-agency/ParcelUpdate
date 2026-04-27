"""
ParcelTables_to_ParcelFeatures.py
Created: April 24th, 2026
Amy Fish, Tahoe Regional Planning Agency

This python script updates the BMP Database based on parcel_county_staging
Converted from VB.NET by: Claude
"""
import os
import logging
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Database connection parameters (mirrors ADO.NET connection string style)
# ---------------------------------------------------------------------------

# BMP database  (Data Source=sql14; Initial Catalog=tahoebmpsde)
BMP_DB = {
    "host":     "sql14",
    "database": "tahoebmpsde",
    "username": "sde",
    "password": "",
    "driver":   "ODBC+Driver+17+for+SQL+Server",
}

# Staging database  (Data Source=sql12; Initial Catalog=sde_tabular)
STAGING_DB = {
    "host":     "sql12",
    "database": "sde_tabular",
    "username": "sde",
    "password": "",
    "driver":   "ODBC+Driver+17+for+SQL+Server",
}


def build_connection_string(cfg: dict) -> str:
    """Build a SQLAlchemy connection string from ADO.NET-style parameters."""
    return (
        f"mssql+pyodbc://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}/{cfg['database']}"
        f"?driver={cfg['driver']}&TrustServerCertificate=yes"
    )


BMP_CONNECTION_STRING     = build_connection_string(BMP_DB)
STAGING_CONNECTION_STRING = build_connection_string(STAGING_DB)

VALIDATE_ONLY: bool = False          # Set True to preview changes without writing
LOG_DIR: str = r"C:\temp"           # Directory for output log files
EMAIL_FROM: str = "infosys@trpa.org"
EMAIL_TO: str = "afish@trpa.gov"
SMTP_HOST: str = "smtp.gmail.com"
SMTP_PORT: int = 587
SMTP_USER: str = "trpa.gis@gmail.com"
SMTP_PASSWORD: str = "TRP@g1s!"

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "bmp_updater.log")),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_bmp_session():
    """Session for the BMP database (sql14/tahoebmpsde) — reads and writes."""
    engine = create_engine(BMP_CONNECTION_STRING, fast_executemany=True)
    return sessionmaker(bind=engine)()


def get_staging_session():
    """Session for the staging database (sql12/sde_tabular) — read only."""
    engine = create_engine(STAGING_CONNECTION_STRING, fast_executemany=True)
    return sessionmaker(bind=engine)()


def fetch_all(session, sql: str, params: dict = None) -> list[dict]:
    """Execute a SELECT and return a list of row dicts."""
    result = session.execute(text(sql), params or {})
    cols = result.keys()
    return [dict(zip(cols, row)) for row in result.fetchall()]


def execute_dml(bmp_session, sql: str, params: dict = None):
    """Execute an INSERT / UPDATE / DELETE statement."""
    bmp_session.execute(text(sql), params or {})


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def get_jurisdiction_id(county_name: str) -> str:
    mapping = {"DG": "1", "EL": "3", "WA": "2", "CC": "9", "PL": "4"}
    return mapping.get(county_name.upper(), "8")


def clean_spaces(value: str) -> str:
    """Collapse multiple consecutive spaces into one."""
    while "  " in value:
        value = value.replace("  ", " ")
    return value.strip()


def standardize_street(addr: str) -> str:
    """Apply the same street abbreviation rules as the original VB code."""
    addr = addr.upper().strip()
    replacements = [
        (" STREET", " ST"),
        ("P O BOX", "PO BOX"),
        ("P.O. BOX", "PO BOX"),
        ("P.O BOX", "PO BOX"),
        (" AVENUE", " AVE"),
        (" DRIVE", " DR"),
        (" CIRCLE", " CIR"),
        (" TERRACE", " TER"),
        (" COURT", " CT"),
        (" TRAIL", " TRL"),
        (" HIGHWAY", " HWY"),
        (" BUILDING", " BLDG"),
        (" APARTMENT", " APT"),
        ("POST OFFICE", "PO"),
        (" SUITE", " STE"),
        (" BOULEVARD", " BLVD"),
        (" APT ", " #"),
        (" UNIT ", " #"),
        (" # ", " #"),
    ]
    # Guard words that should NOT be abbreviated (mirrors VB logic)
    skip_guards = {
        " CIRCLE": ["CIRCLE DR"],
        " TERRACE": ["TERRACE DR", "TERRACE AVE"],
        " COURT": ["COURT ST", "TENNIS COURT", "W BAY COURT", "COURT LN", "COURT DR"],
        " TRAIL": ["WINDING TRAIL", "TRAILSIDE", "TRAIL RIDER", "TARTAN TRAIL",
                   "RANCH TRAIL", "SHADY TRAIL"],
        " BOULEVARD": ["BOULEVARD WAY"],
        " DRIVE": ["DRIVER"],
    }
    for old, new in replacements:
        guards = skip_guards.get(old, [])
        if any(g in addr for g in guards):
            continue
        addr = addr.replace(old, new)

    addr = addr.replace("EAST SAN BERNARDINO", "E SAN BERNARDINO")
    addr = addr.replace("WEST SAN BERNARDINO", "W SAN BERNARDINO")
    addr = addr.replace("SOUTH UPPER TRUCKEE", "S UPPER TRUCKEE")
    addr = addr.replace("NORTH UPPER TRUCKEE", "N UPPER TRUCKEE")
    addr = addr.replace("EAST RIVER PARK", "E RIVER PARK")
    return clean_spaces(addr)


def write_log(filename: str, content: str):
    path = os.path.join(LOG_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log.info("Log written -> %s", path)


# ---------------------------------------------------------------------------
# Error handling / email
# ---------------------------------------------------------------------------

def handle_error(ex: Exception, apn: str = ""):
    msg_lines = [
        "-------------------------------------",
        "Error in BMP Parcel Updater",
        f"APN: {apn}",
        f"Date/Time: {datetime.now()}",
        f"Error: {ex}",
        f"Traceback:\n{traceback.format_exc()}",
        "-------------------------------------",
    ]
    error_text = "\n".join(msg_lines)
    log.error(error_text)
    error_path = os.path.join(LOG_DIR, "Error.txt")
    with open(error_path, "a", encoding="utf-8") as f:
        f.write(error_text + "\n")
    try:
        send_email("ERROR in ParcelUpdater", error_text, EMAIL_TO)
    except Exception as mail_ex:
        log.warning("Could not send error email: %s", mail_ex)


def send_email(subject: str, body: str, to_addr: str):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_FROM
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
    log.info("Email sent to %s  subject: %s", to_addr, subject)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    bmp = get_bmp_session()
    staging = get_staging_session()
    try:
        update_bmp_land_use(bmp, staging, VALIDATE_ONLY)
        update_bmp_attributes(bmp, staging, VALIDATE_ONLY)
        update_addresses_bmp(bmp, staging, VALIDATE_ONLY)
        update_owners_bmp(bmp, staging, VALIDATE_ONLY)
        set_bmp_parcels_inactive(bmp, staging, VALIDATE_ONLY)
        new_parcels_bmp(bmp, staging, VALIDATE_ONLY)
        bmp.commit()
        log.info("All updates complete.")
    except Exception as ex:
        bmp.rollback()
        handle_error(ex)
    finally:
        bmp.close()
        staging.close()


# ---------------------------------------------------------------------------
# set_bmp_parcels_inactive
# ---------------------------------------------------------------------------

def set_bmp_parcels_inactive(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"Checking for inactive parcels in the BMP Database {datetime.now()}",
        "-------------------------------------",
    ]
    total_obsolete = 0
    try:
        # Parcels flagged as "Old APN" in the staging table
        staging_rows = fetch_all(
            staging_session,
            "SELECT APN, Status FROM PARCEL_APN_NEWOLD",
        )
        # Current BMP parcel index  {apn: is_obsolete}
        bmp_rows = fetch_all(
            bmp_session,
            "SELECT APN_String, IsObsolete FROM tblParcel",
        )
        bmp_index = {r["APN_String"]: r["IsObsolete"] for r in bmp_rows}

        for row in staging_rows:
            apn = str(row["APN"])
            status = str(row["Status"])
            if status != "Old APN":
                continue
            if apn not in bmp_index:
                lines.append(f"Parcel is obsolete but missing from BMP DB: {apn}")
                continue
            is_obsolete = str(bmp_index[apn]).upper()
            if is_obsolete == "FALSE":
                lines.append(f"Parcel is now obsolete: {apn}")
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET IsObsolete = 1 WHERE APN_String = :apn",
                        {"apn": apn},
                    )
                total_obsolete += 1
            else:
                lines.append(f"Parcel is ALREADY obsolete: {apn}")

        lines.append(f"Total obsolete: {total_obsolete}")
        lines.append(f"Completed at: {datetime.now()}")
    except Exception as ex:
        handle_error(ex)

    write_log("BMPParcels_Inactive.txt", "\n".join(lines))


# ---------------------------------------------------------------------------
# update_bmp_land_use
# ---------------------------------------------------------------------------

def update_bmp_land_use(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"UPDATE BMP LAND USE CODES {datetime.now()}",
        "-------------------------------------",
    ]
    updated = 0
    try:
        parcels = fetch_all(
            staging_session,
            """
            SELECT APN, JURISDICTION, EXISTING_LANDUSE,
                   REGIONAL_LANDUSE, COUNTY_LANDUSE
            FROM   sde_tabular.sde.parcel_county_staging
            WHERE  Within_TRPA_BNDY = 1
            """,
        )
        bmp_rows = fetch_all(
            bmp_session,
            """
            SELECT APN_STRING, TRPA_LUC_DESCRIPTION,
                   COUNTY_LUC_DESCRIPTION, GenUse
            FROM   sde.tblParcel
            """,
        )
        bmp_index = {r["APN_STRING"]: r for r in bmp_rows}

        for row in parcels:
            apn = str(row["APN"])
            jurisdiction = str(row["JURISDICTION"])
            apo_land_use = str(row["EXISTING_LANDUSE"])
            apo_gen_use = str(row["REGIONAL_LANDUSE"])
            apo_county_luc = str(row["COUNTY_LANDUSE"])

            if apo_gen_use == "Resort Recreation":
                apo_gen_use = "Recreation"

            bmp = bmp_index.get(apn)
            if not bmp:
                continue

            bmp_land_use = str(bmp["TRPA_LUC_DESCRIPTION"])
            bmp_county_luc = str(bmp["COUNTY_LUC_DESCRIPTION"])
            bmp_gen_use = str(bmp["GenUse"])

            if apo_gen_use != bmp_gen_use:
                lines.append(
                    f"TRPA Gen use updated: {apn} ({jurisdiction})  "
                    f"old: {bmp_gen_use} / new: {apo_gen_use}"
                )
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET GenUse = :v WHERE APN_STRING = :apn",
                        {"v": apo_gen_use, "apn": apn},
                    )
                updated += 1

            if apo_land_use != bmp_land_use:
                lines.append(
                    f"TRPA Land use updated: {apn} ({jurisdiction})  "
                    f"old: {bmp_land_use} / new: {apo_land_use}"
                )
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET TRPA_LUC_DESCRIPTION = :v WHERE APN_STRING = :apn",
                        {"v": apo_land_use, "apn": apn},
                    )
                updated += 1

            if bmp_county_luc == "UNASSIGNED":
                bmp_county_luc = ""
            if apo_county_luc != bmp_county_luc:
                lines.append(
                    f"County land use updated: {apn} ({jurisdiction})  "
                    f"old: {bmp_county_luc} / new: {apo_county_luc}"
                )
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET COUNTY_LUC_DESCRIPTION = :v WHERE APN_STRING = :apn",
                        {"v": apo_county_luc, "apn": apn},
                    )
                updated += 1

        lines.append(f"TOTAL UPDATED PARCELS: {updated}")
        lines.append(f"Completed at: {datetime.now()}")
    except Exception as ex:
        handle_error(ex)

    write_log("ParcelUpdate_BMPLandUse.txt", "\n".join(lines))


# ---------------------------------------------------------------------------
# update_bmp_attributes
# ---------------------------------------------------------------------------

def update_bmp_attributes(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"UPDATE BMP Attributes STARTED AT {datetime.now()}",
        "-------------------------------------",
    ]
    try:
        staging = fetch_all(
            staging_session,
            """
            SELECT APN, JURISDICTION, SOIL_2003,
                   WATERSHED_NUMBER, FIREPD
            FROM   Parcel_county_staging
            WHERE  Within_TRPA_BNDY = 1
            """,
        )
        bmp_rows = fetch_all(
            bmp_session,
            """
            SELECT APN_STRING, WatershedID, sFireDistrict,
                   Jurisdiction, sMUKEY, ParcelID
            FROM   v_BMPAttributesForUpdate
            """,
        )
        bmp_index = {r["APN_STRING"]: r for r in bmp_rows}

        jurisdiction_map = {
            "EL": "El Dorado County",
            "CSLT": "City of South Lake Tahoe",
            "DG": "Douglas County",
            "WA": "Washoe County",
            "PL": "Placer County",
            "CC": "Carson City County",
            "SL": "City of South Lake Tahoe",
        }

        for row in staging:
            apn = str(row["APN"])
            jurisdiction = str(row["JURISDICTION"]).strip()
            soil03 = str(row["SOIL_2003"]).strip() or "UNK"
            if soil03 == "None":
                soil03 = "UNK"
            watershed_num = str(row["WATERSHED_NUMBER"])
            firepd = str(row["FIREPD"]).strip()
            firepd = firepd.replace("CSLT FPD", "CSLT FD").replace(
                "FALLEN LEAF LAKE FPD", "FALLEN LEAF LAKE FD"
            )

            bmp = bmp_index.get(apn)
            if not bmp:
                continue

            ppno = bmp["ParcelID"]
            watershed_bmp = str(bmp["WatershedID"])
            firepd_bmp = str(bmp["sFireDistrict"])
            jurisdiction_bmp = str(bmp["Jurisdiction"]) + " County"
            if jurisdiction_bmp == "City South Lake Tahoe County":
                jurisdiction_bmp = "City of South Lake Tahoe"
            soil03_bmp = str(bmp["sMUKEY"])

            # Watershed
            if watershed_bmp != watershed_num and watershed_num:
                try:
                    if int(watershed_num) < 65:
                        lines.append(f"{apn}: Updated Watershed from {watershed_bmp} to {watershed_num}")
                        if not validate_only:
                            execute_dml(
                                bmp_session,
                                "UPDATE sde.tblParcel SET WatershedID = :v WHERE ParcelID = :ppno",
                                {"v": int(watershed_num), "ppno": ppno},
                            )
                except ValueError:
                    pass

            # Fire district
            if firepd_bmp != firepd and firepd:
                action = "Insert" if not firepd_bmp else "Updated"
                lines.append(f"{apn}: {action} Fire PD from {firepd_bmp} to {firepd}")
                if not validate_only:
                    if not firepd_bmp:
                        execute_dml(
                            bmp_session,
                            "INSERT INTO sde.tblFireDistrict (ParcelID, sFireDistrict) VALUES (:ppno, :v)",
                            {"ppno": ppno, "v": firepd},
                        )
                    else:
                        execute_dml(
                            bmp_session,
                            "UPDATE sde.tblFireDistrict SET sFireDistrict = :v WHERE ParcelID = :ppno",
                            {"v": firepd, "ppno": ppno},
                        )

            # Soil
            if soil03_bmp != soil03 and soil03:
                lines.append(f"{apn}: Updated Soil from {soil03_bmp} to {soil03}")
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET sMUKEY = :v WHERE ParcelID = :ppno",
                        {"v": soil03, "ppno": ppno},
                    )

            # Jurisdiction
            jurisdiction_full = jurisdiction_map.get(jurisdiction.upper(), jurisdiction)
            if jurisdiction_bmp != jurisdiction_full:
                skip = (
                    jurisdiction_bmp == "City of South Lake Tahoe"
                    and jurisdiction_full == "El Dorado County"
                )
                if not skip and jurisdiction_full:
                    lines.append(
                        f"{apn}: Updated Jurisdiction from {jurisdiction_bmp} to {jurisdiction_full}"
                    )
                    if not validate_only:
                        execute_dml(
                            bmp_session,
                            "UPDATE sde.tblParcel SET JurisdictionID = :v WHERE ParcelID = :ppno",
                            {"v": 5, "ppno": ppno},
                        )

        lines.append(f"Completed at: {datetime.now()}")
    except Exception as ex:
        handle_error(ex)

    write_log("ParcelUpdate_BMPAttributes.txt", "\n".join(lines))


# ---------------------------------------------------------------------------
# update_addresses_bmp
# ---------------------------------------------------------------------------

def update_addresses_bmp(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"UPDATE BMP ADDRESSES STARTED AT {datetime.now()}",
        "-------------------------------------",
    ]
    updated = unchanged = 0
    try:
        staging = fetch_all(
            staging_session,
            "SELECT APN, JURISDICTION, APO_ADDRESS, PSTL_TOWN, PSTL_ZIP5 FROM Parcel_county_staging WHERE Within_TRPA_BNDY = 1",
        )
        bmp_rows = fetch_all(
            bmp_session,
            "SELECT APN_STRING, ParcelStreet, ParcelCity FROM sde.tblParcel",
        )
        bmp_index = {r["APN_STRING"]: r for r in bmp_rows}

        for row in staging:
            apn = str(row["APN"])
            jurisdiction = str(row["JURISDICTION"])
            bmp = bmp_index.get(apn)
            if not bmp:
                continue

            orig_street = str(bmp["ParcelStreet"]).upper().replace("#", "").strip()
            if orig_street.startswith("0 "):
                orig_street = orig_street[2:]

            new_street = str(row["APO_ADDRESS"] or "").upper().strip()
            new_street = standardize_street(new_street)
            for bad in ("UNIT", "SUITE", "SPACE", "NULL"):
                new_street = new_street.replace(bad, "")
            new_street = clean_spaces(new_street)
            for zero_val in ("0", "0 NULL"):
                if new_street == zero_val:
                    new_street = ""
            if new_street == "0 NO ADDRESS ON FILE":
                new_street = "NO ADDRESS ON FILE"
            if new_street == "0 0":
                new_street = "NO ADDRESS ON FILE"
            if new_street.startswith("0 "):
                new_street = new_street[2:]
            new_street = new_street.replace("#NULL", "").strip()
            if orig_street in ("*NO SITE ADDRESS*", "0", "NONE"):
                orig_street = ""

            if new_street != orig_street:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD: {orig_street} / NEW: {new_street}"
                )
                updated += 1
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET ParcelStreet = :v WHERE APN_STRING = :apn",
                        {"v": new_street, "apn": apn},
                    )
            else:
                unchanged += 1

            # City
            orig_city = str(bmp["ParcelCity"]).upper().strip()
            new_city = str(row["PSTL_TOWN"] or "").upper().strip()
            if new_city in ("NONE", "RENO", "CARSON CITY"):
                new_city = ""
            if orig_city == "NONE":
                orig_city = ""
            if new_city == "CITY OF SOUTH LAKE TAHOE":
                new_city = "SOUTH LAKE TAHOE"

            if orig_city != new_city:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD CITY: {orig_city} / NEW CITY: {new_city}"
                )
                updated += 1
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET ParcelCity = :v WHERE APN_STRING = :apn",
                        {"v": new_city, "apn": apn},
                    )
            else:
                unchanged += 1

        lines += [
            f"TOTAL UPDATED PARCELS: {updated}",
            f"TOTAL UNCHANGED PARCELS: {unchanged}",
            f"UPDATE BMP ADDRESSES FINISHED AT {datetime.now()}",
            "-------------------------------------",
        ]
    except Exception as ex:
        handle_error(ex)

    write_log("ParcelUpdate_BMPAddresses.txt", "\n".join(lines))


# ---------------------------------------------------------------------------
# update_owners_bmp
# ---------------------------------------------------------------------------

def update_owners_bmp(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"UPDATE BMP OWNERS STARTED AT {datetime.now()}",
        "-------------------------------------",
    ]
    updated = 0
    apn = ""
    try:
        staging = fetch_all(
            staging_session,
            """
            SELECT APN, JURISDICTION, OWN_FULL,
                   MAIL_ADD1, MAIL_CITY, MAIL_STATE, MAIL_ZIP5
            FROM   Parcel_county_staging
            WHERE  Within_TRPA_BNDY = 1
            """,
        )
        bmp_rows = fetch_all(
            bmp_session,
            """
            SELECT APN_STRING, OwnerName, OwnerStreet,
                   OwnerCity, OwnerState, OwnerZip
            FROM   sde.tblParcel
            """,
        )
        bmp_index = {r["APN_STRING"]: r for r in bmp_rows}

        for row in staging:
            apn = str(row["APN"])
            jurisdiction = str(row["JURISDICTION"]).strip().upper()
            bmp = bmp_index.get(apn)
            if not bmp:
                continue

            did_update = False

            # --- Owner name ---
            new_name = clean_spaces(str(row["OWN_FULL"] or "").upper())[:100]
            old_name = clean_spaces(str(bmp["OwnerName"] or "").upper())[:100]
            if new_name != old_name:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD Owner: {old_name} / NEW Owner: {new_name}"
                )
                did_update = True
                if not validate_only:
                    last = new_name.split()[0] if new_name else ""
                    first = new_name[len(last):].strip()
                    execute_dml(
                        bmp_session,
                        """UPDATE sde.tblParcel
                              SET OwnerName = :full, OwnerFirst = :first, OwnerLast = :last
                            WHERE APN_STRING = :apn""",
                        {"full": new_name, "first": first, "last": last, "apn": apn},
                    )

            # --- Mailing address ---
            new_addr = standardize_street(
                clean_spaces(str(row["MAIL_ADD1"] or "").upper())
            )[:50]
            old_addr = standardize_street(
                clean_spaces(str(bmp["OwnerStreet"] or "").upper())
            )[:50]
            old_addr = old_addr.replace("P O BOX", "PO BOX")
            new_addr = new_addr.replace("P O BOX", "PO BOX")

            if new_addr != old_addr:
                lines.append(
                    f"APN: {apn}  OLD MAILING ADDRESS: {old_addr} / NEW MAILING ADDRESS: {new_addr}"
                )
                did_update = True
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET OwnerStreet = :v WHERE APN_STRING = :apn",
                        {"v": new_addr, "apn": apn},
                    )

            # --- City ---
            new_city = str(row["MAIL_CITY"] or "").strip().upper()
            old_city = str(bmp["OwnerCity"] or "").strip().upper()
            if new_city == "N/A":
                new_city = ""
            for alias in ("SO LAKE TAHOE",):
                if old_city == alias:
                    old_city = "SOUTH LAKE TAHOE"
                if new_city == alias:
                    new_city = "SOUTH LAKE TAHOE"
            if new_city != old_city:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD CITY: {old_city} / NEW CITY: {new_city}"
                )
                did_update = True
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET OwnerCity = :v WHERE APN_STRING = :apn",
                        {"v": new_city, "apn": apn},
                    )

            # --- State ---
            new_state = str(row["MAIL_STATE"] or "").strip().upper()
            old_state = str(bmp["OwnerState"] or "").strip().upper()
            if len(new_state) == 2 and new_state != old_state:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD STATE: {old_state} / NEW STATE: {new_state}"
                )
                did_update = True
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET OwnerState = :v WHERE APN_STRING = :apn",
                        {"v": new_state, "apn": apn},
                    )

            # --- Zip ---
            def normalize_zip(z) -> str:
                z = str(z or "").strip()[:5].zfill(5)
                return "00000" if z in ("0", "", "0000") else z

            new_zip = normalize_zip(row["MAIL_ZIP5"])
            old_zip = normalize_zip(bmp["OwnerZip"])
            if new_zip != old_zip:
                lines.append(
                    f"APN: {apn} ({jurisdiction})  OLD ZIP: {old_zip} / NEW ZIP: {new_zip}"
                )
                did_update = True
                if not validate_only:
                    execute_dml(
                        bmp_session,
                        "UPDATE sde.tblParcel SET OwnerZip = :v WHERE APN_STRING = :apn",
                        {"v": new_zip, "apn": apn},
                    )

            if did_update:
                updated += 1

        lines += [
            f"TOTAL UPDATED PARCELS: {updated}",
            f"UPDATE BMP OWNERS FINISHED AT {datetime.now()}",
            "-------------------------------------",
        ]
    except Exception as ex:
        handle_error(ex, apn)

    write_log("ParcelUpdate_BMPOwners.txt", "\n".join(lines))


# ---------------------------------------------------------------------------
# new_parcels_bmp
# ---------------------------------------------------------------------------

DUMMY_JURISDICTIONS = {"LT", "FS", "SP", "BL", "SE", "RD", "HA", "SL"}


def new_parcels_bmp(bmp_session, staging_session, validate_only: bool):
    lines = [
        f"ADD NEW BMP PARCELS STARTED AT {datetime.now()}",
        "-------------------------------------",
    ]
    new_count = 0
    apn = ""
    try:
        staging = fetch_all(
            staging_session,
            """
            SELECT APN, JURISDICTION, OWN_FULL,
                   MAIL_ADD1, MAIL_CITY, MAIL_STATE, MAIL_ZIP5,
                   PSTL_TOWN, PSTL_ZIP5,
                   STR_DIR, STR_NAME, STR_SUFFIX, HSE_NUMBR, UNIT_NUMBR
            FROM   Parcel_county_staging
            WHERE  Within_TRPA_BNDY = 1
            """,
        )
        bmp_rows = fetch_all(
            bmp_session,
            "SELECT APN_STRING, IsObsolete FROM sde.tblParcel",
        )
        bmp_index = {r["APN_STRING"]: r for r in bmp_rows}

        for row in staging:
            apn = str(row["APN"])
            if apn == "IP1-559-039":
                continue

            # Derive PPNO
            ppno_str = apn.replace("-", "")
            ppno_str = ppno_str.lstrip("0") or "0"
            try:
                ppno = int(ppno_str)
            except ValueError:
                ppno = 0

            existing = bmp_index.get(apn)
            if existing:
                # Reactivate if obsolete
                if str(existing["IsObsolete"]).upper() == "TRUE":
                    lines.append(f"Obsolete parcel needs to be reactivated APN: {apn}")
                    if not validate_only:
                        execute_dml(
                            bmp_session,
                            "UPDATE sde.tblParcel SET IsObsolete = 0 WHERE APN_STRING = :apn",
                            {"apn": apn},
                        )
                continue  # Already exists; nothing more to do

            # Build parcel address
            jurisdiction = str(row["JURISDICTION"]).strip()
            hse_num = int(row["HSE_NUMBR"] or 0)
            str_dir = str(row["STR_DIR"] or "").strip()
            str_name = str(row["STR_NAME"] or "").strip()
            str_suffix = str(row["STR_SUFFIX"] or "").strip()
            unit = str(row["UNIT_NUMBR"] or "").strip()

            if unit:
                full_street = f"{hse_num} {str_dir} {str_name} {str_suffix} {unit}"
            else:
                full_street = f"{hse_num} {str_dir} {str_name} {str_suffix}"
            full_street = clean_spaces(full_street).strip()

            parcel_city = str(row["PSTL_TOWN"] or "").strip()
            parcel_zip = str(row["PSTL_ZIP5"] or "").strip()
            owner_full = str(row["OWN_FULL"] or "").strip()
            mail_addr = str(row["MAIL_ADD1"] or "").strip()
            mail_city = str(row["MAIL_CITY"] or "").strip()
            mail_state = str(row["MAIL_STATE"] or "").strip()
            mail_zip = str(row["MAIL_ZIP5"] or "").strip()
            jur_id = get_jurisdiction_id(jurisdiction)
            watershed_id = 0

            # Skip dummy / no-address parcels
            if jurisdiction.upper() in DUMMY_JURISDICTIONS:
                continue
            if apn.endswith("-00"):
                continue
            if ppno == 13040002:
                continue

            lines.append(
                f"INSERTING APN: {apn}  STREET: {full_street} / JURISDICTION: {jurisdiction}"
            )
            if not validate_only:
                execute_dml(
                    bmp_session,
                    """
                    INSERT INTO sde.tblParcel
                        (ParcelID, JurisdictionID, Jurisdiction, WatershedID,
                         ParcelStreet, ParcelCity, ParcelZip,
                         OwnerName, OwnerFirst, OwnerLast,
                         OwnerStreet, OwnerCity, OwnerState, OwnerZip,
                         APN_STRING, IsObsolete)
                    VALUES
                        (:ppno, :jur_id, :jur, :wshed,
                         :street, :city, :zip,
                         :own_full, :own_first, :own_last,
                         :mail_addr, :mail_city, :mail_state, :mail_zip,
                         :apn, 0)
                    """,
                    {
                        "ppno": ppno, "jur_id": jur_id, "jur": jurisdiction,
                        "wshed": watershed_id,
                        "street": full_street, "city": parcel_city, "zip": parcel_zip,
                        "own_full": owner_full, "own_first": "", "own_last": "",
                        "mail_addr": mail_addr, "mail_city": mail_city,
                        "mail_state": mail_state, "mail_zip": mail_zip,
                        "apn": apn,
                    },
                )
            new_count += 1

        lines += [
            f"{new_count} new parcels added to BMP database at {datetime.now()}",
            f"TOTAL NEW PARCELS: {new_count}",
        ]
    except Exception as ex:
        handle_error(ex, apn)

    write_log("ParcelUpdate_NewBMPParcels.txt", "\n".join(lines))


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()