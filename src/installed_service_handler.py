import logging
import os
import pathlib
from threading import Timer, Thread
from typing import List, Optional

from python_on_whales import DockerClient, docker
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

logger = logging.getLogger(__name__)


class InstalledServiceHandler(FileSystemEventHandler):
    """Handler of a service on the "iombian-services" folder.

    When a change occurs on the service the compose restarts.
    """

    ACCEPTED_FILES = ["docker-compose.yaml", "docker-compose.yml", ".env"]
    ACCEPTED_EVENTS = ["modified", "created", "deleted"]

    service_path: str
    """The full path of the service"""
    service_name: str
    """The name of the service"""
    wait_seconds: float
    """Seconds to wait between changes before restarting the service compose"""
    timer: Optional[Timer]
    """The timer used for waiting the `wait_seconds` time"""
    observer: BaseObserver
    """The `Observer` of the service folder"""
    files: List[str]
    """The list of the files in the service folder"""
    docker: Optional[DockerClient]
    """The docker client of the service compose"""

    def __init__(self, service_path: str, wait_seconds: float, service_state_change_callback: callable=lambda _: None):
        self.service_path = service_path
        self.service_name = service_path.split("/")[-1]
        self.wait_seconds = wait_seconds
        self.service_state_change_callback = service_state_change_callback
        self.timer = None
        self.observer = None
        self.files = os.listdir(service_path)
        self.docker = self._get_docker()

    def start(self, mode: str="offline"):
        """Start the handler by starting the observer of the service folder."""
        logger.debug(f"Starting '{self.service_name}' Installed Service Handler.")
        try:
            if not self.is_running():
                logger.error(f"Service '{self.service_name}' is not running, starting it up")
                self.up_compose_services()
            if mode == "offline":
                self.observer = Observer()
                self.observer.schedule(self, self.service_path, recursive=True)
                self.observer.start()
        except FileNotFoundError:
            logger.error(
                f"Couldn't start a watcher for the {self.service_name} service, the folder no longer exists."
            )
            self.down_compose_services()
            self.clean_compose_services()

    def stop(self):
        """Stop the handler by stopping the observer of the service folder."""
        logger.debug(f"Stopping '{self.service_name}' Installed Service Handler.")
        if self.observer:
            self.observer.stop()

    def up_compose_services(self):
        """Start the services of the compose file by executing "docker compose pull" and "docker compose up"."""
        if not self.docker:
            return
        try:
            Thread(target=self.service_state_change_callback, args=[self.service_name, "pulling"]).start()
            self.docker.compose.pull()
            Thread(target=self.service_state_change_callback, args=[self.service_name, "starting"]).start()
            self.docker.compose.up(detach=True, pull="never")
            Thread(target=self.service_state_change_callback, args=[self.service_name, "started"]).start()
            logger.info(f"'{self.service_name}' compose services started.")
        except Exception as e:
            logger.error(
                f"An error occurred, couldn't start service {self.service_name}: {e}."
            )
            Thread(target=self.service_state_change_callback, args=[self.service_name, "unknown"]).start()

    def down_compose_services(self, remove_images: bool = False):
        """Shut down the services of the compose file by executing "docker compose down"."""
        if not self.docker:
            return
        self.docker.compose.down(remove_images="all" if remove_images else None)
        logger.info(f"'{self.service_name}' compose services downed.")

    def stop_compose_services(self):
        """Stop the services of the compose file by executing "docker compose stop"."""
        if not self.docker:
            return
        self.docker.compose.stop()
        logger.info(f"'{self.service_name}' compose services stopped.")

    def clean_compose_services(self):
        """Clean the services of the compose file.

        This is done by getting the containers started by the compose file and killing them.
        The volumes are pruned to remove any unused ones.

        This is done like this because, when the service folder is removed and, as such, the compose
        file no longer exists, "docker compose down" can not be directly called.
        """
        if not self.docker:
            return
        containers = self.docker.ps(
            filters={
                "label": f"com.docker.compose.project.config_files={self.service_path}/{self.compose_file}"
            }
        )
        for container in containers:
            docker.container.stop(container)
            docker.container.remove(container)

        docker.volume.prune()
        logger.info(f"'{self.service_name}' compose services cleaned.")

    def reload_compose_services(self):
        """Stop the compose, get the docker client again and start the compose.

        The docker client is loaded again because, if the compose file is changed, the docker client will not be valid.
        """
        if not (self.docker and self.compose_file):
            return

        logger.debug(f"{self.service_name} service modified.")

        self.down_compose_services()
        self.docker = self._get_docker()
        self.up_compose_services()

        self.timer = None

    def is_running(self):
        """Check if the service is running"""
        running_services = self.docker.compose.ls()
        for running_service in running_services:
            if running_service.name == self.service_name and running_service.running == 1:
                return True
        return False

    def on_any_event(self, event: FileSystemEvent):
        """Reload the service when the service changes.

        The service changes when the docker-compose file or the .env file changes in the first level of the folder.

        """
        if event.is_directory:
            return

        path = pathlib.Path(event.src_path)
        file = path.name
        folder = path.parts[-2]

        if (
            file in self.ACCEPTED_FILES
            and folder == self.service_name
            and event.event_type in self.ACCEPTED_EVENTS
        ):
            if self.timer:
                self.timer.cancel()
                self.timer = None

            self.timer = Timer(self.wait_seconds, self.reload_compose_services)
            self.timer.start()

    def _get_compose_file_name(self):
        """Get the name of the compose file in the service.

        This can be "docker-compose.yaml" of "docker-compose.yml".
        """
        if "docker-compose.yaml" in self.files:
            return "docker-compose.yaml"
        elif "docker-compose.yml" in self.files:
            return "docker-compose.yml"

    def _get_docker(self):
        """Get the docker client of the compose of the service."""
        self.compose_file = self._get_compose_file_name()
        if self.compose_file:
            return DockerClient(
                compose_files=[f"{self.service_path}/{self.compose_file}"]
            )
