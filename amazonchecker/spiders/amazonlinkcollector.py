from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule, CrawlSpider
from tldextract import extract
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

    start_urls = ["https://streammentor.com/"]
    allowed_domains = ["streammentor.com", "amazon.com", "merch.amazon.com"]
    rules = [  # Get all links on start url
        Rule(
            link_extractor=LinkExtractor(
                allow_domains='streammentor.com'
            ),
            follow=True,
            callback="parse_page",
        ),
        Rule(link_extractor=LinkExtractor(allow_domains='amazon.com'), callback='parse_amazon', follow=True),
    ]
    
    def parse_start_url(self, response):
        if response.status in (404,400,500):
            item = AmazonProductItem()
            item['referer'] = response.request.headers.get('Referer', None)
            item['status'] = response.status
            item['response']= response.url
            yield item
        if response.status in (301, 302) and 'amazon.com' in response.headers['Location']:
            return self.parse_amazon(response)
        pass

    def parse_amazon(self, response):
        
        report_if = (200, 404,400,500)
        # Check if the link is broken
        if response.status in report_if[0:]:
            item = AmazonProductItem()
            item['referer'] = response.request.headers.get('Referer', None)
            item['status'] = response.status
            item['response']= response.url
            yield item

        item = AmazonProductItem() 

        # Extract the tag query parameter from the URL
        item["tag"] = response.url.split('tag=')[1] if 'tag=' in response.url else None
        item["asin"] = response.meta['asin']
        item["title"] = response.xpath('//*[@id="productTitle"]/text()').extract_first()
        item["image"] = re.search('"large":"(.*?)"',response.text).groups()[0]
        item["rating"] = response.xpath('//*[@id="acrPopover"]/@title').extract_first()
        item["number_of_reviews"] = response.xpath('//*[@id="acrCustomerReviewText"]/text()').extract_first()
        item["price"] = response.xpath('//*[@id="priceblock_ourprice"]/text()').extract_first()

        if not item["price"]:
            item["price"] = response.xpath('//*[@data-asin-price]/@data-asin-price').extract_first() or \
                    response.xpath('//*[@id="price_inside_buybox"]/text()').extract_first()
        
        item["bullet_points"] = response.xpath('//*[@id="feature-bullets"]//li/span/text()').extract()
        item["seller_rank"] = response.xpath('//*[text()="Amazon Best Sellers Rank:"]/parent::*//text()[not(parent::style)]').extract()
        
        yield item