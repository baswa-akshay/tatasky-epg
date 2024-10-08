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
        raise HTTPException(status_code=404, detail={"error": {"code": "404", "message": "Channel not found."}})

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

    # Return channel info with null for Current and Upcoming if not found
    return {
        'Channel': channel_info,
        'Current': current_program if current_program else None,
        'Upcoming': next_program if next_program else None
    }

@app.get("/", response_class=HTMLResponse)
async def read_root():
    content = """
    <!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EPG API Documentation</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f4f4f9;
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
        }
        h1 {
            font-size: 2.5em;
            color: #333;
        }
        h2 {
            font-size: 1.5em;
            color: #555;
            margin-top: 1.5em;
        }
        p {
            font-size: 1.1em;
            color: #666;
        }
        ul {
            padding-left: 20px;
        }
        li {
            margin-bottom: 10px;
        }
        code, pre {
            background-color: #eaeaea;
            padding: 10px;
            border-radius: 5px;
            font-size: 0.95em;
            display: block;
            margin: 10px 0;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        a {
            color: #007bff;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        footer {
            margin-top: 30px;
            font-size: 0.85em;
            text-align: center;
            color: #888;
        }
    </style>
</head>
<body>

<div class="container">
    <h1>EPG API Documentation</h1>
    <p>Welcome to the EPG API! This documentation will guide you on how to use the API to retrieve Electronic Program Guide (EPG) data for TV channels.</p>

    <h2>Endpoints</h2>
    <ul>
        <li><strong>GET /api/epg?id={channel_id}</strong> - Retrieve current and upcoming programs for a specific channel.</li>
    </ul>

    <h2>Example Usage</h2>
    <p>To get the EPG for a channel with ID <code>114</code>, you would use the following request:</p>
    <pre>GET https://tatasky-epg.vercel.app/api/epg?id=114</pre>

    <h2>Sample Response</h2>
    <p>The response will be in JSON format. Here’s a sample response:</p>
    <pre>
{
  "Channel": {
    "id": "114",
    "name": "National Geographic",
    "icon": "https://example.com/natgeo.png"
  },
  "Current": {
    "title": "Wildlife Explorer",
    "desc": "Join the host as they venture into the wild to explore amazing wildlife around the globe.",
    "start": "2024-10-08 10:00:00",
    "stop": "2024-10-08 11:00:00",
    "icon": "https://example.com/current-show.png"
  },
  "Upcoming": {
    "title": "Secrets of the Ocean",
    "desc": "Explore the mysteries of the deep ocean with experts in marine biology and oceanography.",
    "start": "2024-10-08 11:00:00",
    "stop": "2024-10-08 12:00:00",
    "icon": "https://example.com/upcoming-show.png"
  }
}
    </pre>

    <h2>Using the API</h2>

    <h3>Python Example</h3>
    <pre>
import requests

url = "https://tatasky-epg.vercel.app/api/epg?id=114"
response = requests.get(url)
if response.status_code == 200:
    data = response.json()
    print("Channel:", data['Channel']['name'])
    print("Current Show:", data['Current']['title'])
else:
    print("Failed to retrieve data")
    </pre>

    <h3>PHP Example</h3>
    <pre>
<?php
$url = "https://tatasky-epg.vercel.app/api/epg?id=114";
$response = file_get_contents($url);
if ($response !== FALSE) {
    $data = json_decode($response, true);
    echo "Channel: " . $data['Channel']['name'] . "\n";
    echo "Current Show: " . $data['Current']['title'] . "\n";
} else {
    echo "Failed to retrieve data";
}
?>
    </pre>

    <h3>JavaScript (Node.js) Example</h3>
    <pre>
const https = require('https');

const url = 'https://tatasky-epg.vercel.app/api/epg?id=114';

https.get(url, (res) => {
  let data = '';

  res.on('data', (chunk) => {
    data += chunk;
  });

  res.on('end', () => {
    const epgData = JSON.parse(data);
    console.log("Channel:", epgData.Channel.name);
    console.log("Current Show:", epgData.Current.title);
  });
}).on("error", (err) => {
  console.log("Error: " + err.message);
});
    </pre>

    <h2>Error Handling</h2>
    <p>If the channel ID is not found, you’ll get a 404 error like this:</p>
    <pre>
{
    "error": {
        "code": "404",
        "message": "Channel not found."
    }
}
    </pre>

    <h2>Additional Information</h2>
    <p>No rate limiting is applied for this API. You can make as many requests as needed. Ensure that you use valid <code>channel_id</code> values for accurate results.</p>

    <h2>Contact</h2>
    <p>If you encounter any issues or have questions, please reach out to our support team at <a href="mailto:support@example.com">support@example.com</a>.</p>

    <footer>
        © 2024 EPG API - All rights reserved.
    </footer>
</div>

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
    try:
        epg_data = get_current_and_upcoming_epg(xml_data, channel_id)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content=e.detail)

    # Return pretty-printed JSON response using jsonable_encoder
    return JSONResponse(content=jsonable_encoder(epg_data), media_type="application/json")
            
