"""Local office connection wizard: test ESXi, preserve secrets, prepare per-PC agents."""
import argparse
import copy
import datetime
import importlib.util
import json
from pathlib import Path
import queue
import shutil
import ssl
import subprocess
import sys
import threading
from urllib.parse import urlsplit
from file_security import restrict
import service_secrets
import connectors

AGENT_FILES = ('Collect-EndpointSessions.ps1', 'Send-Report.ps1', 'Setup-Agent.ps1',
               'Install-SystemTask.ps1', 'Run-SystemTask.ps1', 'Install-EndpointPilot.ps1')


def inspect_certificate(host, output):
    """Discovery only: no HTTP/authentication and never an automatic trust change."""
    import hashlib
    pem = ssl.get_server_certificate((host,443),timeout=8)
    der = ssl.PEM_cert_to_DER_cert(pem)
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(pem,encoding='ascii')
    return {'sha256':hashlib.sha256(der).hexdigest(), 'sha1':hashlib.sha1(der).hexdigest(), 'path':str(output)}


def save_esxi(root, entries, protector=service_secrets.protect, probe=connectors.esxi):
    """Test all selected connections before modifying config or encrypted secrets."""
    root = Path(root).resolve()
    path = root/'config.local.json'
    original = path.read_bytes()
    config = json.loads(original.decode('utf-8-sig'))
    selected = {device['id']: device for device in config['devices']}
    if not entries:
        raise ValueError('Select at least one server')
    encrypted = root/'data/secure/service-secrets.local.json'
    secrets_original = encrypted.read_bytes() if encrypted.exists() else None
    payload = json.loads(secrets_original.decode('utf-8-sig')) if secrets_original else {'schema':1,'environment':{}}
    if payload.get('schema') != 1 or not isinstance(payload.get('environment'), dict):
        raise ValueError('Unsupported background credential file')
    results, seen = [], set()
    for entry in entries:
        device = selected[entry['id']]
        if entry['id'] in seen or 'esxi' not in (str(device.get('name',''))+' '+str(device.get('kind',''))).lower():
            raise ValueError('Invalid/duplicate ESXi selection')
        seen.add(entry['id'])
        if not entry.get('username') or not entry.get('password'):
            raise ValueError('Username and password are required')
        prefix = 'CENTEREK_'+''.join(c if c.isalnum() else '_' for c in device['id']).upper()
        settings = {'type':'esxi','port':443,'username_env':prefix+'_USERNAME','password_env':prefix+'_PASSWORD'}
        if entry.get('ca_file'):
            ca = Path(entry['ca_file']).resolve()
            if not ca.is_file(): raise ValueError('Trusted PEM certificate file not found')
            settings['ca_file'] = str(ca)
        values = probe(device, dict(settings, _credentials={'username':entry['username'],'password':entry['password']}))
        results.append({'host':device['host'],'memory_total_gb':values.get('memory_total_gb'), 'datastores':len(values.get('datastores',[]))})
        payload['environment'][settings['username_env']] = protector(entry['username'])
        payload['environment'][settings['password_env']] = protector(entry['password'])
        device['collector'] = settings
    # Reject concurrent edits instead of overwriting another administrator's work.
    if path.read_bytes() != original or (encrypted.read_bytes() if encrypted.exists() else None) != secrets_original:
        raise RuntimeError('Configuration changed; reopen the wizard')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = root/('config.esxi-'+stamp+'.local.json')
    backup.write_bytes(original); restrict(backup)
    encrypted.parent.mkdir(parents=True,exist_ok=True);restrict(encrypted.parent,directory=True)
    if secrets_original is not None:
        backup = encrypted.with_name('service-secrets.'+stamp+'.local.json')
        backup.write_bytes(secrets_original);restrict(backup)
    # Publish encrypted credentials first: the old configuration still works if
    # publishing the new config fails. Existing FortiGate ciphertext is untouched.
    temporary = encrypted.with_name('service-secrets.esxi.tmp')
    with temporary.open('x',encoding='utf-8') as output:
        restrict(temporary);json.dump(payload,output)
    temporary.replace(encrypted)
    temporary = path.with_name('config.esxi.tmp')
    with temporary.open('x',encoding='utf-8') as output:
        restrict(temporary);json.dump(config,output,ensure_ascii=False,indent=2)
    temporary.replace(path)
    return results


def endpoint_package(root, assets, computer, url, platform='windows'):
    root, assets = Path(root).resolve(), Path(assets).resolve()
    parsed = urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('Exact HTTPS office origin required')
    # Import the existing office registry; no new account or inbound port.
    sys.path.insert(0,str(root))
    import agents, monitor
    computer = agents.host(computer)
    network = json.loads((root/'server.local.json').read_text(encoding='utf-8-sig'))
    certificate = Path(network['tls_cert'])
    if not certificate.is_absolute(): certificate = root/certificate
    ca = certificate.parent/'panel-ca.pem'
    if not ca.is_file(): raise ValueError('Office panel CA was not found')
    if platform not in ('windows','linux'): raise ValueError('Unsupported endpoint platform')
    files = AGENT_FILES if platform=='windows' else ('linux_collector.py','install_linux_agent.py')
    for name in files:
        if not (assets/name).is_file(): raise ValueError('Missing agent component: '+name)
    folder = assets/'packages'/computer
    if folder.exists(): raise ValueError('Existing package preserved')
    store = monitor.Store(root/'data/monitor.sqlite3')
    registry = agents.Registry(store,root)
    record = None
    try:
        if any(row['computer']==computer and row['kind']=='endpoint' for row in registry.list()):
            raise ValueError('Existing endpoint registration preserved; use its existing protected enrollment')
        folder.mkdir(parents=True);restrict(folder,directory=True)
        record = registry.register(computer,'endpoint')
        record['url'] = url.rstrip('/')
        record['platform'] = platform
        for name in files: shutil.copy2(assets/name,folder/name)
        shutil.copy2(ca,folder/'panel-ca.pem')
        output=folder/'enrollment.local.json'
        with output.open('x',encoding='utf-8') as destination:
            restrict(output);json.dump(record,destination)
        return folder
    except Exception:
        if record: registry.revoke(record['id'])
        raise
    finally: store.db.close()


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('C:/CenterEK'))
    args=parser.parse_args()
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('Run the connection wizard as administrator')
    root=args.root.resolve();assets=Path(__file__).resolve().parent
    config=json.loads((root/'config.local.json').read_text(encoding='utf-8-sig'))
    window=tk.Tk();window.title('CenterEK - Sunucu ve bilgisayar baglantilari');window.geometry('1000x590')
    frame=ttk.Frame(window,padding=18);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='ESXi: RAM / CPU / datastore olcumleri',font=('Segoe UI',15,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Parolalar yalnizca bu sunucuda DPAPI ile saklanir. HTTPS sertifika dogrulamasi aciktir.').pack(anchor='w',pady=8)
    grid=ttk.Frame(frame);grid.pack(fill='x');fields=[]
    for index,title in enumerate(('Sec','Sunucu','Kullanici','Parola','Guvenilen CA PEM (bos: sistem deposu)')):ttk.Label(grid,text=title).grid(row=0,column=index,sticky='w',padx=4)
    for index,device in enumerate([d for d in config['devices'] if 'esxi' in (str(d.get('name',''))+' '+str(d.get('kind',''))).lower()],1):
        enabled=tk.BooleanVar(value=True);user=tk.StringVar();password=tk.StringVar();ca=tk.StringVar(value=device.get('collector',{}).get('ca_file',''))
        ttk.Checkbutton(grid,variable=enabled).grid(row=index,column=0)
        ttk.Label(grid,text=device['host']).grid(row=index,column=1,padx=4)
        ttk.Entry(grid,textvariable=user,width=18).grid(row=index,column=2,padx=4)
        ttk.Entry(grid,textvariable=password,show='*',width=22).grid(row=index,column=3,padx=4)
        ttk.Entry(grid,textvariable=ca,width=40).grid(row=index,column=4,padx=4)
        ttk.Button(grid,text='...',command=lambda target=ca:target.set(filedialog.askopenfilename(filetypes=[('PEM certificates','*.pem *.cer'),('All','*.*')]))).grid(row=index,column=5)
        def certificate(target=device):
            try:
                info=inspect_certificate(target['host'],assets/'discovered-certs'/(target['host']+'.untrusted.pem'))
                messagebox.showinfo('Sertifika - otomatik guvenilmez', 'SHA256: '+info['sha256']+'\n\nSHA1: '+info['sha1']+'\n\n'+info['path']+'\n\nBu sertifika yalnizca agdan okundu. Parmak izini ESXi yonetim ekranindaki sertifikayla bagimsiz dogrulamadan guvenilen CA olarak secmeyin. Bu islem parola gondermedi ve Windows guven deposunu degistirmedi.')
            except Exception as error:messagebox.showerror('Sertifika okunamadi',type(error).__name__)
        ttk.Button(grid,text='Sertifika',command=certificate).grid(row=index,column=6,padx=4)
        fields.append((device,enabled,user,password,ca))
    state=tk.StringVar(value='Giris bilgilerini doldurup test edin. Sertifika hatasinda guvenilen PEM dosyasini secin.')
    ttk.Label(frame,textvariable=state,wraplength=940).pack(anchor='w',pady=12)
    events=queue.Queue()
    def save():
        entries=[{'id':d['id'],'username':u.get(),'password':p.get(),'ca_file':c.get()} for d,e,u,p,c in fields if e.get()]
        save_button.configure(state='disabled');state.set('Baglantilar test ediliyor; henuz ayarlar degistirilmedi...')
        def work():
            try:
                result=save_esxi(root,entries)
                proc=subprocess.run(['powershell.exe','-NoProfile','-File',str(assets/'Restart-OfficeMonitor.ps1'),'-Root',str(root)],capture_output=True,timeout=50)
                if proc.returncode:events.put(('restart',None))
                else:events.put(('ok',result))
            except Exception as error:events.put(('error',type(error).__name__))
            finally:
                for item in entries:item['password']=''
        threading.Thread(target=work,daemon=True).start()
    save_button=ttk.Button(frame,text='Baglantilari test et, kaydet ve izlemeyi yenile',command=save);save_button.pack(anchor='w')
    ttk.Separator(frame).pack(fill='x',pady=18)
    ttk.Label(frame,text='Windows bilgisayar: acik kullanici / IP / RAM / disk',font=('Segoe UI',13,'bold')).pack(anchor='w')
    pc=tk.StringVar(value='DESKTOP-PLGB96P');url=tk.StringVar(value='https://192.168.1.15:8765')
    row=ttk.Frame(frame);row.pack(anchor='w',pady=8)
    ttk.Entry(row,textvariable=pc,width=28).pack(side='left',padx=4)
    ttk.Entry(row,textvariable=url,width=38).pack(side='left',padx=4)
    def package():
        try:
            folder=endpoint_package(root,assets,pc.get().strip(),url.get().strip())
            messagebox.showinfo('Paket hazir',str(folder)+'\nBu klasoru hedef bilgisayara kopyalayin. Yonetici PowerShell ile Install-EndpointPilot.ps1 dosyasini calistirin. Anahtar dosyasini paylasmayin.')
        except Exception as error:
            messagebox.showerror('Paket olusturulamadi',str(error) if isinstance(error,ValueError) else type(error).__name__)
    ttk.Button(row,text='Bu bilgisayar icin ajan paketi olustur',command=package).pack(side='left',padx=4)
    ttk.Label(frame,text='Her bilgisayar icin ayri paket olusturulur. Linux kaynaklari bu Windows ajaniyla toplanmaz.',wraplength=940).pack(anchor='w')
    def poll():
        try:
            kind,result=events.get_nowait();save_button.configure(state='normal')
            if kind=='ok':
                for _,_,_,password,_ in fields:password.set('')
                state.set('Kaydedildi; monitor yeniden baslatildi. Olcumler sonraki toplama turunda Azure dashboarda aktarilir.')
            elif kind=='restart':state.set('Ayarlar kaydedildi; monitor gorevi otomatik yenilenemedi. CenterEK-Server-System gorevini yeniden baslatin.')
            else:state.set('Baglanti testi basarisiz ('+result+'). Ayarlar degistirilmedi. Kullanici/yetki, pyvmomi kurulumu ve HTTPS CA/isim uyumunu kontrol edin.')
        except queue.Empty:pass
        window.after(250,poll)
    poll();window.mainloop()

if __name__=='__main__':main()
