from scrapy import Request
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule, CrawlSpider, Spider
from urllib.parse import urlparse, parse_qs, urlencode
from amazonchecker.items import AmazonProductItem, FailedLinkItem
import re

class AmazonLinkCollector(Spider):
    name = 'amazon_spider'
    handle_httpstatus_list = [400, 403, 404, 406, 409, 410, 500, 501, 502, 503]


    def get_url(self, url):
        if not self.settings.get("SCRAPPER_API"):
            self.logger.info('Scrapper API key is not defined, processing amazon link without proxy %s', url)
            return url
        payload = {'api_key': self.settings.get("SCRAPPER_API"), 'url': url, 'country_code': 'us'}
        proxy_url = 'http://api.scraperapi.com/?' + urlencode(payload)
        self.logger.info('Sending request with proxy to %s', url)
        return proxy_url

    def is_amazon_product_page(self, url):
        return "amazon" in url and not "review" in url and self.asin_patten.search(url) and 'tag' in parse_qs(urlparse(url).query)
    
    def is_invalid_amazon(self, amazon_url):
        return "amazon" in amazon_url and any([deny in amazon_url for deny in ('review', "register", "signin", "/customer-preferences/", "forgot-password", "openid", "kdp.amazon", "aws.amazon", "your-account", "prime", "/gp/help/customer/")])

    def __init__(self, start_url=None, *args, **kwargs):
        super(AmazonLinkCollector, self).__init__(*args, **kwargs)
        self.start_urls = [start_url] if start_url is not None else ["https://streammentor.com/"]
        parts = urlparse(start_url)
        self.allowed_domains = ["api.scraperapi.com", "amazon.com", "merch.amazon.com", parts.netloc]
        self.asin_patten = re.compile('.*\/([a-zA-Z0-9]{10})(?:[/?]|$).*')
        self.amazon_extractor = LinkExtractor(deny=(r'review', r'openid', r"register", r"signin", r"\/customer-preferences\/", r"forgot-password", r"\/your-account", r"prime", r"\/gp\/help\/customer\/"),allow_domains=["amazon.com", "amazon.to", "amzn.to", "amzn", "amzn.com"], deny_domains=["merch.amazon.com", "affiliate-program.amazon.com","kdp.amazon.com", "aws.amazon.com"])
        self.regular_extractor = LinkExtractor(deny=(r'\/wp-admin\/'), allow_domains=[parts.netloc], deny_extensions=("webp", "jpg", "png", "gif") )

        # self.rules = (
        #     # Amazon Link Extractor
        #     Rule(LinkExtractor(deny=(r'review', r'openid', r"register", r"signin", r"\/customer-preferences\/", r"forgot-password", ),allow_domains=["merch.amazon.com", "amazon.com", "amazon.to", "amzn.to", "amzn", "amzn.com"], deny_domains=["kdp.amazon.com", "aws.amazon.com"]),
        #     callback='parse_amazon'),

        #     # Extract regular links
        #     Rule(LinkExtractor(allow_domains=[parts.netloc]), callback='parse_regular'),
        # )
        self.logger.info(f"Amazon Spider created with for url {start_url} with allowed domain {parts.netloc}")

    def is_site_link(self, url):
        return self.start_urls[-1] in url

    def is_icorrectly_cloaked(self, response):
        if not self.is_site_link(response.url):
            return False
        if "amazon.com" in response.xpath('//title/text()').extract_first().lower():
            print("title - ",response.xpath('//title/text()').extract_first().lower())
            print('Url - ', response.url)
            return True
        return False





    def parse(self, response):
        self.logger.info('Parse function called on %s', response.url)

        if self.is_invalid_amazon(response.url):
            return None

        # Check if the link is broken
        if response.status in range(400, 600):
            self.logger.error(f"FAILING status code encountered, saving\n\n")
            item = FailedLinkItem()
            item['status'] = response.status
            item['response']= response.url
            item['referer'] = response.request.headers.get('Referer', "")
            yield item
            return None
        if self.is_icorrectly_cloaked(response):
            self.logger.error(f"Icorrectly Cloaked Link, saving\n\n")
            item = FailedLinkItem()
            item['status'] = 'failing cloak'
            item['response']= response.url
            item['referer'] = response.request.headers.get('Referer', "")
            yield item
            return None

        self.logger.error(f"\n\n Link history for {response.url} {response.request.meta.get('redirect_urls')}\n\n")

        # redirect_history = response.request.meta.get('redirect_urls', [])

        # all_links = list(filter(self.is_amazon_product_page, redirect_history))

        # if redirect_history and all_links:
        #     amazon_link = all_links[0]
        #     self.logger.warning('AMAZON LINK WAS THERE %s but now its not :( %s\n\n', amazon_link, response.url)
        #     yield Request(url=self.get_url(amazon_link), callback=self.parse_amazon)
        #     return None
        

        # Check if the link redirects to Amazon.com
        if self.is_amazon_product_page(response.url):
            self.logger.warning('Current link is AMAZON, calling parse_amazon function... %s\n\n', response.url)
            yield self.parse_amazon(response)
            return None

        # return None
        #  Left From Regular Spider
        if self.is_site_link(response.url):
            self.logger.warning('Url is site link, collecting links to crawl %s\n\n', response.url)
            seen = set()

            # Parse Amazon Links
            amzn_links = [lnk for lnk in self.amazon_extractor.extract_links(response)
                        if lnk.url not in seen and not self.is_invalid_amazon(lnk.url)]    
            self.logger.info(f'\nExtracted {len(amzn_links)} amazon links from {response.url}\n')        
            for lnk in amzn_links:
                seen.add(lnk.url)
                if not self.is_amazon_product_page(lnk.url):
                    yield response.follow(lnk.url, callback=self.parse)
                else:
                    yield Request(url=self.get_url(lnk.url), callback=self.parse_amazon, meta={'orig_url': lnk.url})


            to_crawl = [lnk for lnk in self.regular_extractor.extract_links(response)
                        if lnk.url not in seen]
            self.logger.info(f'\nExtracted {len(to_crawl)} crawlable links from {response.url}\n')        
            for lnk in to_crawl:
                seen.add(lnk.url)
                # yield Request(url=self.get_url(lnk.url), callback=self.parse_amazon)
                yield response.follow(lnk.url, callback=self.parse)
        else:
            return None
        
    
    
    def parse_amazon(self, response):
        amazon_url = response.meta.get("orig_url", None)
        if not amazon_url:
            amazon_url = response.url

        self.logger.warning(f"\n\nParsing amazon product data from {amazon_url}\n\n")

        # Check if the link is broken
        item = AmazonProductItem()
        item['status'] = response.status
        item['response']= amazon_url
        item['referer'] = response.request.headers.get('Referer', "")
    
        
        if response.status in range(400, 600):
            self.logger.info(f"FAILING Amazon Link\n")
            yield item
        else:
            # Extract the tag query parameter from the URL
            q_params = parse_qs(urlparse(amazon_url).query)
            item["tag"] = q_params['tag'][0] if 'tag' in q_params and len(q_params['tag']) > 0 else ''
            
            if not item["tag"] and item['referer']:
                q_params = parse_qs(urlparse(item['referer']).query)
                item["tag"] = q_params['tag'][0] if 'tag' in q_params and len(q_params['tag']) > 0 else ''

                

            # Extaract ASIN 
            item["asin"] =  '' 
            if 'asin' in response.meta:
                item["asin"]= response.meta['asin']
            else:
                match = self.asin_patten.search(amazon_url)
                item["asin"] = match.group(1) if match else ""


            item["title"] = response.xpath('//*[@id="productTitle"]/text()').extract_first()
            try:
                item["image"] = re.search('"large":"(.*?)"',response.text).groups()[0]
            except (AttributeError, IndexError):
                item["image"] = ''
            item["rating"] = response.xpath('//*[@id="acrPopover"]/@title').extract_first()
            item["number_of_reviews"] = response.xpath('//*[@id="acrCustomerReviewText"]/text()').extract_first()
            item['available'] = response.xpath('//div[@id="availability"]/span//text()').extract_first()
            item["price"] = response.xpath('//*[@id="priceblock_ourprice"]/text()').extract_first()
            if not item["price"]:
                item["price"] = response.xpath('//*[@data-asin-price]/@data-asin-price').extract_first() or \
                        response.xpath('//*[@id="price_inside_buybox"]/text()').extract_first()
            
            item["bullet_points"] = response.xpath('//*[@id="feature-bullets"]//li/span/text()').extract()
            item["seller_rank"] = response.xpath('//*[text()="Amazon Best Sellers Rank:"]/parent::*//text()[not(parent::style)]').extract()
            
            yield item



    # def parse_regular(self, response):
    #     self.logger.info('Parse function called on %s', response.url)

    #     # Check if the link is broken
    #     if response.status in range(400, 600):
    #         self.logger.error(f"\n\nFAILING status code in regular link\n\n")
    #         item = AmazonProductItem()
    #         item['referer'] = str(response.request.headers.get('Referer', None))
    #         item['status'] = response.status
    #         item['response']= response.url
    #         return item

    #     redirect_statuses = (301, 302, 303, 307, 308)
        

    #     redirect_urls = response.request.meta.get('redirect_urls', None)


    #     # Hanlde Cloaked Amazon Links
    #     if redirect_urls is not None: # <== this is condition of redirection
    #         self.logger.info("\n\n\nWe have to REDIRECTED, current url-- %s\n\n\n", response.url)
    #         first_amazon_link = next((u for u in redirect_urls if self.is_amazon_product_page(u)), None)
    #         if first_amazon_link is not None:
    #             # Got Amazon 
    #             self.logger.info("\n\n\nFound AMAZON in redirects, following...\n\n\n")
    #             return self.parse_amazon(response)
                

    #     # Check if the link redirects to Amazon.com
    #     if self.is_amazon_product_page(response.url):
    #         self.logger.warning('AMAZON LINK %s\n\n', response.url)
    #         return self.parse_amazon(response)


    