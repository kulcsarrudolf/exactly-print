"""What search engines and link previews see: titles, descriptions,
canonical URLs and the schema.org graph behind each page.

The site's public address is not something the app can know for certain
from behind a proxy, so it is read from the `SITE_URL` environment variable
and falls back to the address the request arrived at.
"""

import os
from dataclasses import dataclass

from fastapi import Request

NAME = "Exactly Print"
TAGLINE = "Upload an image, pick a size, print it exactly that size."
AUTHOR = "Kulcsár Rudolf"
AUTHOR_URL = "https://kulcsarrudolf.com"
REPOSITORY = "https://github.com/kulcsarrudolf/exactly-print"
LICENSE_URL = "https://opensource.org/license/mit"
THEME_COLOR = "#fafaf8"
OG_IMAGE = "/static/og.png"
OG_IMAGE_SIZE = (1200, 630)
OG_IMAGE_ALT = (
    "A sheet of paper with an image laid out at an exact size, crop marks in the corners "
    "and a 100 mm ruler along the bottom, under the words Exactly Print."
)

FEATURES = [
    "Image placed on the page by physical millimetres, not pixels",
    "Width, height or both, in mm or cm; the other side follows the image's proportions",
    "2 mm bleed past the cut line and crop marks in the four corners",
    "Two 100 mm rulers to check whether the printer scaled the page",
    "Per-printer calibration, across and down separately",
    "A4, A3, A5 and Letter, portrait or landscape",
    "PDF download or open to print straight from the browser",
    "Nothing uploaded is stored",
]


@dataclass(frozen=True)
class Page:
    """Everything the `<head>` of a page needs, worded for that page."""

    path: str
    title: str
    description: str
    site_url: str
    og_type: str = "website"

    @property
    def url(self) -> str:
        return self.site_url + self.path

    @property
    def image(self) -> str:
        return self.site_url + OG_IMAGE


def site_url(request: Request) -> str:
    """The origin the site is published at, without a trailing slash."""
    configured = os.environ.get("SITE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    return str(request.base_url).rstrip("/")


INDEX_TITLE = "Exactly Print · Print an image at an exact size in mm or cm"
INDEX_DESCRIPTION = (
    "Upload an image, type its width or height in mm or cm, and get a PDF that prints it at "
    "exactly that size, with crop marks, bleed and a 100 mm ruler to check the printer. "
    "Free, nothing is stored."
)
HELP_TITLE = "Why a print comes out the wrong size, and how to fix it · Exactly Print"
HELP_DESCRIPTION = (
    "Why a printed image comes out a few percent too small or large: print dialog scaling, "
    "driver settings and the printer itself. How to read the 100 mm rulers and calibrate a "
    "printer once so every print measures right."
)


def index_page(request: Request) -> Page:
    return Page("/", INDEX_TITLE, INDEX_DESCRIPTION, site_url(request))


def help_page(request: Request) -> Page:
    return Page("/help", HELP_TITLE, HELP_DESCRIPTION, site_url(request), og_type="article")


def _person() -> dict:
    return {
        "@type": "Person",
        "@id": AUTHOR_URL + "/#person",
        "name": AUTHOR,
        "url": AUTHOR_URL,
    }


def _website(site: str) -> dict:
    return {
        "@type": "WebSite",
        "@id": site + "/#website",
        "url": site + "/",
        "name": NAME,
        "description": TAGLINE,
        "inLanguage": "en",
        "publisher": {"@id": AUTHOR_URL + "/#person"},
    }


def _application(site: str) -> dict:
    return {
        "@type": "WebApplication",
        "@id": site + "/#app",
        "name": NAME,
        "url": site + "/",
        "description": INDEX_DESCRIPTION,
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "Any",
        "browserRequirements": "Requires JavaScript",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "featureList": FEATURES,
        "screenshot": site + OG_IMAGE,
        "softwareHelp": {"@type": "CreativeWork", "url": site + "/help"},
        "license": LICENSE_URL,
        "sameAs": [REPOSITORY],
        "author": {"@id": AUTHOR_URL + "/#person"},
    }


def _webpage(page: Page, **extra) -> dict:
    return {
        "@type": "WebPage",
        "@id": page.url + "#webpage",
        "url": page.url,
        "name": page.title,
        "description": page.description,
        "inLanguage": "en",
        "isPartOf": {"@id": page.site_url + "/#website"},
        "primaryImageOfPage": {"@type": "ImageObject", "url": page.image},
        **extra,
    }


def _breadcrumbs(site: str, *crumbs: tuple[str, str]) -> dict:
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": i, "name": name, "item": site + path}
            for i, (name, path) in enumerate(crumbs, start=1)
        ],
    }


def index_graph(page: Page) -> dict:
    site = page.site_url
    return {
        "@context": "https://schema.org",
        "@graph": [
            _website(site),
            _person(),
            _application(site),
            _webpage(page, about={"@id": site + "/#app"}),
        ],
    }


HELP_STEPS = [
    (
        "Print a test page",
        "Under Printer, leave the calibration on None and print any page at 100%.",
    ),
    (
        "Measure the rulers",
        "Measure both rulers from the 0 to the 100 mark. A tenth of a millimetre matters here.",
    ),
    (
        "Enter the measurements",
        "Click Calibrate…, name the printer, say that the page was printed with no calibration, "
        "and type what the bottom and the left ruler measured.",
    ),
    (
        "Print again to confirm",
        "With that printer chosen, the page is drawn 100 ÷ measured times its real size, "
        "across and down separately, so the printer's own scaling brings both rulers back "
        "to 100 mm.",
    ),
    (
        "Refine if needed",
        "If a ruler is still slightly off, calibrate again with the printer chosen under "
        "'The page was printed with'; the new measurement stacks on the old correction.",
    ),
]

HELP_FAQ = [
    (
        "Why does a print come out the wrong size?",
        "Three things change the size between the PDF and the paper: the print dialog scaling "
        "the page with 'Fit to page' or a mismatched paper size, a scale hidden in the printer "
        "driver's own settings, and the printer itself, whose rollers and heat stretch or "
        "shrink the sheet by a fraction of a percent. Print at 100% / 'Actual size' on the "
        "paper the page names, then calibrate for whatever is left.",
    ),
    (
        "What do the rulers on the page tell you?",
        "Every page carries two 100 mm rulers, one along the bottom and one up the left edge. "
        "If both measure 100 mm on paper, the image is the size you asked for. A ruler 5 mm or "
        "more off is almost always a print dialog or driver setting; a small, constant error "
        "on every print from one printer is what a calibration cancels.",
    ),
    (
        "Where are the printer calibrations stored?",
        "In the browser's local storage on that device only. The server receives just the "
        "chosen factor and name with each preview and PDF, and keeps nothing.",
    ),
]


def help_graph(page: Page) -> dict:
    site = page.site_url
    return {
        "@context": "https://schema.org",
        "@graph": [
            _website(site),
            _person(),
            _webpage(
                page,
                about={"@id": site + "/#app"},
                breadcrumb={"@id": page.url + "#breadcrumb"},
            ),
            {**_breadcrumbs(site, (NAME, "/"), ("Help", "/help")), "@id": page.url + "#breadcrumb"},
            {
                "@type": "HowTo",
                "@id": page.url + "#help-calibrate",
                "name": "Calibrate a printer so a 100 mm ruler prints at 100 mm",
                "description": (
                    "Print a page, measure the rulers, enter what they measured, and the page "
                    "is drawn slightly larger or smaller so the printer's scaling cancels out."
                ),
                "totalTime": "PT10M",
                "tool": [{"@type": "HowToTool", "name": "A steel ruler"}],
                "step": [
                    {
                        "@type": "HowToStep",
                        "position": i,
                        "name": name,
                        "text": text,
                        "url": page.url + "#help-calibrate",
                    }
                    for i, (name, text) in enumerate(HELP_STEPS, start=1)
                ],
            },
            {
                "@type": "FAQPage",
                "@id": page.url + "#faq",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": question,
                        "acceptedAnswer": {"@type": "Answer", "text": answer},
                    }
                    for question, answer in HELP_FAQ
                ],
            },
        ],
    }


def robots_txt(site: str) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /preview",
            "Disallow: /pdf",
            "",
            f"Sitemap: {site}/sitemap.xml",
            "",
        ]
    )


def sitemap_xml(site: str) -> str:
    urls = "".join(
        f"  <url>\n    <loc>{site}{path}</loc>\n    <changefreq>{freq}</changefreq>\n  </url>\n"
        for path, freq in (("/", "monthly"), ("/help", "monthly"))
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )
