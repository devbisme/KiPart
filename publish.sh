#!/usr/bin/env bash
set -euo pipefail

# The version the package reports is the one that gets published, tagged, and
# released, so read it once and use it throughout.
version=$(kipart -v | cut -d' ' -f2)

# Build the distributions and publish them to PyPI. setuptools leaves whatever
# it copied last time in build/, and never removes a file that has since gone
# away, so a deleted one would go on being published from there. Clearing it is
# what keeps a build honest.
rm -f dist/*
rm -rf build
python -m build
python -m twine check dist/*
python -m twine upload --repository pypi dist/*

# Tag the release commit, and push both the branch and the tag.
git tag -f "$version"
git push
git push -f origin "$version"

# Pull this version's notes out of HISTORY.md: the lines between its '## <ver>'
# heading and the next one. index()==1 matches the heading literally, so the
# dots in the version aren't read as a regular expression.
notes=$(awk -v heading="## $version " '
    index($0, heading) == 1 { in_section = 1; next }
    in_section && /^## / { exit }
    in_section { print }
' HISTORY.md)

# Create the GitHub release from the tag, with those notes and the built
# distributions attached.
gh release create "$version" \
    --title "$version" \
    --notes "${notes:-Release $version}" \
    dist/*
