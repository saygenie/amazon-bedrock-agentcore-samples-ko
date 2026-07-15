"""Python 코드와 셸 명령을 비대화형으로 실행하는 사용자 지정 도구입니다.

비대화형 환경(Jupyter 노트북, CI/CD 등)에서는 실패하는 대화형 터미널 승인이
필요한 strands_tools.shell을 대체합니다.
"""

import os
import subprocess
import sys
import tempfile
import traceback

from strands import tool


@tool
def python_exec(code: str, working_dir: str = "") -> str:
    """Execute Python code and return the output.

    Use this tool to run Python scripts. The code runs in a separate Python
    process so all installed packages are available.

    Args:
        code: Python code to execute.
        working_dir: Optional directory to cd into before execution.

    Returns:
        Captured stdout/stderr output, or error traceback.
    """
    try:
        cwd = working_dir or None
        if working_dir:
            os.makedirs(working_dir, exist_ok=True)

        # 코드를 임시 파일에 작성하고 하위 프로세스에서 실행
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=cwd) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        try:
            result = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                cwd=cwd,
                timeout=120,
            )
            output = result.stdout + result.stderr
            return output.strip() or "Code executed successfully (no output)."
        finally:
            os.unlink(tmp_path)

    except subprocess.TimeoutExpired:
        return "Error: Code execution timed out after 120 seconds."
    except Exception:
        return f"Error:\n{traceback.format_exc()}"


@tool
def run_shell(command: str, working_dir: str = "") -> str:
    """Execute a shell command without interactive approval.

    Use this for non-Python commands (e.g. ls, pip install, etc.).

    Args:
        command: Shell command to execute.
        working_dir: Optional working directory.

    Returns:
        Command stdout/stderr output.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,  # nosec B602 - 이 도구에서는 의도적으로 shell=True 사용
            capture_output=True,
            text=True,
            cwd=working_dir or None,
            timeout=120,
        )
        output = result.stdout + result.stderr
        return output.strip() or "Command executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 120 seconds."
    except Exception:
        return f"Error:\n{traceback.format_exc()}"
