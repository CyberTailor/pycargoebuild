import datetime
import io
import tarfile
import textwrap
import typing

from pathlib import Path

import pytest

from pycargoebuild import __version__
from pycargoebuild.cargo import Crate, FileCrate, GitCrate, PackageMetadata
from pycargoebuild.ebuild import (get_ebuild, update_ebuild,
                                  collapse_whitespace, bash_dquote_escape,
                                  url_dquote_escape,
                                  )


@pytest.fixture(scope="session")
def pkg_meta() -> PackageMetadata:
    return PackageMetadata(name="foo",
                           version="1.2.3",
                           license="Apache-2.0 OR MIT",
                           description="Test package",
                           homepage="https://example.com")


def make_crate(path: Path, cargo_toml: bytes) -> None:
    basename = path.name.removesuffix(".crate").removesuffix(".gh.tar.gz")
    with tarfile.open(path, "x:gz") as tarf:
        tar_info = tarfile.TarInfo(f"{basename}/Cargo.toml")
        tar_info.size = len(cargo_toml)
        tarf.addfile(tar_info, io.BytesIO(cargo_toml))


@pytest.fixture(scope="session")
def crate_dir(tmp_path_factory) -> typing.Generator[Path, None, None]:
    tmp_path = tmp_path_factory.mktemp("crates")
    make_crate(tmp_path / "foo-1.crate", b"""
        [package]
        name = "foo"
        version = "1"
        license = "(BSD-3-Clause OR MIT) AND Unicode-DFS-2016"
    """)
    make_crate(tmp_path / "bar-2.crate", b"""
        [package]
        name = "bar"
        version = "2"
        license = "CC0-1.0 OR Unlicense"
    """)
    make_crate(tmp_path / "baz-3.crate", b"""
        [package]
        name = "baz"
        version = "3"
        license-file = "COPYING"
    """)
    make_crate(tmp_path / ("pycargoebuild-5ace474ad2e92da836de"
                           "60afd9014cbae7bdd481.gh.tar.gz"), b"""
        [package]
        name = "test"
        version = "0.1"
        license = "MIT"
    """)
    yield tmp_path


@pytest.fixture(scope="session")
def crates(crate_dir: Path
           ) -> typing.Generator[typing.List[FileCrate], None, None]:
    yield [FileCrate("foo", "1", ""),
           FileCrate("bar", "2", ""),
           FileCrate("baz", "3", ""),
           ]


@pytest.fixture(scope="session")
def crates_plus_git(crates: typing.List[FileCrate]
                    ) -> typing.Generator[typing.List[Crate], None, None]:
    yield crates + [GitCrate("test", "0.1",
                             "https://github.com/projg2/pycargoebuild",
                             "5ace474ad2e92da836de60afd9014cbae7bdd481")]


def test_get_ebuild(real_license_mapping, pkg_meta, crate_dir, crates):
    assert get_ebuild(pkg_meta, crates, crate_dir) == textwrap.dedent(f"""\
        # Copyright {datetime.date.today().year} Gentoo Authors
        # Distributed under the terms of the GNU General Public License v2

        # Autogenerated by pycargoebuild {__version__}

        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        DESCRIPTION="Test package"
        HOMEPAGE="https://example.com"
        SRC_URI="
        \t${{CARGO_CRATE_URIS}}
        "

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tUnicode-DFS-2016
        \t|| ( BSD MIT )
        \t|| ( CC0-1.0 Unlicense )
        "
        SLOT="0"
        KEYWORDS="~amd64"
    """)


def test_get_ebuild_no_license(real_license_mapping, crate_dir, crates):
    pkg_meta = PackageMetadata(name="foo", version="1.2.3")
    assert get_ebuild(pkg_meta, crates, crate_dir) == textwrap.dedent(f"""\
        # Copyright {datetime.date.today().year} Gentoo Authors
        # Distributed under the terms of the GNU General Public License v2

        # Autogenerated by pycargoebuild {__version__}

        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        DESCRIPTION=""
        HOMEPAGE=""
        SRC_URI="
        \t${{CARGO_CRATE_URIS}}
        "

        LICENSE=""
        # Dependent crate licenses
        LICENSE+="
        \tUnicode-DFS-2016
        \t|| ( BSD MIT )
        \t|| ( CC0-1.0 Unlicense )
        "
        SLOT="0"
        KEYWORDS="~amd64"
    """)


def test_get_ebuild_no_crates(real_license_mapping, pkg_meta):
    assert get_ebuild(pkg_meta, [], Path(".")) == textwrap.dedent(f"""\
        # Copyright {datetime.date.today().year} Gentoo Authors
        # Distributed under the terms of the GNU General Public License v2

        # Autogenerated by pycargoebuild {__version__}

        EAPI=8

        CRATES=""

        inherit cargo

        DESCRIPTION="Test package"
        HOMEPAGE="https://example.com"
        SRC_URI="
        \t${{CARGO_CRATE_URIS}}
        "

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+=""
        SLOT="0"
        KEYWORDS="~amd64"
    """)


def test_get_ebuild_no_crate_license(real_license_mapping, pkg_meta, crate_dir,
                                     crates):
    assert get_ebuild(pkg_meta, crates, crate_dir,
                      crate_license=False) == textwrap.dedent(f"""\
        # Copyright {datetime.date.today().year} Gentoo Authors
        # Distributed under the terms of the GNU General Public License v2

        # Autogenerated by pycargoebuild {__version__}

        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        DESCRIPTION="Test package"
        HOMEPAGE="https://example.com"
        SRC_URI="
        \t${{CARGO_CRATE_URIS}}
        "

        LICENSE="|| ( Apache-2.0 MIT )"
        SLOT="0"
        KEYWORDS="~amd64"
    """)


def test_get_ebuild_git_crates(real_license_mapping, pkg_meta, crate_dir,
                               crates_plus_git):
    assert get_ebuild(pkg_meta, crates_plus_git, crate_dir
                      ) == textwrap.dedent(f"""\
        # Copyright {datetime.date.today().year} Gentoo Authors
        # Distributed under the terms of the GNU General Public License v2

        # Autogenerated by pycargoebuild {__version__}

        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        declare -A GIT_CRATES=(
        \t[test]='https://github.com/projg2/pycargoebuild;5ace474ad2e92da836de60afd9014cbae7bdd481;pycargoebuild-%commit%'
        )

        inherit cargo

        DESCRIPTION="Test package"
        HOMEPAGE="https://example.com"
        SRC_URI="
        \t${{CARGO_CRATE_URIS}}
        "

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
        SLOT="0"
        KEYWORDS="~amd64"
    """)


def test_update_ebuild(real_license_mapping, pkg_meta, crate_dir, crates):
    old_ebuild = textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar-1
        \tbaz-10
        "

        inherit cargo

        SRC_URI="${{CARGO_CRATE_URIS}}"

        LICENSE="MIT"
        # Dependent crate licenses
        LICENSE+=" CC0-1.0"
        SLOT="0"
        KEYWORDS="~amd64 ~x86"
    """)

    assert update_ebuild(old_ebuild, pkg_meta, crates, crate_dir
                         ) == textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        SRC_URI="${{CARGO_CRATE_URIS}}"

        LICENSE="MIT"
        # Dependent crate licenses
        LICENSE+="
        \tUnicode-DFS-2016
        \t|| ( BSD MIT )
        \t|| ( CC0-1.0 Unlicense )
        "
        SLOT="0"
        KEYWORDS="~amd64 ~x86"
    """)


def test_update_ebuild_no_crate_license(real_license_mapping,
                                        pkg_meta, crate_dir,
                                        crates):
    old_ebuild = textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar-1
        \tbaz-10
        "

        inherit cargo

        SRC_URI="${{CARGO_CRATE_URIS}}"

        LICENSE="MIT"
        SLOT="0"
        KEYWORDS="~amd64 ~x86"
    """)

    assert update_ebuild(old_ebuild, pkg_meta, crates, crate_dir,
                         crate_license=False) == textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        SRC_URI="${{CARGO_CRATE_URIS}}"

        LICENSE="MIT"
        SLOT="0"
        KEYWORDS="~amd64 ~x86"
    """)


BAD_UPDATE_TEST_CASES = {
    "empty": "",
    "double-crates": textwrap.dedent("""\
        CRATES=""
        # Dependent crate licenses
        LICENSE+=""
        CRATES=""
    """),
    "no-crates": textwrap.dedent("""\
        # Dependent crate licenses
        LICENSE+=""
    """),
    "double-license": textwrap.dedent("""\
        CRATES=""
        # Dependent crate licenses
        LICENSE+=""
        # Dependent crate licenses
        LICENSE+=""
    """),
    "no-license": textwrap.dedent("""\
        CRATES=""
    """),
    "no-license-comment": textwrap.dedent("""\
        CRATES=""
        LICENSE+=""
    """),
}


@pytest.mark.parametrize("case", BAD_UPDATE_TEST_CASES)
def test_update_ebuild_fail(real_license_mapping, pkg_meta, crate_dir, crates,
                            case):
    with pytest.raises(RuntimeError):
        update_ebuild(BAD_UPDATE_TEST_CASES[case], pkg_meta, crates, crate_dir)


def test_update_ebuild_fail_with_crate_license(real_license_mapping,
                                               pkg_meta, crate_dir, crates):
    with pytest.raises(RuntimeError):
        update_ebuild(textwrap.dedent("""\
                CRATES=""
                # Dependent crate licenses
                LICENSE+=""
            """), pkg_meta, crates, crate_dir, crate_license=False)


def test_update_git_crates(real_license_mapping, pkg_meta, crate_dir,
                           crates_plus_git):
    old_ebuild = textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        declare -A GIT_CRATES=(
        \t[else]='total-junk-here'
        \t[something]='https://github.com/projg2/pycargoebuild;5ace474ad2e92da836de60afd9014cbae7bdd481;pycargoebuild-%commit%'
        )

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
    """)

    assert update_ebuild(old_ebuild, pkg_meta, crates_plus_git, crate_dir
                         ) == textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        declare -A GIT_CRATES=(
        \t[test]='https://github.com/projg2/pycargoebuild;5ace474ad2e92da836de60afd9014cbae7bdd481;pycargoebuild-%commit%'
        )

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
    """)


def test_update_remove_git_crates(real_license_mapping, pkg_meta, crate_dir,
                                  crates):
    old_ebuild = textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        declare -A GIT_CRATES=(
        \t[else]='total-junk-here'
        \t[something]='https://github.com/projg2/pycargoebuild;5ace474ad2e92da836de60afd9014cbae7bdd481;pycargoebuild-%commit%'
        )

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
    """)

    assert update_ebuild(old_ebuild, pkg_meta, crates, crate_dir
                         ) == textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tUnicode-DFS-2016
        \t|| ( BSD MIT )
        \t|| ( CC0-1.0 Unlicense )
        "
    """)


def test_update_add_git_crates(real_license_mapping, pkg_meta, crate_dir,
                               crates_plus_git):
    old_ebuild = textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
    """)

    assert update_ebuild(old_ebuild, pkg_meta, crates_plus_git, crate_dir
                         ) == textwrap.dedent("""\
        EAPI=8

        CRATES="
        \tbar@2
        \tbaz@3
        \tfoo@1
        "

        declare -A GIT_CRATES=(
        \t[test]='https://github.com/projg2/pycargoebuild;5ace474ad2e92da836de60afd9014cbae7bdd481;pycargoebuild-%commit%'
        )

        inherit cargo

        LICENSE="|| ( Apache-2.0 MIT )"
        # Dependent crate licenses
        LICENSE+="
        \tMIT Unicode-DFS-2016
        \t|| ( CC0-1.0 Unlicense )
        "
    """)


def test_collapse_whitespace():
    assert collapse_whitespace("\tfoo  bar \n baz \u00A0") == "foo bar baz"


def test_bash_dquote_escape():
    assert (bash_dquote_escape('my `very` "special" $(package)\\') ==
            r'my \`very\` \"special\" \$(package)\\')


def test_url_dquote_escape():
    assert (url_dquote_escape(
                "https://example.com/\u00A0`tricky \"${whitespace}\"") ==
            "https://example.com/%C2%A0%60tricky+%22%24{whitespace}%22")
