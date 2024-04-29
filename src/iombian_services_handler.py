import logging
import os
from typing import List

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from installed_service_handler import InstalledServiceHandler

logger = logging.getLogger(__name__)


class IombianServicesHandler(FileSystemEventHandler):
    """Handler of the "iombian-services" folder.

    When a folder is created, creates an `InstalledServiceHandler` for that service.
    """

    base_path: str
    """Full path of the "iombian-services" folder"""
    wait_seconds: float
    """Seconds waited between changes on the service before restarting the service"""
    observer: BaseObserver
    """The `Observer` of the "iombian-services" folder"""
    services: List[InstalledServiceHandler]
    """List of the `InstalledServiceHandler` on the "iombian-services" folder"""

    def __init__(self, base_path: str, wait_seconds: float) -> None:
        self.base_path = base_path
        self.wait_seconds = wait_seconds
        self.observer = Observer()
        self.services = []

    def start(self):
        """Start the handler by starting the observer of the "iombian-services" folder."""
        logger.info("IoMBian Installed Services Handler started.")
        self.observer.schedule(self, self.base_path)
        self.observer.start()

    def stop(self):
        """Stop the handler by stopping the observer of the "iombian-services" folder.

        Also stop all of the services in the "iombian-services" folder, but not the composes.
        """
        logger.info("IoMBian Installed Services Handler stopped.")
        self.observer.stop()
        for service in self.services:
            service.stop()

    def read_local_services(self):
        """Read the services in "iombian-services", start them and add them to the `services` list."""
        self.services = []
        service_names = os.listdir(self.base_path)
        for service_name in service_names:
            service_path = f"{self.base_path}/{service_name}"
            service = InstalledServiceHandler(service_path, self.wait_seconds)
            service.start()
            self.services.append(service)

    def on_created(self, event: FileSystemEvent):
        """When a new service is added to "iombian-services", start the service and the compose of the services.

        A service is added when a folder is created in the "iombian-services" folder.
        """
        if not isinstance(event, DirCreatedEvent):
            return

        service_name = event.src_path
        service = InstalledServiceHandler(service_name, self.wait_seconds)
        service.up()
        service.start()
        self.services.append(service)
        logger.debug(f"{service_name} service added.")

    def on_deleted(self, event: FileSystemEvent):
        """When a service is removed from "iombian-services", stop the service and the compose of the services.

        A service is removed when a folder is deleted from the "iombian-services" folder.
        """
        if not isinstance(event, DirDeletedEvent):
            return

        service_name = event.src_path
        service = self._get_service_by_name(service_name)
        if service:
            service.stop()
            service.down()
            self.services.remove(service)
            logger.debug(f"{service_name} service removed.")

    def _get_service_by_name(self, service_name: str):
        """Given the service name, return the service in "iombian-services"."""
        for service in self.services:
            if service.service_name == service_name:
                return service
