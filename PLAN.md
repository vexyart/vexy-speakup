<!-- this_file: PLAN.md -->
# Plan

1. First release: tag `v0.1.0` on a clean commit, `uv build`, `twine check`,
   upload only after explicit approval.
2. Keep packaging aligned with vexy-subs: hatch-vcs versions, src layout,
   Fire CLI, the same `test.sh` shape and privacy-focused `.gitignore`.
3. Speaker-separation or multitrack input would be needed before overlap can be
   processed per voice; until then overlap stays one mixed fragment.
