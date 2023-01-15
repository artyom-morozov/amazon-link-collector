from os import environ
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.
# Scrapy settings for amazonchecker project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# from dotenv import dotenv_values

BOT_NAME = 'amazonchecker'

SPIDER_MODULES = ['amazonchecker.spiders']
NEWSPIDER_MODULE = 'amazonchecker.spiders'


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'amazonchecker (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
CONCURRENT_REQUESTS = 5
RETRY_TIMES = 5

# Configure a delay for requests for the same website (default: 0)
# See https://docs.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
#DOWNLOAD_DELAY = 3
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
#COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
#DEFAULT_REQUEST_HEADERS = {
#   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
#   'Accept-Language': 'en',
#}

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
SPIDER_MIDDLEWARES = {
   'amazonchecker.middlewares.AmazoncheckerSpiderMiddleware': 543,
}

# Scrape Ops
DOWNLOADER_MIDDLEWARES = { 
    'amazonchecker.middlewares.AmazonRedirectMiddleware': 600,
    'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
}


# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
#EXTENSIONS = {
#    'scrapy.extensions.telnet.TelnetConsole': None,
#}

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
   'amazonchecker.pipelines.AmazonCheckerPipeline': 300,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 0.5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = True

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

# Set settings whose default value is deprecated to a future-proof value
# REQUEST_FINGERPRINTER_IMPLEMENTATION = '2.7'
# TWISTED_REACTOR = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'

LOG_FILE="scrapy-spider-%(id)s.log"
LOG_FILE_APPEND=False
LOG_ENABLED=True
LOG_LEVEL="DEBUG"
LOG_STDOUT = True

# Credentials
SCRAPPER_API = environ.get("SCRAPER_API_KEY", "")
AWS_S3_ACCESS_KEY_ID = environ.get("AWS_S3_ACCESS_KEY_ID", "")
AWS_S3_SECRET_ACCESS_KEY = environ.get("AWS_S3_SECRET_ACCESS_KEY", "")


# Store Items 
FEEDS = {
    's3://amzlinkcheck-crawler-data/scraping/feeds/%(name)s/%(start_url)s/%(id)s_%(time)s.json': {
        'format': 'json',
        'encoding': 'utf8',
        'indent': 4,
    },
}