import requests
import gzip
import io
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import pytz
import xml.etree.ElementTree as ET

app = FastAPI()

# Allow CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)

def download_and_extract_epg(url):
    response = requests.get(url)
    response.raise_for_status()  # Raise an error for bad responses
    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
        xml_contents = gz.read()
    return xml_contents

def convert_to_ist(time_str):
    dt = datetime.strptime(time_str, "%Y%m%d%H%M%S %z")
    return dt.astimezone(pytz.timezone('Asia/Kolkata'))

def format_datetime(dt):
    """Convert datetime to string in a specific format."""
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def get_current_and_upcoming_epg(xml_data, channel_id):
    xml_root = ET.fromstring(xml_data)
    current_time = datetime.now(pytz.timezone('Asia/Kolkata'))

    current_program = None
    next_program = None
    channel_info = None

    # Get channel information
    for channel in xml_root.findall("channel"):
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
            start_time = convert_to_ist(programme.attrib['start'])
            stop_time = convert_to_ist(programme.attrib['stop'])

            programs.append({
                'title': programme.find("title").text if programme.find("title") is not None else "N/A",
                'desc': programme.find("desc").text if programme.find("desc") is not None else "N/A",
                'start': format_datetime(start_time),  # Convert to string
                'stop': format_datetime(stop_time),    # Convert to string
                'icon': programme.find("icon").attrib['src'] if programme.find("icon") is not None else None
            })

    # Sort programs by start time
    programs.sort(key=lambda x: x['start'])

    # Find current and next program
    for index, program in enumerate(programs):
        # Compare string representations of time
        if program['start'] <= format_datetime(current_time) < program['stop']:
            current_program = program
            next_program = programs[index + 1] if index + 1 < len(programs) else None
            break

    if not current_program:  # If no current program found, find the next one
        for program in programs:
            if program['start'] > format_datetime(current_time):
                next_program = program
                break

    return {
        'Channel': channel_info,
        'Current': current_program,
        'Upcoming': next_program
    }

@app.get("/", response_class=HTMLResponse)
async def read_root():
    content = """
    <html>
        <head>
            <title>EPG API Documentation</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 20px;
                    background-color: #f4f4f4;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }
                h1 {
                    color: #333;
                }
                h2 {
                    color: #666;
                }
                ul {
                    list-style-type: none;
                    padding-left: 0;
                }
                li {
                    margin: 10px 0;
                }
                code {
                    background-color: #eee;
                    padding: 2px 4px;
                    border-radius: 4px;
                }
                pre {
                    background-color: #eee;
                    padding: 10px;
                    border-radius: 4px;
                    overflow: auto;
                }
            </style>
        </head>
        <body>
            <h1>EPG API</h1>
            <p>Welcome to the EPG API. Use the following endpoints:</p>
            <h2>Available Endpoints</h2>
            <ul>
                <li><strong>/epg?id={channel_id}</strong> - Get the current and upcoming programs for the specified channel.</li>
            </ul>
            <h2>Example Usage</h2>
            <p>To get the EPG for channel ID <code>114</code>, make a GET request to:</p>
            <pre><code>GET /epg?id=114</code></pre>
        </body>
    </html>
    """
    return HTMLResponse(content=content)

@app.get("/api/epg")
async def get_epg(id: int):
    channel_id = f'ts{id}'
    url = 'https://avkb.short.gy/tsepg.xml.gz'

    # Download and extract the XML data
    xml_data = download_and_extract_epg(url)

    # Get EPG data for the requested channel
    epg_data = get_current_and_upcoming_epg(xml_data, channel_id)

    # Return pretty-printed JSON response using jsonable_encoder
    return JSONResponse(content=jsonable_encoder(epg_data), media_type="application/json")
