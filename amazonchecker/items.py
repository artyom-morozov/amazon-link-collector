# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
from scrapy.item import Item, Field

class AmazonProductItem(Item):
    referer =Field() # where the link is extracted
    response= Field() # url that was requested
    status = Field() # status code received
    asin = Field()
    title = Field()
    tag = Field()
    image = Field()
    rating = Field()
    number_of_reviews = Field()
    price = Field()
    bullet_points = Field()
    seller_rank = Field()


# class FailedLinkItem(Item):
#     referer =Field() # where the link is extracted
#     response= Field() # url that was requested
#     status = Field() # status code received

# class AmazonProductItem(scrapy.Item):
#     # define the fields for your item here like:
#     # name = scrapy.Field()
#     pass
