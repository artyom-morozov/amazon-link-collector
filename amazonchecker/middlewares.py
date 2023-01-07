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


class AmazonCollectorRedirectMiddleware(RedirectMiddleware):
    def process_response(self, request, response, spider):
        if request.meta.get('dont_redirect', False):
            return response

        if response.status in (301, 302, 303, 307, 308):
            new_url = safe_url_string(response.headers['Location'])
            self.logger.info('Redirecting to %s', new_url)
            if spider.is_amazon_product_page(new_url):
                self.logger.warning('Encountered AMAZON LINK in redirect, parsing %s', new_url)
                return request.replace(url=spider.get_url(new_url),
                                      callback=spider.parse_amazon,
                                      meta={'orig_url': new_url},
                                      dont_filter=True)
            else:
                # Ignore the redirect if it is not an Amazon product page
                raise IgnoreRequest()
        else:
            return response

class AmazonProductMiddleware(HttpProxyMiddleware):
    asin_pattern = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
    logger = logging.getLogger()
    SCRAPPER_API = ''
    


    def is_amazon_product_page(self, url):
        return "amazon" in url and not "review" in url and self.asin_pattern.search(url) and 'tag' in parse_qs(urlparse(url).query)

    def get_url(self, url):
        if not self.SCRAPPER_API:
            self.logger.info('Scrapper API key is not defined, processing amazon link without proxy %s', url)
            return url
        payload = {'api_key': self.SCRAPPER_API, 'url': url, 'country_code': 'us'}
        proxy_url = 'http://api.scraperapi.com/?' + urlencode(payload)
        return proxy_url

    def process_request(self, request, spider):
        if self.is_amazon_product_page(request.url):
            self.SCRAPPER_API = spider.settings.get("SCRAPPER_API", "")
            self.logger.warning("\n\nSending AMAZON link through Scrapper API %s\n\n", request.url)
            request.replace(url=self.get_url(request.url))
        else:
            self.logger.warning("\n\nNot using Scrapper for -> %s\n\n", request.url)
        return None





class AmazonRedirectMiddleware(RedirectMiddleware):
    logger = logging.getLogger()

    def __init__(self, settings):
        super().__init__(settings)
        self.asin_pattern = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
    
    def is_amazon_product_page(self, url):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        return "amazon" in url and not "review" in url and self.asin_pattern.search(url) and 'tag' in query_params
    
    # def get_url(self, url):
    #     if not self.settings.get("SCRAPPER_API", ""):
    #         self.logger.info('Scrapper API key is not defined, processing amazon link without proxy %s', url)
    #         return url
    #     payload = {'api_key': self.settings.get("SCRAPPER_API"), 'url': url, 'country_code': 'us'}
    #     proxy_url = 'http://api.scraperapi.com/?' + urlencode(payload)
    #     return proxy_url
    
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
        # else:
        #     # Ignore the redirect if it is not an Amazon product page
        #     raise IgnoreRequest()

        if response.status in (301, 307, 308) or request.method == 'HEAD':
            redirected = _build_redirect_request(request, url=redirected_url)
            return self._redirect(redirected, request, spider, response.status)

        redirected = self._redirect_request_using_get(request, redirected_url)
        return self._redirect(redirected, request, spider, response.status)
        # # Check if the response is a redirect
        # if response.status in (301, 302, 303, 307, 308):
        #     redirect_url = response.headers['Location']
        #     # Check if the redirect url is an Amazon product page
        #     if self.is_amazon_product_page(redirect_url):
        #         # Build a new request using the proxy url
        #         new_request = Request(self.get_url(redirect_url))
        #         # Set the meta data of the new request to match the original request
        #         new_request.meta.update(request.meta)
        #         return new_request
        # # Return the response as-is if it is not a redirect or the redirect url is not an Amazon product page
        # return response


class AmazoncheckerSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
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

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)


class AmazoncheckerDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info('Spider opened: %s' % spider.name)
