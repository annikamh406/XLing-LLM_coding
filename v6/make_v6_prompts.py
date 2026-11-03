#!/usr/bin/env python3
"""Build the v6 policy, schema and five full English-example prompts from v5."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "v5"

ADDITION = """### Determine what the target negator negates

A negator can negate material in the same clause, or refer back to something
in the interaction: an earlier statement, an offer, or an ongoing or proposed
action.

Transcripts may omit commas and other punctuation. Do not rely on punctuation
to decide whether `no` stands separately or negates the words that follow it.

For example, in "no that's my plate," "that's my plate" may explain why the
child objects to something. It is not necessarily what `no` negates. Use the
surrounding context to identify the target of `no`, then classify its function:

- Resisting an offer or action => `Rejection`.
- Contradicting a claim => `Denial`.

A following adult response may address the child's explanation rather than
the target of `no`. For example, "it is?" may respond to "that's my plate";
it does not by itself establish what the child was negating.

The target of negation need not be explicitly mentioned. You may infer an
action or claim when there is adequate evidence in the surrounding context.
If the evidence does not clearly support an interpretation, record
uncertainty.

For contrast:

- Adult is handling the child's toy. Child: "No, that's mine!" Adult:
  "Yes, it's yours. I'm just putting it away." => `Rejection`: ownership
  explains the objection to handling or putting away the toy.
- Adult: "That's Anna's toy." Child: "No, that's mine!" => `Denial`:
  the child corrects an explicit ownership claim.

"""


def insert_before(text, marker):
    if text.count(marker) != 1:
        raise ValueError(f"Expected exactly one insertion point: {marker!r}")
    return text.replace(marker, ADDITION + marker, 1)


def version(text):
    return text.replace("v5/", "v6/").replace("bloom_v5", "bloom_v6").replace(
        "Bloom v5", "Bloom v6"
    ).replace("p005", "p0061")


def main():
    names = ["bloom_v5_english_prompt.md"]
    for language in ("german", "hebrew", "spanish", "tagalog"):
        names.append(f"bloom_v5_{language}_prompt_english_examples.md")
    for name in names:
        text = version((SOURCE / name).read_text())
        text = insert_before(text, "Five traps to avoid:\n")
        (HERE / name.replace("bloom_v5", "bloom_v6")).write_text(text)

    policy = version((SOURCE / "Bloom_coding_policy_v5.md").read_text())
    policy = policy.replace(
        "Supersedes `bloom_v4` (`v4/Bloom_coding_policy_v4.md`)",
        "Supersedes `bloom_v5` (`v5/Bloom_coding_policy_v5.md`)",
        1,
    ).replace("v6/CHANGES_FROM_V4.md", "v6/CHANGES_FROM_V5.md", 1)
    policy = insert_before(policy, "### Missing referent is not missing function\n")
    (HERE / "Bloom_coding_policy_v6.md").write_text(policy)

    schema = json.loads((SOURCE / "bloom_v5_output.schema.json").read_text())
    schema["$id"] = "bloom_v6_output.schema.json"
    schema["title"] = "Bloom v6 LLM Coding Output"
    schema["description"] = (
        "Strict output schema for multilingual Bloom negation coding, policy "
        "bloom_v6. The output structure is unchanged from bloom_v5; only the "
        "schema version is bumped so v6 runs remain traceable."
    )
    schema["properties"]["schema_version"]["const"] = "bloom_v6"
    (HERE / "bloom_v6_output.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
