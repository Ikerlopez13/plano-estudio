"""Servidor local de Plano Estudio: ejecutar python app.py."""
import base64, io, json, os, secrets, tempfile, threading, webbrowser
import urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse
from pathlib import Path
import cad

ROOT=Path(__file__).resolve().parent

def load_env():
    """Carga variables desde .env.local (prioritario) y .env sin dependencias externas."""
    for name in ('.env.local','.env'):
        p=ROOT/name
        if not p.exists(): continue
        for line in p.read_text(encoding='utf-8').splitlines():
            line=line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            k,v=line.split('=',1)
            v=v.strip().strip('"').strip("'")
            os.environ.setdefault(k.strip(),v)   # el primero gana: .env.local manda

load_env()

TOKEN=secrets.token_urlsafe(32)       # anti-CSRF: va incrustado en la página servida
AUTH=secrets.token_urlsafe(32)        # cookie de sesión tras iniciar sesión con contraseña
PASSWORD=os.environ.get('PLANO_PASSWORD','')   # vacío = sin login (cómodo en local)
PORT=int(os.environ.get('PLANO_PORT') or os.environ.get('PORT') or '8765')
BIND=os.environ.get('PLANO_BIND','127.0.0.1')  # usa 0.0.0.0 para desplegar
# Hosts públicos permitidos al desplegar (coma-separados). '*' = cualquiera (la contraseña protege).
ALLOWED_HOSTS={h.strip() for h in os.environ.get('PLANO_ALLOWED_HOSTS','').split(',') if h.strip()}
LOCAL_HOSTS={f'127.0.0.1:{PORT}',f'localhost:{PORT}'}

DOC=cad.fresh(); HISTORY=[]; PROPOSAL=None

def snapshot():
    # Un plano vacío no tiene caja envolvente: devolvemos SVG vacío en vez de error.
    svg=cad.render(DOC) if len(DOC.modelspace()) else ''
    return {'summary':cad.summary(DOC),'svg':svg,'undo':bool(HISTORY)}

def commit(new):
    global DOC,PROPOSAL
    HISTORY.append(cad.dumps(DOC))
    if len(HISTORY)>12: HISTORY.pop(0)
    DOC=new; PROPOSAL=None

def context(prompt):
    return cad.INSTRUCTIONS+'\n\nESTADO DEL PLANO:\n'+json.dumps(cad.summary(DOC),ensure_ascii=False)+'\n\nPETICIÓN:\n'+prompt

def ask_ai(prompt,key,model):
    if not key: key=os.environ.get('OPENAI_API_KEY','')
    if not key: raise ValueError('Falta la clave de API. Puedes usar el modo «Usar este chat» sin clave.')
    payload={'model':model,'instructions':cad.INSTRUCTIONS,'input':'ESTADO:\n'+json.dumps(cad.summary(DOC),ensure_ascii=False)+'\nPETICIÓN:\n'+prompt,'text':{'format':{'type':'json_object'}},'max_output_tokens':16000,'store':False}
    req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=180) as response: result=json.load(response)
    except urllib.error.HTTPError as e:
        # No mostrar cabeceras ni credenciales en los errores.
        raise ValueError(f'La API respondió con error {e.code}. Comprueba clave, saldo y acceso al modelo.') from None
    except urllib.error.URLError:
        raise ValueError('No se pudo conectar a la API. Comprueba tu conexión.') from None
    if result.get('status')!='completed': raise ValueError('La IA no terminó la respuesta. Reduce la petición y vuelve a intentar.')
    parts=[part['text'] for item in result.get('output',[]) for part in item.get('content',[]) if part.get('type')=='output_text']
    if not parts: raise ValueError('La IA no devolvió un plano válido.')
    return json.loads(''.join(parts))

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,data,status=200,mime='application/json',cookie=None):
        if isinstance(data,dict): data=json.dumps(data,ensure_ascii=False).encode()
        elif isinstance(data,str): data=data.encode('utf-8')
        self.send_response(status); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' blob: data:; style-src 'self'; script-src 'self'; frame-ancestors 'none'")
        if cookie is not None: self.send_header('Set-Cookie',cookie)
        self.end_headers(); self.wfile.write(data)
    def valid_host(self):
        host=self.headers.get('Host','')
        return host in LOCAL_HOSTS or '*' in ALLOWED_HOSTS or host in ALLOWED_HOSTS
    def valid_origin(self):
        origin=self.headers.get('Origin')
        if not origin: return True
        if '*' in ALLOWED_HOSTS: return True
        return urlparse(origin).netloc in (LOCAL_HOSTS|ALLOWED_HOSTS)
    def authed(self):
        if not PASSWORD: return True
        raw=self.headers.get('Cookie','')
        if not raw: return False
        m=SimpleCookie(raw).get('plano_auth')
        return bool(m) and secrets.compare_digest(m.value,AUTH)
    def set_cookie(self,value,maxage=None):
        secure='; Secure' if self.headers.get('X-Forwarded-Proto')=='https' else ''
        age=f'; Max-Age={maxage}' if maxage is not None else ''
        return f'plano_auth={value}; HttpOnly; SameSite=Lax; Path=/{secure}{age}'
    def do_GET(self):
        if not self.valid_host(): return self.send({'error':'Host no permitido'},403)
        route=self.path.split('?')[0]
        if route=='/':
            page='static/login.html' if (PASSWORD and not self.authed()) else 'static/index.html'
            s=(ROOT/page).read_text(encoding='utf-8').replace('__TOKEN__',TOKEN)
            return self.send(s,mime='text/html; charset=utf-8')
        if route in ('/app.js','/login.js','/style.css'):
            return self.send((ROOT/'static'/route[1:]).read_bytes(),mime='text/javascript' if route.endswith('.js') else 'text/css')
        if self.headers.get('X-Plano-Token')!=TOKEN: return self.send({'error':'Sesión no válida'},403)
        if not self.authed(): return self.send({'error':'Inicia sesión.'},401)
        try:
            if route=='/state': return self.send(snapshot())
            self.send({'error':'No encontrado'},404)
        except Exception as e: self.send({'error':str(e)},400)
    def do_POST(self):
        global DOC,PROPOSAL
        if not self.valid_host() or not self.valid_origin(): return self.send({'error':'Origen no permitido'},403)
        try:
            n=int(self.headers.get('Content-Length','0'))
            if n<=0 or n>20_000_000: raise ValueError('Petición vacía o demasiado grande (máximo 20 MB).')
            body=json.loads(self.rfile.read(n))
            route=self.path
            # Inicio de sesión: no requiere token ni cookie previos.
            if route=='/login':
                if not PASSWORD: return self.send({'ok':True})
                if secrets.compare_digest(str(body.get('password','')),PASSWORD):
                    return self.send({'ok':True},cookie=self.set_cookie(AUTH))
                return self.send({'error':'Contraseña incorrecta.'},401)
            if route=='/logout':
                return self.send({'ok':True},cookie=self.set_cookie('',maxage=0))
            # A partir de aquí: hace falta token anti-CSRF y sesión válida.
            if self.headers.get('X-Plano-Token')!=TOKEN: return self.send({'error':'Sesión no válida'},403)
            if not self.authed(): return self.send({'error':'Inicia sesión.'},401)
            if route=='/context': return self.send({'text':context(str(body.get('prompt',''))[:20000])})
            if route in ('/propose','/ai'):
                PROPOSAL=None
                package=ask_ai(str(body.get('prompt',''))[:20000],body.get('key',''),body.get('model','gpt-4.1')) if route=='/ai' else body['package']
                new=cad.apply(DOC,package)
                result={'svg':cad.render(new),'summary':cad.summary(new),'message':str(package.get('summary','Propuesta preparada.')),'assumptions':package.get('assumptions',[]),'operations':len(package['operations'])}
                PROPOSAL=new
                return self.send(result)
            if route=='/accept':
                if PROPOSAL is None: raise ValueError('No hay una propuesta pendiente.')
                commit(PROPOSAL); return self.send(snapshot())
            if route=='/cancel': PROPOSAL=None; return self.send(snapshot())
            if route=='/undo':
                if not HISTORY: raise ValueError('No hay cambios para deshacer.')
                DOC=cad.loads(HISTORY.pop()); PROPOSAL=None; return self.send(snapshot())
            if route=='/new': commit(cad.fresh()); return self.send(snapshot())
            if route=='/example': commit(cad.apply(cad.fresh(),cad.example())); return self.send(snapshot())
            if route=='/import':
                raw=base64.b64decode(body['data'],validate=True)
                if raw.startswith(b'AC10'): raise ValueError('Este archivo parece DWG. Ábrelo en AutoCAD y guárdalo como DXF.')
                name=None
                try:
                    with tempfile.NamedTemporaryFile(suffix='.dxf',delete=False) as f: f.write(raw); name=f.name
                    new=cad.ezdxf.readfile(name)
                finally:
                    if name: os.unlink(name)
                if new.units not in (0,4): raise ValueError('Este DXF no está en milímetros. Convierte sus unidades en AutoCAD a mm antes de importarlo.')
                if new.units==0 and body.get('unitless_mm') is not True: raise ValueError('El DXF no declara unidades. Marca «Confirmo que el dibujo está en mm» si es correcto.')
                new.units=4
                if len(new.modelspace())>10000: raise ValueError('Esta versión admite importar hasta 10.000 entidades de modelo.')
                audit=new.audit()
                if audit.has_errors: raise ValueError('El archivo tiene errores DXF que requieren revisión en AutoCAD.')
                cad.layers(new); cad.render(new)
                commit(new); return self.send(snapshot())
            if route=='/export':
                if PROPOSAL is not None: raise ValueError('Aplica o descarta la propuesta antes de exportar.')
                if len(DOC.modelspace())==0: raise ValueError('El plano está vacío.')
                with_sheet=body.get('sheet',True)
                new=cad.sheet(DOC,body.get('paper','A3'),float(body.get('scale',50)),str(body.get('title','Plano de interiores'))) if with_sheet else DOC
                if body.get('format')=='pdf':
                    if not with_sheet: raise ValueError('El PDF requiere una lámina.')
                    return self.send(cad.render(new,paper=True,pdf=True),mime='application/pdf')
                return self.send(cad.dumps(new).encode('utf-8'),mime='application/dxf')
            self.send({'error':'No encontrado'},404)
        except Exception as e:
            self.send({'error':str(e)[:800]},400)

if __name__=='__main__':
    server=HTTPServer((BIND,PORT),Handler)
    where=f'http://127.0.0.1:{PORT}' if BIND in ('127.0.0.1','localhost') else f'puerto {PORT} (bind {BIND})'
    print(f'Plano Estudio abierto en {where}')
    print('Protegido con contraseña.' if PASSWORD else 'Sin contraseña (modo local). Define PLANO_PASSWORD para exigir login.')
    print('Mantén esta ventana abierta. Ctrl+C para cerrar.')
    if BIND in ('127.0.0.1','localhost') and '--no-browser' not in __import__('sys').argv:
        threading.Timer(0.7,lambda:webbrowser.open(f'http://127.0.0.1:{PORT}')).start()
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
