from datetime import datetime
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from base.base_scraper import BaseNewsScraper
from base.base_models import Article


class KotakuReviewsScraper(BaseNewsScraper):
    """
    Scraper para los reviews de Kotaku.
    Recorre varias páginas: /reviews, /reviews/page/2, /reviews/page/3, ...
    """
    source_name = "Kotaku-Reviews"
    BASE_URL = "https://kotaku.com"

    def __init__(self, max_pages: int = 5, output_dir: str = "data/raw", meta_dir: str = "data/meta"):
        super().__init__(output_dir=output_dir, meta_dir=meta_dir)
        self.max_pages = max_pages

    @property
    def start_urls(self) -> list[str]:
        """
        Genera las URLs de las páginas de reviews:
        Página 1  -> https://kotaku.com/reviews
        Página 2+ -> https://kotaku.com/reviews/page/N
        """
        urls: list[str] = ["https://kotaku.com/reviews"]
        for page in range(2, self.max_pages + 1):
            urls.append(f"https://kotaku.com/reviews/page/{page}")
        return urls

    def normalize_url(self, url: str) -> str:
        if url.startswith("/"):
            return self.BASE_URL + url
        return url

    # ------------ LISTADO: /reviews y /reviews/page/N ------------

    def extract_article_links(self, page: Page):
        """
        Extrae los links de las tarjetas de review.

        Ejemplo HTML que encontraste:
        <a href="https://kotaku.com/call-of-duty-black-ops-7-review-..."
           class="block"
           cmp-ltrk="archive-posts"
           ...>
        """
        CARD_LINK_SELECTOR = 'a.block[cmp-ltrk="archive-posts"][href]'

        try:
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

            # Evitar páginas de autor:
            if "/author/" in href:
                continue

            yield href

    # ------------ REVIEW INDIVIDUAL ------------

    def extract_article_data(self, page: Page, url: str) -> Article | None:
        # --- título ---
        try:
            title = page.locator("h1").inner_text().strip()
        except Exception:
            print(f"[{self.source_name}] No se pudo obtener título para {url}")
            return None

        # --- fecha ---
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
        ARTICLE_CONTAINER_SELECTOR = "div.entry-content"

        # Usamos locator directamente en la page
        container = page.locator(ARTICLE_CONTAINER_SELECTOR)
        if container.count() == 0:
            print(f"[{self.source_name}] No se encontró contenedor de artículo para {url}")
            return None

        # Tomamos todos los <p> dentro de ese contenedor
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

