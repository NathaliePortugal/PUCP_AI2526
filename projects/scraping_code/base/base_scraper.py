from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
import csv
from typing import Iterable, List
from pathlib import Path

from datetime import datetime
from playwright.sync_api import sync_playwright, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError


from base.base_models import Article


class BaseNewsScraper(ABC):
    """
    Clase base para scrapers de noticias.

    Para implementar un nuevo scraper:
    - Sobrescribe `source_name`
    - Sobrescribe `start_urls`
    - Implementa `extract_article_links`
    - Implementa `extract_article_data`
    """

    # Nombre de la fuente (IGN, PCGamer, etc.)
    source_name: str = "BASE"

    # URLs iniciales donde se listan noticias
    start_urls: List[str] = []

    #vamos a guardar los datos en esta carpeta data/raw
    def __init__(self, output_dir: str = "data/raw", meta_dir: str = "data/meta"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.meta_dir = Path(meta_dir)
        self.meta_dir.mkdir(parents=True, exist_ok=True)

        #archivo global de URLs vsitas segun la fuente
        self.seen_urls_file = self.meta_dir / f"{self.source_name.lower()}_seen_urls.txt"

    # ---------- Métodos que las subclases DEBEN implementar ----------

    @abstractmethod
    def extract_article_links(self, page: Page) -> Iterable[str]:
        """
        Dado un Page apuntando a una página de listado,
        devolver URLs (absolutas o relativas) de artículos individuales.
        """
        raise NotImplementedError

    @abstractmethod
    def extract_article_data(self, page: Page, url: str) -> Article | None:
        """
        Dado un Page ya colocado en la URL del artículo,
        devolver un Article o None si no se pudo parsear.
        """
        raise NotImplementedError

    # ---------- Métodos comunes reutilizables ----------

    def normalize_url(self, url: str) -> str:
        """
        En caso de URL relativa, la subclase puede sobrescribir esto
        o usarlo en extract_article_links para componer la URL absoluta.
        Por defecto, asume que ya viene absoluta.
        """
        return url

    def get_output_file_for_today(self) -> Path:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        filename = f"{self.source_name.lower()}_{today}.csv"
        return self.output_dir / filename

    def ensure_csv_header(self, path: Path):
        if not path.exists():
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "id",
                    "source",
                    "title",
                    "url",
                    "published_at",
                    "text",
                    "created_at",
                ])

    def load_existing_urls(self, path: Path) -> set[str]:
        """
        Para evitar duplicados dentro del MISMO archivo de salida.
        """
        if not path.exists():
            return set()
        urls = set()
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                urls.add(row["url"])
        return urls

    def save_articles(self, path: Path, articles: list[Article]):
        if not articles:
            return
        self.ensure_csv_header(path)
        with path.open("a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for art in articles:
                writer.writerow([
                    art.id,
                    art.source,
                    art.title,
                    art.url,
                    art.published_at,
                    art.text,
                    art.created_at,
                ])

    def load_global_seen_urls(self) -> set[str]:
        if not self.seen_urls_file.exists():
            return set()
        with self.seen_urls_file.open("r", encoding="utf-8-sig") as f:
            return {line.strip() for line in f if line.strip()}

    def save_global_seen_urls(self, urls: set[str]):
        with self.seen_urls_file.open("w", encoding="utf-8-sig") as f:
            for u in sorted(urls):
                f.write(u + "\n")   
    # ---------- Método principal de ejecución ----------

    def run(self) -> list[Article]:
        output_file = self.get_output_file_for_today()
        existing_urls_today = self.load_existing_urls(output_file)
        # NUEVO: URLs globales vistas (hoy + días anteriores)
        global_seen_urls = self.load_global_seen_urls()

        collected: list[Article] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context()
            context.set_default_timeout(15000)
            page = context.new_page()

            for start_url in self.start_urls:
                print(f"[{self.source_name}] Listado: {start_url}")
                try:
                    page.goto(start_url, wait_until="domcontentloaded", timeout=30000)
                except PlaywrightTimeoutError:
                    print(f"[{self.source_name}] Timeout cargando listado {start_url}, lo salto.")
                    continue

                links = list(self.extract_article_links(page))
                print(f"[{self.source_name}] Encontrados {len(links)} links en listado.")

                total = len(links)

                for idx, raw_url in enumerate(links, start=1):
                    url = self.normalize_url(raw_url)

                    # evitar duplicados globales (días anteriores)
                    if url in global_seen_urls:
                        print(f"[{self.source_name}] ({idx}/{total}) Ya visto antes, skip: {url}")
                        continue

                    print(f"[{self.source_name}] ({idx}/{total}) Procesando: {url}")

                    article_page = context.new_page()
                    try:
                        article_page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        article = self.extract_article_data(article_page, url)
                    except PlaywrightTimeoutError:
                        print(f"[{self.source_name}] Timeout al abrir {url}, lo salto.")
                        article_page.close()
                        continue
                    except Exception as ex:
                        print(f"[{self.source_name}] Error abriendo {url}: {ex}")
                        article_page.close()
                        continue
                    finally:
                        article_page.close()

                    if article is None:
                        print(f"[{self.source_name}] Sin datos válidos en {url}, lo salto.")
                        continue

                    existing_urls_today.add(url)
                    global_seen_urls.add(url)
                    collected.append(article)

            browser.close()

        self.save_articles(output_file, collected)
        self.save_global_seen_urls(global_seen_urls)

        print(f"[{self.source_name}] Guardados {len(collected)} artículos nuevos en {output_file}")
        return collected

