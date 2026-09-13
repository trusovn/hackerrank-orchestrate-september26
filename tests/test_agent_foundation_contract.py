import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE_AGENT_DOCS = (
    Path("AGENTS.md"),
    Path(".agents/workflow.md"),
    Path("docs/project-map.md"),
    Path("docs/diagnostics.md"),
)
AGENT_NAVIGATION_DOCS = AUTHORITATIVE_AGENT_DOCS + (
    Path("code/buy_or_wait/README.md"),
)
REQUIRED_AGENT_PATHS = AGENT_NAVIGATION_DOCS + (Path("problem_statement.md"),)
REQUIRED_ROOT_LINKS = {
    ".agents/workflow.md",
    "docs/project-map.md",
    "docs/diagnostics.md",
    "problem_statement.md",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def local_link_targets(document: Path) -> list[str]:
    targets = []
    for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
        target = target.strip().strip("<>")
        if target.startswith(("https://", "http://", "mailto:", "#")):
            continue
        targets.append(target.split("#", 1)[0])
    return targets


class AgentFoundationContractTests(unittest.TestCase):
    def test_required_agent_documents_exist(self) -> None:
        for relative_path in REQUIRED_AGENT_PATHS:
            with self.subTest(path=relative_path):
                self.assertTrue((REPO_ROOT / relative_path).is_file(), relative_path)

    def test_root_instructions_link_to_authoritative_documents(self) -> None:
        targets = set(local_link_targets(REPO_ROOT / "AGENTS.md"))
        self.assertTrue(
            REQUIRED_ROOT_LINKS.issubset(targets),
            f"missing AGENTS.md links: {sorted(REQUIRED_ROOT_LINKS - targets)}",
        )

    def test_local_links_in_agent_navigation_documents_resolve(self) -> None:
        for relative_document in AGENT_NAVIGATION_DOCS:
            document = REPO_ROOT / relative_document
            if not document.is_file():
                continue
            for target in local_link_targets(document):
                if target.startswith("/"):
                    resolved = REPO_ROOT / target.lstrip("/")
                else:
                    resolved = document.parent / target
                with self.subTest(document=relative_document, target=target):
                    self.assertTrue(resolved.exists(), resolved)


if __name__ == "__main__":
    unittest.main()
