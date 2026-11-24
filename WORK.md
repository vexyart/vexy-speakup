<!-- this_file: WORK.md -->
# Work record

PyPI lists releases 1.0.0 through 1.0.3. Issue 101 acceptance is recorded in
CHANGELOG.md. The original research and listening measurements are in `issues/`.

The fly-january 0.2.1 strict build passed with no warnings. All 16 HTML pages
referenced the theme assets. The full pytest run recorded 113 passes and one
failure because the sandbox denied `ps` in the cancellation test (86% coverage).
Ruff passed.

Release housekeeping passed shell syntax, actionlint and strict documentation
checks. Both distributions passed twine. Fresh wheel and sdist installs each
reported `1.0.4.dev2+g0c89be06d.d20261124` when invoked outside the checkout.
