from scraper_models.ign_reviews_scraper import IgnReviewsScraper
from scraper_models.kotaku_reviews_scraper import KotakuReviewsScraper
# luego agregarán más:
# from .pcgamer_reviews_scraper import PcGamerReviewsScraper
# from .vandal_reviews_scraper import VandalReviewsScraper

def main():
    
    scrapers = [
        #IgnReviewsScraper(),
        KotakuReviewsScraper(max_pages=50),
        # PcGamerReviewsScraper(),
        # VandalReviewsScraper(),
    ]

    for scraper in scrapers:
        print(f"=== Ejecutando {scraper.source_name} ===")
        scraper.run()


if __name__ == "__main__":
    main()