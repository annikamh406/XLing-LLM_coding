#!/usr/bin/env python3
"""Build V6.4 from V6.3.1: Denial last, plus an absence-as-correction example."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / '6.3.1'

OLD_DEFINITION = '- **Denial:** the child is correcting a claim, answering a factual question, or describing how things are, without a reasonably supported rejecting function.'
NEW_DEFINITION = '- **Denial is a last-resort content category.** Use it when the child negates a factual claim and none of the more specific categories—`Nonpossession`, `Nonexistence`, or `Rejection`—fits. Correcting someone, answering a question, or making a factual statement does not by itself establish Denial: those same conversational moves can express absence, lack of possession, or rejection.'
OLD_ORDER = '''4. **Then Denial:** use `Denial` for a truth claim only after
   `Nonpossession`, `Nonexistence`, and `Rejection` have been ruled out.
   `Denial` is the residual content label, not the default for every
   declarative-looking negative sentence.'''
NEW_ORDER = '''4. **Denial last:** choose `Denial` only after checking that
   `Nonpossession`, `Nonexistence`, and `Rejection` do not fit. Being able to
   paraphrase the utterance as a negative factual statement is not sufficient.'''
OLD_EXAMPLE = '''Context: Caregiver opens fridge, expected milk is gone. Child says: `No milk.`
Target: `no`

Prediction: `Nonexistence`; all flags `No`.
Reason: expected referent is absent.'''
NEW_EXAMPLE = '''Context: Adult: `there's still milk in the fridge.` The child looks inside
and says: `No, there isn't any.`
Target: `no`

Prediction: `Nonexistence`; all flags `No`.
Reason: the child says the expected milk is absent. This also corrects the
adult's claim, but correcting someone does not make the category Denial.'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected exactly one passage: {old[:70]}')
    return text.replace(old, new)


def revised(text):
    text = replace_once(text, OLD_DEFINITION, NEW_DEFINITION)
    text = replace_once(text, OLD_ORDER, NEW_ORDER)
    text = replace_once(text, OLD_EXAMPLE, NEW_EXAMPLE)
    return text.replace('p00631', 'p0064').replace('v6/6.3.1/', 'v6/6.4/')


def main():
    paths = sorted(PARENT.glob('bloom_v6_*prompt*.md'))
    if len(paths) != 5:
        raise ValueError('Expected five source prompts')
    for path in paths:
        (HERE / path.name).write_text(revised(path.read_text()))
    section = replace_once((PARENT/'rejection_denial_section.md').read_text(), OLD_DEFINITION, NEW_DEFINITION)
    (HERE/'rejection_denial_section.md').write_text(section)
    policy = replace_once((PARENT/'Bloom_coding_policy_v6.md').read_text(), OLD_DEFINITION, NEW_DEFINITION)
    policy = replace_once(policy,
        '7. Choose `Denial` when the main function of the negation is to assert that some proposition is false (or to affirm a negative proposition), and `Nonpossession`, `Nonexistence`, and `Rejection` do not apply.',
        '7. **Denial last:** choose `Denial` only after checking that `Nonpossession`, `Nonexistence`, and `Rejection` do not fit. Being able to paraphrase the utterance as a negative factual statement is not sufficient.')
    (HERE/'Bloom_coding_policy_v6.md').write_text(policy)


if __name__ == '__main__':
    main()
