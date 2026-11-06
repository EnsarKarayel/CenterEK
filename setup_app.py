"""Frozen Windows setup UI and background application entry point."""
import argparse
import json
import os
from pathlib import Path
import queue
import socket
import sys
import threading
import webbrowser


def assets_root():
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))


def serve(root, remaining):
    import monitor
    monitor.ROOT = Path(root).resolve()
    os.chdir(monitor.ROOT)
    os.environ['CENTEREK_RUN_MODE'] = 'background'
    logs = monitor.ROOT / 'data/logs'
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / 'application.log'
    if path.exists() and path.stat().st_size > 5 * 1024**2:
        path.replace(path.with_suffix('.log.1'))
    sys.stdout = sys.stderr = path.open('a', encoding='utf-8', buffering=1)
    sys.argv = ['CenterEK', *remaining]
    monitor.main()


def self_test(report):
    import tempfile
    import auth
    import connectors
    import monitor
    import service_secrets
    from cryptography import x509
    from pyVmomi import vim
    result = {'runtime': sys.version.split()[0], 'frozen': bool(getattr(sys, 'frozen', False)), 'checks': {}}
    store = monitor.Store(':memory:')
    try:
        accounts = auth.Auth(store)
        accounts.add_user('self-test', 'temporary-self-test-pass', 'admin')
        token, error = accounts.login('self-test', 'temporary-self-test-pass', 'local')
        result['checks']['authentication'] = error is None and accounts.user(token)['role'] == 'admin'
        result['checks']['snmpv3'] = connectors.snmp_auth({'version': '3', '_credentials': {
            'username': 'test', 'auth_password': 'test-auth-long', 'privacy_password': 'test-privacy-long'}}).security_level == 'authPriv'
        result['checks']['esxi_sdk'] = bool(vim.HostSystem)
        result['checks']['dpapi'] = service_secrets.unprotect(service_secrets.protect('ephemeral-check')) == 'ephemeral-check'
        result['checks']['assets'] = all((assets_root() / 'web' / name).is_file() for name in
                                        ('index.html', 'app.js', 'dashboard.js', 'i18n.js', 'theme.css'))
        with tempfile.TemporaryDirectory() as temporary:
            import tls_setup
            output = Path(temporary) / 'certs'
            tls_setup.create(output, 'localhost', ['127.0.0.1'])
            cert = x509.load_pem_x509_certificate((output / 'panel-cert.pem').read_bytes())
            result['checks']['certificate'] = cert.subject is not None
    finally:
        store.db.close()
    result['ok'] = all(result['checks'].values())
    Path(report).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1


WORDS = {
 'tr': ('CenterEK Kurulum', 'Temiz kurulum · Windows 10/11, Server 2019+ · x64', 'Kurulum klasörü', 'Yönetici kullanıcı adı', 'Yönetici parolası', 'Parola tekrar', 'Panel portu', 'Erişim', 'Yalnızca bu bilgisayar', 'Yerel ağ (LAN)', 'LAN IP adresi', 'Panel DNS adı', 'Bu bilgisayarın ölçüm ajanını kur', 'Bu bilgisayarda AD/DNS ajanını da kur (AD modülü gerekir)', 'Üretilen yerel CA sertifikasına Windows’ta güven', 'LAN için Private/Domain profillerinde yerel subnet erişimine izin ver', 'Kur', 'Paneli aç', 'Kurulum tamamlandı', 'Parolalar eşleşmiyor.', 'Kurulum sürüyor; tamamlanmasını bekleyin.'),
 'en': ('CenterEK Setup', 'Fresh install · Windows 10/11, Server 2019+ · x64', 'Installation folder', 'Administrator username', 'Administrator password', 'Repeat password', 'Panel port', 'Access', 'This computer only', 'Local network (LAN)', 'LAN IP address', 'Panel DNS name', 'Install monitoring agent on this computer', 'Also install AD/DNS agent here (AD module required)', 'Trust the generated local CA in Windows', 'Allow local-subnet access on Private/Domain profiles for LAN', 'Install', 'Open panel', 'Installation completed', 'Passwords do not match.', 'Installation is running; please wait.'),
 'fr': ('Installation CenterEK', 'Installation neuve · Windows 10/11, Server 2019+ · x64', 'Dossier d’installation', 'Identifiant administrateur', 'Mot de passe administrateur', 'Répéter le mot de passe', 'Port du panneau', 'Accès', 'Cet ordinateur uniquement', 'Réseau local (LAN)', 'Adresse IP LAN', 'Nom DNS du panneau', 'Installer l’agent sur cet ordinateur', 'Installer aussi l’agent AD/DNS ici (module AD requis)', 'Approuver la CA locale générée dans Windows', 'Autoriser le sous-réseau local sur les profils Privé/Domaine', 'Installer', 'Ouvrir le panneau', 'Installation terminée', 'Les mots de passe ne correspondent pas.', 'Installation en cours ; veuillez patienter.'),
 'de': ('CenterEK Einrichtung', 'Neuinstallation · Windows 10/11, Server 2019+ · x64', 'Installationsordner', 'Administrator-Benutzername', 'Administratorpasswort', 'Passwort wiederholen', 'Panel-Port', 'Zugriff', 'Nur dieser Computer', 'Lokales Netzwerk (LAN)', 'LAN-IP-Adresse', 'Panel-DNS-Name', 'Agent auf diesem Computer installieren', 'AD/DNS-Agent ebenfalls installieren (AD-Modul erforderlich)', 'Generierter lokaler CA unter Windows vertrauen', 'Lokales Subnetz in privaten/Domänenprofilen für LAN erlauben', 'Installieren', 'Panel öffnen', 'Installation abgeschlossen', 'Passwörter stimmen nicht überein.', 'Installation läuft; bitte warten.')
}


for code,text in {'tr':'Bağlı yerel ağları otomatik bul ve cihazları izle','en':'Automatically discover connected local networks and monitor devices','fr':'Découvrir les réseaux locaux connectés et surveiller les équipements','de':'Verbundene lokale Netzwerke automatisch erkennen und Geräte überwachen'}.items():
    WORDS[code] += (text,)

def wizard(preview=False, check_report=None):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
    import installer_core
    if not preview and getattr(sys, 'frozen', False) and os.name == 'nt':
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, None, str(Path(sys.executable).parent), 1)
            if result <= 32:
                messagebox.showerror('CenterEK Setup', 'Administrator permission is required. Installation did not start.')
            return
    root = tk.Tk()
    root.title('CenterEK Setup')
    root.geometry('760x'+str(min(830,root.winfo_screenheight()-100)))
    root.minsize(660, 620)
    root.configure(bg='#f1f5f3')
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('TFrame', background='#f1f5f3')
    style.configure('TLabel', background='#f1f5f3', foreground='#2A4954', font=('Segoe UI', 10))
    style.configure('TCheckbutton', background='#f1f5f3', foreground='#2A4954')
    style.configure('TButton', font=('Segoe UI', 10), padding=8)
    container=ttk.Frame(root);container.pack(fill='both',expand=True)
    canvas=tk.Canvas(container,bg='#f1f5f3',highlightthickness=0)
    scrollbar=ttk.Scrollbar(container,orient='vertical',command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set);scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
    frame = ttk.Frame(canvas, padding=24)
    content=canvas.create_window((0,0),window=frame,anchor='nw')
    frame.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda event:canvas.itemconfigure(content,width=event.width))
    root.bind('<MouseWheel>',lambda event:canvas.yview_scroll(-int(event.delta/120),'units'))
    frame.columnconfigure(1, weight=1)
    language = tk.StringVar(value='tr')
    ttk.Label(frame, text='Language / Dil').grid(row=0, column=0, sticky='w', pady=(0, 14))
    combo = ttk.Combobox(frame, textvariable=language, values=list(WORDS), state='readonly', width=12)
    combo.grid(row=0, column=1, sticky='w', pady=(0, 14))
    caption = ttk.Label(frame, font=('Segoe UI', 10, 'bold'), wraplength=680)
    caption.grid(row=1, column=0, columnspan=3, sticky='w', pady=(0, 18))
    values = {'target': tk.StringVar(value=str(Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'CenterEK')),
              'username': tk.StringVar(value='admin'), 'password': tk.StringVar(), 'repeat': tk.StringVar(),
              'port': tk.StringVar(value='8765'), 'mode': tk.StringVar(value='local'),
              'address': tk.StringVar(), 'hostname': tk.StringVar(value='localhost')}
    labels = {}
    for row, (key, word) in enumerate([('target', 2), ('username', 3), ('password', 4), ('repeat', 5), ('port', 6)], start=2):
        label = ttk.Label(frame)
        label.grid(row=row, column=0, sticky='w', padx=(0, 18), pady=7)
        labels[word] = label
        entry = ttk.Entry(frame, textvariable=values[key], show='•' if key in ('password', 'repeat') else '')
        entry.grid(row=row, column=1, sticky='ew', pady=7)
    ttk.Button(frame, text='…', command=lambda: values['target'].set(filedialog.askdirectory() or values['target'].get())).grid(row=2, column=2, padx=(8, 0))
    mode_frame = ttk.Frame(frame)
    mode_frame.grid(row=7, column=0, columnspan=3, sticky='ew', pady=12)
    local = ttk.Radiobutton(mode_frame, variable=values['mode'], value='local')
    local.pack(side='left')
    lan = ttk.Radiobutton(mode_frame, variable=values['mode'], value='lan')
    lan.pack(side='left', padx=20)
    for row, key, word in [(8, 'address', 10), (9, 'hostname', 11)]:
        label = ttk.Label(frame)
        label.grid(row=row, column=0, sticky='w', pady=7)
        labels[word] = label
        ttk.Entry(frame, textvariable=values[key]).grid(row=row, column=1, sticky='ew', pady=7)
    checks = {}
    flags = {}
    for row, key, word, default in [(10,'endpoint',12,True),(11,'directory',13,False),(12,'trust_ca',14,True),(13,'firewall',15,False),(14,'auto_discover',21,True)]:
        flags[key] = tk.BooleanVar(value=default)
        checks[word] = ttk.Checkbutton(frame, variable=flags[key])
        checks[word].grid(row=row, column=0, columnspan=3, sticky='w', pady=5)
    progress_bar = ttk.Progressbar(frame, mode='indeterminate')
    progress_bar.grid(row=15, column=0, columnspan=3, sticky='ew', pady=(18, 8))
    status = tk.Text(frame, height=4, wrap='word', bg='white', fg='#2A4954', font=('Segoe UI', 9), state='disabled')
    status.grid(row=16, column=0, columnspan=3, sticky='nsew')
    frame.rowconfigure(16, weight=1)
    actions = ttk.Frame(root,padding=(24,12))
    actions.pack(side='bottom',fill='x')
    open_button = ttk.Button(actions, state='disabled')
    open_button.pack(side='left', padx=8)
    install_button = ttk.Button(actions)
    install_button.pack(side='left')
    state = {'busy': False, 'url': None}
    events = queue.Queue()
    def translate(*_):
        words = WORDS[language.get()]
        root.title(words[0]); caption.configure(text=words[1])
        for index, label in labels.items(): label.configure(text=words[index])
        for index, check in checks.items(): check.configure(text=words[index])
        local.configure(text=words[8]); lan.configure(text=words[9])
        install_button.configure(text=words[16]);open_button.configure(text=words[17])
    combo.bind('<<ComboboxSelected>>', translate)
    def append(message):
        status.configure(state='normal');status.insert('end', message+'\n');status.see('end');status.configure(state='disabled')
    def run():
        if preview:return
        if state['busy']: return
        words = WORDS[language.get()]
        if values['password'].get() != values['repeat'].get():
            messagebox.showerror(words[0], words[19]);return
        try:
            options = installer_core.Options(target=values['target'].get(), username=values['username'].get(),
                password=values['password'].get(), port=int(values['port'].get()), mode=values['mode'].get(),
                address='127.0.0.1' if values['mode'].get() == 'local' else values['address'].get(),
                hostname=values['hostname'].get(), language=language.get(), **{k:v.get() for k,v in flags.items()})
            installer_core.validate(options)
            if not getattr(sys, 'frozen', False): raise ValueError('Use the built installer package, not the source entry point.')
        except Exception as error:
            messagebox.showerror(words[0], str(error));return
        state['busy']=True;install_button.configure(state='disabled');progress_bar.start(12)
        values['password'].set('');values['repeat'].set('')
        def worker():
            try:
                url=installer_core.install(options, sys.executable, assets_root(), lambda message:events.put(('progress',message)))
                events.put(('done',url))
            except Exception as error: events.put(('error',str(error)))
            finally: options.password=''
        threading.Thread(target=worker, daemon=True).start()
    install_button.configure(command=run)
    if preview:install_button.configure(state='disabled')
    open_button.configure(command=lambda:webbrowser.open(state['url']))
    def poll():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='progress':append(value)
                else:
                    state['busy']=False;progress_bar.stop()
                    if kind=='done':
                        state['url']=value;open_button.configure(state='normal');append(WORDS[language.get()][18]+'\n'+value)
                    else:
                        append('ERROR: '+value);messagebox.showerror(WORDS[language.get()][0],value)
        except queue.Empty: pass
        root.after(150,poll)
    def close():
        if state['busy']:messagebox.showinfo(WORDS[language.get()][0],WORDS[language.get()][20]);return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW',close)
    translate();poll()
    if check_report:
        def check_ui():
            root.update_idletasks()
            result={'gui_started':True,'install_disabled':install_button.instate(['disabled']),
                    'actions_visible':bool(install_button.winfo_ismapped()),'languages':list(WORDS),
                    'auto_discovery_selected':flags['auto_discover'].get(),
                    'size':[root.winfo_width(),root.winfo_height()], 'visual_acceptance':'pending'}
            result['ok']=result['install_disabled'] and result['actions_visible'] and len(result['languages'])==4
            Path(check_report).write_text(json.dumps(result,indent=2),encoding='utf-8')
            root.destroy()
        root.after(600,check_ui)
    root.mainloop()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--serve',action='store_true');parser.add_argument('--root')
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--report')
    parser.add_argument('--preview-wizard',action='store_true')
    parser.add_argument('--check-wizard',action='store_true')
    args,remaining=parser.parse_known_args()
    if args.check_wizard:
        if not args.report:parser.error('--report required')
        wizard(preview=True,check_report=args.report)
    elif args.serve:
        if not args.root:parser.error('--root required')
        serve(args.root,remaining)
    elif args.self_test:
        if not args.report:parser.error('--report required')
        raise SystemExit(self_test(args.report))
    else:
        installed=Path(sys.executable).parent/'installation.local.json'
        if getattr(sys,'frozen',False) and installed.exists():
            data=json.loads(installed.read_text(encoding='utf-8'))
            if data.get('status')=='ready':webbrowser.open(data['url']);return
        wizard(preview=args.preview_wizard)


if __name__=='__main__':
    main()
