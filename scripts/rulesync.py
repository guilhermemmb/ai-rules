"""Wrapper for rulesync distribute."""
import subprocess
from pathlib import Path


def run_rulesync(script_dir, logger):
    """
    Run rulesync generate to distribute rules globally.

    Returns True on success, False otherwise.
    """
    logger.debug("Running rulesync distribute")

    script_path = Path(script_dir)
    if not script_path.exists():
        logger.error(f"Script directory not found: {script_dir}")
        return False

    try:
        result = subprocess.run(
            ["rulesync", "generate", "--global"],
            cwd=str(script_path),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"rulesync failed: {result.stderr}")
            return False

        logger.debug(f"rulesync output: {result.stdout}")
        logger.success("Rules distributed via rulesync")
        return True
    except FileNotFoundError:
        logger.error("rulesync command not found")
        return False
    except subprocess.TimeoutExpired:
        logger.error("rulesync timed out")
        return False
    except Exception as e:
        logger.error(f"rulesync failed: {e}")
        return False
