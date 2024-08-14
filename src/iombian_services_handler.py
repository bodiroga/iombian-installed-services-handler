import logging
import os
import pathlib
import threading
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
    local_service_state_change_callback: callable
    """Callback function to be called when a service state changes"""
    mode: str
    """Mode of the installation process: 'online' (based on Firebase) or 'offline' (based on folder events)"""

    def __init__(self, base_path: str, wait_seconds: float, local_service_state_change_callback: callable=lambda _: None):
        self.base_path = base_path
        self.wait_seconds = wait_seconds
        self.local_service_state_change_callback = local_service_state_change_callback
        self.observer = None
        self.mode = "offline"
        self.services = []

    def set_mode(self, mode: str):
        """Set the handler mode: 'online' or 'offline'"""
        logger.debug(f"Setting mode to '{mode}'")
        self.mode = mode

    def start(self):
        """Start the handler by starting the observer of the "iombian-services" folder."""
        logger.debug(f"IoMBian Services Handler started.")
        if self.mode == "offline":
            self.observer = Observer()
            self.observer.schedule(self, self.base_path)
            self.observer.start()

    def stop(self):
        """Stop the handler by stopping the observer of the "iombian-services" folder.

        Also stop all of the services in the "iombian-services" folder, but not the composes.
        """
        logger.debug("IoMBian Services Handler stopped.")
        if self.observer:
            self.observer.stop()
        for service in self.services:
            service.stop()

    def read_local_services(self):
        """Read the services in "iombian-services", start them and add them to the `services` list."""
        logger.debug("Reading local services")
        self.services = []
        service_names = os.listdir(self.base_path)
        logger.debug(f"{len(service_names)} local services detected")
        for service_name in service_names:
            service_path = f"{self.base_path}/{service_name}"
            service = InstalledServiceHandler(
                service_path, self.wait_seconds, self.on_local_service_state_changed)
            service.start(self.mode)
            self.services.append(service)

    def start_service(self, service_name: str):
        """Start a service by it's name: up
        
        Method exposed so that external programs can interact with the services.
        """
        service = self._get_service_by_name(service_name)
        if service:
            service.reload_compose_services()
            return
        service_path = "/".join([self.base_path, service_name])
        service = InstalledServiceHandler(
            service_path, self.wait_seconds, self.on_local_service_state_changed)
        service.up_compose_services()
        service.start(self.mode)
        self.services.append(service)

    def reconfigure_service(self, service_name: str):
        """Reconfigure a service by it's name: stop and up
        
        Method exposed so that external programs can interact with the services.
        """
        service = self._get_service_by_name(service_name)
        if service:
            service.stop_compose_services()
            service.up_compose_services()

    def delete_service(self, service_name: str):
        """delete a service by it's name: stop, down and clean
        
        Method exposed so that external programs can interact with the services.
        """
        service = self._get_service_by_name(service_name)
        if service:
            service.stop()
            service.down_compose_services(remove_images=True)
            service.clean_compose_services()
            self.services.remove(service)

    def on_created(self, event: FileSystemEvent):
        """When a new service is added to "iombian-services", start the service and the compose of the services.

        A service is added when a folder is created in the "iombian-services" folder.
        """
        if not isinstance(event, DirCreatedEvent):
            return

        service_path = event.src_path
        service_name = pathlib.Path(service_path).stem
        logger.debug(f"{service_name} service folder was created.")
        service = InstalledServiceHandler(
            service_path, self.wait_seconds, self.on_local_service_state_changed)
        service.up_compose_services()
        service.start(self.mode)
        self.services.append(service)
        logger.debug(f"{service_path} service added.")

    def on_deleted(self, event: FileSystemEvent):
        """When a service is removed from "iombian-services", stop the service and the compose of the services.

        A service is removed when a folder is deleted from the "iombian-services" folder.
        """
        if not isinstance(event, DirDeletedEvent):
            return

        service_name = pathlib.Path(event.src_path).stem
        logger.debug(f"{service_name} service folder was removed.")
        service = self._get_service_by_name(service_name)
        if service:
            service.stop()
            service.clean_compose_services()
            self.services.remove(service)
            logger.debug(f"{service_name} service removed.")

    def on_local_service_state_changed(self, service_name: str, new_state: str):
        """Called when a local service changes it's state.

        :param service_name:
            Name of the service that changed it's state.
        :type event:
            :class:`str`
        :param new_state:
            New state of the service.
        :type event:
            :class:`str`
        """
        if self.local_service_state_change_callback:
            threading.Thread(target=self.local_service_state_change_callback, args=[service_name, new_state]).start()

    def _get_service_by_name(self, service_name: str):
        """Given the service name, return the service in "iombian-services"."""
        for service in self.services:
            if service.service_name == service_name:
                return service
