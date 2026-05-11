from bs4 import XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from enocean.communicators.serialcommunicator import SerialCommunicator
import queue
import traceback
import sys

PORT = "/dev/ttyUSB0"

communicator = SerialCommunicator(
    port=PORT,
    timeout=0.5   # 🔥 très important
)
communicator.start()

while communicator.is_alive():
    try:
        packet = communicator.receive.get(timeout=1)
        if packet:
            print(packet)

    except queue.Empty:
        continue
    except KeyboardInterrupt:
        print("Interruption clavier")
        break
    except Exception:
        traceback.print_exc(file=sys.stdout)
        break

if communicator.is_alive():
    communicator.stop()
    print("Fin propre du programme")