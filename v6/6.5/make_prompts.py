#!/usr/bin/env python3
"""Build V6.5: contrast rejecting current play with reporting a preference."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.4'
OLD = '''**A report about a preference**

Adult: "What foods don't you like?"
Child: "I don't like carrots."

→ `Denial` when the exchange concerns the child's preferences and there is no reasonably supported refusal of carrots in the situation.'''
NEW = '''**A preference answer that rejects the current interaction**

Adult is showing the child a toy duck and making it quack.
Adult: "Do you like this?"
Child: "No."
Adult: "Okay, sorry," and stops.

→ `Rejection`: the child's answer functions as an objection to the toy or play. Although the question asks about liking, the exchange concerns whether to continue the current interaction. Reporting a preference and rejecting something can happen in the same utterance.

**A report about a preference**

Adult: "Which animals do you like?"
Child: "I don't like ducks."

→ `Denial`: the child reports a preference in a discussion about animals; the exchange does not reasonably support rejecting a particular toy or activity.'''


def revised(text):
    if text.count(OLD) != 1:
        raise ValueError('Expected exactly one preference-report example')
    return text.replace(OLD, NEW).replace('p0064', 'p0065').replace('v6/6.4/', 'v6/6.5/')


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths + [PARENT/'Bloom_coding_policy_v6.md', PARENT/'rejection_denial_section.md']:
        (HERE/path.name).write_text(revised(path.read_text()))


if __name__ == '__main__':
    main()
