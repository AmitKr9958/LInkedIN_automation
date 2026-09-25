from app.skills import companies, people, posts, saved
from app.skills.parsing import LinkItem, clean_text, dedupe_by, unique_items


class _FakeLink:
    def __init__(self, text="", href=""):
        self._text, self._href = text, href

    async def count(self):
        return 1 if (self._text or self._href) else 0

    async def text_content(self):
        return self._text

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name):
        return self._href if name == "href" else None

    @property
    def first(self):
        return self


class _FakeLinkList:
    """Locator-shaped list: real Playwright locators support nth/first/count."""

    def __init__(self, links):
        self._links = links

    async def count(self):
        return len(self._links)

    def nth(self, index):
        return self._links[index]

    @property
    def first(self):
        return self._links[0] if self._links else _FakeLink("")


class _FakeCard:
    def __init__(self, text="", name="", headline="", href=""):
        self._text, self._name, self._headline, self._href = text, name, headline, href

    async def inner_text(self):
        return self._text

    def locator(self, selector):
        if "primary-subtitle" in selector:
            return _FakeLinkList([_FakeLink(self._headline, self._href)])
        if "title-text" in selector or "[href" in selector:
            return _FakeLinkList([_FakeLink(self._name, self._href)])
        return _FakeLinkList([_FakeLink(self._text, self._href)])


class _FakeCards:
    def __init__(self, cards):
        self._cards = cards

    async def count(self):
        return len(self._cards)

    def nth(self, index):
        return self._cards[index]


class _FakePage:
    def __init__(self, cards):
        self._cards = cards

    async def goto(self, url, **kwargs):
        self.last_url = url

    def locator(self, selector):
        return _FakeCards(self._cards)


class _SDUIPage:
    """SDUI page: legacy locators find nothing; evaluate returns a DOM snapshot."""

    def __init__(self, rows):
        self._rows = rows

    async def goto(self, url, **kwargs):
        self.last_url = url

    def locator(self, selector):
        return _FakeCards([])

    async def evaluate(self, script):
        return self._rows


class _HybridPage:
    """Legacy shells present but yield nothing; the SDUI snapshot has the data."""

    def __init__(self, rows):
        self._rows = rows
        self._cards = [_FakeCard("", name="", href="")]

    async def goto(self, url, **kwargs):
        self.last_url = url

    def locator(self, selector):
        return _FakeCards(self._cards)

    async def evaluate(self, script):
        return self._rows


def test_parsing_helpers_dedupe_and_clean():
    assert clean_text("  Power   BI\nreporting ") == "Power BI reporting"
    items = [LinkItem("first", "u1"), LinkItem("dup", "u1"), LinkItem("second", "u2"), LinkItem("", "")]
    assert [item.text for item in unique_items(items)] == ["first", "second"]
    assert dedupe_by(["a", "a", "b"], lambda value: value) == ["a", "b"]
    assert dedupe_by(["", ""], lambda value: value) == []


async def test_people_search_dedupes_duplicate_profiles():
    cards = [
        _FakeCard("Priya Rao\n• 2nd\nRecruiter\nGurugram, India", name="Priya Rao", href="https://www.linkedin.com/in/priya"),
        _FakeCard("Priya Rao\n• 2nd\nRecruiter\nGurugram, India", name="Priya Rao", href="https://www.linkedin.com/in/priya"),
        _FakeCard("Rahul\n• 3rd+\nBI Developer\nDelhi, India", name="Rahul", href="https://www.linkedin.com/in/rahul"),
    ]
    results = await people.search(_FakePage(cards), "Power BI recruiter")
    assert [person.name for person in results] == ["Priya Rao", "Rahul"]
    assert [person.headline for person in results] == ["Recruiter", "BI Developer"]
    assert [person.location for person in results] == ["Gurugram, India", "Delhi, India"]


async def test_companies_search_dedupes_duplicate_companies():
    cards = [
        _FakeCard("Acme analytics", name="Acme", href="https://www.linkedin.com/company/acme"),
        _FakeCard("Acme analytics", name="Acme", href="https://www.linkedin.com/company/acme"),
        _FakeCard("Beta data", name="Beta", href="https://www.linkedin.com/company/beta"),
    ]
    results = await companies.search(_FakePage(cards), "analytics")
    assert [company.name for company in results] == ["Acme", "Beta"]


async def test_posts_search_dedupes_duplicate_posts():
    cards = [
        _FakeCard("Power BI tips", name="Priya", href="https://www.linkedin.com/in/priya"),
        _FakeCard("Power BI tips", name="Priya", href="https://www.linkedin.com/in/priya"),
        _FakeCard("Another post", name="Rahul", href="https://www.linkedin.com/in/rahul"),
    ]
    results = await posts.search(_FakePage(cards), "Power BI")
    assert len(results) == 2
    assert results[0].author == "Priya"


async def test_saved_posts_dedupe_and_capture_permalink():
    cards = [
        _FakeCard("Saved analytics post", href="https://www.linkedin.com/feed/update/urn:li:activity:9"),
        _FakeCard("Saved analytics post", href="https://www.linkedin.com/feed/update/urn:li:activity:9"),
    ]
    results = await saved.read_saved_posts(_FakePage(cards))
    assert len(results) == 1
    assert results[0].href.endswith("activity:9")


async def test_companies_sdui_snapshot_skips_query_variants_and_dedupes():
    rows = [
        {"href": "https://www.linkedin.com/company/acme", "text": "Acme\nAnalytics\n1,234 followers"},
        {"href": "https://www.linkedin.com/company/acme?trk=search", "text": "Acme\nAnalytics"},
        {"href": "https://www.linkedin.com/company/acme/", "text": "Acme\nAnalytics"},
        {"href": "https://www.linkedin.com/company/beta", "text": "Beta\nData\n999 followers"},
    ]
    results = await companies.search(_SDUIPage(rows), "analytics")
    assert [company.name for company in results] == ["Acme", "Beta"]
    assert results[0].industry == "Analytics"
    assert results[1].industry == "Data"


async def test_people_sdui_snapshot_parses_card_lines_and_dedupes():
    rows = [
        {"text": "Priya Rao\n• 2nd\nRecruiter\nGurugram, India", "author": "Priya Rao", "href": "https://www.linkedin.com/in/priya"},
        {"text": "Priya Rao\n• 2nd\nRecruiter\nGurugram, India", "author": "Priya Rao", "href": "https://www.linkedin.com/in/priya"},
        {"text": "Rahul\n• 3rd+\nBI Developer\nDelhi, India", "author": "Rahul", "href": "https://www.linkedin.com/in/rahul"},
        {"text": "Promoted slot", "author": "", "href": ""},
    ]
    results = await people.search(_SDUIPage(rows), "Power BI recruiter")
    assert [person.name for person in results] == ["Priya Rao", "Rahul"]
    assert results[0].headline == "Recruiter"
    assert results[0].location == "Gurugram, India"


async def test_posts_sdui_snapshot_picks_author_and_dedupes_by_text():
    rows = [
        {"text": "Power BI tips", "author": "Priya", "href": "https://www.linkedin.com/in/priya"},
        {"text": "Power BI tips", "author": "Priya", "href": "https://www.linkedin.com/in/priya"},
        {"text": "Another post", "author": "Rahul", "href": "https://www.linkedin.com/in/rahul"},
    ]
    results = await posts.search(_SDUIPage(rows), "Power BI")
    assert len(results) == 2
    assert results[0].author == "Priya"


async def test_saved_sdui_snapshot_dedupes_by_permalink():
    rows = [
        {"text": "Saved analytics post", "href": "https://www.linkedin.com/feed/update/urn:li:activity:9"},
        {"text": "Saved analytics post", "href": "https://www.linkedin.com/feed/update/urn:li:activity:9"},
    ]
    results = await saved.read_saved_posts(_SDUIPage(rows))
    assert len(results) == 1
    assert results[0].href.endswith("activity:9")


async def test_companies_sdui_snapshot_strips_page_by_label():
    rows = [
        {
            "href": "https://www.linkedin.com/company/big-time-data",
            "text": "Page by Big Time Data\nIT Services\n1,200 followers",
        },
    ]
    results = await companies.search(_SDUIPage(rows), "Power BI")
    assert [company.name for company in results] == ["Big Time Data"]
    assert results[0].industry == "IT Services"


async def test_companies_fall_back_to_sdui_when_legacy_extract_is_empty():
    rows = [{"href": "https://www.linkedin.com/company/acme", "text": "Acme\nAnalytics"}]
    results = await companies.search(_HybridPage(rows), "analytics")
    assert [company.name for company in results] == ["Acme"]


async def test_people_fall_back_to_sdui_when_legacy_extract_is_empty():
    rows = [
        {
            "text": "Priya Rao\n• 2nd\nRecruiter\nGurugram, India",
            "author": "Priya Rao",
            "href": "https://www.linkedin.com/in/priya",
        },
    ]
    results = await people.search(_HybridPage(rows), "Power BI recruiter")
    assert [person.name for person in results] == ["Priya Rao"]
    assert results[0].headline == "Recruiter"


async def test_people_sdui_snapshot_names_from_card_lines_when_link_text_empty():
    rows = [
        {
            "text": "Sara Mejia\n• 2nd\nMicrosoft BI Recruiter\nGreater Melbourne Area",
            "author": "",
            "href": "https://www.linkedin.com/in/sara-mejia",
        },
    ]
    results = await people.search(_SDUIPage(rows), "Power BI recruiter")
    assert [person.name for person in results] == ["Sara Mejia"]
    assert results[0].headline == "Microsoft BI Recruiter"
    assert results[0].location == "Greater Melbourne Area"


async def test_people_sdui_snapshot_splits_inline_degree_lines():
    rows = [
        {
            "text": "Sara Mejia • 2nd Connecting Best-In-Class Microsoft BI professionals Greater Melbourne Area",
            "author": "",
            "href": "https://www.linkedin.com/in/sara-mejia",
        },
    ]
    results = await people.search(_SDUIPage(rows), "Power BI recruiter")
    assert results[0].name == "Sara Mejia"
    assert results[0].headline == "Connecting Best-In-Class Microsoft BI professionals Greater Melbourne Area"
