from datetime import datetime, timedelta
import operator
import itertools
import re
import os
import time
import tomlpython
import json
import logging
import arrow

from BeautifulSoup import BeautifulStoneSoup
import requests

project_directory = os.path.realpath(os.path.dirname(os.path.realpath(__file__)))
config_file_path = os.path.join(project_directory,  "config.toml")
log_file_path = os.path.join(project_directory,  "log", "everydayToggl.log")

# Set up logging
logger = logging.getLogger('everydayToggl')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(log_file_path)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
logger.addHandler(handler)


with open(config_file_path) as config_file:
     config = tomlpython.parse(config_file.read())
TIMESHEET_LOG_DIRECTORY = config['toggl']['timesheet_log_directory']

def create_new_entry(day, start_time, end_time, description):
    start_datetime = datetime.strptime(start_time.strip(), "%H:%M")
    end_datetime = datetime.strptime(end_time.strip(), "%H:%M")
    tz_aware_start = arrow.get(datetime(day.year, day.month, day.day, start_datetime.hour, start_datetime.minute), 'Australia/Melbourne')
    tz_aware_end = arrow.get(datetime(day.year, day.month, day.day, end_datetime.hour, end_datetime.minute), 'Australia/Melbourne')

    data = {
        'time_entry': {
            'description': description,
            'pid': config['toggl']['project_id'],
            'start': str(tz_aware_start),
            'duration': (tz_aware_end - tz_aware_start).seconds,
            'created_with': 'everydayToggl',
            'billable': True,
        }
    }
    response = requests.post('https://www.toggl.com/api/v8/time_entries', auth=(config['toggl']['toggl_api_key'], 'api_token'), json=data)
    logger.info(response.content)
    return response.content


def parse_time_entries_in_file(file_path):
    entries = []
    with open(file_path) as timesheet_log_file:
        lines = timesheet_log_file.readlines()
        for line in lines:
            matches = re.match('(?P<log_cruft>.*?> )s:(?P<start>.*? )e:(?P<end>.*? )(?P<description>.*)$', line)
            if matches:
                try:    
                    found_attributes = matches.groupdict()
                    for required_attribute in ['start', 'end', 'description']:
                        if not found_attributes.has_key(required_attribute):
                            raise AttributeError()
                        else:
                            if not found_attributes[required_attribute]:
                                raise AttributeError()
                except AttributeError as e:
                    logger.error("Found some but not all of 'start', 'end' and 'description' parts in the following line: {0} from file at {1}".format(line, file_path))
                else:
                    entries.append(matches.groupdict())
            else:
                logger.info("Could not parse 'start', 'end' and 'description' out of the following line: {0} from file at {1}".format(line, file_path))

    return entries

    
def togglify_time_entries_from_yesterday():
    yesterday =  datetime.today() - timedelta(days=1)
    # dirty hack to pad the month
    if yesterday.month < 10:
        month = '0{0}'.format(yesterday.month)
    else:
        month = yesterday.month

    filename = 'mytimesheets_{year}_{month}_{day}.log'.format(year=yesterday.year, month=month, day=yesterday.day)
    filepath = os.path.join(TIMESHEET_LOG_DIRECTORY, filename)

    time_entries = parse_time_entries_in_file(filepath)
    for entry in time_entries:
        create_new_entry(yesterday, entry['start'], entry['end'], entry['description'])
        
togglify_time_entries_from_yesterday()
