.PHONY: typecheck test

typecheck:
	uv ty check .

test:
	uv run pytest -v
