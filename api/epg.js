// api/epg.js

const axios = require('axios');
const fs = require('fs');
const zlib = require('zlib');
const { parseStringPromise } = require('xml2js');

// Function to download and extract the XML file
async function downloadAndExtractEPG(url) {
    const gzFile = 'epg.xml.gz';
    const xmlFile = 'epg.xml';

    try {
        // Download the gzipped XML file
        const response = await axios.get(url, { responseType: 'arraybuffer' });
        fs.writeFileSync(gzFile, response.data);
        console.log('EPG file downloaded successfully.');
    } catch (error) {
        console.error('Error downloading the EPG:', error);
        throw new Error('Failed to download EPG file');
    }

    try {
        // Extract the gzipped file
        const xmlContents = zlib.gunzipSync(fs.readFileSync(gzFile));
        fs.writeFileSync(xmlFile, xmlContents);
        console.log('EPG file extracted successfully.');
    } catch (error) {
        console.error('Error extracting the EPG:', error);
        throw new Error('Failed to extract EPG file');
    }

    return xmlFile;
}

// Function to convert time to IST
function convertToIST(time) {
    const dateTime = new Date(`${time.slice(0, 8)}T${time.slice(8, 14)}+00:00`);
    return dateTime.toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
}

// Function to get the current and upcoming program for a specific channel
async function getCurrentAndUpcomingEPG(xmlFile, channelId) {
    const xmlData = fs.readFileSync(xmlFile);
    const result = await parseStringPromise(xmlData);

    const currentTime = new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' });
    const programs = [];

    // Get channel information
    const channelInfo = result.tv.channel.find(channel => channel.$.id === channelId);
    if (!channelInfo) {
        return null; // Channel not found
    }

    // Get program information
    for (const programme of result.tv.programme) {
        if (programme.$.channel === channelId) {
            const start = convertToIST(programme.$.start);
            const stop = convertToIST(programme.$.stop);
            programs.push({
                title: programme.title[0],
                desc: programme.desc[0],
                start: start,
                stop: stop,
                icon: programme.icon ? programme.icon[0].$.src : null,
                startTime: new Date(start),
                stopTime: new Date(stop),
            });
        }
    }

    // Sort programs by start time
    programs.sort((a, b) => a.startTime - b.startTime);

    const currentProgram = programs.find(program => program.startTime <= new Date(currentTime) && program.stopTime > new Date(currentTime));
    const nextProgram = currentProgram ? programs[programs.indexOf(currentProgram) + 1] : programs.find(program => program.startTime > new Date(currentTime));

    return {
        Channel: {
            id: channelInfo.$.id,
            name: channelInfo['display-name'][0],
            icon: channelInfo.icon ? channelInfo.icon[0].$.src : null,
        },
        Current: currentProgram,
        Upcoming: nextProgram
    };
}

// Main function to handle requests
module.exports = async (req, res) => {
    const channelId = req.query.id ? 'ts' + req.query.id : null;

    if (!channelId) {
        return res.status(400).json({ error: 'Channel ID is missing.' });
    }

    const url = 'https://avkb.short.gy/tsepg.xml.gz';

    try {
        console.log('Downloading and extracting EPG from URL:', url);
        const xmlFile = await downloadAndExtractEPG(url);
        console.log('EPG file downloaded and extracted:', xmlFile);
        
        const epgData = await getCurrentAndUpcomingEPG(xmlFile, channelId);
        console.log('EPG data retrieved:', epgData);

        // Clean up XML files after processing
        fs.unlinkSync(xmlFile);
        fs.unlinkSync('epg.xml.gz');

        res.setHeader('Content-Type', 'application/json');
        res.status(200).json(epgData);
    } catch (error) {
        console.error('Error occurred:', error);
        res.status(500).json({ error: 'An error occurred while processing the request.' });
    }
};
