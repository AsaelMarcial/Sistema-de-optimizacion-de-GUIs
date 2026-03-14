from __future__ import annotations

from bs4 import BeautifulSoup


def parse_html(html_content: str) -> dict[str, int]:
    soup = BeautifulSoup(html_content, "html.parser")
    return {
        "buttons": len(soup.find_all("button")),
        "images": len(soup.find_all("img")),
        "divs": len(soup.find_all("div")),
        "inputs": len(soup.find_all("input")),
        "headings": len(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])),
        "paragraphs": len(soup.find_all("p")),
        "links": len(soup.find_all("a")),
        "lists": len(soup.find_all(["ul", "ol"])),
    }
