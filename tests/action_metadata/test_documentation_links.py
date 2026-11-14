"""Check repository Markdown paths and heading anchors without network access."""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def anchors(path):
    result, counts = set(), {}
    fenced = False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if fenced or not re.match(r"^#{1,6} ", line):
            continue
        title = re.sub(r"^#{1,6} ", "", line).strip().lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        result.add(slug + (f"-{count}" if count else ""))
    return result


class DocumentationLinks(unittest.TestCase):
    def test_relative_links_and_anchors(self):
        files = [ROOT / "README.md", *ROOT.glob("*/README.md"), *ROOT.glob("docs/*.md")]
        for source in files:
            # Template placeholders are not links until instantiated.
            if source.name == "README_TEMPLATE.md":
                continue
            for match in re.finditer(r"\[[^\]\n]*\]\(([^)\s]+)\)", source.read_text()):
                url = urlsplit(match[1])
                if url.scheme or url.netloc:
                    continue
                target = (source.parent / unquote(url.path)).resolve() if url.path else source
                with self.subTest(source=source.relative_to(ROOT), link=match[1]):
                    self.assertTrue(target.exists(), str(target))
                    if url.fragment:
                        self.assertTrue(target.is_file())
                        self.assertIn(unquote(url.fragment), anchors(target))


if __name__ == "__main__":
    unittest.main()
