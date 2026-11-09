#!/usr/bin/env python3
"""Build V6.3.1 by removing only the V6.3 scope reminder."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.3'
REMINDER = ('**Apply this distinction after checking Nonpossession and Nonexistence.** '
            'Answering a factual question or contradicting a claim does not by itself establish Denial. '
            'If the negation expresses absence, use Nonexistence, even when it also corrects someone.\n\n')


def revised(text):
    if text.count(REMINDER) != 1:
        raise ValueError('Expected exactly one V6.3 scope reminder')
    return text.replace(REMINDER, '').replace('p0063', 'p00631').replace('v6/6.3/', 'v6/6.3.1/')


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths + [PARENT / 'Bloom_coding_policy_v6.md', PARENT / 'rejection_denial_section.md']:
        (HERE / path.name).write_text(revised(path.read_text()))


if __name__ == '__main__':
    main()
