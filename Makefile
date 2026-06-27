.PHONY: install test check generate context evidence

install:
	pip install -e ".[dev]"

test:
	pytest

check:
	nornyx check examples/governed_delivery_control_plane.nyx

generate:
	nornyx generate examples/governed_delivery_control_plane.nyx --out generated/governed_delivery_control_plane

context:
	nornyx context-build examples/governed_delivery_control_plane.nyx --repo . --out generated/context_pack.json

evidence:
	nornyx evidence-pack --out generated/evidence
