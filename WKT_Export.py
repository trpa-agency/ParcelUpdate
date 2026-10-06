import csv
import os
import smtplib
import sys
import time
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote
import re
import requests
from pyproj import Transformer

# setup
WKT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Updated_Shapes_2026-09-02.wkt")
POST_URL = "https://api.laketahoeinfo.org/parcels"
API_KEY = "ee44fc77-6602-4276-9a8b-1e4508104e9f"

# The following 2 variables are if you are just wanted to test the update
TEST_ONLY = False   # set to true if you want to just see what parcels would be updated
MAX_PARCELS = None  # only process this many parcels (None for all)

# WKT geometries can be very large
csv.field_size_limit(sys.maxsize)

# email parameters
subject = "Parcel Tracker shapes updated"
sender_email = "infosys@trpa.org"
receiver_email = "afish@trpa.gov"

# log messages are printed and kept to attach to the email
log_lines = []


def log(message):
    print(message)
    log_lines.append(message)


def send_mail(body):
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email

    msgText = MIMEText(body, 'html')
    msg.attach(msgText)

    attachment = MIMEText("\n".join(log_lines))
    attachment.add_header("Content-Disposition", "attachment", filename="parcel_geometry_update_log.txt")
    msg.attach(attachment)

    try:
        with smtplib.SMTP("mail.smtp2go.com", 25) as smtpObj:
            smtpObj.ehlo()
            smtpObj.starttls()
            smtpObj.sendmail(sender_email, receiver_email, msg.as_string())
    except Exception as e:
        print(e)


# time a function
def timer(func):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        log(f"Function {func.__name__} took {end_time - start_time} seconds to execute.")
        return result
    return wrapper


# The API expects lon/lat (WGS 84, EPSG:4326, longitude first) and does not reproject.
# The source parcel data is in NAD83 / UTM zone 10N (meters), so convert before posting
SOURCE_EPSG = 26910
_transformer = Transformer.from_crs(SOURCE_EPSG, 4326, always_xy=True)
_coord_pair = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)")


def wkt_to_wgs84(wkt):
    def convert(match):
        lon, lat = _transformer.transform(float(match.group(1)), float(match.group(2)))
        return f"{lon:.9f} {lat:.9f}"
    return _coord_pair.sub(convert, wkt)


def check_lon_lat(apn, wkt):
    first = _coord_pair.search(wkt)
    lon, lat = float(first.group(1)), float(first.group(2))
    if not (-121 < lon < -119 and 38 < lat < 40):
        raise ValueError(f"{apn}: converted coordinate ({lon}, {lat}) is outside the Tahoe area")


# read APN/WKT pairs from the tab-delimited export, converted to lon/lat
def read_wkt_file(wkt_path):
    with open(wkt_path, newline="", encoding="utf-8") as wkt_file:
        reader = csv.DictReader(wkt_file, delimiter="\t")
        parcels = []
        for row in reader:
            wkt = wkt_to_wgs84(row["WKT"])
            check_lon_lat(row["APN"], wkt)
            parcels.append((row["APN"], wkt))
        return parcels


# post each geometry to the API
@timer
def post_parcel_geom_update(parcels, base_url, api_key, test_only=True):
    total_count = 0
    failures = []
    for apn, wkt in parcels:
        total_count += 1
        if (total_count % 1000) == 0:
            log(f"Updating row {total_count}")
        parcel_url = f"{base_url}/{quote(str(apn), safe='')}/geometry"
        if test_only:
            log(f"[test only] Would post to URL: {parcel_url}")
            continue
        try:
            response = requests.post(
                parcel_url,
                headers={"x-api-key": api_key},
                json={"Wkt": wkt},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            failures.append(apn)
    log(f"Processed {total_count} parcels, {len(failures)} failures")
    return failures


try:
    parcels = read_wkt_file(WKT_FILE)
    log(f"Read {len(parcels)} parcels from {WKT_FILE}")

    if MAX_PARCELS is not None:
        parcels = parcels[:MAX_PARCELS]
        log(f"Limiting to first {len(parcels)} parcels")

    failures = post_parcel_geom_update(parcels, POST_URL, API_KEY, test_only=TEST_ONLY)

    mode = "TEST ONLY - " if TEST_ONLY else ""
    
    
    # Keep track of how many failures and successes there are
    failed_set = set(failures)
    succeeded_apns = [apn for apn, _ in parcels if apn not in failed_set]
    succeeded = len(succeeded_apns)
    if failures:
        header = f"{mode}WARNING - {len(failures)} of {len(parcels)} parcel geometries failed to update - Check Log"
    else:
        header = f"{mode}SUCCESS - all {len(parcels)} parcel geometries were sent to the API."
    
    summary = (f"<br><br>Successful updates: {succeeded}"
        f"<br>Failed updates: {len(failures)}")
    
    log(f"Successful updates: {succeeded}")
    log(f"Failed updates: {len(failures)}")
    
    if succeeded_apns:
        log("Succeeded APNs: " + ", ".join(succeeded_apns))
    if failures:
        log("Failed APNs: " + ", ".join(failures))
    
    
    send_mail(header + summary)
    print('Sending email...')

# catch any errors
except Exception:
    log(f"\n{'='*80}\nERROR\n{'='*80}\n{traceback.format_exc()}")
    send_mail("ERROR - Parcel geometry update failed - Check Log")
    print('Sending error email...')
