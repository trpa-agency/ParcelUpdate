"""
Accela_LCV_Upload.py
Created: July 29, 2026
Amy Fish, Tahoe Regional Planning Agency

Reads \\arcmain\\e$\\DownloadTahoeIndex.xlsx (columns: File, APN, File Number, Type).
Rows are grouped by their parcel IDs, since a document can reference multiple parcels and 
multiple documents 

For each unique parcel set:
  1. Checks whether every parcel in the set exists in Accela.
  2. If they all exist: creates ONE "Land Capability Verification" record
     with ALL of those parcels attached, then uploads every file from every
     row in the group (from \\arcmain\\e$\\DownloadTahoe\\) to that one record.
  3. If any parcel is missing: logs every row in the group as failed and
     moves on -- no partial records get created.
Writes a per-file success/failure log to \\arcmain\\e$\\DownloadTahoe\\accela_lcv_log.csv (rows
sharing the same RecordID mean those files were attached to the same record).

Requires: pip install requests openpyxl
"""
import os
import re
import sys
import csv
import json
import datetime
import requests
import openpyxl

# --- Config ---
AUTH_URL = "https://auth.accela.com/oauth2/token"
RECORDS_URL = "https://apis.accela.com/v4/records"
PARCELS_URL = "https://apis.accela.com/v4/parcels"

APP_ID = ""

PASSWORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "passwords.txt")


def load_credentials(path):
    creds = {}
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            creds[key.strip()] = value.strip()
    return creds


_creds = load_credentials(PASSWORDS_FILE)

scope = "records documents parcels"
client_id = "638769013925399246"
client_secret = _creds["client_secret"]
username = _creds["username"]
password = _creds["password"]
environment = "NONPROD1"
grant_type = "password"
agency_name = "TRPA"

INDEX_XLSX = r"\\arcmain\\e$\\DownloadTahoe\\Index.xlsx"
DOCS_FOLDER = r"\\arcmain\\e$\\DownloadTahoe"  # ASSUMPTION: files in the "File" column live here
LOG_CSV = r"\\arcmain\\e$\\DownloadTahoe\\accela_lcv_log.csv"

# Hardcoded record type: Land Capability Verification (per spec)
LCV_TYPE = {
    "module": "Building",
    "value": "Building/ERS/Assessments/Land Cap Verification",
    "type": "ERS",
    "text": "Land Capability Verification",
    "group": "Building",
    "alias": "Land Capability Verification",
    "category": "Land Cap Verification",
    "subType": "Assessments",
    "id": "Building-ERS-Assessments-Land.cCap.cVerification",
}
LCV_STATUS = {"text": "Closed", "value": "Closed"}
LCV_ASSIGNED_DEPT = "TRPA/ERS/NA/NA/NA/RECORDS/NA"


def authenticate():
    auth_payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": grant_type,
        "username": username,
        "password": password,
        "agency_name": agency_name,
        "environment": environment,
        "scope": scope,
    }
    auth_headers = {"Content-Type": "application/x-www-form-urlencoded"}

    resp = requests.post(AUTH_URL, data=auth_payload, headers=auth_headers)
    if resp.status_code != 200:
        sys.exit(f"Auth error: {resp.status_code} {resp.text}")

    tok = resp.json().get("access_token")
    if not tok:
        sys.exit(f"No access_token in auth response: {resp.text}")
    return tok


def base_headers(access_token):
    return {
        # NOTE: if calls 401, try switching to f"Bearer {access_token}"
        "Authorization": access_token,
        "Content-Type": "application/json",
        "x-accela-appid": APP_ID,
    }


def read_index(xlsx_path):
    """Read File, APN, File Number, Type columns from Index.xlsx into a list of dicts."""
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(h).strip() if h else "" for h in rows[0]]
    col_idx = {name: header.index(name) for name in ("File", "APN", "File Number", "Type") if name in header}

    missing = [c for c in ("File", "APN", "File Number", "Type") if c not in col_idx]
    if missing:
        sys.exit(f"Index.xlsx is missing expected column(s): {missing}. Found columns: {header}")

    records = []
    for row in rows[1:]:
        if row is None or all(v is None for v in row):
            continue
        records.append({
            "File": row[col_idx["File"]],
            "APN": row[col_idx["APN"]],
            "File Number": row[col_idx["File Number"]],
            "Type": row[col_idx["Type"]],
        })
        if len(records) >= 5:   #For testing purposes I'm just running the first 5
            break
    return records


TO_RANGE_PATTERN = re.compile(r"([\d\-]+)\s+TO\s+-?(\d{1,4})", re.IGNORECASE)
APN_DELIM_PATTERN = re.compile(r"\\[nN]|[\n,/]|\bAND\b", re.IGNORECASE)

# Valid full-APN shapes by county. Format: (compiled regex, expected # of dash-separated groups)
# El Dorado:  xxx-xxx-xxx
# Placer:     xxx-xxx-xxx
# Washoe:     xxx-xxx-xx
# Douglas:    xxxx-xx-xxx-xxx
FULL_APN_SHAPES = [
    re.compile(r"^\d{3}-\d{3}-\d{3}$"),        # El Dorado / Placer
    re.compile(r"^\d{3}-\d{3}-\d{2}$"),        # Washoe
    re.compile(r"^\d{4}-\d{2}-\d{3}-\d{3}$"),  # Douglas
]


def match_full_apn(tok):
    """Return (prefix, last_group_width) if tok matches one of the known county
    APN shapes exactly, else None. prefix is everything before the final group
    (what shorthand tokens borrow); last_group_width is how many digits the
    final group should have (used to zero-pad shorthand tokens correctly)."""
    for pat in FULL_APN_SHAPES:
        if pat.match(tok):
            prefix, last = tok.rsplit("-", 1)
            return prefix, len(last)
    return None


def _tokenize_apn_segment(segment, base_prefix, last_width):
    """Split one chunk of an APN cell into tokens and resolve each against the
    running base_prefix/last_width (state carried from the most recent full APN)."""
    pieces = APN_DELIM_PATTERN.split(segment)
    tokens = []
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        # Handles cells with no delimiter at all between full APNs, e.g.
        # "124-082-16 124-082-17 124-082-18"
        for sub in re.split(r"\s+", p):
            sub = sub.strip(" \t.,;`'\"")
            if sub:
                tokens.append(sub)

    results = []
    for tok in tokens:
        full = match_full_apn(tok)
        if full:
            base_prefix, last_width = full
            results.append((tok, tok))
            continue

        digits = re.sub(r"\D", "", tok)
        if not digits:
            continue  # stray punctuation only, nothing to parse

        if base_prefix and last_width:
            results.append((f"{base_prefix}-{digits.zfill(last_width)}", tok))
        else:
            results.append((None, tok))  # unresolvable: no prior full APN in this cell

    return results, base_prefix, last_width


def parse_apn_cell(raw):
    """
    Parse an Index.xlsx APN cell that may contain multiple APNs. Handles, in
    combination or alone:
      - real newlines AND the literal two-character sequence \\n / \\N
        (some cells contain a typed backslash-n rather than an actual newline)
      - commas, slashes, and the word "AND" as separators
      - space-separated full APNs with no delimiter at all
      - APN string that borrows the prefix from the most recent full APN
        in the cell, e.g. "090-243-004 AND -005" -> ...-004, ...-005
      - no leading dash, e.g. "122-181-02 AND 42" -> ...-02, ...-42
      - four county APN shapes: El Dorado/Placer (xxx-xxx-xxx), Washoe
        (xxx-xxx-xx), Douglas (xxxx-xx-xxx-xxx)
      - stray trailing punctuation, e.g. "093-360-016`"
      - accidental double dashes, e.g. "116-220--008" -> 116-220-008
      - "BASE-NN TO -MM" / "BASE-NN TO MM" ranges, expanded to every APN in
        the range, e.g. "123-190-01 TO -25" -> 25 APNs

    Returns a list of (resolved_apn, raw_token) tuples. resolved_apn is None
    when a token can't be resolved (e.g. a shorthand token with no preceding
    full APN in the cell, or an APN that doesn't match any known county shape)
    -- log these as errors
    """
    if raw is None:
        return []

    text = re.sub(r"-{2,}", "-", str(raw))  # collapse accidental double dashes
    results = []
    base_prefix = None
    last_width = None
    pos = 0

    for m in TO_RANGE_PATTERN.finditer(text):
        full = match_full_apn(m.group(1))
        if not full:
            continue  # not actually a valid "APN TO N" range; leave for normal tokenizing
        prefix, width = full
        start_num = int(m.group(1).rsplit("-", 1)[1])
        end_num = int(m.group(2))

        preceding = text[pos:m.start()]
        sub_results, base_prefix, last_width = _tokenize_apn_segment(preceding, base_prefix, last_width)
        results.extend(sub_results)

        rng = range(start_num, end_num + 1) if start_num <= end_num else range(start_num, end_num - 1, -1)
        for n in rng:
            results.append((f"{prefix}-{str(n).zfill(width)}", m.group(0)))

        base_prefix, last_width = prefix, width
        pos = m.end()

    remainder = text[pos:]
    sub_results, base_prefix, last_width = _tokenize_apn_segment(remainder, base_prefix, last_width)
    results.extend(sub_results)
    return results


def resolve_row_parcels(row):
    """
    Resolve an Index.xlsx row's APN cell into a deduplicated list of parcel
    APNs. Returns (parcels, error):
      - (['090-282-018', '090-282-019'], None) on success
      - (None, "some error message") if the cell is blank or contains any
        token that couldn't be resolved -- the whole row is treated as failed
        rather than partially processed, since a permit with a silently
        incomplete parcel list is worse than one flagged for a human to check.
    """
    parsed = parse_apn_cell(row["APN"])
    if not parsed:
        return None, "No APN found in cell"

    apns = []
    bad_tokens = []
    for apn, raw_token in parsed:
        if apn is None:
            bad_tokens.append(raw_token)
        elif apn not in apns:
            apns.append(apn)

    if bad_tokens:
        return None, f"Could not resolve APN token(s): {', '.join(bad_tokens)}"
    if not apns:
        return None, "No valid APNs resolved from cell"
    return apns, None


def build_row_entries(raw_rows):
    """Attach resolved parcel list (or parse error) to each raw Index.xlsx row."""
    entries = []
    for row in raw_rows:
        parcels, error = resolve_row_parcels(row)
        entries.append({
            "File": row["File"],
            "File Number": row["File Number"],
            "Type": row["Type"],
            "APN Raw": row["APN"],
            "Parcels": parcels,
            "ParseError": error,
        })
    return entries


def group_rows_by_parcel_set(entries):
    """
    Group rows that reference the exact same SET of parcels into one permit.
    Two rows listing "090-282-018 AND -019" (in either order, any formatting)
    both resolve to {090-282-018, 090-282-019} and end up in the same group --
    meaning one record gets created with both parcels attached, and every
    file from every row in the group gets uploaded to that one record.
    Rows with a ParseError are excluded here; the caller logs them directly.
    """
    grouped = {}
    order = []
    for e in entries:
        if e["ParseError"] or not e["Parcels"]:
            continue
        key = tuple(sorted(e["Parcels"]))
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(e)
    return [(key, grouped[key]) for key in order]


def check_parcel_exists(access_token, apn):
    """Return the parcel JSON if the APN exists in Accela, else None."""
    headers = base_headers(access_token)
    resp = requests.get(f"{PARCELS_URL}/{apn}", headers=headers)

    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        # Treat other errors as "couldn't confirm" rather than silently skipping
        raise RuntimeError(f"Parcel lookup error for APN {apn}: {resp.status_code} {resp.text}")

    data = resp.json()
    result = data.get("result", data)
    if not result:
        return None
    return result


def create_lcv_record(access_token, apns):
    """Create a Land Capability Verification record tied to ALL of the given
    APNs at once. Returns (record_id, custom_id)."""
    headers = base_headers(access_token)
    today = datetime.date.today().isoformat()

    payload = {
        "customId": None,
        "description": "Created by 1DocStop import",
        "id": None,
        "openedDate": today,
        "parcels": [{"id": apn, "parcelNumber": apn} for apn in apns],
        "status": LCV_STATUS,
        "assignedUser": "OLD FILE",
        "assignedToDepartment": LCV_ASSIGNED_DEPT,
        "type": LCV_TYPE,
    }

    resp = requests.post(RECORDS_URL, headers=headers, data=json.dumps(payload))
    if resp.status_code != 200:
        raise RuntimeError(f"Record creation error for parcels {apns}: {resp.status_code} {resp.text}")

    data = resp.json()
    result = data.get("result", data)
    record_id = result.get("id")
    custom_id = result.get("customId")
    if not record_id:
        raise RuntimeError(f"Record created but no id returned for parcels {apns}: {resp.text}")
    return record_id, custom_id


def get_record_fees(access_token, record_id):
    """Return the list of fee line items currently on a record."""
    headers = base_headers(access_token)
    resp = requests.get(f"{RECORDS_URL}/{record_id}/fees", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Get fees error for record {record_id}: {resp.status_code} {resp.text}")

    data = resp.json()
    result = data.get("result", data)
    return result or []


def delete_record_fees(access_token, record_id, fee_ids):
    """Delete the given fee line item ids from a record."""
    if not fee_ids:
        return
    headers = base_headers(access_token)
    ids_str = ",".join(str(fid) for fid in fee_ids)
    resp = requests.delete(f"{RECORDS_URL}/{record_id}/fees/{ids_str}", headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"Delete fees error for record {record_id}: {resp.status_code} {resp.text}")


def remove_auto_added_fees(access_token, record_id):
    """Remove every fee line item Accela auto-added when the record was created."""
    fees = get_record_fees(access_token, record_id)
    fee_ids = [f.get("id") for f in fees if f.get("id")]
    delete_record_fees(access_token, record_id, fee_ids)
    return len(fee_ids)


def upload_document(access_token, record_id, file_path):
    """Attach a PDF document to the given record."""
    if not os.path.isfile(file_path):
        raise RuntimeError(f"Document file not found: {file_path}")

    url = f"{RECORDS_URL}/{record_id}/documents"
    file_name = os.path.basename(file_path)

    headers = {
        "Authorization": access_token,
        "x-accela-appid": APP_ID,
        # Do NOT set Content-Type here; requests will set the correct multipart boundary
    }
    payload = {
        "fileInfo": json.dumps([{
            "fileName": file_name,
            "type": "application/pdf",
            "description": "LCV Doc from 1DocStop",
        }])
    }

    with open(file_path, "rb") as f:
        files = [("uploadFile", (file_name, f, "application/pdf"))]
        resp = requests.post(url, headers=headers, data=payload, files=files)

    if resp.status_code != 200:
        raise RuntimeError(f"Document upload error for record {record_id}: {resp.status_code} {resp.text}")


def main():
    token = authenticate()
    raw_rows = read_index(INDEX_XLSX)

    if not raw_rows:
        print(f"No rows found in {INDEX_XLSX}")
        return

    entries = build_row_entries(raw_rows)

    log_rows = []
    success_count = 0
    failure_count = 0

    # Rows whose APN cell couldn't be fully resolved never make it into a
    # group -- log them here as immediate failures.
    for e in entries:
        if e["ParseError"] or not e["Parcels"]:
            log_rows.append({
                "File": e["File"], "Parcels": "", "APN Raw": e["APN Raw"],
                "File Number": e["File Number"], "Type": e["Type"],
                "Status": "FAILED", "RecordID": "",
                "Message": e["ParseError"] or "No valid APNs resolved from cell",
            })
            failure_count += 1

    # Cache parcel-existence checks -- the same APN can appear in multiple
    # different permit groups, and there's no reason to look it up twice.
    parcel_cache = {}

    def parcel_exists_cached(apn):
        if apn not in parcel_cache:
            parcel_cache[apn] = bool(check_parcel_exists(token, apn))
        return parcel_cache[apn]

    for parcel_set, group in group_rows_by_parcel_set(entries):
        parcels_str = "; ".join(parcel_set)

        # 1. Confirm every parcel in the set exists before creating anything
        missing = []
        lookup_error = None
        for apn in parcel_set:
            try:
                if not parcel_exists_cached(apn):
                    missing.append(apn)
            except Exception as e:
                lookup_error = str(e)
                break

        if lookup_error:
            for row in group:
                log_rows.append({
                    "File": row["File"], "Parcels": parcels_str, "APN Raw": row["APN Raw"],
                    "File Number": row["File Number"], "Type": row["Type"],
                    "Status": "FAILED", "RecordID": "",
                    "Message": f"Parcel lookup error: {lookup_error}",
                })
                failure_count += 1
            print(f"[FAIL] parcels {parcels_str}: parcel lookup error: {lookup_error}")
            continue

        if missing:
            msg = f"Parcel(s) not found in Accela: {', '.join(missing)}"
            for row in group:
                log_rows.append({
                    "File": row["File"], "Parcels": parcels_str, "APN Raw": row["APN Raw"],
                    "File Number": row["File Number"], "Type": row["Type"],
                    "Status": "FAILED", "RecordID": "",
                    "Message": msg,
                })
                failure_count += 1
            print(f"[FAIL] parcels {parcels_str}: {msg}")
            continue

        # 2. Create ONE record covering every parcel in this group
        try:
            record_id, custom_id = create_lcv_record(token, list(parcel_set))
        except Exception as e:
            for row in group:
                log_rows.append({
                    "File": row["File"], "Parcels": parcels_str, "APN Raw": row["APN Raw"],
                    "File Number": row["File Number"], "Type": row["Type"],
                    "Status": "FAILED", "RecordID": "",
                    "Message": f"Record creation error: {e}",
                })
                failure_count += 1
            print(f"[FAIL] parcels {parcels_str}: record creation error: {e}")
            continue

        print(f"[OK] parcels {parcels_str} -> record {custom_id or record_id} "
              f"({len(group)} document(s) to attach)")

        # 2b. Remove the fee(s) Accela auto-added on record creation
        try:
            removed = remove_auto_added_fees(token, record_id)
            if removed:
                print(f"    [OK] removed {removed} auto-added fee(s) from record {custom_id or record_id}")
        except Exception as e:
            print(f"    [WARN] could not remove auto-added fee(s) from record {custom_id or record_id}: {e}")

        # 3. Upload every file from every row in this group to that one record
        for row in group:
            file_name = row["File"]
            log_entry = {
                "File": file_name, "Parcels": parcels_str, "APN Raw": row["APN Raw"],
                "File Number": row["File Number"], "Type": row["Type"],
                "Status": "", "RecordID": record_id, "Message": "",
            }
            if not file_name:
                log_entry["Status"] = "FAILED"
                log_entry["Message"] = "Blank File value in Index.xlsx"
                log_rows.append(log_entry)
                failure_count += 1
                continue

            try:
                file_path = os.path.join(DOCS_FOLDER, str(file_name))
                upload_document(token, record_id, file_path)
                log_entry["Status"] = "SUCCESS"
                log_entry["Message"] = f"Attached to record {custom_id or record_id}"
                success_count += 1
                print(f"    [OK] {file_name} attached")
            except Exception as e:
                log_entry["Status"] = "FAILED"
                log_entry["Message"] = str(e)
                failure_count += 1
                print(f"    [FAIL] {file_name}: {e}")

            log_rows.append(log_entry)

    with open(LOG_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["File", "Parcels", "APN Raw", "File Number", "Type", "Status", "RecordID", "Message"]
        )
        writer.writeheader()
        writer.writerows(log_rows)

    print(f"\nDone. {success_count} succeeded, {failure_count} failed. Log written to {LOG_CSV}")


if __name__ == "__main__":
    main()