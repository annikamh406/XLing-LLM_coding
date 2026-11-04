#!/usr/bin/env python3
"""Derive 6.1.1 from the preserved 6.1 prompts; do not modify the parent."""
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent
OLD="""The target of negation need not be explicitly mentioned. You may infer an
action or claim when there is adequate evidence in the surrounding context.
If the evidence does not clearly support an interpretation, record
uncertainty.
"""
NEW="""**Use both the child's words and the surrounding context to identify the speech act.**

A child can reject something without first receiving an explicit offer or
instruction. For example, "don't want that" can itself express a rejection.
Not knowing exactly what "that" refers to does not prevent us from recognizing
the refusal.

The same words can also correct a claim or report a preference. Decide what
the child is doing in this exchange: refusing something, correcting what
someone said, or describing how they feel. Do not choose `Denial` simply
because no offer or instruction appears in the transcript.

The target of negation need not be explicitly mentioned. You may infer an
action or claim when there is adequate evidence in the child's utterance and
the surrounding context. If the evidence does not clearly support an
interpretation, record uncertainty.
"""


def revised(text):
    if text.count(OLD)!=1:raise ValueError('Expected one 6.1 inference paragraph')
    return text.replace(OLD,NEW,1).replace('p0061','p00611').replace(
        'v6/Bloom_coding_policy_v5.md','v6/6.1.1/Bloom_coding_policy_v6.md').replace(
        'v6/Bloom_coding_policy_v6.md','v6/6.1.1/Bloom_coding_policy_v6.md')


def main():
    for source in sorted(PARENT.glob('bloom_v6_*prompt*.md')):
        (HERE/source.name).write_text(revised(source.read_text()))
    (HERE/'Bloom_coding_policy_v6.md').write_text(revised((PARENT/'Bloom_coding_policy_v6.md').read_text()))


if __name__=='__main__':main()
