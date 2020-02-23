from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime, timedelta
import dateparser
from flask import Flask
import hashlib
import icalendar
import json
import logging
import os
import yaml

LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=LOGLEVEL)

# Get env vars
config_file = os.environ.get("CONFIG_FILE", "config.yaml")
if "CREDS_JSON" not in os.environ:
    exit("Error: no JSON credentials.")
creds_json = os.environ.get("CREDS_JSON")

app = Flask(__name__)

# Load the config yaml
# TODO: Validate file, error handling.
# Cache the config as a global var.
# Note: the app will need to restart to load new configs
cache_config = []
def load_config(config_file, endpoint = False):
    global cache_config
    if not cache_config:
        logging.debug("load_config: loading config from file")
        cf = open(config_file, "r")
        config = yaml.safe_load(cf)
        cf.close()
        cache_config = config
    else:
        logging.debug("load_config: loading config from cache")
        config = cache_config

    if endpoint:
        for cal in config:
            if cal["endpoint"] == endpoint:
                logging.debug("load_config: returning config for {}".format(endpoint))
                return cal

    # If not a specific endpoing, return an array of all configs
    logging.debug("load_config: returning all config (no endpoint specified)")
    return config


# Load the spreadsheet data
# TODO: Validate auth, error handling, etc
def load_sheet(json_creds, sheet_id, sheet_range):
    logging.debug("load_sheet: loading sheet {} with range {}".format(sheet_id, sheet_range))
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    service_account_info = json.loads(json_creds)
    credentials = service_account.Credentials.from_service_account_info(service_account_info, scopes = scopes)

    service = build("sheets", "v4", credentials = credentials)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=sheet_id, range=sheet_range).execute()
    values = result.get("values", [])
    return values


# Extract fields from a record
def load_record(row, columns):
    record = {}
    for column in columns:
        index = col_to_key(column["column"])
        if index < len(row):
            record[column["name"]] = row[index]

            # If a required row is empty, return a blank record.
            # Further code should validate records.
            if column.get("required", False) and not row[index]:
                logging.debug("load_record: column {} is required, but was empty. skipping record.".format(column["name"]))
                return {}

            # Include and exclude filters
            # If exclude filter exists and the row has a record
            if column.get("exclude", False) and row[index]:
                if row[index] in column.get("exclude"):
                    logging.debug("load_record: column {} cannot be {} (exclude filter). skipping record.".format(column["name"], row[index]))
                    return {}

            # If exclude filter exists and the row has a record
            if column.get("include", False) and row[index]:
                if row[index] not in column.get("include"):
                    logging.debug("load_record: column {} cannot be {} (include filter). skipping record.".format(column["name"], row[index]))
                    return {}

    return record


# Use the event template to populate info for the ical event.
def make_event(record, template):
    event = {}

    # Process general template substitution
    for field_name, field in template.items():
        event[field_name] = field
        for column, value in record.items():
            event[field_name] = event[field_name].replace("["+column+"]", value)

        if field_name is "summary":
            logging.debug("make_event: loading fields for event {}".format(event[field_name]))

    # Add ical event metadata
    if "dtstamp" not in event:
        logging.debug("make_event: adding dtstamp.")
        event["dtstamp"] = datetime.now()
    if "uid" not in event:
        logging.debug("make_event: adding uid.")
        m = hashlib.md5()
        unique = event["summary"] + event["dtstart"]
        m.update(unique.encode("utf-8"))
        event["uid"] = m.hexdigest()

    # Test for dates
    dtstart = dateparser.parse(event["dtstart"])
    dtend = dateparser.parse(event["dtend"])
    if not isinstance(dtstart, datetime.date) or not isinstance(dtend, datetime.date):
        logging.debug("make_event: dates could not be parsed for record: {}".format(json.dumps(record)))
        return {}

    # Convert dates
    event["dtstart"] = dtstart.date()
    dtend = dtend + timedelta(days = 1)
    event["dtend"] = dtend.date()

    return event


# Get the range of columns
def get_range(config):
    r = []
    for column in config["columns"]:
        r.append(column.get("column"))
    r.sort()
    # Range format is Sheet name + ! + column + row + : + column
    return "{}!{}{}:{}".format(config["sheetName"], r[0], config["startRow"], r[-1])


# Convert columns to indexes
# Caveat: does not support cols past Z (e.g. no AA, AB, etc).
def col_to_key(col):
    cols = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]
    return cols.index(col)


# Get the calendar marked by the endpoint
@app.route("/cal/<endpoint>")
def get_calendar(endpoint):
    # Load the config and get the google sheet.
    config = load_config(config_file, endpoint)
    col_range = get_range(config)
    sheet = load_sheet(creds_json, config["spreadsheetID"], col_range)

    # Set up the ical
    cal = icalendar.Calendar()
    cal.add("prodid", "-//github.com/jyee/sheets-to-ics//")
    cal.add("version", "2.0")

    # Add events
    for row in sheet:
        record = load_record(row, config["columns"])
        if not record:
            continue
        ev = make_event(record, config["event"])
        if not ev:
            continue

        event = icalendar.Event()
        for key, value in ev.items():
            event.add(key, value)
        cal.add_component(event)

    return cal.to_ical()

if __name__ == "__main__":
    app.run(host = "0.0.0.0")
