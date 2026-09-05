# Licensing and publication

The owner approved the MIT license for the original agent code and
documentation on 2026-09-05. See the repository [LICENSE](../LICENSE).
Release 2.0.2 includes the license in source and wheel distributions.

Crafter is installed as a dependency, not vendored here. Its source and game
assets are provided by Danijar Hafner's project under its
[MIT license](https://github.com/danijar/crafter/blob/main/LICENSE). NumPy,
Pillow, imageio, opensimplex and ruamel.yaml retain their respective licenses.
The optional Pygame viewer dependency retains its own LGPL license and is
installed separately, not vendored into this package.
No paper PDF, human gameplay archive, neural weights, credentials, or private
machine paths are included in this repository-style folder.

Before pushing publicly:

1. Retain LICENSE and its copyright/permission notice in distributions.
2. Review README, audit, and benchmark caveats; do not call this a 1M-step RL result.
3. Run the tests and evidence verifier using the locked dependency environment.
4. Follow [Publishing](PUBLISHING.md) to attach a remote and push.

No remote repository was created and no upload was performed during packaging.
