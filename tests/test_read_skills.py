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
