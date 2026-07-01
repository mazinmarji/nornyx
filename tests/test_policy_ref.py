"""Policy `ref`: a contract references a canonical policy instead of copying it."""

from __future__ import annotations

import pytest

from nornyx.checker import check_document, has_errors
from nornyx.parser import NornyxParseError, load_nyx

SERVICE = """\
nornyx: "0.1"
project:
  name: RefService
policies:
  - name: SafeDeliveryPolicy
    ref: {ref}
agents:
  - name: Builder
    role: "Implement scoped patches."
    policy: SafeDeliveryPolicy
"""

NYX_SOURCE = """\
nornyx: "0.1"
project:
  name: OrgPolicies
policies:
  - name: SafeDeliveryPolicy
    rules:
      - deny secrets_to_llm
      - require tests_if_code_changed
      - require human_approval_before_merge
"""

MANIFEST_SOURCE = """\
workspace: Org
policies:
  SafeDeliveryPolicy:
    - deny secrets_to_llm
    - require tests_if_code_changed
    - require human_approval_before_merge
"""

RESOLVED = [
    "deny secrets_to_llm",
    "require tests_if_code_changed",
    "require human_approval_before_merge",
]


def _write(tmp_path, service_ref, source_name, source_text):
    (tmp_path / source_name).write_text(source_text, encoding="utf-8")
    contract = tmp_path / "service.nyx"
    contract.write_text(SERVICE.format(ref=service_ref), encoding="utf-8")
    return contract


def test_ref_resolves_from_nyx_source(tmp_path):
    contract = _write(tmp_path, "org.nyx#SafeDeliveryPolicy", "org.nyx", NYX_SOURCE)
    doc = load_nyx(contract)
    policy = doc["policies"][0]
    assert policy["rules"] == RESOLVED
    assert "ref" not in policy  # compiled away
    assert not has_errors(check_document(doc))


def test_ref_resolves_from_workspace_manifest(tmp_path):
    contract = _write(
        tmp_path, "org.workspace.yaml#SafeDeliveryPolicy", "org.workspace.yaml", MANIFEST_SOURCE
    )
    doc = load_nyx(contract)
    assert doc["policies"][0]["rules"] == RESOLVED


def test_generated_policy_carries_resolved_rules(tmp_path):
    from nornyx.generator import generate_artifacts

    contract = _write(tmp_path, "org.nyx#SafeDeliveryPolicy", "org.nyx", NYX_SOURCE)
    out = tmp_path / "gen"
    generate_artifacts(load_nyx(contract), out)
    policy_yaml = (out / "policy.yaml").read_text(encoding="utf-8")
    for rule in RESOLVED:
        assert rule in policy_yaml
    assert "ref:" not in policy_yaml  # the artifact is inline, not a ref


def test_editing_the_source_updates_every_referencing_contract(tmp_path):
    contract = _write(tmp_path, "org.nyx#SafeDeliveryPolicy", "org.nyx", NYX_SOURCE)
    assert load_nyx(contract)["policies"][0]["rules"] == RESOLVED
    # Change the single source; the referencing contract reflects it with no edit.
    (tmp_path / "org.nyx").write_text(
        NYX_SOURCE + "      - require changelog_updated\n", encoding="utf-8"
    )
    assert "require changelog_updated" in load_nyx(contract)["policies"][0]["rules"]


def test_backward_compatible_inline_policy_untouched(tmp_path):
    contract = tmp_path / "inline.nyx"
    contract.write_text(NYX_SOURCE, encoding="utf-8")  # no ref anywhere
    doc = load_nyx(contract)
    assert doc["policies"][0]["rules"] == RESOLVED


@pytest.mark.parametrize(
    "ref, needle",
    [
        ("missing.nyx#SafeDeliveryPolicy", "ref source not found"),
        ("org.nyx#DoesNotExist", "not found in org.nyx"),
        ("no-hash-here", "must be '<path>#<PolicyName>'"),
    ],
)
def test_ref_errors_are_clear(tmp_path, ref, needle):
    (tmp_path / "org.nyx").write_text(NYX_SOURCE, encoding="utf-8")
    contract = tmp_path / "service.nyx"
    contract.write_text(SERVICE.format(ref=ref), encoding="utf-8")
    with pytest.raises(NornyxParseError) as exc:
        load_nyx(contract)
    assert needle in str(exc.value)


def test_ref_and_rules_together_is_rejected(tmp_path):
    (tmp_path / "org.nyx").write_text(NYX_SOURCE, encoding="utf-8")
    contract = tmp_path / "service.nyx"
    contract.write_text(
        'nornyx: "0.1"\n'
        "project:\n  name: X\n"
        "policies:\n"
        "  - name: SafeDeliveryPolicy\n"
        "    ref: org.nyx#SafeDeliveryPolicy\n"
        "    rules: [deny secrets_to_llm]\n",
        encoding="utf-8",
    )
    with pytest.raises(NornyxParseError) as exc:
        load_nyx(contract)
    assert "either 'ref' or 'rules'" in str(exc.value)
