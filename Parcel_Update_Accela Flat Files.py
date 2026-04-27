"""
accela_apo_files.py
Original Author: Amy Fish
Last VB.NET Update: 6/5/2024
Purpose: Create flat files of parcel information to update Accela
"""

import os
import logging
import smtplib
import traceback
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from collections import defaultdict

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Staging database  (Data Source=sql12; Initial Catalog=sde)
STAGING_DB = {
    "host":     "sql12",
    "database": "sde",
    "trusted":  False,   # Windows auth — no username/password needed
    "username": "sde",
    "password": "",
    "driver":   "ODBC+Driver+17+for+SQL+Server",
}

# Staging tabular database  (Data Source=sql12; Initial Catalog=sde_tabular)
STAGING_TABULAR_DB = {
    "host":     "sql12",
    "database": "sde_tabular",
    "trusted":  False,   # Windows auth — no username/password needed
    "username": "sde",
    "password": "",
    "driver":   "ODBC+Driver+17+for+SQL+Server",
}

# Accela database  (Data Source=sql24; Initial Catalog=TRPA_PROD; Integrated Security=True)
ACCELA_DB = {
    "host":     "sql24",
    "database": "TRPA_PROD",
    "driver":   "ODBC+Driver+17+for+SQL+Server",
    "trusted":  True,   # Windows auth — no username/password needed
}

# Output directory for flat files
OUTPUT_DIR: str = r"C:\temp"

# Email settings
EMAIL_FROM: str = "infosys@trpa.org"
EMAIL_TO:   str = "afish@trpa.gov"
SMTP_HOST:  str = "smtp.gmail.com"
SMTP_PORT:  int = 587
SMTP_USER:  str = "trpa.gis@gmail.com"
SMTP_PASSWORD: str = "TRP@g1s!"

# Feature flags (mirrors VB booleans)
CHECK_CHARS:       bool = True   # Validate pipe counts on each record
CHECK_FOR_MODS:    bool = True   # Compare existing Accela records for changes
UPDATE_ATTRIBUTES: bool = True   # Include attribute comparison/update
 
# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(OUTPUT_DIR, "accela_apo_files.log")),
    ],
)
log = logging.getLogger(__name__)
 
# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
 
def build_connection_string(cfg: dict) -> str:
    """Build a SQLAlchemy connection string from config dict."""
    if cfg.get("trusted"):
        return (
            f"mssql+pyodbc://@{cfg['host']}/{cfg['database']}"
            f"?driver={cfg['driver']}&TrustServerCertificate=yes"
            f"&trusted_connection=yes"
        )
    return (
        f"mssql+pyodbc://{cfg['username']}:{cfg['password']}"
        f"@{cfg['host']}/{cfg['database']}"
        f"?driver={cfg['driver']}&TrustServerCertificate=yes"
    )
 
 
def get_session(cfg: dict):
    engine = create_engine(build_connection_string(cfg), fast_executemany=True)
    return sessionmaker(bind=engine)()
 
 
def fetch_all(session, sql: str, params: dict = None) -> list[dict]:
    result = session.execute(text(sql), params or {})
    cols = list(result.keys())
    return [dict(zip(cols, row)) for row in result.fetchall()]
 
# ---------------------------------------------------------------------------
# Error handling / email
# ---------------------------------------------------------------------------
 
def handle_error(ex: Exception, apn: str = ""):
    msg = "\n".join([
        "-------------------------------------",
        "Error in AccelaAPOFiles",
        f"APN: {apn}",
        f"Date/Time: {datetime.now()}",
        f"Error: {ex}",
        f"Traceback:\n{traceback.format_exc()}",
        "-------------------------------------",
    ])
    log.error(msg)
    with open(os.path.join(OUTPUT_DIR, "Error.txt"), "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    try:
        send_email("ERROR in AccelaAPOFiles", msg, EMAIL_TO)
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
 
# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
 
def count_character(value: str, ch: str) -> int:
    """Count occurrences of ch in value (mirrors VB CountCharacter)."""
    return value.count(ch)
 
 
def get_suffix(suffix: str) -> str:
    """Normalize street suffix abbreviations."""
    suffix_map = {
        "TE":    "TER",
        "CI":    "CIR",
        "BL":    "BLVD",
        "TR":    "TRL",
        "WY":    "WAY",
        "E":     "",
        "L":     "",
        "AV":    "AVE",
        "LP":    "LOOP",
        "HY":    "HWY",
        "PY":    "PKWY",
        "PKY":   "PKWY",
        "DRIVE": "DR",
    }
    return suffix_map.get(suffix, suffix)
 
 
def clean_street(street: str) -> str:
    """Clean and normalize a street name string."""
    street = street.replace("  ", " ").upper().strip()
    if not street:
        return "NONE"
 
    replacements = [
        ("UNIT",               ""),
        ("SUITE",              ""),
        ("SPACE",              ""),
        ("NULL",               ""),
        ("'",                  ""),
        ("  ",                 " "),
        ("#NULL",              ""),
        ("EAST SAN BERNARDINO","E SAN BERNARDINO"),
        ("WEST SAN BERNARDINO","W SAN BERNARDINO"),
        ("SOUTH UPPER TRUCKEE","S UPPER TRUCKEE"),
        ("NORTH UPPER TRUCKEE","N UPPER TRUCKEE"),
        ("EAST RIVER PARK",    "E RIVER PARK"),
    ]
    for old, new in replacements:
        street = street.replace(old, new)
 
    street = street.strip()
 
    if street in ("0", "0 NULL", "0 0"):
        return "NO ADDRESS ON FILE"
    if street == "NO ADDRESS ON FILE":
        return "NONE"
    if street.startswith("0 "):
        street = street[2:]
 
    return street
 
 
def translate_jurisdiction(code: str) -> str:
    mapping = {
        "EL":   "El Dorado County",
        "CSLT": "City of South Lake Tahoe",
        "DG":   "Douglas County",
        "WA":   "Washoe County",
        "PL":   "Placer County",
        "CC":   "Carson City County",
        "SL":   "City of South Lake Tahoe",
    }
    return mapping.get(code.upper(), code)
 
 
def write_file(filename: str, content: str):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    log.info("Written -> %s", path)
 
# ---------------------------------------------------------------------------
# File check
# ---------------------------------------------------------------------------
 
def accela_apo_file_check():
    """Check output flat files for column counts and duplicate APNs."""
    try:
        # --- Check column 4 value distribution in parcel_attr.txt ---
        attr_path = os.path.join(OUTPUT_DIR, "parcel_attr.txt")
        counts: dict[str, int] = defaultdict(int)
        for line in open(attr_path, encoding="utf-8"):
            cols = line.split("|")
            if len(cols) >= 4:
                key = cols[3].strip()
                counts[key] += 1
        log.info("parcel_attr.txt column-4 distribution:")
        for k, v in counts.items():
            log.info("  %s : %d", k, v)
 
        # --- Check for duplicate APNs in parcel_base.txt ---
        base_path = os.path.join(OUTPUT_DIR, "parcel_base.txt")
        apn_counts: dict[str, int] = defaultdict(int)
        for line in open(base_path, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            cols = line.split("|")
            if len(cols) >= 2:
                apn = cols[1].strip()
                if apn:
                    apn_counts[apn.upper()] += 1
 
        duplicates = {apn: cnt for apn, cnt in apn_counts.items() if cnt > 1}
        if not duplicates:
            log.info("parcel_base.txt: No duplicate APNs found.")
        else:
            log.warning("parcel_base.txt: Duplicate APNs found:")
            for apn, cnt in sorted(duplicates.items(), key=lambda x: -x[1]):
                log.warning("  %s : %d", apn, cnt)
 
    except Exception as ex:
        handle_error(ex)
 
# ---------------------------------------------------------------------------
# Main file creation
# ---------------------------------------------------------------------------
 
def accela_apo_file_creation():
    status_lines = [
        f"Creating Parcel Update file for Accela {datetime.now()}",
        "-------------------------------------",
    ]
 
    # Output string buffers
    s_parcel = ""
    s_addr   = ""
    s_owner  = ""
    s_attr   = ""
 
    new_parcels       = 0
    owners_updated    = 0
    addresses_updated = 0
    total_obsolete    = 0
 
    apn = ""
 
    try:
        staging_session = get_session(STAGING_DB)
        accela_session  = get_session(ACCELA_DB)
 
        # ---------------------------------------------------------------
        # Load all data upfront into dicts indexed by APN
        # ---------------------------------------------------------------
        log.info("Loading staging parcels...")
        staging_rows = fetch_all(
            staging_session,
            """
            SELECT APN, PPNO, HRA_NAME, JURISDICTION, COUNTY_LANDUSE_DESCRIPTION,
                   OWNERSHIP_TYPE, PARCEL_SQFT, PRIORITY_WATERSHED,
                   WITHIN_TRPA_BNDY, WATERSHED_NAME, COUNTY_LANDUSE_CODE,
                   FIREPD, WATERSHED_NUMBER,
                   OWN_FULL, MAIL_ADD1, MAIL_CITY, MAIL_STATE, MAIL_ZIP5,
                   PSTL_TOWN, APO_ADDRESS, PSTL_STATE, PSTL_ZIP5,
                   STR_DIR, STR_NAME, STR_SUFFIX, HSE_NUMBR, UNIT_NUMBR
            FROM   parcel_master
            """,
        )
 
        log.info("Loading Accela parcels...")
        accela_parcels = {
            r["L1_PARCEL_NBR"]: r
            for r in fetch_all(accela_session, "SELECT L1_PARCEL_NBR, L1_PARCEL_STATUS FROM dbo.L3PARCEL")
        }
 
        log.info("Loading Accela addresses...")
        accela_addrs = {
            r["L1_PARCEL_NBR"]: r
            for r in fetch_all(accela_session, """
                SELECT dbo.L3ADDRES.*, dbo.L3PARCEL.L1_PARCEL_NBR
                FROM dbo.XPARADDR 
                INNER JOIN dbo.L3PARCEL ON dbo.XPARADDR.SOURCE_SEQ_NBR = dbo.L3PARCEL.SOURCE_SEQ_NBR 
                    AND dbo.XPARADDR.L1_PARCEL_NBR = dbo.L3PARCEL.L1_PARCEL_NBR 
                INNER JOIN dbo.L3ADDRES ON dbo.XPARADDR.SOURCE_SEQ_NBR = dbo.L3ADDRES.SOURCE_SEQ_NBR 
                    AND dbo.XPARADDR.L1_ADDRESS_NBR = dbo.L3ADDRES.L1_ADDRESS_NBR
            """)
        }
 
        log.info("Loading Accela owners...")
        accela_owners = {
            r["L1_PARCEL_NBR"]: r
            for r in fetch_all(accela_session, """
                SELECT dbo.L3PARCEL.L1_PARCEL_NBR, dbo.L3OWNERS.L1_OWNER_NBR, dbo.L3OWNERS.SOURCE_SEQ_NBR, dbo.L3OWNERS.L1_EVENT_ID, dbo.L3OWNERS.L1_PRIMARY_OWNER, dbo.L3OWNERS.L1_OWNER_STATUS, 
                         dbo.L3OWNERS.L1_OWNER_FULL_NAME, dbo.L3OWNERS.L1_OWNER_TITLE, dbo.L3OWNERS.L1_OWNER_FNAME, dbo.L3OWNERS.L1_OWNER_MNAME, dbo.L3OWNERS.L1_OWNER_LNAME, dbo.L3OWNERS.L1_TAX_ID, 
                         dbo.L3OWNERS.L1_ADDRESS1, dbo.L3OWNERS.L1_ADDRESS2, dbo.L3OWNERS.L1_ADDRESS3, dbo.L3OWNERS.L1_CITY, dbo.L3OWNERS.L1_STATE, dbo.L3OWNERS.L1_ZIP, dbo.L3OWNERS.L1_COUNTRY, 
                         dbo.L3OWNERS.L1_PHONE, dbo.L3OWNERS.L1_FAX, dbo.L3OWNERS.L1_MAIL_ADDRESS1, dbo.L3OWNERS.L1_MAIL_ADDRESS2, dbo.L3OWNERS.L1_MAIL_ADDRESS3, dbo.L3OWNERS.L1_MAIL_CITY, 
                         dbo.L3OWNERS.L1_MAIL_STATE, dbo.L3OWNERS.L1_MAIL_ZIP, dbo.L3OWNERS.L1_MAIL_COUNTRY, dbo.L3OWNERS.L1_UDF1, dbo.L3OWNERS.L1_UDF2, dbo.L3OWNERS.L1_UDF3, dbo.L3OWNERS.L1_UDF4, 
                         dbo.L3OWNERS.REC_DATE, dbo.L3OWNERS.REC_FUL_NAM, dbo.L3OWNERS.REC_STATUS, dbo.L3OWNERS.GA_IVR_PIN, dbo.L3OWNERS.L1_EMAIL, dbo.L3OWNERS.EXT_UID, 
                         dbo.L3OWNERS.L1_PHONE_COUNTRY_CODE, dbo.L3OWNERS.L1_FAX_COUNTRY_CODE, dbo.L3OWNERS.L1_MAIL_FULL_NAME
                FROM dbo.XPAROWNR 
                INNER JOIN dbo.L3OWNERS ON dbo.XPAROWNR.SOURCE_SEQ_NBR = dbo.L3OWNERS.SOURCE_SEQ_NBR AND dbo.XPAROWNR.L1_OWNER_NBR = dbo.L3OWNERS.L1_OWNER_NBR 
                INNER JOIN dbo.L3PARCEL ON dbo.XPAROWNR.SOURCE_SEQ_NBR = dbo.L3PARCEL.SOURCE_SEQ_NBR AND dbo.XPAROWNR.L1_PARCEL_NBR = dbo.L3PARCEL.L1_PARCEL_NBR
            """)
        }
 
        log.info("Loading Accela attributes...")
        # Build nested index: {apn: {attr_name: attr_value}}
        accela_attrs: dict[str, dict[str, str]] = defaultdict(dict)
        for r in fetch_all(accela_session, "SELECT L1_APO_NBR, L1_ATTRIBUTE_NAME, L1_ATTRIBUTE_VALUE FROM dbo.L3APO_ATTRIBUTE"):
            accela_attrs[r["L1_APO_NBR"]][r["L1_ATTRIBUTE_NAME"]] = str(r["L1_ATTRIBUTE_VALUE"] or "").strip()
 
        status_lines.append(f"Data loaded: {datetime.now()}")
 
        # ---------------------------------------------------------------
        # Headers
        # ---------------------------------------------------------------
        parcel_header = (
            "SOURCE_SEQ_NBR|L1_PARCEL_NBR|L1_PARCEL_STATUS|L1_BLOCK|L1_BOOK|L1_CENSUS_TRACT|"
            "L1_COUNCIL_DISTRICT|L1_EXEMPT_VALUE|L1_GIS_SEQ_NBR|L1_IMPROVED_VALUE|"
            "L1_INSPECTION_DISTRICT|L1_LAND_VALUE|L1_LEGAL_DESC|L1_LOT|L1_MAP_NBR|L1_MAP_REF|"
            "L1_PAGE|L1_PARCEL|L1_PARCEL_AREA|L1_PLAN_AREA|L1_SUPERVISOR_DISTRICT|L1_TRACT|"
            "GIS_ID|L1_SUBDIVISION|L1_TOWNSHIP|L1_RANGE|L1_SECTION|L1_PRIMARY_PAR_FLG|EXT_UID\r\n"
        )
        addr_header = (
            "SERV_PROV_CODE|SOURCE_SEQ_NBR|L1_PARCEL_NBR|L1_ADDR_STATUS|L1_HSE_NBR_START|"
            "L1_HSE_NBR_END|L1_HSE_FRAC_NBR_START|L1_HSE_FRAC_NBR_END|L1_UNIT_START|L1_UNIT_END|"
            "L1_UNIT_TYPE|L1_STR_DIR|L1_STR_NAME|L1_STR_SUFFIX|L1_STR_PREFIX|L1_STR_SUFFIX_DIR|"
            "L1_SITUS_CITY|L1_SITUS_STATE|L1_SITUS_ZIP|L1_SITUS_COUNTY|L1_SITUS_COUNTRY|"
            "L1_X_COORD|L1_Y_COORD|L1_ADDR_DESC|L1_SITUS_COUNTRY_CODE|L1_INSP_DISTRICT|"
            "ATTRIB_TEMP_NAME_1|ATTRIB_NAME_1|ATTRIB_VALUE_1|ATTRIB_TEMP_NAME_2|ATTRIB_NAME_2|"
            "ATTRIB_VALUE_2|ATTRIB_TEMP_NAME_3|ATTRIB_NAME_3|ATTRIB_VALUE_3|ATTRIB_TEMP_NAME_4|"
            "ATTRIB_NAME_4|ATTRIB_VALUE_4|ATTRIB_TEMP_NAME_5|ATTRIB_NAME_5|ATTRIB_VALUE_5|"
            "ATTRIB_TEMP_NAME_6|ATTRIB_NAME_6|ATTRIB_VALUE_6|ATTRIB_TEMP_NAME_7|ATTRIB_NAME_7|"
            "ATTRIB_VALUE_7|ATTRIB_TEMP_NAME_8|ATTRIB_NAME_8|ATTRIB_VALUE_8|ATTRIB_TEMP_NAME_9|"
            "ATTRIB_NAME_9|ATTRIB_VALUE_9|ATTRIB_TEMP_NAME_10|ATTRIB_NAME_10|ATTRIB_VALUE_10|"
            "ATTRIB_TEMP_NAME_11|ATTRIB_NAME_11|ATTRIB_VALUE_11|ATTRIB_TEMP_NAME_12|"
            "ATTRIB_NAME_12|ATTRIB_VALUE_12|ATTRIB_TEMP_NAME_13|ATTRIB_NAME_13|ATTRIB_VALUE_13|"
            "ATTRIB_TEMP_NAME_14|ATTRIB_NAME_14|ATTRIB_VALUE_14|ATTRIB_TEMP_NAME_15|"
            "ATTRIB_NAME_15|ATTRIB_VALUE_15|L1_ADDRESS1|L1_ADDRESS2|L1_SITUS_NBRHD_PREFIX|"
            "L1_SITUS_NBRHD|L1_FULL_ADDRESS|EXT_UID|L1_HSE_NBR_ALPHA_START|L1_HSE_NBR_ALPHA_END|"
            "L1_LEVEL_PREFIX|L1_LEVEL_NBR_START|L1_LEVEL_NBR_END|L1_VALIDATE_ADDR_FLAG\r\n"
        )
        owner_header = (
            "SOURCE_SEQ_NBR|L1_PARCEL_NBR|L1_OWNER_STATUS|L1_OWNER_TITLE|L1_OWNER_FULL_NAME|"
            "ISPRIMARY|L1_OWNER_FNAME|L1_OWNER_MNAME|L1_OWNER_LNAME|L1_ADDRESS1|L1_ADDRESS2|"
            "L1_ADDRESS3|L1_CITY|L1_STATE|L1_ZIP|L1_COUNTRY|L1_PHONE|L1_FAX|L1_MAIL_ADDRESS1|"
            "L1_MAIL_ADDRESS2|L1_MAIL_ADDRESS3|L1_MAIL_CITY|L1_MAIL_STATE|L1_MAIL_ZIP|"
            "L1_MAIL_COUNTRY|L1_TAX_ID|L1_EVENT|L1_EMAIL|ATTRIB_TEMP_NAME_1|ATTRIB_NAME_1|"
            "ATTRIB_VALUE_1|ATTRIB_TEMP_NAME_2|ATTRIB_NAME_2|ATTRIB_VALUE_2|ATTRIB_TEMP_NAME_3|"
            "ATTRIB_NAME_3|ATTRIB_VALUE_3|ATTRIB_TEMP_NAME_4|ATTRIB_NAME_4|ATTRIB_VALUE_4|"
            "ATTRIB_TEMP_NAME_5|ATTRIB_NAME_5|ATTRIB_VALUE_5|ATTRIB_TEMP_NAME_6|ATTRIB_NAME_6|"
            "ATTRIB_VALUE_6|ATTRIB_TEMP_NAME_7|ATTRIB_NAME_7|ATTRIB_VALUE_7|ATTRIB_TEMP_NAME_8|"
            "ATTRIB_NAME_8|ATTRIB_VALUE_8|ATTRIB_TEMP_NAME_9|ATTRIB_NAME_9|ATTRIB_VALUE_9|"
            "ATTRIB_TEMP_NAME_10|ATTRIB_NAME_10|ATTRIB_VALUE_10|ATTRIB_TEMP_NAME_11|"
            "ATTRIB_NAME_11|ATTRIB_VALUE_11|ATTRIB_TEMP_NAME_12|ATTRIB_NAME_12|ATTRIB_VALUE_12|"
            "ATTRIB_TEMP_NAME_13|ATTRIB_NAME_13|ATTRIB_TEMP_NAME_14|ATTRIB_NAME_14|"
            "ATTRIB_VALUE_14|ATTRIB_TEMP_NAME_15|ATTRIB_NAME_15|ATTRIB_VALUE_15|"
            "L1_PHONE_COUNTRY_CODE|L1_FAX_COUNTRY_CODE|EXT_UID\r\n"
        )
        attr_header = "SOURCE_SEQ_NBR|L1_PARCEL_NBR|L1_ATTRIB_TEMP_NAME|L1_ATTRIB_NAME|L1_ATTRIB_VALUE\r\n"
 
        # Validate header pipe counts
        if CHECK_CHARS:
            assert count_character(parcel_header, "|") == 28, "Parcel header pipe count mismatch"
            assert count_character(addr_header,   "|") == 82, "Address header pipe count mismatch"
            assert count_character(owner_header,  "|") == 74, "Owner header pipe count mismatch"
 
        s_parcel = parcel_header
        s_addr   = addr_header
        s_owner  = owner_header
        s_attr   = attr_header
 
        # ---------------------------------------------------------------
        # Track APNs written (used later to skip inactive duplicates)
        # ---------------------------------------------------------------
        apn_set: set[str] = set()
 
        # ---------------------------------------------------------------
        # Process each staging parcel
        # ---------------------------------------------------------------
        for row in staging_rows:
            addr_changed  = False
            owner_changed = False
            attrs_changed = False
 
            apn = str(row["APN"] or "").strip()
            if "--" in apn:
                status_lines.append(f"Invalid APN!!!: {apn}")
                apn = apn.replace("--", "-")
 
            # --- Attributes ---
            ppno_raw = row["PPNO"]
            if ppno_raw is not None:
                try:
                    # Convert to float then int to strip decimal places
                    ppno = str(int(float(ppno_raw)))
                except (ValueError, TypeError):
                    ppno = str(ppno_raw).strip()
            else:
                ppno = ""
            hra_value         = str(row["HRA_NAME"] or "").strip()
            jurisdiction_code = str(row["JURISDICTION"] or "").strip()
            county_luc_value  = str(row["COUNTY_LANDUSE_DESCRIPTION"] or "").strip()
            ownership_value   = str(row["OWNERSHIP_TYPE"] or "").strip()
            parcel_size_value = str(int(row["PARCEL_SQFT"] or 0))
            priority_value    = str(row["PRIORITY_WATERSHED"] or "").strip()
            trpa_boundary     = "YES" if str(row["WITHIN_TRPA_BNDY"] or "") == "1" else "NO"
            watershed_value   = str(row["WATERSHED_NAME"] or "").strip()
            luc_value         = str(row["COUNTY_LANDUSE_CODE"] or "").strip()
            fire_district     = str(row["FIREPD"] or "").strip()
            watershed_num     = str(row["WATERSHED_NUMBER"] or "").strip()
 
            jurisdiction_value = translate_jurisdiction(jurisdiction_code)
 
            # --- Owner ---
            new_full_name  = str(row["OWN_FULL"] or "").upper().strip()
            new_full_name  = new_full_name.replace("'", "").replace("  ", " ").replace("  ", " ")
            new_first_name = ""
            new_last_name  = ""
            new_address    = str(row["MAIL_ADD1"] or "").upper().strip()
            new_mail_city  = str(row["MAIL_CITY"] or "").upper().strip()
            new_mail_state = str(row["MAIL_STATE"] or "").upper().strip()
            new_mail_zip   = str(row["MAIL_ZIP5"] or "").strip()
            new_address    = new_address.replace("P O BOX", "PO BOX")
 
            # --- Address ---
            new_city      = str(row["PSTL_TOWN"] or "").upper().strip()
            new_apo_addr  = str(row["APO_ADDRESS"] or "").upper().strip().replace("'", "")
            new_state     = str(row["PSTL_STATE"] or "").upper().strip()
            new_zip       = str(row["PSTL_ZIP5"] or "").strip()
            new_county    = jurisdiction_code.upper()
            new_dir       = str(row["STR_DIR"] or "").upper().strip()
            new_street    = clean_street(str(row["STR_NAME"] or "").upper().strip())
            new_suffix    = get_suffix(str(row["STR_SUFFIX"] or "").upper().strip())
            new_hse_num   = str(row["HSE_NUMBR"] or "").strip()
            new_unit      = str(row["UNIT_NUMBR"] or "").upper().strip()
            new_unit      = new_unit.replace("NULL", "").replace("#", "").strip()
 
            # State fallback
            if not new_state:
                if new_county in ("DG", "WA"):
                    new_state = "NV"
                elif new_county in ("EL", "PL"):
                    new_state = "CA"
 
            # Misc cleanup
            if new_city in ("RENO", "CARSON CITY", ""):
                new_city = "NONE"
            if new_city == "CITY OF SOUTH LAKE TAHOE":
                new_city = "SOUTH LAKE TAHOE"
            if not new_hse_num:
                new_hse_num = "0"
            if not new_zip:
                new_zip = "0"
            if new_dir == "NULL":
                new_dir = ""
 
            # -------------------------------------------------------
            # Existing parcel — check for changes
            # -------------------------------------------------------
            if apn in accela_parcels:
                if CHECK_FOR_MODS:
                    # --- Address comparison ---
                    to_update = False
                    if apn in accela_addrs:
                        a = accela_addrs[apn]
                        old_hse_num = str(a.get("L1_HSE_NBR_START") or "")
                        old_street  = str(a.get("L1_STR_NAME") or "").upper().replace("'", "").replace("  ", " ")
                        old_suffix  = str(a.get("L1_STR_SUFFIX") or "")
                        old_state   = str(a.get("L1_SITUS_STATE") or "")
                        old_unit    = str(a.get("L1_UNIT_START") or "").upper().replace("#", "").strip()
                        old_dir     = str(a.get("L1_STR_DIR") or "")
                        old_city    = str(a.get("L1_SITUS_CITY") or "").upper()
                        old_zip     = str(a.get("L1_SITUS_ZIP") or "0")
                        if not old_city:
                            old_city = "NONE"
 
                        if old_street != new_street:
                            status_lines.append(f"{new_county} APN: {apn}  OLD STREET: {old_street} / NEW STREET: {new_street}")
                            to_update = True
                        # Normalize house numbers: treat "0" as equivalent to empty
                        old_hse_num_norm = old_hse_num if old_hse_num != "0" else ""
                        new_hse_num_norm = new_hse_num if new_hse_num != "0" else ""
                        
                        if old_hse_num_norm != new_hse_num_norm:
                            status_lines.append(f"{new_county} APN: {apn}  OLD NUMBER: '{old_hse_num}' / NEW NUMBER: '{new_hse_num}'")
                            to_update = True
                        if old_suffix != new_suffix:
                            status_lines.append(f"{new_county} APN: {apn}  OLD SUFFIX: {old_suffix} / NEW SUFFIX: {new_suffix}")
                            to_update = True
                        if old_state != new_state:
                            status_lines.append(f"APN: {apn}  OLD STATE: {old_state} / NEW STATE: {new_state}")
                            to_update = True
                        if old_unit != new_unit:
                            status_lines.append(f"APN: {apn}  OLD UNIT: {old_unit} / NEW UNIT: {new_unit}")
                            to_update = True
                        if old_dir != new_dir:
                            status_lines.append(f"APN: {apn}  OLD DIR: {old_dir} / NEW DIR: {new_dir}")
                            to_update = True
 
                        if to_update:
                            addr_changed = True
                            s_addr += (
                                f"TRPA|115|{apn}|A|{new_hse_num}||||{new_unit}|||{new_dir}|"
                                f"{new_street}|{new_suffix}|||{new_city}|{new_state}|{new_zip}|"
                                f"||||||||||||||||||||||||||||||||||||||||||||||||||||"
                                f"{new_apo_addr}|||||||||||\r\n"
                            )
                            addresses_updated += 1
 
                    # --- Owner comparison ---
                    if new_full_name:
                        to_update = False
                        if apn in accela_owners:
                            o = accela_owners[apn]
                            old_address   = str(o.get("L1_MAIL_ADDRESS1") or "").upper().strip()
                            old_full_name = str(o.get("L1_OWNER_FULL_NAME") or "").upper().strip()
 
                            to_update = (
                                new_full_name[:20] != old_full_name[:20]
                                or old_address != new_address
                            )
 
                        if to_update:
                            status_lines.append(
                                f"APN: {apn}  Old Owner: {old_full_name}/{old_address} "
                                f"/ New Owner: {new_full_name}/{new_address}"
                            )
                            owner_changed = True
                            owner_rec = (
                                f"115|{apn}|A||{new_full_name}|Y|{new_first_name}||{new_last_name}"
                                f"||||||||||{new_address}|||{new_mail_city}|{new_mail_state}|"
                                f"{new_mail_zip}||||||||||||||||||||||||||||||||||||||||||||||||||||"
                                f"\r\n"
                            )
                            if CHECK_CHARS:
                                if count_character(owner_rec, "|") == 75:
                                    s_owner += owner_rec
                                    owners_updated += 1
                                else:
                                    log.error("Owner pipe count mismatch for APN %s — skipping", apn)
                            else:
                                s_owner += owner_rec
                                owners_updated += 1
 
                    # --- Attribute comparison ---
                    if UPDATE_ATTRIBUTES:
                        apn_attrs = accela_attrs.get(apn, {})
 
                        def get_attr(keyword: str, exact: bool = False) -> str:
                            """Find attribute value by keyword match."""
                            for name, val in apn_attrs.items():
                                if exact:
                                    if name == keyword:
                                        return val
                                else:
                                    if keyword.upper() in name.upper():
                                        return val
                            return ""
 
                        ppno_accela         = get_attr("PPNO")
                        hra_accela          = get_attr("HRA")
                        jurisdiction_accela = get_attr("JURISDICTION")
                        county_luc_accela   = get_attr("DESCRIPTION")
                        ownership_accela    = get_attr("OWNERSHIP")
                        parcel_size_accela  = get_attr("PARCEL_SIZE")
                        priority_accela     = get_attr("PRIORITY")
                        trpa_boundary_accela= get_attr("TRPA_BOUNDARY")
                        watershed_accela    = get_attr("WATERSHED", exact=True)
                        luc_accela          = get_attr("LAND_USE_CODE")
                        fire_accela         = get_attr("FIRE_DISTRICT")
                        wshed_num_accela    = get_attr("WATERSHED_NUMBER")
 
                        def add_attr(attr_name: str, new_val: str, old_val: str, force: bool = False):
                            nonlocal attrs_changed
                            if new_val.upper() != old_val.upper() and (new_val or force):
                                s_attr_line = f"115|{apn}|PARCEL|{attr_name}|{new_val}\r\n"
                                return s_attr_line, True
                            return "", False
 
                        for attr_name, new_val, old_val in [
                            ("PPNO",             ppno,              ppno_accela),
                            ("HRA",              hra_value,         hra_accela),
                            ("JURISDICTION",     jurisdiction_value,jurisdiction_accela),
                            ("DESCRIPTION",      county_luc_value,  county_luc_accela),
                            ("OWNERSHIP",        ownership_value,   ownership_accela),
                            ("PRIORITY",         priority_value,    priority_accela),
                            ("TRPA_BOUNDARY",    trpa_boundary,     trpa_boundary_accela),
                            ("WATERSHED",        watershed_value,   watershed_accela),
                            ("LAND_USE_CODE",    luc_value,         luc_accela),
                            ("FIRE_DISTRICT",    fire_district,     fire_accela),
                            ("WATERSHED_NUMBER", watershed_num,     wshed_num_accela),
                        ]:
                            line, changed = add_attr(attr_name, new_val, old_val)
                            if changed:
                                s_attr += line
                                attrs_changed = True



 
                        # Parcel size — only update if difference > 1
                        try:
                            ps_new = int(parcel_size_value or 0)
                            ps_old = int(parcel_size_accela or 0)
                            if abs(ps_new - ps_old) > 1 and parcel_size_value:
                                s_attr += f"115|{apn}|PARCEL|PARCEL_SIZE|{parcel_size_value}\r\n"
                                attrs_changed = True
                        except ValueError:
                            pass
 
                    # Write parcel record if anything changed
                    if attrs_changed or addr_changed or owner_changed:
                        s_parcel += f"115|{apn}|A|||||||||||||||||||||||||Y|\r\n"
                        apn_set.add(apn)
 
            # -------------------------------------------------------
            # New parcel — add everything
            # -------------------------------------------------------
            else:
                new_parcels += 1
                apn_set.add(apn)
                s_parcel += f"115|{apn}|A|||||||||||||||||||||||||Y|\r\n"
 
                s_addr += (
                    f"TRPA|115|{apn}|A|{new_hse_num}||||{new_unit}|||{new_dir}|"
                    f"{new_street}|{new_suffix}|||{new_city}|{new_state}|{new_zip}|"
                    f"||||||||||||||||||||||||||||||||||||||||||||||||||||"
                    f"{new_apo_addr}|||||||||||\r\n"
                )
 
                if new_full_name:
                    owner_rec = (
                        f"115|{apn}|A||{new_full_name}|Y|{new_first_name}||{new_last_name}"
                        f"||||||||||{new_address}|||{new_mail_city}|{new_mail_state}|"
                        f"{new_mail_zip}||||||||||||||||||||||||||||||||||||||||||||||||||||"
                        f"\r\n"
                    )
                    if CHECK_CHARS:
                        if count_character(owner_rec, "|") == 75:
                            s_owner += owner_rec
                        else:
                            log.error("New owner pipe count mismatch for APN %s — skipping", apn)
                    else:
                        s_owner += owner_rec
 
                if UPDATE_ATTRIBUTES:
                    for attr_name, val in [
                        ("PPNO",             ppno),
                        ("HRA",              hra_value),
                        ("JURISDICTION",     jurisdiction_value),
                        ("DESCRIPTION",      county_luc_value),
                        ("OWNERSHIP",        ownership_value),
                        ("PARCEL_SIZE",      parcel_size_value),
                        ("PRIORITY",         priority_value),
                        ("TRPA_BOUNDARY",    trpa_boundary),
                        ("WATERSHED",        watershed_value),
                        ("LAND_USE_CODE",    luc_value),
                        ("FIRE_DISTRICT",    fire_district),
                        ("WATERSHED_NUMBER", watershed_num),
                    ]:
                        if val:
                            s_attr += f"115|{apn}|PARCEL|{attr_name}|{val}\r\n"
 
        # ---------------------------------------------------------------
        # Inactive / obsolete parcels
        # ---------------------------------------------------------------
        status_lines.append(f"Starting process to Add/Deactivate Parcels: {datetime.now()}")
 
        tabular_session = get_session(STAGING_TABULAR_DB)
        inactive_rows = fetch_all(
            tabular_session,
            "SELECT APN, Status FROM PARCEL_APN_NEWOLD"
        )

        for row in inactive_rows:
            inactive_apn = str(row["APN"] or "").strip()
            if inactive_apn in apn_set:
                continue  # Already processed above — skip
            if str(row["Status"]) != "Old APN":
                continue

            if inactive_apn in accela_parcels:
                accela_status = str(accela_parcels[inactive_apn].get("L1_PARCEL_STATUS") or "")
                if accela_status == "A":
                    s_parcel += f"115|{inactive_apn}|I|||||||||||||||||||||||||Y|\r\n"
                    status_lines.append(f"Parcel is now obsolete: {inactive_apn}")
                    total_obsolete += 1
                else:
                    status_lines.append(f"Parcel is ALREADY obsolete: {inactive_apn}")
            else:
                status_lines.append(f"Parcel is obsolete but missing from Accela: {inactive_apn}")
 
        # ---------------------------------------------------------------
        # Write output files
        # ---------------------------------------------------------------
        write_file("parcel_base.txt",    s_parcel)
        write_file("parcel_address.txt", s_addr)
        write_file("parcel_owner.txt",   s_owner)
        write_file("parcel_attr.txt",    s_attr)
 
        status_lines += [
            f"Total parcels set to inactive: {total_obsolete}",
            f"New Accela Parcels added: {new_parcels}",
            f"Total Addresses updated: {addresses_updated}",
            f"Total Owners updated: {owners_updated}",
            f"Completed at: {datetime.now()}",
        ]
        
        # Log the update counts
        log.info(f"Address records updated: {addresses_updated}")
        log.info(f"Owner records updated: {owners_updated}")
 
    except Exception as ex:
        handle_error(ex, apn)
 
    finally:
        write_file("accela_apo_status.txt", "\n".join(status_lines))
 
# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
 
def main():
    start = datetime.now()
    log.info("AccelaAPOFiles started at %s", start)
    accela_apo_file_creation()
    # Only run file check if the output files were actually created
    if os.path.exists(os.path.join(OUTPUT_DIR, "parcel_attr.txt")):
        accela_apo_file_check()
    else:
        log.warning("Skipping file check — output files not found in %s", OUTPUT_DIR)
    end = datetime.now()
    log.info("AccelaAPOFiles finished at %s (elapsed: %s)", end, end - start)
 
 
if __name__ == "__main__":
    main()
