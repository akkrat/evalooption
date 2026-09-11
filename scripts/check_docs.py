"""Check that local Markdown links resolve to files in a clean Git checkout."""
from pathlib import Path
import json
import posixpath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    tracked = set(subprocess.check_output(
        ['git', 'ls-files', '-z'], cwd=root).decode().rstrip('\0').split('\0'))
    directories = {str(parent) for name in tracked for parent in Path(name).parents}
    errors = []
    checked = 0
    for name in sorted(tracked):
        if not name.endswith('.md'):
            continue
        source = (root / name).read_text()
        # Skip code blocks; paths in examples are not navigation links.
        source = re.sub(r'```.*?```', '', source, flags=re.S)
        for match in re.finditer(r'\[[^\]]*\]\(([^)]+)\)', source):
            target = match.group(1).strip().strip('<>')
            url = urlsplit(target)
            if url.scheme or url.netloc:
                continue
            checked += 1
            path = posixpath.normpath(posixpath.join(
                str(Path(name).parent), unquote(url.path))) if url.path else name
            if path not in tracked and path not in directories:
                errors.append(f'{name}: {target} is not in Git')
            elif url.fragment and path.endswith('.md'):
                text = (root / path).read_text()
                headings = re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, re.M)
                anchors = {re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-') for h in headings}
                if unquote(url.fragment) not in anchors:
                    errors.append(f'{name}: missing heading {target}')
    return {'passed': not errors, 'local_links_checked': checked, 'errors': errors}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)
