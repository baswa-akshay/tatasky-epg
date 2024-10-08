import os
import gzip
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from xml.etree import ElementTree as ET
from pytz import timezone

app = FastAPI()

# Function to download and extract the XML file
def download_and_extract_epg(url: str) -> str:
    gz_file = 'epg.xml.gz'
    xml_file = 'epg.xml'

    # Download the gzipped XML file
    response = requests.get(url)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to download the XML file")

    # Save the gzipped content to a file
    with open(gz_file, 'wb') as f:
        f.write(response.content)

    # Extract the .gz file
    with gzip.open(gz_file, 'rb') as f:
        with open(xml_file, 'wb') as out_f:
            out_f.write(f.read())
    
    return xml_file

# Function to convert time to IST
def convert_to_ist(time_str: str) -> str:
    naive_time = datetime.strptime(time_str, '%Y%m%d%H%M%S %z')
    ist_time = naive_time.astimezone(timezone('Asia/Kolkata'))
    return ist_time.strftime('%Y-%m-%d %H:%M:%S')

# Function to get current and upcoming program for a specific channel
@app.get("/api/epg")
async def get_current_and_upcoming_epg(id: str):
    channel_id = 'ts' + id

    # URL to the gzipped EPG XML file
    url = 'https://avkb.short.gy/tsepg.xml.gz'
    xml_file = download_and_extract_epg(url)

    # Load the XML file
    tree = ET.parse(xml_file)
    root = tree.getroot()

    current_time = datetime.now(timezone('Asia/Kolkata'))

    current_program = None
    next_program = None
    channel_info = None

    # Get channel information
    for channel in root.findall('channel'):
        if channel.get('id') == channel_id:
            channel_info = {
                'id': channel.get('id'),
                'name': channel.find('display-name').text,
                'icon': channel.find('icon').get('src')
            }
            break

    # Get program information
    programs = []
    for programme in root.findall('programme'):
        if programme.get('channel') == channel_id:
            start = convert_to_ist(programme.get('start'))
            stop = convert_to_ist(programme.get('stop'))
            start_time = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            stop_time = datetime.strptime(stop, '%Y-%m-%d %H:%M:%S')

            programs.append({
                'title': programme.find('title').text,
                'desc': programme.find('desc').text,
                'start': start,
                'stop': stop,
                'startTime': start_time,
                'stopTime': stop_time,
                'icon': programme.find('icon').get('src') if programme.find('icon') is not None else None
            })

    # Sort programs by start time
    programs.sort(key=lambda x: x['startTime'])

    # Find current and next program
    for index, program in enumerate(programs):
        if program['startTime'] <= current_time < program['stopTime']:
            current_program = program
            next_program = programs[index + 1] if index + 1 < len(programs) else None
            break

    # If no current program found, set next program to the first future program
    if not current_program:
        next_program = next((program for program in programs if program['startTime'] > current_time), None)

    return {
        'Channel': channel_info,
        'Current': current_program,
        'Upcoming': next_program
    }

