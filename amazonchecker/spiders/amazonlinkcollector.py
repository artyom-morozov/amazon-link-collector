from scrapy import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule, CrawlSpider, Spider
from urllib.parse import urlparse, parse_qs, urlencode
from amazonchecker.items import AmazonProductItem 
import re
# from dotenv import dotenv_values
API = ""
# use Scrapper API for requests
def get_url(url):
    payload = {'api_key': API, 'url': url, 'country_code': 'us'}
    proxy_url = 'http://api.scraperapi.com/?' + urlencode(payload)
    return proxy_url


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

    amazonExtractor = LinkExtractor(allow_domains=["merch.amazon", "amazon"], deny_domains=["kdp.amazon.com", "aws.amazon.com"], restrict_text=['review', "register", "signin", "/customer-preferences/", "forgot-password"])

    asin_patten = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
    start_urls = ["https://streammentor.com/streaming-equipment/#headphones"]
    allowed_domains = ["amazon.com", "merch.amazon.com", "streammentor.com"]
    
    rules = [  # Get all links on start url
        Rule(
            link_extractor=LinkExtractor(
                allow_domains='streammentor.com'
            ),
            follow=True,
            callback="parse_regular"
        ),
        Rule(
            link_extractor=amazonExtractor,
            follow=True,
            callback="parse_amazon"
        ),
    ]
    
    def is_amazon_product_page(self, url):
        return "amazon" in url and not "review" in url and self.asin_patten.search(url) and 'tag' in parse_qs(urlparse(url).query)

    
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

    def parse_regular(self, response):
        self.logger.info('Parse function called on %s', response.url)


        if response.status in (301, 302):
            self.logger.info('\n\n\nRedirect is HAPPENING %s\n\n\n', response)

        redirect_statuses = (301, 302, 303, 307, 308)
        

        redirect_urls = response.request.meta.get('redirect_urls', None)


        # Hanlde Cloaked Amazon Links
        if (response.status in redirect_statuses or 'Location' in response.headers) and redirect_urls is not None: # <== this is condition of redirection
            self.logger.info(f"\n\n\nWe're about to REDIRECT, current url--\n\n\n", response.url)
            first_amazon_link = next((u for u in redirect_urls if self.is_amazon_product_page(u)), None)
            if first_amazon_link is not None:
                # Got Amazon 
                self.logger.info("\n\n\nFound AMAZON in redirects, following...\n\n\n")
                yield Request(url=first_amazon_link, callback=self.parse_amazon)
                

        # Check if the link is broken
        if response.status in range(400, 600):
            self.logger.error(f"\n\nFAILING status code in regular link\n\n")
            item = AmazonProductItem()
            item['referer'] = response.request.headers.get('Referer', None)
            item['status'] = response.status
            item['response']= response.url
            yield item

        
        # Check if the link redirects to Amazon.com
        if self.is_amazon_product_page(response.url):
            self.logger.warning('AMAZON LINK %s\n\n', response.url)
            yield self.parse_amazon(response)
        
        # Extract Amazon Links and Process
        # for link in self.amazonExtractor.extract_links(response):
        #     self.logger.warning('(1) New Amazon Link extracted %s', link)
        #     yield Request(url=get_url(link.url), callback=self.parse_amazon)
        #     # yield Request(link.url, callback=self.parse_amazon)

        # for link in LinkExtractor(allow_domains=self.allowed_domains[-1]).extract_links(response):
        #     # self.logger.warning('(2) Regular Link extracted %s', link)
        #     yield Request(url=link.url, callback=self.parse)


    def parse_amazon(self, response):
        self.logger.warning(f"\n\nParsing amazon link {response.url}\n\n")

        # Check if the link is broken
        item = AmazonProductItem()
        item['referer'] = response.request.headers.get('Referer', None)
        item['status'] = response.status
        item['response']= response.url
        
        if response.status in range(400, 600):
            self.logger.info(f"\n\nFAILING status cde in Amazon Link\n\n")
            yield item

        # Extract the tag query parameter from the URL
        q_params = parse_qs(urlparse(response.url).query)
        item["tag"] = q_params['tag'][0] if 'tag' in q_params and len(q_params['tag']) > 0 else ''
        
        if not item["tag"] and item['referer']:
            q_params = parse_qs(urlparse(item['referer']).query)
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