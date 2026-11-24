"""Piezas visuales del panel «Historias» (marca v5). Funciones puras: reciben datos y devuelven HTML escapado."""
import html, zlib

e = lambda s: html.escape(str(s if s is not None else ""))
FASES = {"match": ("Match", "#9a93ab"), "conversando": ("Conversando", "#8B3DFF"), "plan": ("Plan propuesto", "#E0428F"),
         "contacto": ("En WhatsApp", "#FF5A6E"), "cita_fijada": ("Cita fijada", "#C9A447"), "cita_hecha": ("Cita hecha", "#C9A447"),
         "resultado": ("Resultado", "#8B3DFF")}
RES = {"repetir": "Repetir", "relacion": "Relación", "sin_quimica": "Sin química", "descartada": "Historia cerrada"}
TEMP = {1: "Templada", 2: "Con chispa", 3: "Muy viva"}
APP = {"tinder": "Tinder", "hinge": "Hinge", "bumble": "Bumble"}
ABRIR = {"tinder": "https://tinder.com/app/messages", "hinge": "hinge://", "bumble": "bumble://"}
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]

CSS = """:root{--a:#FF5A6E;--b:#E0428F;--c:#8B3DFF;--d:#E6C67A;--tinta:#14101F;--crema:#FFF7F4;--ink:#14101F;--bg:#FFF7F4;--card:#fff;
--line:rgba(20,16,31,.09);--mute:rgba(20,16,31,.6);--grad:linear-gradient(120deg,#FF5A6E,#E0428F 50%,#8B3DFF);--ease:cubic-bezier(.2,.8,.2,1)}
@media(prefers-color-scheme:dark){:root{--ink:#FFF7F4;--bg:#100c19;--card:#1c1529;--line:rgba(255,247,244,.1);--mute:rgba(255,247,244,.62)}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{margin:0;font:16px/1.5 Lato,system-ui,sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
h1,h2,h3,.dsp,button,.btn{font-family:Manrope,system-ui,sans-serif}a{color:inherit}
.app{max-width:480px;margin:0 auto;padding-bottom:104px}.pad{padding:0 16px}
.hero{background:var(--tinta);color:var(--crema);border-radius:0 0 32px 32px;padding:20px 16px 24px;position:relative;overflow:hidden;
background-image:radial-gradient(rgba(255,255,255,.06) 1px,transparent 1px);background-size:3px 3px}
.hero:before{content:"";position:absolute;right:-70px;top:-90px;width:230px;height:230px;border-radius:50%;background:var(--grad);opacity:.38;filter:blur(48px)}
.hero>*{position:relative}.top{display:flex;justify-content:space-between;align-items:center;gap:10px}
.marca{display:flex;align-items:center;gap:8px;font:800 17px Manrope,sans-serif;letter-spacing:-.02em;text-decoration:none}.marca img{width:28px;height:28px;border-radius:9px}
.fecha{font-size:11px;letter-spacing:.14em;text-transform:uppercase;opacity:.6}
h1{font:800 32px/1.08 Manrope,sans-serif;letter-spacing:-.03em;margin:22px 0 6px}.hero p{margin:0;color:rgba(255,247,244,.7);font-size:15px}.hero b{color:var(--crema)}
.semana{display:flex;gap:8px;overflow-x:auto;margin-top:18px;scrollbar-width:none;text-decoration:none}.semana::-webkit-scrollbar{display:none}
.dia{flex:0 0 72px;border-radius:18px;padding:10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);color:var(--crema);text-decoration:none}
.dia small{display:block;font-size:12px;opacity:.65}.dia b{display:block;font:800 24px Manrope,sans-serif;color:inherit}.dia span{font-size:12px;opacity:.8;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dia.hoy{background:var(--grad);border-color:transparent}.dia.hoy small,.dia.hoy span{opacity:1}
.eti{font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:var(--mute);margin:26px 0 12px;display:flex;justify-content:space-between;font-weight:700}
.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:16px;margin-bottom:12px;box-shadow:0 10px 28px -20px rgba(20,16,31,.35)}
.quien{display:flex;gap:12px;align-items:center;text-decoration:none}.quien h3{margin:0;font:800 19px Manrope,sans-serif;letter-spacing:-.02em}
.meta{font-size:13px;color:var(--mute);display:flex;gap:6px;align-items:center;flex-wrap:wrap}.hora{margin-left:auto;font-size:13px;color:var(--mute)}
.av{flex:0 0 auto;width:48px;height:48px;border-radius:50%;display:grid;place-items:center;color:#fff;font:800 19px Manrope,sans-serif}
.av.g{width:88px;height:88px;font-size:34px}.t1{box-shadow:0 0 0 2px var(--card),0 0 0 4px rgba(127,120,145,.35)}.t2{box-shadow:0 0 0 2px var(--card),0 0 0 4px var(--d)}.t3{box-shadow:0 0 0 2px var(--card),0 0 0 4px var(--a)}
.hero .t1,.hero .t2,.hero .t3{--card:var(--tinta)}
.pill{display:inline-flex;align-items:center;gap:6px;border-radius:999px;padding:4px 10px;font:700 12px Manrope,sans-serif;background:var(--line);color:inherit;border:0;cursor:pointer;min-height:28px}
.pill i{width:8px;height:8px;border-radius:50%;display:inline-block}
.cita{margin:12px 0 0;font-size:16px}.sug{margin-top:12px;border-radius:18px;background:var(--bg);border:1px solid var(--line);padding:12px}
.sug label{font:800 11px Manrope,sans-serif;letter-spacing:.16em;text-transform:uppercase;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
textarea,input,select{width:100%;font:16px Lato,sans-serif;color:var(--ink);background:transparent;border:0;resize:vertical}
.sug textarea{min-height:56px;padding:4px 0 0}.campo{border:1px solid var(--line);border-radius:14px;padding:12px;background:var(--card)}
.acc{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}.acc form{display:contents}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 20px;border-radius:999px;border:0;background:var(--grad);color:#fff;
font:800 15px Manrope,sans-serif;text-decoration:none;cursor:pointer;transition:transform .14s var(--ease)}.btn.flex{flex:1}
.btn.sec{background:transparent;color:var(--ink);border:1px solid var(--line)}.btn.ink{background:var(--tinta);color:var(--crema);width:100%}
@media(prefers-color-scheme:dark){.btn.ink{background:var(--crema);color:var(--tinta)}}
.btn:active,.pill:active,.dia:active{transform:scale(.97)}:focus-visible{outline:2px solid var(--c);outline-offset:2px}
.res{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}.res button{min-height:52px;border-radius:16px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:800 15px Manrope,sans-serif;cursor:pointer}
.oro{border-color:rgba(230,198,122,.7)!important;background:rgba(230,198,122,.14)!important}.antes{font:800 11px Manrope,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#a8862f}
@media(prefers-color-scheme:dark){.antes{color:var(--d)}}
.vacio{text-align:center;padding:36px 16px;color:var(--mute)}.vacio b{display:block;font:800 22px Manrope,sans-serif;color:var(--ink);margin-bottom:6px}
.tab{position:fixed;left:50%;transform:translateX(-50%);bottom:12px;width:min(456px,calc(100% - 24px));background:var(--tinta);border-radius:28px;display:flex;padding:6px;z-index:5;
box-shadow:0 18px 40px -16px rgba(20,16,31,.7)}.tab a{flex:1;min-height:56px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;
color:rgba(255,247,244,.6);text-decoration:none;font:700 12px Manrope,sans-serif;border-radius:22px;position:relative}.tab a[aria-current]{color:#fff;background:rgba(255,255,255,.08)}
.tab svg{width:22px;height:22px}.tab sup{position:absolute;top:6px;left:calc(50% + 6px);background:var(--grad);color:#fff;border-radius:999px;font-size:11px;min-width:18px;height:18px;line-height:18px;text-align:center;padding:0 4px}
.embudo{display:flex;height:8px;border-radius:999px;overflow:hidden;background:var(--line);margin:14px 0 6px}.embudo i{display:block}
.chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;scrollbar-width:none}.chips a{flex:0 0 auto;min-height:40px;display:inline-flex;align-items:center;padding:0 14px;border-radius:999px;
border:1px solid var(--line);text-decoration:none;font:700 14px Manrope,sans-serif}.chips a[aria-current]{background:var(--tinta);color:var(--crema);border-color:var(--tinta)}
@media(prefers-color-scheme:dark){.chips a[aria-current]{background:var(--crema);color:var(--tinta)}}
.buscar{display:flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:0 16px;min-height:48px;background:var(--card);margin-top:16px}
.fila{display:flex;gap:12px;align-items:center;padding:12px 0;border-top:1px solid var(--line);text-decoration:none}.fila:first-of-type{border-top:0}
.fila .txt{flex:1;min-width:0}.fila h3{margin:0;font:800 16px Manrope,sans-serif}.fila p{margin:2px 0 0;font-size:13px;color:var(--mute);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.barra{display:flex;gap:4px;margin-top:16px}.barra i{flex:1;height:6px;border-radius:999px;background:rgba(255,255,255,.14)}.barra i.on{background:var(--grad)}
.tl{list-style:none;margin:0;padding:0;position:relative}.tl li{position:relative;padding:0 0 16px 44px}.tl li:before{content:attr(data-n);position:absolute;left:0;top:0;width:30px;height:30px;
border-radius:50%;background:var(--card);border:1px solid var(--line);display:grid;place-items:center;font:800 13px Manrope,sans-serif}
.tl li:after{content:"";position:absolute;left:14px;top:32px;bottom:0;width:2px;background:linear-gradient(var(--a),var(--c));opacity:.35}.tl li:last-child:after{display:none}
.tl b{font-family:Manrope,sans-serif}.tl small{display:block;color:var(--mute)}
.temp{display:flex;gap:8px}.temp button{flex:1;min-height:44px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--ink);font:700 14px Manrope,sans-serif;cursor:pointer}
.temp button[aria-checked=true]{background:var(--grad);color:#fff;border-color:transparent}
dialog{border:0;border-radius:32px 32px 0 0;margin:auto auto 0;width:min(480px,100%);max-width:100%;padding:20px 16px 28px;background:var(--card);color:var(--ink)}
dialog::backdrop{background:rgba(20,16,31,.55)}.rejilla{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:12px 0}
.rejilla button{min-height:52px;border-radius:16px;border:1px solid var(--line);background:var(--bg);color:var(--ink);font:800 14px Manrope,sans-serif;cursor:pointer;text-align:left;padding:0 14px}
.rejilla button[aria-current]{border-color:var(--c);box-shadow:inset 0 0 0 1px var(--c)}
.toast{position:fixed;left:50%;bottom:96px;transform:translateX(-50%);background:var(--tinta);color:var(--crema);border-radius:999px;padding:8px 8px 8px 18px;display:flex;gap:12px;
align-items:center;z-index:9;box-shadow:0 12px 30px -10px rgba(0,0,0,.6);max-width:calc(100% - 24px)}.toast button{min-height:40px;border-radius:999px;border:0;padding:0 14px;
background:rgba(255,255,255,.12);color:#fff;font:800 14px Manrope,sans-serif;cursor:pointer}
.ok{color:#1a9d5a;font-weight:700}.mute{color:var(--mute)}.cifras{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.cifras div{text-align:center}.cifras b{display:block;font:800 26px Manrope,sans-serif}
.cifras small{color:var(--mute)}.rojo{border-color:rgba(255,90,110,.5)}img.qr{width:260px;max-width:100%;background:#fff;border-radius:12px;padding:8px}
.wa{display:flex;flex-direction:column;gap:18px}.waqr{order:-1}@media(max-width:700px){.waqr{order:0}}
section{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:16px;margin:0 0 12px}section h2{font:800 18px Manrope,sans-serif;margin:0 0 8px}
section p,section li{color:var(--mute)}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}"""

ICON = {"hoy": '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-5v-6h-4v6H5a1 1 0 0 1-1-1z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
        "historias": '<circle cx="9" cy="8" r="3.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M3 20c.6-3.4 3-5.5 6-5.5s5.4 2.1 6 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5c1.8.7 2.9 2.6 3.2 5.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
        "agenda": '<rect x="4" y="5.5" width="16" height="15" rx="3" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M4 10h16M9 3v4M15 3v4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
        "ajustes": '<circle cx="12" cy="12" r="3.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>'}

JS = """(function(){try{var y=sessionStorage.getItem('y:'+location.pathname);if(y)scrollTo(0,+y)}catch(_){}
addEventListener('beforeunload',function(){try{sessionStorage.setItem('y:'+location.pathname,scrollY)}catch(_){}})})();
function hoja(id){var d=document.getElementById(id);if(d&&d.showModal){d.showModal();d.onclick=function(ev){if(ev.target===d)d.close()}}}
function copiar(id,url){var t=document.getElementById(id).value;var ir=function(){location.href=url};
if(navigator.clipboard)navigator.clipboard.writeText(t).then(ir,function(){prompt('Copia el mensaje:',t)});else{prompt('Copia el mensaje:',t)}}
function filtrar(v){v=v.toLowerCase();document.querySelectorAll('[data-q]').forEach(function(x){x.hidden=x.dataset.q.indexOf(v)<0})}
document.addEventListener('submit',function(ev){var b=ev.target.querySelector('button[type=submit],button:not([type])');if(b){b.setAttribute('aria-busy','true');b.style.opacity=.6}});"""


def avatar(nombre, pid, temp=2, grande=False):
    h = zlib.crc32(str(pid).encode()) % 360
    ini = (str(nombre or "?").strip()[:1] or "?").upper()
    return (f'<span class="av{" g" if grande else ""} t{temp}" aria-hidden="true" style="background:linear-gradient(135deg,hsl({h} 70% 58%),hsl({(h + 40) % 360} 65% 42%))">'
            f'{e(ini)}</span>')


def pill(etapa, resultado=None, pid=None):
    nom, col = FASES.get(etapa, FASES["conversando"])
    if etapa == "resultado" and resultado:
        nom = RES.get(resultado, nom)
    attr = f' onclick="hoja(\'fase{pid}\')" aria-label="Fase: {e(nom)}. Cambiar"' if pid else ""
    tag = "button type=\"button\"" if pid else "span"
    return f'<{tag} class="pill"{attr}><i style="background:{col}"></i>{e(nom)}</{tag.split()[0]}>'


def ruta(jids):
    """Hinge → WhatsApp a partir de los canales de la persona."""
    vistos = []
    for j in jids:
        n = "WhatsApp" if "@" in j else "Instagram" if j.startswith("ig:") else APP.get(j.removeprefix("n-").split(":")[0], "App")
        if n not in vistos:
            vistos.append(n)
    return " → ".join(vistos)


def nombre_vis(n):
    """Los teléfonos nunca se ven enteros."""
    t = str(n or "?")
    d = "".join(ch for ch in t if ch.isdigit())
    return f"+{d[:2]} {d[2]}•• ••• {d[-3:]}" if len(d) >= 9 and not any(ch.isalpha() for ch in t) else t


def tabbar(activa, n_hoy=0):
    out = []
    for k, t, href in (("hoy", "Hoy", "/"), ("historias", "Historias", "/historias"), ("agenda", "Agenda", "/agenda"), ("ajustes", "Ajustes", "/ajustes")):
        sup = f"<sup>{n_hoy}</sup>" if k == "hoy" and n_hoy else ""
        cur = ' aria-current="page"' if k == activa else ""
        out.append(f'<a href="{href}"{cur}><svg viewBox="0 0 24 24" aria-hidden="true">{ICON[k]}</svg>{t}{sup}</a>')
    return '<nav class="tab" aria-label="Secciones">' + "".join(out) + "</nav>"


def toast(texto, undo=None):
    if not texto:
        return ""
    b = (f'<form method="post" action="/deshacer"><input type="hidden" name="ev" value="{int(undo)}"><button>Deshacer</button></form>'
         if undo else "")
    return f'<div class="toast" role="status" aria-live="polite"><span>{e(texto)}</span>{b}</div><script>setTimeout(function(){{var t=document.querySelector(".toast");if(t)t.remove()}},6000)</script>'


def form(accion, boton, clase="btn", campos="", extra=""):
    return f'<form method="post" action="{e(accion)}" style="display:inline">{campos}<button class="{clase}"{extra}>{boton}</button></form>'


def hidden(**kw):
    return "".join(f'<input type="hidden" name="{k}" value="{e(v)}">' for k, v in kw.items())


def hoja_fase(pid, etapa, volver):
    camino = "".join(f'<button name="e" value="{k}"{" aria-current=true" if k == etapa else ""}>{v[0]}</button>'
                     for k, v in FASES.items() if k != "resultado")
    res = "".join(f'<button name="r" value="{k}">{v}</button>' for k, v in RES.items())
    return (f'<dialog id="fase{pid}" aria-label="Cambiar fase"><h2 class="dsp" style="margin:0">¿En qué punto estáis?</h2>'
            f'<form method="post" action="/p/{pid}/etapa">{hidden(v=volver)}<div class="eti" style="margin:16px 0 0">Camino</div><div class="rejilla">{camino}</div></form>'
            f'<form method="post" action="/p/{pid}/resultado">{hidden(v=volver)}<div class="eti" style="margin:8px 0 0">Resultado</div><div class="rejilla">{res}</div></form>'
            '<p class="mute" style="font-size:13px;margin:0">Lo que elijas manda: la IA ya no lo cambiará.</p>'
            f'<div class="acc"><button class="btn sec flex" onclick="this.closest(\'dialog\').close()">Cerrar</button></div></dialog>')


def tarjeta_resultado(p, volver):
    res = "".join(f'<button name="r" value="{k}">{v if k != "descartada" else "Cerrar historia"}</button>' for k, v in RES.items())
    return (f'<article class="card oro"><div class="antes">Por anotar · {e(p["cita_txt"] or "tu cita")}</div>'
            f'<a class="quien" href="/p/{p["id"]}" style="margin-top:10px">{avatar(p["nombre"], p["id"], p["temperatura"])}<h3>¿Qué tal con {e(p["nombre"])}?</h3></a>'
            f'<form method="post" action="/p/{p["id"]}/resultado">{hidden(v=volver)}<div class="res">{res}</div></form>'
            '<p class="mute" style="font-size:13px;margin:10px 0 0">Queda entre tú y CelestIA.</p></article>')


def tarjeta_respuesta(s, volver):
    """s: sugerencia + datos de persona. Botón principal según el canal."""
    jid, sid = s["jid"], s["id"]
    if "@" in jid or jid.startswith(("n-", "ig:")):
        prin = f'<button class="btn flex" form="fe{sid}">{"Enviar por WhatsApp" if "@" in jid else "Enviar por Instagram" if jid.startswith("ig:") else "Enviar desde tu Android"}</button>'
    else:
        app_ = jid.split(":")[0]
        prin = (f'<button class="btn flex" type="button" onclick="copiar(\'t{sid}\',\'{ABRIR.get(app_, "/")}\');'
                f'fetch(\'/sug/{sid}/copiada\',{{method:\'POST\'}})">Copiar y abrir {APP.get(app_, "la app")}</button>')
    cuando = (s["creado"] or "")[11:16]
    return (f'<article class="card"><a class="quien" href="/p/{s["pid"]}">{avatar(s["pnombre"], s["pid"], s["temperatura"])}<div>'
            f'<h3>{e(nombre_vis(s["pnombre"]))}</h3><div class="meta">{pill(s["etapa"], s["resultado"])} · vía {e(ruta([jid]))}</div></div>'
            f'<span class="hora">{e(cuando)}</span></a><p class="cita">«{e(s["entrada"])}»</p>'
            f'<div class="sug"><label for="t{sid}">Sugerencia</label><textarea id="t{sid}" name="t" form="fe{sid}" maxlength="600">{e(s["texto"])}</textarea></div>'
            f'<form id="fe{sid}" method="post" action="/sug/{sid}/enviar">{hidden(v=volver)}</form>'
            f'<div class="acc">{prin}{form(f"/sug/{sid}/otra", "Otra", "btn sec", hidden(v=volver))}{form(f"/sug/{sid}/luego", "Luego", "btn sec", hidden(v=volver))}</div></article>')


def tarjeta_escalada(s, volver):
    return (f'<article class="card oro"><div class="antes">Necesita tu criterio</div>'
            f'<a class="quien" href="/p/{s["pid"]}" style="margin-top:10px">{avatar(s["pnombre"], s["pid"], s["temperatura"])}<h3>{e(nombre_vis(s["pnombre"]))}</h3></a>'
            f'<p class="cita">«{e(s["entrada"])}»</p><p class="mute" style="margin:6px 0 0">CelestIA no contesta sola: {e(s["motivo"] or "es delicado")}.</p>'
            f'<div class="acc"><a class="btn sec flex" href="/p/{s["pid"]}">Abrir historia</a>{form(f"/sug/{s["id"]}/descartar", "Ya le he contestado", "btn sec", hidden(v=volver))}</div></article>')


def pagina(cuerpo, activa=None, n_hoy=0, aviso="", undo=None):
    nav = tabbar(activa, n_hoy) if activa else ""
    return ('<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="robots" content="noindex"><title>CelestIA</title><link rel="icon" href="/icon-192.png"><link rel="manifest" href="/manifest.webmanifest">'
            '<link rel="apple-touch-icon" href="/apple-touch-icon.png"><meta name="apple-mobile-web-app-capable" content="yes">'
            '<meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
            '<meta name="apple-mobile-web-app-title" content="CelestIA"><meta name="theme-color" content="#14101F">'
            '<meta name="color-scheme" content="light dark">'
            '<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@700;800&family=Lato:wght@400;700&display=swap" rel="stylesheet">'
            f'<style>{CSS}</style></head><body><div class="app">{cuerpo}</div>{nav}{toast(aviso, undo)}<script>{JS}</script></body></html>')


def cabecera(titulo, sub="", fecha="", volver=None, derecha=""):
    izq = (f'<a class="marca" href="{e(volver)}" aria-label="Volver">← Volver</a>' if volver else
           '<a class="marca" href="/"><img src="/logo.png" alt="">CelestIA</a>')
    return (f'<header class="hero"><div class="top">{izq}<span class="fecha">{e(fecha)}</span>{derecha}</div>'
            f'<h1>{titulo}</h1>' + (f"<p>{sub}</p>" if sub else ""))
