#!/usr/bin/env python3
"""Build V6.6 from V6.4 with only the approved CHAT-reading guide added."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.4'
GUIDE = (HERE/'reading_chat.md').read_text().rstrip() + '\n\n'


def insert_once(text, anchor):
    if text.count(anchor) != 1:
        raise ValueError(f'Expected exactly one insertion anchor: {anchor}')
    return text.replace(anchor, GUIDE + anchor)


def revised(text):
    text = insert_once(text, '### Align and interpret the target occurrence\n')
    return text.replace('p0064', 'p0066').replace('v6/6.4/', 'v6/6.6/')


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths:
        (HERE/path.name).write_text(revised(path.read_text()))
    policy = insert_once((PARENT/'Bloom_coding_policy_v6.md').read_text(),
                         '### Target occurrence alignment and contextual reconstruction\n')
    (HERE/'Bloom_coding_policy_v6.md').write_text(policy)
    (HERE/'rejection_denial_section.md').write_text((PARENT/'rejection_denial_section.md').read_text())


if __name__ == '__main__':
    main()
