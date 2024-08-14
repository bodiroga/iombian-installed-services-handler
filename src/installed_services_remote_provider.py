#!/usr/bin/env python3

from firestore_client_handler import FirestoreClientHandler
import logging
import threading

from google.cloud.firestore_v1 import DocumentSnapshot
from google.cloud.firestore_v1.watch import ChangeType, DocumentChange
from proto.datetime_helpers import DatetimeWithNanoseconds
from typing import List

logger = logging.getLogger(__name__)


class InstalledServicesRemoteProvider(FirestoreClientHandler):

    RESTART_DELAY_TIME_S = 0.5

    def __init__(self, api_key: str, project_id: str, refresh_token: str, device_id: str, connection_state_change_callback: callable=lambda _: None, service_state_change_callback: callable=lambda _: None):
        super().__init__(api_key, project_id, refresh_token)
        self.device_id = device_id
        self.connection_state_change_callback = connection_state_change_callback
        self.service_state_change_callback = service_state_change_callback
        self.start_timeout_timer = None
        self.device = None
        self.watch = None

    def start(self, timeout: int=0):
        logger.debug("Starting IoMBian Installed Services Remote Provider")
        if timeout > 0:
            self.start_timeout_timer = threading.Timer(interval=timeout, function=self.connection_state_change_callback, args=["timeout"])
            self.start_timeout_timer.start()
        self.initialize_client()

    def stop(self):
        logger.debug("Stopping IoMBian Installed Services Remote Provider")
        if self.watch is not None:
            self.watch.unsubscribe()
        self.device = None
        self.stop_client()

    def restart(self):
        """Restart the Installed Services Remote Provider by calling `stop()` and `start()`."""
        self.stop()
        self.start()

    def on_client_initialized(self):
        """Callback function when the client is initialized."""
        logger.debug("Firestore client initialized")
        if self.start_timeout_timer:
            self.start_timeout_timer.cancel()
            self.start_timeout_timer = None
        threading.Thread(target=self.connection_state_change_callback, args=["connected"]).start()
        self.device = (
            self.client.collection("users")
            .document(self.user_id)
            .collection("devices")
            .document(self.device_id)
        )
        self.watch = self.device.collection("installed_services").on_snapshot(
            self._on_installed_service_change
        )

    def on_server_not_responding(self):
        """Callback function when the server is not responding."""
        logger.error("Firestore server not responding")
        threading.Timer(self.RESTART_DELAY_TIME_S, self.restart).start()
        threading.Thread(target=self.connection_state_change_callback, args=["disconnected"]).start()         

    def on_token_expired(self):
        """Callback function when the token is expired."""
        logger.debug("Refreshing Firebase client token id")
        threading.Timer(self.RESTART_DELAY_TIME_S, self.restart).start()

    def update_remote_service_status(self, service_name: str, service_status: str):
        """Given the service name and a status, update the service status in firebase."""
        logger.debug(
            f"Updating '{service_name}' service status to {service_status} in Firebase")
        service_reference = self.device.collection("installed_services").document(
            service_name
        )
        try:
            service_reference.update({"status": service_status})
        except:
            logger.warning(f"The '{service_name}' service is not installed in Firebase, status cannot be updated")

    def _on_installed_service_change(
        self,
        snapshots: List[DocumentSnapshot],
        changes: List[DocumentChange],
        read_time: DatetimeWithNanoseconds,
    ):
        """For each change in the installed services collection, check the status field and act accordingly.

        Here is the list of the status values that should be handled:
            - downloaded: the installation information is downloaded to the device.
            - to-be-uninstalled: the user has indicated that the service should be uninstalled.
        """
        for change in changes:
            service_snapshot = change.document
            service_name = service_snapshot.id

            if change.type == ChangeType.REMOVED:
                 continue

            service_status = service_snapshot.to_dict().get("status")

            logger.debug(
                f"Firebase notification received for '{service_name}' service ({service_status})")
  
            if not service_status:
                logger.error(f"'{service_name}' service does not have any status in Firebase")
                continue

            if service_status in ["downloaded", "reconfigured", "updated", "to-be-updated", "to-be-uninstalled"]:
                threading.Thread(target=self.service_state_change_callback, args=[service_name, service_status]).start()
