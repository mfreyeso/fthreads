.PHONY: typecheck test

typecheck:
	uv run ty check .

test:
	uv run pytest -v
