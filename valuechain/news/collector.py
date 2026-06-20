"""
네이버 뉴스 API 기반 섹터별 기사 수집.

환경변수:
    NAVER_CLIENT_ID
    NAVER_CLIENT_SECRET
"""
from __future__ import annotations
import os
import urllib.request
import urllib.parse
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass
class NewsItem:
    title: str
    description: str
    pub_date: str
    link: str


def _load_env():
    """프로젝트 루트의 .env에서 환경변수 로드."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    env_path = os.path.normpath(env_path)
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())


_load_env()


def search_news(query: str, display: int = 20) -> list[NewsItem]:
    """
    네이버 뉴스 검색 API 호출.
    query: 검색어 (예: "반도체 수출")
    display: 가져올 기사 수 (최대 100)
    """
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음")

    enc_query = urllib.parse.quote(query)
    url = (f"https://openapi.naver.com/v1/search/news.json"
           f"?query={enc_query}&display={display}&sort=date")

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    items = []
    for it in data.get("items", []):
        title = _strip_tags(it.get("title", ""))
        desc  = _strip_tags(it.get("description", ""))
        items.append(NewsItem(title, desc, it.get("pubDate", ""), it.get("link", "")))
    return items


def search_news_with_total(query: str, display: int = 5) -> tuple[list[NewsItem], int]:
    """기사 목록과 총 건수를 함께 반환."""
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(".env에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 없음")

    enc_query = urllib.parse.quote(query)
    url = (f"https://openapi.naver.com/v1/search/news.json"
           f"?query={enc_query}&display={display}&sort=date")

    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", client_id)
    req.add_header("X-Naver-Client-Secret", client_secret)

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    total = int(data.get("total", 0))
    items = []
    for it in data.get("items", []):
        title = _strip_tags(it.get("title", ""))
        desc  = _strip_tags(it.get("description", ""))
        items.append(NewsItem(title, desc, it.get("pubDate", ""), it.get("link", "")))
    return items, total


def _strip_tags(text: str) -> str:
    """HTML 태그 제거."""
    import re
    return re.sub(r"<[^>]+>", "", text).strip()
