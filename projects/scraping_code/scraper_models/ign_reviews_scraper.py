# scraping/ign_reviews_scraper.py

from datetime import datetime
from playwright.sync_api import Page

from base.base_scraper import BaseNewsScraper
from base.base_models import Article


class IgnReviewsScraper(BaseNewsScraper):
    """
    Scraper para game reviews de IGN:
    https://www.ign.com/reviews/games
    """
    source_name = "IGN-Reviews"

    # Punto de entrada: listado de reviews de juegos
    start_urls = [
        "https://www.ign.com/reviews/games",
    ]

    BASE_URL = "https://www.ign.com"

    # ------------ Helpers específicos de IGN ------------

    def normalize_url(self, url: str) -> str:
        # IGN suele usar URLs absolutas, pero por si acaso:
        if url.startswith("/"):
            return self.BASE_URL + url
        return url

    def extract_article_links(self, page: Page):
        """
        Aquí obtienes los links a CADA review individual desde el listado.

        PASO QUE HARÁS A MANO:
        - Abre https://www.ign.com/reviews/games
        - F12 → Inspector
        - Mira el HTML de una tarjeta de review
        - Encuentra el <a> que lleva al review
        - Construye un selector CSS que lo capture
        """
        # EJEMPLO / PLANTILLA:
        CARD_LINK_SELECTOR = "a.item-body[data-cy='item-body']"  # Esto hay que buscar en cada pagina con F12 y ver el DOM

        cards = page.locator(CARD_LINK_SELECTOR)
        count = cards.count()
        print(f"[{self.source_name}] Encontradas {count} tarjetas de review en el listado.")

        for i in range(count):
            card = cards.nth(i) #Extrae el titulo
            href = card.get_attribute("href")
            if not href:
                continue
            yield href

    def extract_article_data(self, page: Page, url: str) -> Article | None:
        """
        Extrae título, fecha y cuerpo del review desde la página individual.
        Contenedor principal:
          <div data-cy="article-content" class="... article-content page-0">
        Párrafos:
          <p data-cy="paragraph" class="paragraph ...">...</p>
        """
        # --- título ---
        try:
            # Normalmente el título es un <h1> principal
            title = page.locator("h1").inner_text().strip()
        except Exception:
            print(f"[{self.source_name}] No se pudo obtener título para {url}")
            return None

        # --- fecha de publicación ---
        published_at = None
        try:
            # Muchas webs usan meta "article:published_time"
            meta = page.locator('meta[property="article:published_time"]')
            if meta.count() > 0:
                published_at = meta.first.get_attribute("content")
        except Exception:
            pass

        if not published_at:
            published_at = datetime.now(datetime.timezone.utc).isoformat()

        # --- cuerpo del review ---
        # Aquí también tienes que mirar el DOM:
        #   - qué contenedor envuelve el texto del review
        #   - de ahí puedes sacar todos los <p>
        # <div data-cy="article-content" ...>
        # EJEMPLO / PLANTILLA:

        content_container = page.locator("div[data-cy='article-content']")
        if content_container.count() == 0:
            print(f"[{self.source_name}] No se encontró article-content para {url}")
            return None
        
        paragraphs = content_container.locator("p[data-cy='paragraph']").all_text_contents()
        text = "\n".join(p.strip() for p in paragraphs if p and p.strip())

        if not text:
            print(f"[{self.source_name}] Review vacío para {url}")
            return None

        created_at = Article.now_iso()
        article_id = str(hash(url))

        return Article(
            id=article_id,
            source=self.source_name,
            title=title,
            url=url,
            published_at=published_at,
            text=text,
            created_at=created_at,
        )
