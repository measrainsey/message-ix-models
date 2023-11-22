from typing import Dict

try:
    # ixmp 3.8.0 and later
    from ixmp.util import maybe_check_out, maybe_commit, parse_url
except ImportError:
    # ixmp <= 3.7.0
    from ixmp.utils import (  # type: ignore [no-redef]  # noqa: F401
        maybe_check_out,
        maybe_commit,
        parse_url,
    )


def rename_dims() -> Dict[str, str]:
    """Access :data:`.ixmp.report.common.RENAME_DIMS`.

    This provides backwards-compatibility with ixmp versions 3.7.0 and earlier. It can
    be removed when message-ix-models no longer supports versions of ixmp older than
    3.8.0.
    """
    try:
        # ixmp 3.8.0 and later
        import ixmp.report.common
    except ImportError:
        # ixmp <= 3.7.0
        import ixmp.reporting.util  # type: ignore [import-not-found]

        return ixmp.reporting.util.RENAME_DIMS
    else:
        return ixmp.report.common.RENAME_DIMS
