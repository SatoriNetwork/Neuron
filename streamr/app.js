const { StreamrClient } = require('streamr-client');
const http = require('http');

const hostname = '127.0.0.1';
const port = 3000;

const server = http.createServer((req, res) => {
  res.statusCode = 200;
  res.setHeader('Content-Type', 'text/plain');
  res.end('Hello World');
});

server.listen(port, hostname, () => {
  console.log(`Server running at http://${hostname}:${port}/`);
});

async function subscribeTest() {
    // not sensitive
    const privateKey = 'a8b2f15fa298f086e3fd80990bf0380184f90a7c9dce738dd3e3418e2892ff54'
    const streamr = new StreamrClient({
        auth: {
            privateKey: privateKey,
        },
    })
    //const streamId = 'binance-streamr.eth/ETHUSDT/ticker'
    //const streamId = 'streamr.eth/demos/twitter/sample'
    const streamId = 'streamr.eth/metrics/network/sec'
    const subscription = await streamr.subscribe({
        stream: streamId,
    },
    (message) => {
        // This function will be called when new messages occur
        //console.log(JSON.stringify(message))
        console.log(message)
    })
}
subscribeTest();

//That's odd! I'll try on a windows machine to double check. That same code works for me, the only thing I can think of is a Polygon RPC failure, but that should be in the logs.
//[1:15 AM]
//And make sure you're using "streamr-client": "^6.0.1" 
//@meta stack
//I switched to that streamr.eth/metrics/network/sec but I still cannot find a signal, though I can find peers now   Server running at http://127.0.0.1:3000/ INFO [2022-03-07T19:28:22.902] (TrackerConnector    ): Connected to tracker 0x05e7a0 INFO [2022-03-07T19:33:21.990] (WebRtcEndpoint      ): Successfully connected to 2 peers (0xBdf526,0xc87578), still trying to connect: 0xCA8742 (node:24364) UnhandledPromiseRejectionWarning: Error: NOT_FOUND: Stream not found: id=streamr.eth/metrics/network/sec     at Proxy.getStream (c:\repos\Satori\node\node_modules\streamr-client\src\StreamRegistry.js:189:19) (Use `node --trace-warnings ...` to show where the warning was created) (node:24364) UnhandledPromiseRejectionWarning: Unhandled promise rejection. This error originated either by throwing inside of an async function without a catch block, or by rejecting a promise which was not handled with .catch(). To terminate the node process on unhandled promise rejection, use the CLI flag `--unhandled-rejections=strict` (see https://nodejs.org/api/cli.html#cli_unhandled_rejections_mode). (rejection id: 57) (node:24364) [DEP0018] DeprecationWarning: Unhandled promise rejections are deprecated. In the future, promise rejections that are not handled will terminate the Node.js process with a non-zero exit code. INFO [2022-03-07T19:38:22.002] (WebRtcEndpoint      ): Successfully connected to 3 peers (0xBdf526,0xc87578,0x2BB046) (edited)
//Matthew | Streamr Network — 03/08/2022
//I'm informed that the Beta.3 contained this bug, so double underline the need for the latest stable streamr-client version!