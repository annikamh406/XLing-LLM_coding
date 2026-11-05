#!/usr/bin/env python3
"""Build V6.3 from V6.2 with the approved scope and example revisions."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.2'
SECTION = (HERE / 'rejection_denial_section.md').read_text().rstrip() + '\n\n'


def replace_once(text, pattern, replacement):
    output, count = re.subn(pattern, lambda _: replacement, text, flags=re.S)
    if count != 1:
        raise ValueError(f'Expected one match, found {count}: {pattern}')
    return output


def revised(text):
    text = replace_once(
        text, r'### Rejection versus Denial\n.*?(?=### Uncoded vs Excluded\n)', SECTION
    )
    text = text.replace('p0062', 'p0063').replace('v6/6.2/', 'v6/6.3/')
    # Replace the worked examples too, so they do not retain the ambiguous
    # imperative/rule and failed-placement contrasts from earlier versions.
    text = replace_once(text, r'Example K:\n.*?(?=Example L:\n)', """Example K:

Context: Caregiver asks: `what is the rule about the sofa?`
Child: `we don't jump on it.`
Target: `don't`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: child answers a question about a rule; the exchange supports reporting
the rule rather than directing someone's behavior.

""")
    text = replace_once(text, r'Example T:\n.*?(?=Example U:\n)', """Example T:

Context: Child tries putting a puzzle piece into a slot and says:
`it doesn't fit. Help me.`
Target: `doesn't`

Prediction: `Denial`; `certain` `Yes`; all flags `No`.
Reason: child reports difficulty and seeks help with the attempt. Nothing is
absent, so this is not `Nonexistence`. If an exchange reasonably supports both
reporting a placement problem and opposing the placement, prefer `Rejection`
and set `certain` to `No`.

""")
    return text


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError(f'Expected five source prompts, found {len(paths)}')
    for path in paths:
        (HERE / path.name).write_text(revised(path.read_text()))
    policy = (PARENT / 'Bloom_coding_policy_v6.md').read_text()
    policy = replace_once(
        policy, r'### Rejection versus Denial\n.*?(?=## Required coding fields)', SECTION
    )
    (HERE / 'Bloom_coding_policy_v6.md').write_text(policy.replace('p0062', 'p0063'))


if __name__ == '__main__':
    main()
