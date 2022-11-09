import datetime
import hashlib
import subprocess
import sys
import tarfile

from pathlib import Path

import license_expression

from pycargoebuild import __version__
from pycargoebuild.license import spdx_to_ebuild

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


EBUILD_TEMPLATE = """\
# Copyright {year} Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

# Autogenerated by pycargoebuild {prog_version}

EAPI=8

CRATES="
{crates}
"

inherit cargo

DESCRIPTION="{description}"
HOMEPAGE="{homepage}"
SRC_URI="
\t$(cargo_crate_uris)
"

LICENSE="{pkg_license}"
# Dependent crate licenses
LICENSE+=" {crate_licenses}"
SLOT="0"
KEYWORDS="~amd64"
"""


def cargo_to_spdx(license_str: str) -> str:
    """
    Convert deprecated Cargo license string to SPDX-2.0, if necessary.
    """
    return license_str.replace("/", " OR ")


def get_ebuild(cargo_toml: dict, cargo_lock: dict, distdir: Path) -> str:
    """
    Get ebuild contents for passed contents of Cargo.toml and Cargo.lock.
    """

    # get package's license
    pkgmeta = cargo_toml["package"]
    spdx = license_expression.get_spdx_licensing()
    assert "license_file" not in pkgmeta
    pkg_license = pkgmeta["license"]
    parsed_pkg_license = spdx.parse(pkg_license, validate=True, strict=True)

    # get crate list from Cargo.lock
    assert cargo_lock["version"] == 3
    deps = [(p["name"], p["version"], p["checksum"])
            for p in cargo_lock["package"]
            if p["name"] != pkgmeta["name"]]
    crates = "\n".join(f"\t{p}-{v}" for p, v, _ in deps)

    # fetch all crates, verify their checksums and grab licenses
    distdir.mkdir(parents=True, exist_ok=True)
    buffer = bytearray(128 * 1024)
    mv = memoryview(buffer)
    crate_licenses = set()
    for p, v, csum in deps:
        path = distdir / f"{p}-{v}.crate"
        if not path.exists():
            url = f"https://crates.io/api/v1/crates/{p}/{v}/download"
            subprocess.check_call(["wget", "-O", path, url])
        with open(path, "rb", buffering=0) as f:
            hasher = hashlib.sha256()
            while True:
                rd = f.readinto(mv)
                if rd == 0:
                    break
                hasher.update(mv[:rd])
            assert hasher.hexdigest() == csum, (
                f"checksum mismatch for {path}, got: {hasher.hexdigest()}, "
                f"exp: {csum}")
        with tarfile.open(path, "r:gz") as crate:
            with crate.extractfile(f"{p}-{v}/Cargo.toml") as tarf:
                crate_toml = tomllib.load(tarf)
                assert "license_file" not in crate_toml["package"]
                crate_licenses.add(
                    cargo_to_spdx(crate_toml["package"]["license"]))

    # build list of (additional) crate licenses
    crate_licenses.discard(pkg_license)
    combined_license = " AND ".join(f"( {x} )" for x in crate_licenses)
    parsed_license = spdx.parse(combined_license, validate=True, strict=True)
    final_license = parsed_license.simplify()

    return EBUILD_TEMPLATE.format(crates=crates,
                                  crate_licenses=spdx_to_ebuild(final_license),
                                  description=pkgmeta.get("description", ""),
                                  homepage=pkgmeta["homepage"],
                                  pkg_license=spdx_to_ebuild(
                                      parsed_pkg_license),
                                  prog_version=__version__,
                                  year=datetime.date.today().year)
