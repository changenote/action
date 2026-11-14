"""Check local usage snippets and the documented public Action contract."""

from pathlib import Path
import re
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]


class ReleaseExamples(unittest.TestCase):
    def test_usage_examples_use_default_cli_version(self):
        sources = [ROOT / "README.md", *ROOT.glob("*/README.md"),
                   *ROOT.glob("docs/*.md")]
        for source in sources:
            for block in re.findall(r"```yaml\n(.*?)```", source.read_text(), re.DOTALL):
                workflow = yaml.load(block, Loader=yaml.BaseLoader)
                jobs = workflow.get("jobs", {"example": workflow})
                for job in jobs.values():
                    for step in job.get("steps", []):
                        name = step.get("uses", "").split("@", 1)[0]
                        if (name not in ("changenote/action", "{{action-path}}")
                                and not name.startswith("changenote/action/")):
                            continue
                        with self.subTest(source=source.relative_to(ROOT), uses=step["uses"]):
                            self.assertNotIn("version", step.get("with", {}))

    def test_public_contract_is_documented(self):
        action = yaml.load((ROOT / "action.yml").read_text(), Loader=yaml.BaseLoader)
        guide = (ROOT / "docs/github-actions.md").read_text()
        for key in (*action["inputs"], *action["outputs"]):
            self.assertIn("`" + key + "`", guide)
        self.assertIn("full-tree", guide)
        self.assertIn("Hosted tool installation", guide)
        self.assertIn("docs/github-actions.md", (ROOT / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
