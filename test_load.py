"""Fetch text from Project Gutenberg and send N map-reduce requests."""

import argparse
import logging
import random
import threading
import urllib.request
from pathlib import Path

from client import do_request, my_funs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CACHE_DIR: Path = Path(__file__).parent / ".gutenberg_cache"

# Public domain books from Project Gutenberg (plain text URLs)
GUTENBERG_URLS: list[str] = [
    "https://www.gutenberg.org/files/2701/2701-0.txt",  # Moby Dick
    "https://www.gutenberg.org/files/1342/1342-0.txt",  # Pride and Prejudice
    "https://www.gutenberg.org/files/84/84-0.txt",  # Frankenstein
]

SEED: int = 42


def _url_to_cache_path(url: str) -> Path:
    return CACHE_DIR / url.rsplit("/", 1)[-1]


def fetch_text(url: str) -> str:
    cached: Path = _url_to_cache_path(url)
    if cached.exists():
        logger.info(f"Cache hit: {cached.name}")
        return cached.read_text(encoding="utf-8-sig")

    logger.info(f"Downloading {url}")
    with urllib.request.urlopen(url) as resp:
        text: str = resp.read().decode("utf-8-sig")

    CACHE_DIR.mkdir(exist_ok=True)
    cached.write_text(text, encoding="utf-8")
    return text


def fetch_corpus(urls: list[str]) -> list[str]:
    words: list[str] = []
    for url in urls:
        words.extend(fetch_text(url).split())
    logger.info(f"Corpus size: {len(words)} words")
    return words


def random_chunk(
    corpus: list[str], min_words: int = 1000, max_words: int = 5000
) -> list[str]:
    """Pick a random contiguous slice of the corpus."""
    size: int = random.randint(min_words, max_words)
    start: int = random.randint(0, max(0, len(corpus) - size))
    return corpus[start : start + size]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send N map-reduce requests with Gutenberg text"
    )
    parser.add_argument("n", type=int, help="Number of requests to send")
    parser.add_argument(
        "--chunk-size",
        type=int,
        nargs=2,
        default=[500, 1000],
        metavar=("MIN", "MAX"),
        help="Min and max words per chunk (default: 500 1000)",
    )
    args: argparse.Namespace = parser.parse_args()
    min_words, max_words = args.chunk_size

    random.seed(SEED)
    corpus: list[str] = fetch_corpus(GUTENBERG_URLS)

    chunks: list[list[str]] = [
        random_chunk(corpus, min_words, max_words) for _ in range(args.n)
    ]

    def send_request(i: int, chunk: list[str]) -> None:
        logger.info(f"Request {i + 1}/{args.n}: sending {len(chunk)} words")
        do_request(my_funs, chunk)

    threads: list[threading.Thread] = [
        threading.Thread(target=send_request, args=(i, c))
        for i, c in enumerate(chunks)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    logger.info("All requests completed")


if __name__ == "__main__":
    main()
