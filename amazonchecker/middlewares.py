# Define here the models for your spider middleware
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from scrapy import signals

# useful for handling different item types with a single interface
from itemadapter import is_item, ItemAdapter
from w3lib.url import safe_url_string


import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from scrapy import Request
from scrapy.downloadermiddlewares.httpproxy import HttpProxyMiddleware
from scrapy.downloadermiddlewares.redirect import _build_redirect_request, RedirectMiddleware
from scrapy.utils.response import response_status_message
from scrapy.exceptions import IgnoreRequest
import logging

class AmazoncheckerSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(s.item_scraped_callback, signal=signals.item_scraped)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def item_scraped_callback(self, item, response, spider):
        spider.logger.warning(f"IN SCRAPY!!!: Item {item} scraped from spider {spider}, url was {response.url}")

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)




class AmazonRedirectMiddleware(RedirectMiddleware):
    logger = logging.getLogger()

    def __init__(self, settings):
        super().__init__(settings)
        self.asin_pattern = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
    
    def is_amazon_product_page(self, url):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        return "amazon" in url and not "review" in url and self.asin_pattern.search(url) and 'tag' in query_params
    
    def process_response(self, request, response, spider):
        if (
            request.meta.get('dont_redirect', False)
            or response.status in getattr(spider, 'handle_httpstatus_list', [])
            or response.status in request.meta.get('handle_httpstatus_list', [])
            or request.meta.get('handle_httpstatus_all', False)
        ):
            return response

        allowed_status = (301, 302, 303, 307, 308)
        if 'Location' not in response.headers or response.status not in allowed_status:
            return response

        location = safe_url_string(response.headers['Location'])
        if response.headers['Location'].startswith(b'//'):
            request_scheme = urlparse(request.url).scheme
            location = request_scheme + '://' + location.lstrip('/')

        redirected_url = urljoin(request.url, location)

        self.logger.warning(f"Redirect url is {redirected_url}, is it amazon? - {self.is_amazon_product_page(redirected_url)}")
        if self.is_amazon_product_page(redirected_url):
            self.logger.warning('Encountered AMAZON LINK in redirect, parsing %s', redirected_url)
            return request.replace(url=spider.get_url(redirected_url),
                                    callback=spider.parse_amazon,
                                    meta={'orig_url': redirected_url},
                                    dont_filter=True)

        if response.status in (301, 307, 308) or request.method == 'HEAD':
            redirected = _build_redirect_request(request, url=redirected_url)
            return self._redirect(redirected, request, spider, response.status)

        redirected = self._redirect_request_using_get(request, redirected_url)
        return self._redirect(redirected, request, spider, response.status)