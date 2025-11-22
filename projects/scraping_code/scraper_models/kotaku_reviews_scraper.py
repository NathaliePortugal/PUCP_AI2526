from datetime import datetime
from playwright.sync_api import Page
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from base.base_scraper import BaseNewsScraper
from base.base_models import Article


class KotakuReviewsScraper(BaseNewsScraper):
    """
    Scraper para los reviews de Kotaku:
    https://kotaku.com/reviews
    """
    source_name = "Kotaku-Reviews"

    start_urls = [
        "https://kotaku.com/reviews",
    ]

    BASE_URL = "https://kotaku.com"

    # ---------------- Helpers de URL ----------------

    def normalize_url(self, url: str) -> str:
        if url.startswith("/"):
            return self.BASE_URL + url
        return url

    # ---------------- Listado de reviews ----------------

    def extract_article_links(self, page: Page):
        """
        Usa el <a class="block" cmp-ltrk="archive-posts" ...> que encontraste
        para sacar los links de cada review.
        """
        #CARD_LINK_SELECTOR = 'a.block[cmp-ltrk="archive-posts"]'
        CARD_LINK_SELECTOR = 'a.block[cmp-ltrk="archive-posts"][href]'

        try:
            # Espera hasta que haya al menos uno en el DOM (máx 15s)
            page.wait_for_selector(CARD_LINK_SELECTOR, timeout=15000)
        except PlaywrightTimeoutError:
            print(f"[{self.source_name}] No aparecieron reviews en el DOM, selector: {CARD_LINK_SELECTOR}")
            return []

        anchors = page.locator(CARD_LINK_SELECTOR)
        count = anchors.count()
        print(f"[{self.source_name}] Encontrados {count} items en listado de reviews.")

        for i in range(count):
            href = anchors.nth(i).get_attribute("href")
            if not href:
                continue

            if "/author/" in href:
                continue

            yield href

    # ---------------- Review individual ----------------

    def extract_article_data(self, page: Page, url: str) -> Article | None:
        """
        Estamos ya dentro del review individual, algo como:
        https://kotaku.com/call-of-duty-black-ops-7-review-xxxx

        Del HTML que vimos por texto:
        - El título aparece como <h1> Call Of Duty Black Ops 7: The Kotaku Review
        - Los párrafos de contenido empiezan directo luego del bloque “By Zack... Published...”.

        Ideal:
        - Encontrar el contenedor principal del artículo (ej. <article> o un <div> con data-*).
        - Dentro de ese contenedor, sacar todos los <p>.
        """

        # ---- título ----
        try:
            title = page.locator("h1").inner_text().strip()
        except Exception:
            print(f"[{self.source_name}] No se pudo obtener título para {url}")
            return None

        # ---- fecha ----
        published_at = None
        try:
            meta = page.locator('meta[property="article:published_time"]')
            if meta.count() > 0:
                published_at = meta.first.get_attribute("content")
        except Exception:
            pass

        if not published_at:
            published_at = datetime.utcnow().isoformat()

        # --- cuerpo del review ---
        # <div class="entry-content prose ...">
        ARTICLE_CONTAINER_SELECTOR = "div.entry-content"

        container = page.locator(ARTICLE_CONTAINER_SELECTOR)
        if container.count() == 0:
            print(f"[{self.source_name}] No se encontró contenedor de artículo para {url}")
            return None

        # Puedes usar p "normales", o si ves un data-cy/atributo particular, mejor:
        paragraphs = container.locator("p").all_text_contents()
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
