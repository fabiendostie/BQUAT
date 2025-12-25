# Versioning

This repository follows Semantic Versioning (SemVer 2.0.0).

## Policy

- Version format: MAJOR.MINOR.PATCH
- Breaking changes increment MAJOR.
- Backward-compatible features increment MINOR.
- Backward-compatible fixes increment PATCH.

## Conventional Commits mapping

- feat: MINOR
- fix: PATCH
- feat!: MAJOR (breaking)
- fix!: MAJOR (breaking)
- Other types (chore, docs, ci, test) do not change version by themselves.

## Source of truth

- Version is stored in the root `VERSION` file.
- Release notes live in `CHANGELOG.md` and must include the current VERSION entry.
- Releases should tag the repository with the same version string.
- Release notes must reference the VERSION value and summarize changes.
