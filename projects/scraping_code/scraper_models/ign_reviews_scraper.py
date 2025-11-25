# scraping/ign_reviews_scraper.py

from datetime import datetime
from playwright.sync_api import Page
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
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
        CARD_LINK_SELECTOR = "a.item-body[data-cy='item-body']"

        # Scroll progresivo
        max_scrolls = 10
        last_count = 0

        for i in range(max_scrolls):
            # espera a que haya al menos algunos items
            try:
                page.wait_for_selector(CARD_LINK_SELECTOR, timeout=5000)
            except PlaywrightTimeoutError:
                break

            anchors = page.locator(CARD_LINK_SELECTOR)
            count = anchors.count()

            if count == last_count:
                # ya no aparecen nuevos items → paramos
                break

            last_count = count
            # scroll hacia abajo
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(1500)  # 1.5s para que carguen nuevos

        # al final, tomamos todos los links cargados
        anchors = page.locator(CARD_LINK_SELECTOR)
        count = anchors.count()
        print(f"[{self.source_name}] Total de reviews visibles tras scroll: {count}")

        for i in range(count):
            href = anchors.nth(i).get_attribute("href")
            if href:
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
