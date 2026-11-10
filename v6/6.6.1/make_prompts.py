#!/usr/bin/env python3
"""Move the V6.6 CHAT guide to the end without changing its text."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.6'
GUIDE = (HERE / 'reading_chat.md').read_text().rstrip() + '\n\n'


def revised(text):
    if text.count(GUIDE) != 1:
        raise ValueError('Expected one unchanged CHAT guide')
    text = text.replace(GUIDE, '').replace('p0066', 'p00661').replace('v6/6.6/', 'v6/6.6.1/')
    return text.rstrip() + '\n\n' + GUIDE.rstrip() + '\n'


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths + [PARENT / 'Bloom_coding_policy_v6.md']:
        (HERE / path.name).write_text(revised(path.read_text()))


if __name__ == '__main__':
    main()
