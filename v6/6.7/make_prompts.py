#!/usr/bin/env python3
"""Generate the V6.4 worked-example deletion test."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.4'
REMOVE = ('J', 'K', 'T', 'U', 'X')


def revised(text):
    prefix, examples = text.split('## Examples\n', 1)
    examples, suffix = examples.split('## Batch Input\n', 1)
    for letter in REMOVE:
        examples, count = re.subn(
            rf'^Example {letter}:\n.*?(?=^Example [A-Z]+:|\Z)', '',
            examples, flags=re.M | re.S,
        )
        if count != 1:
            raise ValueError(f'Expected one worked example {letter}')
    text = prefix + '## Examples\n' + examples + '## Batch Input\n' + suffix
    return text.replace('p0064', 'p0067').replace('v6/6.4/', 'v6/6.7/')


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths:
        (HERE / path.name).write_text(revised(path.read_text()))


if __name__ == '__main__':
    main()
