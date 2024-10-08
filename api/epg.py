import requests
import gzip
import io
from fastapi import FastAPI, HTTPException
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET

app = FastAPI()

def download_and_extract_epg(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
        xml_contents = gz.read()
    return xml_contents

def convert_to_ist(time_str):
    dt = datetime.strptime(time_str, "%Y%m%d%H%M%S %z")
    ist = dt.astimezone(pytz.timezone('Asia/Kolkata'))
    return ist.strftime('%Y-%m-%d %H:%M:%S')

def get_current_and_upcoming_epg(xml_data, channel_id):
    xml_root = ET.fromstring(xml_data)
    current_time = datetime.now(pytz.timezone('Asia/Kolkata'))

    current_program = None
    next_program = None
    channel_info = None

    # Get channel information
    for channel in xml_root.findall("channel"):  # Make sure to use `findall`
        try:
            if channel.attrib['id'] == channel_id:
                channel_info = {
                    'id': channel.attrib['id'],
                    'name': channel.find("display-name").text,
                    'icon': channel.find("icon").attrib['src']
                }
                break
        except KeyError as e:
            print(f"KeyError: {e} for channel: {ET.tostring(channel)}")
            continue

    if channel_info is None:
        raise HTTPException(status_code=404, detail=f"Channel ID '{channel_id}' not found in EPG.")

    programs = []
    # Get program information
    for programme in xml_root.findall("programme"):
        if programme.attrib['channel'] == channel_id:
            start = convert_to_ist(programme.attrib['start'])
            stop = convert_to_ist(programme.attrib['stop'])
            start_time = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            stop_time = datetime.strptime(stop, '%Y-%m-%d %H:%M:%S')

            programs.append({
                'title': programme.find("title").text,
                'desc': programme.find("desc").text,
                'start': start,
                'stop': stop,
                'startTime': start_time,
                'stopTime': stop_time,
                'icon': programme.find("icon").attrib['src']
            })

    # Sort programs by start time
    programs.sort(key=lambda x: x['startTime'])

    # Find current and next program
    for index, program in enumerate(programs):
        if program['startTime'] <= current_time < program['stopTime']:
            current_program = program
            next_program = programs[index + 1] if index + 1 < len(programs) else None
            break

    if not current_program:  # If no current program found, find the next one
        for program in programs:
            if program['startTime'] > current_time:
                next_program = program
                break

    return {
        'Channel': channel_info,
        'Current': current_program,
        'Upcoming': next_program
    }

@app.get("/api/epg")
async def get_epg(id: int):
    channel_id = f'ts{id}'
    url = 'https://avkb.short.gy/tsepg.xml.gz'

    # Download and extract the XML data
    xml_data = download_and_extract_epg(url)

    # Get EPG data for the requested channel
    epg_data = get_current_and_upcoming_epg(xml_data, channel_id)

    return epg_data
