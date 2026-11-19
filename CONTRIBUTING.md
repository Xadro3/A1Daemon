# Contributing

0.5.0 prioritizes a small working prototype, maintainable installation and clear limitations. New hardware workarounds need exact board/device matching, a source reference, a reproduction, validation and an uninstall path. Monitor upstream issues before duplicating a fix. Do not silently reset controllers/audio or change a kernel/BIOS setting.

Run `python -m unittest discover -s tests -v`, `node tests/test_adapter.cjs`, `node tests/test_navigation.cjs`, and JavaScript syntax checks. Linux is required for the complete sysfs/setup fixtures. Run `python packaging/build_release.py` to create the clean source archive and checksummed PKGBUILD. Build the native package with makepkg as a regular user, then create the graphical setup archive with `python packaging/build_release.py --package <package-file>`.

Changes to privileged APIs require validation/authorization tests. Installer changes require failure/rollback and uninstall tests. GUI changes require controller and keyboard checks. Include real test evidence and limitations in pull requests, and avoid claims of support for untested distributions. Preserve user changes and package-manager ownership.

This project is MIT licensed. Contributions must be original or carry compatible attribution/license information. Do not copy kernel, HHD, InputPlumber or Steam code into the runtime without reviewing its license. We currently use existing OS interfaces and an original Steam adapter; there are no vendored third-party runtime libraries.
