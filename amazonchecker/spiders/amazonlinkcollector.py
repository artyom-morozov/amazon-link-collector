from scrapy import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule, CrawlSpider
from tldextract import extract
from urllib.parse import urlparse, parse_qs
from amazonchecker.items import AmazonProductItem 
import re
import json

class AmazonLinkCollector(CrawlSpider):
    name = 'amazon_spider'

    # Throttle crawl speed to prevent hitting site too hard
    custom_settings = {
        'CONCURRENT_REQUESTS': 2, # only 2 requests at the same time
        'DOWNLOAD_DELAY': 0.5 # delay between requests
    }

    # allowed_domains = []

    # Get all links on start url
    # rules = [  
        
    # ]\
    asin_patten = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
    start_urls = ["https://streammentor.com/"]
    allowed_domains = ["streammentor.com", "amazon.com", "merch.amazon.com"]
    rules = [  # Get all links on start url
        Rule(
            link_extractor=LinkExtractor(
                allow_domains='streammentor.com'
            ),
            follow=True,
            callback='parse',
        ),
        Rule(link_extractor=LinkExtractor(allow_domains='amazon.com'), callback='parse_amazon', follow=True),
    ]


    
    # def __init__(self, url=None, *args, **kwargs):
    #     super(AmazonLinkCollector, self).__init__(*args, **kwargs)
        
    #     self.asin_patten = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
        
    #     self.start_urls = [url]
        
    #     domain = '.'.join(urlparse(url).netloc.split('.')[-2:])
        
    #     self.allowed_domains = ("amazon.com", "merch.amazon.com", domain)
        
    #     self.rules = (
    #         Rule(
    #                 link_extractor=LinkExtractor(allow_domains=["merch.amazon.com", "amazon.com"], deny=r'^.*review.*$'), 
    #                 callback='parse_amazon', 
    #                 follow=True
    #             ),
    #         Rule(
    #                 link_extractor=LinkExtractor(
    #                     allow_domains=domain
    #                 ),
    #                 follow=True,
    #                 callback='parse_page',
    #             )
    #     )
            
        # self.no_reviews =  LinkExtractor(allow_domains=self.allowed_domains, deny=r'^.*review.*$')

        # self.rules = [
        #     Rule(
        #         link_extractor=self.no_reviews,
        #         callback="parse",
        #         follow=True,
        #         process_request='process_request',
        #     )
        # ]




    # def start_requests(self):
    #     yield Request(self.start_urls[0])
    # def parse_start_url(self, response):
    #     if response.status in (404,400,500):
    #         item = AmazonProductItem()
    #         item['referer'] = response.request.headers.get('Referer', None)
    #         item['status'] = response.status
    #         item['response']= response.url
    #         yield item
    #     if response.status in (301, 302) and 'amazon.com' in response.headers['Location']:
    #         return self.parse_amazon(response)
    #     pass

    def parse(self, request):
        self.logger.info('Parse function called on %s', request.url)
        # Check if the link is broken
        if request.status >= 400:
            item = AmazonProductItem()
            item['referer'] = request.headers.get('Referer', None)
            item['status'] = request.status
            item['response']= request.url
            yield item

        
        # Check if the link redirects to Amazon.com
        if ("amazon.com" in request.url and "review" not in request.url) or (request.status in (301, 302) and 'amazon.com' in request.headers['Location']):
            self.logger.warning('AMAZON LINK %s\n\n', request.url)
            return self.parse_amazon(request)
        
        for link in LinkExtractor(allow_domains=["merch.amazon.com", "amazon.com"], deny=r'^.*review.*$').extract_links(request):
            self.logger.warning('(1) Link extracted %s', link)
            yield Request(link.url, callback=self.parse_amazon)

        for link in LinkExtractor(allow_domains=self.allowed_domains[-1]).extract_links(request):
            self.logger.warning('(2) Link extracted %s', link)
            yield Request(link.url, callback=self.parse_page)
    
    
    # def parse_page(self, response):
    #     if response.status >= 400:
    #         item = AmazonProductItem()
    #         item['referer'] = response.request.headers.get('Referer', None)
    #         item['status'] = response.status
    #         item['response']= response.url
    #         yield item
    #     if response.status in (301, 302) and 'amazon.com' in response.headers['Location']:
    #         return self.parse_amazon(response)

    def parse_amazon(self, response):
        # Check if the link is broken
        if response.status in (404,400,500):
            item = AmazonProductItem()
            item['referer'] = response.request.headers.get('Referer', None)
            item['status'] = response.status
            item['response']= response.url
            yield item


        item = AmazonProductItem() 

        # Extract the tag query parameter from the URL
        q_params = parse_qs(urlparse(response.url).query)
        item["tag"] = q_params['tag'][0] if 'tag' in q_params and len(q_params['tag']) > 0 else ''
        
        # Extaract ASIN 
        item["asin"] =  '' 
        if 'asin' in response.meta:
            item["asin"]= response.meta['asin']
        else:
            match = self.asin_patten.search(response.url)
            item["asin"] = match.group(1) if match else ""


        item["title"] = response.xpath('//*[@id="productTitle"]/text()').extract_first()
        try:
            item["image"] = re.search('"large":"(.*?)"',response.text).groups()[0]
        except (AttributeError, IndexError):
            item["image"] = ''
        item["rating"] = response.xpath('//*[@id="acrPopover"]/@title').extract_first()
        item["number_of_reviews"] = response.xpath('//*[@id="acrCustomerReviewText"]/text()').extract_first()
        item["price"] = response.xpath('//*[@id="priceblock_ourprice"]/text()').extract_first()

        if not item["price"]:
            item["price"] = response.xpath('//*[@data-asin-price]/@data-asin-price').extract_first() or \
                    response.xpath('//*[@id="price_inside_buybox"]/text()').extract_first()
        
        item["bullet_points"] = response.xpath('//*[@id="feature-bullets"]//li/span/text()').extract()
        item["seller_rank"] = response.xpath('//*[text()="Amazon Best Sellers Rank:"]/parent::*//text()[not(parent::style)]').extract()
        
        yield item