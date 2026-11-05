#!/usr/bin/env python3
"""Consolidate the approved 6.2 Rejection/Denial section in all five prompts."""
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
PARENT=HERE.parent/'6.1.1'
SECTION=(HERE/'rejection_denial_section.md').read_text().rstrip()+'\n\n'


def replace_once(text,pattern,replacement):
    output,n=re.subn(pattern,lambda _:replacement,text,flags=re.S)
    if n!=1:raise ValueError(f'Expected one section, found {n}: {pattern}')
    return output


def revised(text):
    # Remove the accumulated uptake, live-move, anaphora, five-trap and
    # imperative decision prose together, rather than adding another caveat.
    text=replace_once(text,r'### Use the participants as your guide\n.*?(?=### Uncoded vs Excluded\n)',SECTION)
    text=text.replace('p00611','p0062').replace('p0061','p0062')
    text=text.replace('v6/6.1.1/Bloom_coding_policy_v6.md','v6/6.2/Bloom_coding_policy_v6.md')
    text=text.replace('v6/Bloom_coding_policy_v5.md','v6/6.2/Bloom_coding_policy_v6.md')
    # Keep the existing examples' labels, but remove rationales that would
    # reintroduce explicit-offer/directive requirements or make uptake decisive.
    text=text.replace('Reason: denies a claim about the child; nothing was offered, so not Rejection.',
        'Reason: corrects a claim about the child; a rejecting function is not reasonably supported in this exchange.')
    text=text.replace('is absent) and not `Rejection` (no directive is being resisted).',
        'is absent). The child is attempting the placement and reporting its failure, rather than opposing it.')
    text=text.replace('Reason: child restates the rule; the agreement response shows it asserts a\nnorm rather than stopping an action.',
        'Reason: child restates the rule in a rule-discussion; no specific action being opposed is reasonably supported. Agreement is supporting evidence, not decisive by itself.')
    text=text.replace('Use `Uncoded` only when at least two functions remain genuinely plausible',
        'If the remaining plausible alternatives are Rejection and Denial, apply the\nRejection-first tie-break above: choose `Rejection` with `certain` = `No`.\nDo not use `Uncoded` for that tie.\n\nUse `Uncoded` only when at least two functions remain genuinely plausible')
    return text


def main():
    for path in sorted(PARENT.glob('bloom_v6_*prompt*.md')):
        (HERE/path.name).write_text(revised(path.read_text()))
    policy=(PARENT/'Bloom_coding_policy_v6.md').read_text()
    policy=replace_once(policy,r'### Literal content versus live discourse move\n.*?(?=### Missing referent is not missing function\n)','')
    policy=replace_once(policy,r'### Interlocutor uptake\n.*?(?=## Required coding fields)',SECTION)
    (HERE/'Bloom_coding_policy_v6.md').write_text(policy)


if __name__=='__main__':main()
