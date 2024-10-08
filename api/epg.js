// Enable error handling
process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
});
process.on('unhandledRejection', (reason) => {
    console.error('Unhandled Rejection:', reason);
});

// Import required modules
const https = require('https');
const fs = require('fs');
const zlib = require('zlib');
const { parseStringPromise } = require('xml2js');

// Function to download and extract the XML file
function downloadAndExtractEPG(url) {
    return new Promise((resolve, reject) => {
        const gzFile = 'epg.xml.gz';
        const xmlFile = 'epg.xml';

        const file = fs.createWriteStream(gzFile);
        https.get(url, (response) => {
            response.pipe(file);
            file.on('finish', () => {
                file.close(() => {
                    // Extract the .gz file
                    fs.createReadStream(gzFile)
                        .pipe(zlib.createGunzip())
                        .pipe(fs.createWriteStream(xmlFile))
                        .on('finish', () => {
                            resolve(xmlFile);
                        })
                        .on('error', (err) => reject(err));
                });
            });
        }).on('error', (err) => {
            fs.unlink(gzFile); // Delete the file async. (if error)
            reject(err);
        });
    });
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

// Main script logic to handle requests
async function handleRequest(req, res) {
    const url = 'https://avkb.short.gy/tsepg.xml.gz';
    const channelId = req.query.id ? 'ts' + req.query.id : null;

    if (!channelId) {
        return res.status(400).json({ error: 'Channel ID is missing.' });
    }

    try {
        // Download and extract the XML file (no caching, always get the latest)
        const xmlFile = await downloadAndExtractEPG(url);

        // Get the current and upcoming EPG data for the requested channel
        const epgData = await getCurrentAndUpcomingEPG(xmlFile, channelId);

        // Clean up XML files after processing
        fs.unlinkSync(xmlFile); // Remove the XML file after use
        fs.unlinkSync('epg.xml.gz'); // Remove the gzipped file after use

        res.setHeader('Content-Type', 'application/json');
        res.status(200).json(epgData);
    } catch (error) {
        console.error(error);
        res.status(500).json({ error: 'An error occurred while processing the request.' });
    }
}

// Example usage (HTTP server simulation)
// You can replace this with your actual server logic
const http = require('http');
const url = require('url');

const server = http.createServer((req, res) => {
    const query = url.parse(req.url, true).query;
    if (req.method === 'GET' && req.url.startsWith('/epg')) {
        handleRequest({ query }, res);
    } else {
        res.statusCode = 404;
        res.end('Not Found');
    }
});

server.listen(3000, () => {
    console.log('Server is listening on port 3000');
});
                
