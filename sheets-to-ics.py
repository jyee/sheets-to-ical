from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import datetime
import dateparser
from flask import Flask
import hashlib
import icalendar
import json
import os
import requests
import yaml

# Get env vars
config_file = os.environ.get("CONFIG_FILE", "config.yaml")

app = Flask(__name__)

# Load the config yaml
# TODO: Validate file, error handling.
# Cache the config as a global var.
# Note: the app will need to restart to load new configs
cache_config = []
def load_config(config_file, endpoint = False):
    global cache_config
    if not cache_config:
        cf = open(config_file, "r")
        config = yaml.safe_load(cf)
        cf.close()
        cache_config = config
    else:
        config = cache_config

    if endpoint:
        for cal in config:
            if cal["endpoint"] == endpoint:
                return cal

    # If not a specific endpoing, return an array of all configs
    return config


# Load the spreadsheet data
# TODO: Validate auth, error handling, etc
def load_sheet(secret_file, sheet_id, sheet_range):
    secret_file = os.path.join(os.getcwd(), secret_file)
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = service_account.Credentials.from_service_account_file(secret_file, scopes = scopes)

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

    # Add ical event metadata
    event["dtstamp"] = datetime.now()
    m = hashlib.md5()
    unique = event['summary'] + event['dtstart']
    m.update(unique.encode('utf-8'))
    event['uid'] = m.hexdigest()

    # Convert dates
    event["dtstart"] = dateparser.parse(event["dtstart"])
    event["dtend"] = dateparser.parse(event["dtend"])

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
    sheet = load_sheet(config["authJSONFile"], config["spreadsheetID"], col_range)

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

        event = icalendar.Event()
        for key, value in ev.items():
            event.add(key, value)
        cal.add_component(event)

    return cal.to_ical()

if __name__ == "__main__":
    app.run(host = "0.0.0.0", port = "5000")
