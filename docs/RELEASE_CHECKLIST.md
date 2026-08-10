# PEOS v1 release checklist

- [x] Version and lockfile are 1.0.0; MIT license file/metadata are present.
- [x] MAP, PLAN, CONTRIBUTING, recovery/security docs, and ADR 0016 are current.
- [x] Backup tamper/overwrite/fault, migration ruin-gate, and GC TOCTOU/re-reference tests exist.
- [x] Synthetic example backup verifies and contains generated synthetic evidence only.
- [x] Wheel/sdist build; installed executable completes three compilers and SQLite rebuild.
- [x] Final local regression: 222 passed and 1 Windows symlink test skipped for missing privilege;
  static checks, three mypy platforms, build, archive inspection, and isolated acceptance passed.
- [x] Fresh detached-checkout acceptance passed at `2515b48970c745c9cc069275ce0b1613e5d140da`.
- [x] Implementation CI run `31354787204` is GREEN at
  `e7e1213bef82e3b5fe8d1bec9fba3f3b526f210b` (`quality` and `release-smoke`).
- [ ] Final documentation HEAD CI is GREEN.
- [ ] Annotated `v1.0.0` points to final CI-GREEN HEAD and is pushed without force.
- [x] No PyPI, GitHub Release, cloud backup, or other public publication is performed.
