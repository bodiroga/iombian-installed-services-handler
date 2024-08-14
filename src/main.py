import logging
import os
import signal

from communication_module import CommunicationModule
from installed_services_remote_provider import InstalledServicesRemoteProvider
from iombian_services_handler import IombianServicesHandler

CONFIG_HOST = os.environ.get("CONFIG_HOST", "127.0.0.1")
CONFIG_PORT = int(os.environ.get("CONFIG_PORT", 5555))
BASE_PATH = os.environ.get("BASE_PATH", "/opt/iombian-services")
WAIT_SECONDS = int(os.environ.get("WAIT_SECONDS", 1))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s - %(name)-16s - %(message)s", level=LOG_LEVEL
)
logger = logging.getLogger(__name__)


def on_remote_connection_state_changed(state: str):
    logger.debug(f"New remote connection state: {state}")
    if state == "connected":
        iombian_services_handler.set_mode("online")
        iombian_services_handler.read_local_services()
        iombian_services_handler.start()
    elif state == "timeout":
        logger.warning("The remote connection timeout, start the services handler in 'offline' mode")
        iombian_services_handler.read_local_services()
        iombian_services_handler.start()


def on_local_service_state_changed(service_name: str, new_state: str):
    logger.debug(f"New state for local service: {service_name}: {new_state}")
    if iombian_services_remote_provider:
        iombian_services_remote_provider.update_remote_service_status(service_name, new_state)


def on_remote_service_state_changed(service_name: str, new_state: str):
    logger.debug(f"New state for remote service: {service_name}: {new_state}")
    if new_state == "downloaded":
        logger.info(f"'{service_name}' service downloaded, starting it...")
        iombian_services_handler.start_service(service_name)
    elif new_state == "reconfigured":
        logger.info(f"'{service_name}' service reconfigured, starting it...")
        iombian_services_handler.reconfigure_service(service_name)
    elif new_state == "updated":
        logger.info(f"'{service_name}' service updated, starting it...")
        iombian_services_handler.start_service(service_name)
    elif new_state == "to-be-updated":
        # Stopping the service and removing the images is needed before the old files are removed
        logger.info(f"'{service_name}' service to be updated, starting it...")
        iombian_services_handler.delete_service(service_name)
    elif new_state == "to-be-uninstalled":
        logger.info(f"'{service_name}' service to be uninstalled, stopping it...")
        iombian_services_handler.delete_service(service_name)
        if iombian_services_remote_provider:
            iombian_services_remote_provider.update_remote_service_status(service_name, "to-be-removed")


def signal_handler(sig, frame):
    logger.info("Stopping IoMBian Installed Services Handler Service")
    iombian_services_handler.stop()
    if iombian_services_remote_provider:
        iombian_services_remote_provider.stop()


if __name__ == "__main__":
    logger.info("Starting IoMBian Installed Services Handler Service")

    comm_module = CommunicationModule(host=CONFIG_HOST, port=CONFIG_PORT)
    comm_module.start()

    api_key = str(comm_module.execute_command("get_api_key"))
    project_id = str(comm_module.execute_command("get_project_id"))
    refresh_token = str(comm_module.execute_command("get_refresh_token"))
    device_id = str(comm_module.execute_command("get_device_id"))

    iombian_services_handler = IombianServicesHandler(
            BASE_PATH, WAIT_SECONDS, on_local_service_state_changed)
    
    if not (api_key and project_id and refresh_token and device_id):
        logger.warning(
            "Wasn't able to get the necessary information from the config file handler"
        )
        iombian_services_handler.read_local_services()
        iombian_services_handler.start()
    else:
        iombian_services_remote_provider = InstalledServicesRemoteProvider(api_key, project_id, refresh_token, device_id, on_remote_connection_state_changed, on_remote_service_state_changed)
        iombian_services_remote_provider.start(timeout=30)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.pause()
