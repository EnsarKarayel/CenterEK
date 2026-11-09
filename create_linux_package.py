"""Generate a Linux-specific endpoint package on the existing office monitor."""
import argparse
from pathlib import Path
from office_setup import endpoint_package
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root',type=Path,default=Path('C:/CenterEK'))
parser.add_argument('--computer',default='VOLO-PRODDB')
parser.add_argument('--url',default='https://192.168.1.15:8765')
args=parser.parse_args()
folder=endpoint_package(args.root,Path(__file__).resolve().parent,args.computer,args.url,platform='linux')
print('Linux package ready: '+str(folder))
print('Contains a computer-bound enrollment credential. Transfer securely; never paste it into chat or Git.')
