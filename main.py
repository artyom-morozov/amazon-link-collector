from fastapi import FastAPI, WebSocket, Form
from fastapi.responses import HTMLResponse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

app = FastAPI()
process = CrawlerProcess(get_project_settings())

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>AmazonChecker</title>
    </head>
    <body>
        <h1>AmazonChecker API</h1>


        <form action="/crawl" method="post" onsubmit="startCrawl(event)">
            <label for="url">URL to crawl:</label><br>
            <input type="text" id="url" name="url"><br>
            <input type="submit" value="Submit">
        </form> 

        <table id="items">
            <thead>
                <tr>
                    <th>Image</th>
                    <th>Tag</th>
                    <th>Available</th>
                    <th>Title</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        </table>
        <script>
            function startCrawl(event) {
                event.preventDefault();
                var form = event.target;
                var url = form.elements.url.value;
                var ws = new WebSocket("ws://localhost:8000/crawl");
                ws.onopen = function() {
                    ws.send(url);
                };     
                ws.onmessage = function(event) {
                    var data = JSON.parse(event.data);
                    var tbody = document.getElementById('items').tBodies[0];
                    var row = tbody.insertRow();
                    var imageCell = row.insertCell();
                    imageCell.innerHTML = '<img src="' + data.image + '"/>';
                    var tagCell = row.insertCell();
                    tagCell.innerText = data.tag;
                    var availableCell = row.insertCell();
                    availableCell.innerText = data.available;
                    var titleCell = row.insertCell();
                    titleCell.innerText = data.title;
                };
            }
        </script>
    </body>
</html>
"""

@app.websocket("/crawl")
async def crawl(websocket: WebSocket):
    await websocket.accept()

    url = await websocket.receive_text()

    def item_callback(item):
        websocket.send_json(item)

    process.crawl('amazon_spider', start_url=url, item_callback=item_callback)
    process.start()
    await websocket.close()

@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")