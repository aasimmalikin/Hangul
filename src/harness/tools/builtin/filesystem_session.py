"""Wrap MCP filesystem tools so every path argument is forced inside the caller's
session folder. Isolation becomes structural: the agent cannot read or write
outside data/sessions/<session_id>/, no matter what path it sends. This is the
same closure pattern as the session-aware search_docs tool."""

from pathlib import Path
from harness.tools.base import Tool

_SESSIONS_ROOT = Path("data/sessions")

# arguments that carry a single path, and ones that carry a list of paths
_PATH_ARGS = {"path", "source", "destination"}
_PATH_LIST_ARGS = {"paths"}


def _force_into_session(raw_path: str, session_dir: Path) -> str:
    """Rewrite any path to live inside session_dir, keeping only its final name.

    'notes.txt'            -> <session_dir>/notes.txt
    '.'  or ''             -> <session_dir>            (list/read the folder itself)
    '/mnt/session/a.txt'   -> <session_dir>/a.txt      (invented paths are neutralized)
    'sub/dir/file.txt'     -> <session_dir>/file.txt   (dirs stripped)
    """
    if not raw_path or raw_path in (".", "./", session_dir.name):
        return str(session_dir)
    name = Path(raw_path).name
    if not name or name in (".", ".."):
        return str(session_dir)
    return str(session_dir / name)


def wrap_filesystem_tool(tool: Tool, session_id: str) -> Tool:
    session_dir = (_SESSIONS_ROOT / session_id).resolve()
    session_dir.mkdir(parents=True, exist_ok=True)
    original = tool.handler

    async def handler(**kwargs) -> str:
        # rewrite every path-bearing argument into the session folder
        for k in list(kwargs.keys()):
            v = kwargs[k]
            if k in _PATH_ARGS and isinstance(v, str):
                kwargs[k] = _force_into_session(v, session_dir)
            elif k in _PATH_LIST_ARGS and isinstance(v, list):
                kwargs[k] = [_force_into_session(p, session_dir)
                             for p in v if isinstance(p, str)]
        # if the model sent no path at all, default to the session folder
        if not any(k in kwargs for k in (_PATH_ARGS | _PATH_LIST_ARGS)):
            kwargs["path"] = str(session_dir)
        return await original(**kwargs)

    return Tool(
        name=tool.name,
        description=tool.description,
        parameter=tool.parameter,
        handler=handler,
    )
