from fastapi import FastAPI, Request, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
import crochet # <---
from scrapy import signals
from scrapy.signalmanager import dispatcher
from scrapy.crawler import CrawlerRunner
from scrapy.utils.project import get_project_settings
from scrapy.utils.log import configure_logging
from amazonchecker.spiders.amazonlinkcollector import AmazonLinkCollector
from dotenv import dotenv_values
from scrapy.utils.log import configure_logging
import uuid
from datetime import datetime
from starlette.exceptions import WebSocketException 
from fastapi.middleware.cors import CORSMiddleware
from websockets.exceptions import ConnectionClosedError
from collections import defaultdict
from urllib.parse import urlparse
from asyncio import sleep

origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000",
    "http://amzlinkcheck.com/",
    "http://amzlinkcheck.com/*"
]



config = dotenv_values('.env')  # take environment variables from .env.

crochet.setup()  # setting up crochet to execute

scrapy_settings = get_project_settings()
scrapy_settings.update({
    'COOKIES_ENABLED' : False,
    "LOG_ENABLED": True,
    "LOG_STDOUT" : False,
    "LOG_FILE_APPEND": True,
    "SCRAPPER_API": config["SCRAPER_API_KEY"]
})

# init the logger using setting
configure_logging(scrapy_settings)

CRAWL_RUNNER = CrawlerRunner(settings=scrapy_settings)  # initialize CrawlerRunner

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the crawling running as False
class SpiderStatusWithSocket:
    def __init__(self, websocket=None, running=False, items=[], crawled_links=0, date_started="", crawler_process=None, links=defaultdict(bool), finished=False):
        self.websocket: WebSocket = websocket
        self.running = running
        self.items = items
        self.crawled_links = crawled_links
        self.date_started = date_started
        self.crawler_process = crawler_process
        self.links = links
        self.finished = finished
    
    def transform_links(self):
        output = [] 
        for key in self.links.keys():
            output.append({"link": key, "crawled": self.links[key]})
        return output


    def to_json(self):
        return {
                "running": self.running, 
                "items": self.items, 
                "crawled_links": self.crawled_links,
                "date_started": self.date_started,
                # uncomment this when adding link processing
                # "links": self.transform_links(),
                "links": [],
                "finished": self.finished
            }

class ConnectionManager:
    def __init__(self):
        self.running_spiders = {}

    async def connect(self, websocket: WebSocket, spider_id: str):
        if spider_id not in self.running_spiders:
            raise Exception(f"Spider with ID {spider_id} does not exist")
        print(f"Spider with ID {spider_id} exists. It has {len(self.running_spiders[spider_id].items)}. Udating websocket...")
        await websocket.accept()
        self.running_spiders[spider_id].websocket = websocket

    def disconnect(self, spider_id):
        if not spider_id in self.running_spiders:
            raise Exception(f"Spider with ID {spider_id} does not exist") 
        self.running_spiders[spider_id].running = False
        self.running_spiders[spider_id].finished = True
        if not self.running_spiders[spider_id].crawler_process is None:
            print("Crawler process now --",self.running_spiders[spider_id].crawler_process)
            self.running_spiders[spider_id].crawler_process.cancel()
        del self.running_spiders[spider_id]
        print(f"Spider wit ID {spider_id} was deleted. Spiders now", self.running_spiders)

            

    async def disconnect_and_notify(self, spider_id):
        if not spider_id in self.running_spiders:
            raise Exception(f"Spider with ID {spider_id} does not exist") 
        print("Closing connection and notifying client")
        self.running_spiders[spider_id].running = False
        self.running_spiders[spider_id].finished = True
        if not self.running_spiders[spider_id].websocket is None:
            await self.running_spiders[spider_id].websocket.send_json(self.running_spiders[spider_id].to_json())
            await self.running_spiders[spider_id].websocket.close()
        if not self.running_spiders[spider_id].crawler_process is None:
            self.running_spiders[spider_id].crawler_process.cancel()
        del self.running_spiders[spider_id]
        print(f"Spider wit ID {spider_id} was deleted. Spiders now", self.running_spiders)

    async def disconnect_and_fail(self, spider_id):
        if not spider_id in self.running_spiders:
            raise Exception(f"Spider with ID {spider_id} does not exist") 
        print("Closing connection and notifying client with failure.")
        self.running_spiders[spider_id].running = False
        self.running_spiders[spider_id].finished = True

        if not self.running_spiders[spider_id].websocket is None:
            await self.running_spiders[spider_id].websocket.send_json({"failed": True})
            await self.running_spiders[spider_id].websocket.close()
        if not self.running_spiders[spider_id].crawler_process is None:
            self.running_spiders[spider_id].crawler_process.cancel()
        del self.running_spiders[spider_id]
        print(f"Spider wit ID {spider_id} was deleted. Spiders now", self.running_spiders)
            

    async def send_to_client(self, spider_id: str):
        if not spider_id in self.running_spiders:
            raise Exception(f"Spider with ID {spider_id} does not exist") 
        if self.running_spiders[spider_id].websocket is None:
            raise Exception(f"Spider with ID {spider_id} does not have a websocket opened")
        await self.running_spiders[spider_id].websocket.send_json(self.running_spiders[spider_id].to_json())
            


manager = ConnectionManager()



@app.websocket("/ws/{spider_id}")
async def websocket_endpoint(websocket: WebSocket, spider_id: str):
    print("Received connection for spider with id", spider_id)
    try:
        await manager.connect(websocket, spider_id)
        
        # if spider is not running sleep and retry 10 times
        for i in range(10):
            if manager.running_spiders[spider_id].running:
                break
            print(f"Spider Crawling process did not start. Retrying ({i+1}/10)...")
            if i == 9:
                await manager.disconnect_and_fail(spider_id)
            await sleep(1)

        
        # Run loop until spider is finished or is not running
        while manager.running_spiders[spider_id].running is True and manager.running_spiders[spider_id].finished is False:
            await manager.send_to_client(spider_id)
            await sleep(1)
        
        print("Spider Crawler 'run' process stoped. Closing websocket...")
        
        await manager.disconnect_and_notify(spider_id)
    
    except (WebSocketException, ConnectionClosedError, WebSocketDisconnect) as e:
        print("Websocket Disconnected Error", e)
        print("Process", CRAWL_RUNNER.crawlers)
        manager.disconnect(spider_id)
        stop_crawler(spider_id)
    
    except Exception as e:
        print("Unknown Websocket Error", e)
        manager.disconnect(spider_id)
        stop_crawler(spider_id)



    
        

def started_scrape(spider):
    if spider.id and spider.id in manager.running_spiders:
        print(f'Spider with id {spider.id} started crawling')
        manager.running_spiders[spider.id].running = True
        manager.running_spiders[spider.id].date_started = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# Function to be called when spider finishes scraping
def finished_scrape(spider, *args, **kwargs):
    print(f'Spider with id {spider.id} finished crawling')
    if spider.id and spider.id in manager.running_spiders:
        print("stoping everything")
        manager.running_spiders[spider.id].running = False
        manager.running_spiders[spider.id].finished = True

# Function to be called when a new item is scraped
def item_scraped_callback(item, response, spider):
    if spider.id and spider.id in manager.running_spiders and manager.running_spiders[spider.id].running and not manager.running_spiders[spider.id].finished:
        manager.running_spiders[spider.id].items.append(dict(item))

# TODO: activate this if you want to see scheduled links
# def link_scheduled(request, spider):
#     running_spiders[spider.id].crawled_links += 1
    # running_spiders[spider.id].links[request.url] = False

def link_crawled(response, request, spider):
    if spider.id and spider.id in manager.running_spiders and manager.running_spiders[spider.id].running and not manager.running_spiders[spider.id].finished:
        manager.running_spiders[spider.id].crawled_links += 1
        manager.running_spiders[spider.id].links[request.url] = True

@crochet.run_in_reactor
def stop_crawler(spider_id):
    for c in list(CRAWL_RUNNER.crawlers):
        print("Crawler in Crawlr runner - ", c)
        if c.spider and c.spider.id and c.spider.id == spider_id:
            c.engine.close_spider(spider=c.spider, reason='disconnect')




@crochet.run_in_reactor
def crawl_with_crochet(url, spider_id):
    dispatcher.connect(started_scrape, signal=signals.spider_opened)
    
    # Connect the item_scraped signal to the item_scraped function
    dispatcher.connect(item_scraped_callback, signal=signals.item_scraped)

    # TODO: activate this for Scheduled Links Processing
    # dispatcher.connect(link_scheduled, signal=signals.request_scheduled)    
    
    # Connect the response_downloaded signal to the link_crawled function
    dispatcher.connect(link_crawled, signal=signals.response_downloaded)


    # Connect the spider_closed signal to the finished_scrape function
    dispatcher.connect(finished_scrape, signal=signals.spider_closed)

    
    eventual = CRAWL_RUNNER.crawl(AmazonLinkCollector, start_url=url, spider_id=spider_id)

    return eventual


@app.post("/start_crawl")
async def start_spider(request: Request, url: str = Form(...)):
    print("Got Url from client", url)

    new_spider_id = str(uuid.uuid4())
    try:
        # check if url is valid
        result = urlparse(url)
        if not bool(result.scheme and result.netloc):
            raise ValueError("Invalid URL")
        manager.running_spiders[new_spider_id] = SpiderStatusWithSocket(websocket=None, running=False, items=[], crawled_links=0, date_started="", crawler_process=None, links={}, finished=False)
        manager.running_spiders[new_spider_id].crawler_process = crawl_with_crochet(url, spider_id=new_spider_id)
        print(f"Created new spider for id {new_spider_id}. It has {len(manager.running_spiders[new_spider_id].items)} items.")
    except ValueError as e:
        # return a Bad Request if the link is not valid
        return JSONResponse(content={"Invalid URL provided": str(e)}, status_code=400)
    return {"spider_id": new_spider_id}