# Versioning

This project uses semantic versioning (SemVer).

## Version Format

`MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## How to Bump Version

```bash
# Patch (1.0.0 → 1.0.1)
python bump_version.py patch

# Minor (1.0.0 → 1.1.0)
python bump_version.py minor

# Major (1.0.0 → 2.0.0)
python bump_version.py major
```

## Deployment

1. Bump version before deploying
2. Commit and push
3. DigitalOcean will deploy automatically
4. Check version in dashboard footer

## Current Version

See `VERSION` file or check dashboard footer.
