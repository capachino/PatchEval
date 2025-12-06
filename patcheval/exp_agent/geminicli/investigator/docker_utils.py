import logging
import shutil
import subprocess
import uuid
from pathlib import Path


logger = logging.getLogger(__name__)


def extract_workspace_from_image(docker_image_name: str, workspace_dest: Path):
    """
    Extracts the /workspace directory from a Docker image to a local path.
    """
    logger.info(
        "Extracting '/workspace' from docker image '%s' to '%s'...",
        docker_image_name,
        workspace_dest,
    )
    container_name = f"extractor-{uuid.uuid4().hex}"

    try:
        logger.info("Creating temporary container '%s'...", container_name)
        subprocess.run(
            ["docker", "create", "--name", container_name, docker_image_name],
            check=True, capture_output=True, text=True,
        )

        logger.info("Copying /workspace from container...")
        if workspace_dest.exists():
            logger.info("Removing existing destination directory: %s", workspace_dest)
            shutil.rmtree(workspace_dest)

        subprocess.run(
            ["docker", "cp", f"{container_name}:/workspace", str(workspace_dest)],
            check=True, capture_output=True, text=True,
        )

        logger.info("Successfully extracted '/workspace' to '%s'.", workspace_dest)
    finally:
        logger.info("Removing temporary container '%s'...", container_name)
        cleanup_process = subprocess.run(
            ["docker", "rm", container_name], capture_output=True, text=True
        )
        if cleanup_process.returncode != 0 and "No such container" not in cleanup_process.stderr:
            logger.warning(
                "Failed to remove temporary container '%s': %s",
                container_name,
                cleanup_process.stderr,
            )
        elif cleanup_process.returncode == 0:
             logger.info("Temporary container removed.")