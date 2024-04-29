import logging
import signal

from iombian_services_handler import IombianServicesHandler

BASE_PATH = "/opt/iombian-services"
WAIT_SECONDS = 1
LOG_LEVEL = "DEBUG"

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s - %(name)-16s - %(message)s", level=LOG_LEVEL
)
logger = logging.getLogger(__name__)


def signal_handler(sig, frame):
    iombian_services_handler.stop()


if __name__ == "__main__":
    iombian_services_handler = IombianServicesHandler(BASE_PATH, WAIT_SECONDS)
    iombian_services_handler.read_local_services()
    iombian_services_handler.start()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.pause()
