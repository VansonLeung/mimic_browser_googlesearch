import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "Missing dependency: playwright\n"
        "Install with: python3 -m pip install -r requirements.txt\n"
        "Then install the browser with: python3 -m playwright install chromium",
        file=sys.stderr,
    )
    raise


ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "browser-state.json"
DEBUG_DIR = ROOT / "google-search-debug"

GOOGLE_DOMAINS = [
    "https://www.google.com",
    "https://www.google.co.uk",
    "https://www.google.ca",
    "https://www.google.com.au",
]

SEARCH_INPUT_SELECTORS = [
    "textarea[name='q']",
    "input[name='q']",
    "textarea[title='Search']",
    "input[title='Search']",
    "textarea[aria-label='Search']",
    "input[aria-label='Search']",
    "textarea",
]

RESULT_SELECTORS = [
    "#search",
    "#rso",
    ".g",
    "[data-sokoban-container]",
    "div[role='main']",
]

BLOCK_URL_MARKERS = [
    "google.com/sorry/index",
    "google.com/sorry",
    "recaptcha",
    "captcha",
    "unusual traffic",
]

BLOCK_BODY_MARKERS = [
    "yvlrue",
    "captcha",
    "unusual traffic",
    "/httpservice/retry/enablejs",
    "sg_ss",
    "sg_rel",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_")
    return (slug or "query")[:60]


def is_blocked(page: Any) -> bool:
    current_url = page.url.lower()
    if any(marker in current_url for marker in BLOCK_URL_MARKERS):
        return True

    try:
        body = page.content().lower()
    except Exception:
        return False

    return any(marker in body for marker in BLOCK_BODY_MARKERS)


def wait_for_manual_unblock(page: Any, timeout_ms: int, stage: str) -> bool:
    print(
        f"Blocked at stage '{stage}'. Complete any visible verification in the browser.",
        file=sys.stderr,
    )
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        if not is_blocked(page):
            return True
        page.wait_for_timeout(1000)
    return False


def save_debug(page: Any, query: str, label: str) -> dict[str, str]:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = DEBUG_DIR / f"{slugify(query)}-{label}-{stamp}"
    html_path = base.with_suffix(".html")
    png_path = base.with_suffix(".png")

    html_path.write_text(page.content(), encoding="utf-8")
    page.screenshot(path=str(png_path), full_page=True)

    return {"html": str(html_path), "screenshot": str(png_path)}


def wait_for_result_container(page: Any, timeout_ms: int) -> bool:
    per_selector_timeout = max(1000, timeout_ms // 2)
    for selector in RESULT_SELECTORS:
        try:
            page.wait_for_selector(selector, timeout=per_selector_timeout)
            return True
        except PlaywrightTimeoutError:
            continue
    return False


def extract_results(page: Any, limit: int) -> list[dict[str, str]]:
    return page.evaluate(
        """
        (maxResults) => {
          const results = [];
          const seenUrls = new Set();

          const selectorSets = [
            { container: '#search div[data-hveid]', title: 'h3', snippet: '.VwiC3b' },
            { container: '#rso div[data-hveid]', title: 'h3', snippet: '[data-sncf="1"]' },
            { container: '.g', title: 'h3', snippet: 'div[style*="webkit-line-clamp"]' },
            { container: 'div[jscontroller][data-hveid]', title: 'h3', snippet: 'div[role="text"]' }
          ];

          const alternativeSnippetSelectors = [
            '.VwiC3b',
            '[data-sncf="1"]',
            'div[style*="webkit-line-clamp"]',
            'div[role="text"]'
          ];

          for (const selectors of selectorSets) {
            if (results.length >= maxResults) break;
            const containers = document.querySelectorAll(selectors.container);

            for (const container of containers) {
              if (results.length >= maxResults) break;

              const titleElement = container.querySelector(selectors.title);
              if (!titleElement) continue;

              const title = (titleElement.textContent || '').trim();
              let link = '';

              const linkInTitle = titleElement.querySelector('a');
              if (linkInTitle) {
                link = linkInTitle.href;
              } else {
                let current = titleElement;
                while (current && current.tagName !== 'A') {
                  current = current.parentElement;
                }
                if (current instanceof HTMLAnchorElement) {
                  link = current.href;
                } else {
                  const containerLink = container.querySelector('a');
                  if (containerLink) link = containerLink.href;
                }
              }

              if (!link || !link.startsWith('http') || seenUrls.has(link)) continue;

              let snippet = '';
              const snippetElement = container.querySelector(selectors.snippet);
              if (snippetElement) {
                snippet = (snippetElement.textContent || '').trim();
              } else {
                for (const altSelector of alternativeSnippetSelectors) {
                  const element = container.querySelector(altSelector);
                  if (element) {
                    snippet = (element.textContent || '').trim();
                    break;
                  }
                }

                if (!snippet) {
                  const textNodes = Array.from(container.querySelectorAll('div')).filter(el =>
                    !el.querySelector('h3') &&
                    (el.textContent || '').trim().length > 20
                  );
                  if (textNodes.length > 0) {
                    snippet = (textNodes[0].textContent || '').trim();
                  }
                }
              }

              if (title && link) {
                results.push({ title, link, snippet });
                seenUrls.add(link);
              }
            }
          }

          if (results.length < maxResults) {
            const anchors = Array.from(document.querySelectorAll("a[href^='http']"));
            for (const el of anchors) {
              if (results.length >= maxResults) break;
              if (!(el instanceof HTMLAnchorElement)) continue;

              const link = el.href;
              if (
                !link ||
                seenUrls.has(link) ||
                link.includes('google.com/') ||
                link.includes('accounts.google') ||
                link.includes('support.google')
              ) {
                continue;
              }

              const title = (el.textContent || '').trim();
              if (!title) continue;

              let snippet = '';
              let parent = el.parentElement;
              for (let i = 0; i < 3 && parent; i++) {
                const text = (parent.textContent || '').trim();
                if (text.length > 20 && text !== title) {
                  snippet = text;
                  break;
                }
                parent = parent.parentElement;
              }

              results.push({ title, link, snippet });
              seenUrls.add(link);
            }
          }

          return results.slice(0, maxResults);
        }
        """,
        limit,
    )


def create_context(browser: Any, locale: str) -> Any:
    options: dict[str, Any] = {
        "locale": locale,
        "timezone_id": "Asia/Hong_Kong",
        "viewport": {"width": 1365, "height": 900},
        "screen": {"width": 1365, "height": 900},
        "is_mobile": False,
        "has_touch": False,
        "java_script_enabled": True,
        "accept_downloads": True,
        "permissions": ["geolocation", "notifications"],
        "user_agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    }

    if STATE_PATH.exists():
        options["storage_state"] = str(STATE_PATH)

    context = browser.new_context(**options)
    context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'zh-CN'] });
        window.chrome = { runtime: {}, loadTimes: function () {}, csi: function () {}, app: {} };

        if (typeof WebGLRenderingContext !== 'undefined') {
          const getParameter = WebGLRenderingContext.prototype.getParameter;
          WebGLRenderingContext.prototype.getParameter = function (parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.call(this, parameter);
          };
        }

        Object.defineProperty(window.screen, 'width', { get: () => 1365 });
        Object.defineProperty(window.screen, 'height', { get: () => 900 });
        Object.defineProperty(window.screen, 'colorDepth', { get: () => 24 });
        Object.defineProperty(window.screen, 'pixelDepth', { get: () => 24 });
        """
    )
    return context


def run_search(query: str, limit: int, timeout_ms: int, headless: bool, locale: str) -> dict[str, Any]:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=headless,
            timeout=timeout_ms * 2,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--no-first-run",
                "--disable-dev-shm-usage",
            ],
        )
        context = create_context(browser, locale)
        page = context.new_page()

        try:
            domain_index = int(time.time()) % len(GOOGLE_DOMAINS)
            domain = GOOGLE_DOMAINS[domain_index]

            page.goto(domain, wait_until="networkidle", timeout=timeout_ms)
            if is_blocked(page):
                if headless or not wait_for_manual_unblock(page, timeout_ms, "home"):
                    debug = save_debug(page, query, "blocked-home")
                    return {"blocked": True, "stage": "home", "debug": debug}

            search_input = None
            for selector in SEARCH_INPUT_SELECTORS:
                handle = page.query_selector(selector)
                if handle:
                    search_input = handle
                    break

            if search_input is None:
                debug = save_debug(page, query, "missing-input")
                raise RuntimeError(f"Could not find Google search input. Debug saved: {debug}")

            search_input.click()
            page.keyboard.type(query, delay=20)
            page.wait_for_timeout(200)
            page.keyboard.press("Enter")
            page.wait_for_load_state("networkidle", timeout=timeout_ms)

            if is_blocked(page):
                if headless or not wait_for_manual_unblock(page, timeout_ms, "search"):
                    debug = save_debug(page, query, "blocked-search")
                    return {"blocked": True, "stage": "search", "debug": debug}

            if not wait_for_result_container(page, timeout_ms):
                if is_blocked(page):
                    if headless or not wait_for_manual_unblock(page, timeout_ms, "results"):
                        debug = save_debug(page, query, "blocked-results")
                        return {"blocked": True, "stage": "results", "debug": debug}
                    if wait_for_result_container(page, timeout_ms):
                        page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    else:
                        debug = save_debug(page, query, "missing-results-after-unblock")
                        raise RuntimeError(f"Could not find result containers after unblock. Debug saved: {debug}")
                else:
                    debug = save_debug(page, query, "missing-results")
                    raise RuntimeError(f"Could not find result containers. Debug saved: {debug}")

            page.wait_for_timeout(500)
            results = extract_results(page, limit)
            debug = save_debug(page, query, "results")

            context.storage_state(path=str(STATE_PATH))
            return {
                "blocked": False,
                "query": query,
                "url": page.url,
                "results": results,
                "debug": debug,
                "statePath": str(STATE_PATH),
            }
        finally:
            context.close()
            browser.close()


def search_with_fallback(query: str, limit: int, timeout_ms: int, locale: str) -> dict[str, Any]:
    first = run_search(query, limit, timeout_ms, headless=True, locale=locale)
    if not first.get("blocked"):
        return first

    print(
        f"Headless run was blocked at stage '{first.get('stage')}'. "
        "Retrying in headed mode. Complete any visible verification in the browser.",
        file=sys.stderr,
    )
    headed = run_search(query, limit, timeout_ms * 2, headless=False, locale=locale)
    if headed.get("blocked"):
        headed["previousHeadlessBlock"] = first
    return headed


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright-based Google search test.")
    parser.add_argument("query", nargs="?", default="python programming language")
    parser.add_argument("-l", "--limit", type=int, default=10)
    parser.add_argument("-t", "--timeout", type=int, default=60000, help="Timeout in milliseconds.")
    parser.add_argument("--locale", default="en-US")
    args = parser.parse_args()

    result = search_with_fallback(args.query, args.limit, args.timeout, args.locale)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
