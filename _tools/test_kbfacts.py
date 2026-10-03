"""kbfacts.code_pointer: a path whose first segment merely looks like a host is a pointer; a url shape is not."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kbfacts  # noqa: E402


def ptr(note):
    return kbfacts.code_pointer({"note": note})


class TestCodePointer(unittest.TestCase):
    def test_code_pointer_valid_lookalikes(self):
        for note, want in (("Contoso.Web.App/Program.cs#Main", ("Contoso.Web.App/Program.cs", "Main")),
                           ("Foo.Net/Bar.cs#X", ("Foo.Net/Bar.cs", "X")),
                           ("README.org#x", ("README.org", "x")),
                           ("Contoso.Web.App/src/Program.cs#L10-L20", ("Contoso.Web.App/src/Program.cs", "L10-L20")),
                           ("example.com#frag", ("example.com", "frag")),
                           ("www.example.com/a/b#y", ("www.example.com/a/b", "y")),
                           ("src/raw/x.py#f", ("src/raw/x.py", "f")),
                           ("src/and/or.py#f", ("src/and/or.py", "f"))):
            self.assertEqual(ptr(note), want, note)
        # rejected shapes beside them: a scheme-less url (host, then a forge marker) and a prose pair
        for note in ("github.com/org/repo/blob/main/x.py#f", "host.example.com/-/x#f", "gitlab.com/g/p/tree/main#f",
                     "example.org/raw/x#f", "Contoso.Web.App/blob/main/Program.cs#Main", "and/or#x", "his/her#y"):
            self.assertIsNone(ptr(note), note)
        # a rejected shape does not hide a later valid pointer
        self.assertEqual(ptr("github.com/o/r/blob/main/x#y, then Foo.Net/Bar.cs#X"), ("Foo.Net/Bar.cs", "X"))

    def test_code_pointer_other_refusals_stay(self):
        for note in ("https://example.com/a/b.py#f", "src/#f", "adr-new#f", "no pointer here"):
            self.assertIsNone(ptr(note), note)


if __name__ == "__main__":
    unittest.main()
