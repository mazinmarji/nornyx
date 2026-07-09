"""Regression: `on:` (and other YAML 1.1 booleans) must stay string keys.

Plain YAML coerces on/off/yes/no to booleans, which silently dropped the `on`
key in harness repair steps (`- on: test_failure` -> `{True: ...}`). Nornyx
restricts implicit bool resolution to true/false only.
"""
import textwrap

from nornyx.parser import load_nyx


def _write(tmp_path, body: str):
    path = tmp_path / "sample.nyx"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def test_on_key_is_preserved_as_string(tmp_path):
    path = _write(
        tmp_path,
        """
        nornyx: "0.1"
        project:
          name: OnKey
        harnesses:
          - name: H
            repair:
              - on: test_failure
                action: repair
        """,
    )
    data = load_nyx(path)
    repair = data["harnesses"][0]["repair"][0]
    assert "on" in repair
    assert repair["on"] == "test_failure"
    assert True not in repair


def test_yaml_11_booleans_stay_strings(tmp_path):
    path = _write(
        tmp_path,
        """
        nornyx: "0.1"
        project:
          name: Bools
        flags:
          a: on
          b: off
          c: yes
          d: no
          e: true
          f: false
        """,
    )
    flags = load_nyx(path)["flags"]
    assert flags["a"] == "on"
    assert flags["b"] == "off"
    assert flags["c"] == "yes"
    assert flags["d"] == "no"
    # Genuine booleans still coerce.
    assert flags["e"] is True
    assert flags["f"] is False
