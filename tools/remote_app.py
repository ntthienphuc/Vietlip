"""Pinned SSH transport for the authorized application training workstation."""
from pathlib import Path
import argparse
import base64
import subprocess

HOST='PC@100.97.93.24'
REMOTE_ROOT='D:/Lip_App_Window_20261107'
OPTIONS=['-i',r'C:\Users\thien\.ssh\id_ed25519','-o','BatchMode=yes',
    '-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes',
    '-o',r'UserKnownHostsFile=E:\Project\Lip\Unified_PR_2026-11-02\Followup_Review_2026-11-02\work\known_hosts',
    '-o','ConnectTimeout=10','-o','ServerAliveInterval=30']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('mode',choices=['run','put','get'])
    p.add_argument('source')
    p.add_argument('target',nargs='?')
    p.add_argument('--timeout',type=int,default=60)
    args=p.parse_args()
    if args.mode=='run':
        script=Path(args.source).read_text(encoding='utf-8-sig')
        script="$ProgressPreference='SilentlyContinue'\n"+script
        encoded=base64.b64encode(script.encode('utf-16le')).decode()
        command=['ssh','-T',*OPTIONS,HOST,'powershell -NoProfile -NonInteractive -EncodedCommand '+encoded]
    else:
        remote=args.target if args.mode=='put' else args.source
        if not remote.startswith(REMOTE_ROOT+'/') or '..' in remote.split('/'):
            raise ValueError('Transfers must stay under the app training root')
        command=['scp','-q',*OPTIONS]
        command+=([str(Path(args.source).resolve()),HOST+':'+remote] if args.mode=='put'
                  else [HOST+':'+remote,str(Path(args.target).resolve())])
    result=subprocess.run(command,timeout=args.timeout)
    raise SystemExit(result.returncode)

if __name__=='__main__':main()
