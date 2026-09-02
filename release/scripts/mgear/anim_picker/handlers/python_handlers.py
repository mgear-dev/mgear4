import functools

import mgear


@functools.lru_cache(maxsize=512)
def _compile(cmd):
    """Compile a script string to a cached code object.

    ``exec`` of a string recompiles the whole source every call, which is
    costly for scripts embedding large literals. Caching the compiled code
    keyed by the source means a given script compiles at most once per Maya
    session (reused across the init pass, clicks, custom menus, ...).

    Args:
        cmd (str): The script source to compile.

    Returns:
        code: The compiled code object.
    """
    return compile(cmd, "<anim_picker_action>", "exec")


def safe_code_exec(cmd, env=None):
    """Safely execute code in new namespace with specified dictionary"""
    if not cmd:
        return
    if env is None:
        env = {}
    try:
        exec(_compile(cmd), env)
    except Exception as e:
        mgear.log(
            "anim_picker: custom action failed: {}".format(e),
            mgear.sev_error,
        )
