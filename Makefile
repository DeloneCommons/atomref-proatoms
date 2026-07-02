.PHONY: docs-build docs-serve

docs-build:
	NO_MKDOCS_2_WARNING=1 mkdocs build

docs-serve:
	NO_MKDOCS_2_WARNING=1 mkdocs serve
