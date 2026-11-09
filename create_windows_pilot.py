from pathlib import Path
from office_setup import endpoint_package
folder=endpoint_package(Path('C:/CenterEK'),Path(__file__).resolve().parent,'DESKTOP-PLGB96P','https://192.168.1.15:8765')
print('Windows package ready: '+str(folder))
print('Copy only this package to the matching computer. Never paste enrollment contents into chat.')
