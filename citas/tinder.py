#!/usr/bin/env python3
"""Conector Tinder via la pestana logueada de tinder.com (Chromium por CDP, $CDP_PORT). Solo GET salvo `enviar`.
usage: tinder.py matches | chat MATCH_ID | perfil MATCH_ID | enviar MATCH_ID TEXTO (autónomo; respeta envio.py: PAUSA, 45 s, 40/día, registro)
Endpoints sacados del bundle/red de la web: /v2/matches, /v2/matches/{id}/messages, /user/{id},
POST /user/matches/{id} (sendMessage). Nunca llama a /v2/seen (no marca como visto)."""
import asyncio, json, os, re, sys, time, urllib.request
import websockets
from cdp import CDP, PORT
import envio

# fetch dentro de la pagina: mismo origen, token de localStorage; el token nunca sale de la pestana.
API = """async (path, opts={}) => { const r = await fetch('https://api.gotinder.com'+path, {...opts, headers:{
  'x-auth-token': localStorage['TinderWeb/APIToken'], platform:'web', 'app-version':'1073902', 'tinder-version':'7.39.2',
  accept:'application/json', 'content-type':'application/json'}});
  if (!r.ok) throw new Error('HTTP '+r.status+' '+path); return r.json(); }"""

MATCHES = """(async()=>{ const api=%s; const out=[];
 for (const msg of [1,0]) { let tok='';
  for (let p=0;p<3;p++) { // ponytail: max 3 paginas x 60 por tipo; subir si hay mas
   const d=(await api('/v2/matches?locale=es&count=60&message='+msg+'&is_tinder_u=false&include_conversations=true'+(tok?'&page_token='+tok:''))).data;
   out.push(...d.matches); tok=d.next_page_token; if(!tok) break; await new Promise(r=>setTimeout(r,1500)); } }
 return out.map(m=>{ const p=m.person||{}, last=(m.messages||[]).slice(-1)[0];
  const age=p.birth_date&&!p.hide_age?Math.floor((Date.now()-Date.parse(p.birth_date))/3.15576e10):null;
  const quien=last?(last.from===p._id?'ella':'yo'):null;
  return {match_id:m._id, nombre:p.name, edad:age, bio:(p.bio||'').slice(0,140),
   ultimo:last?{quien, texto:last.message, fecha:last.sent_date}:null,
   fecha:m.last_activity_date||m.created_date, mensajes:m.message_count,
   toca_contestar: !last || quien==='ella'}; }); })()"""

CHAT = """(async()=>{ const api=%s, id=%s; let tok='', ms=[];
 const ella=(await api('/v2/matches/'+id)).data.person._id;
 for (let p=0;p<5;p++) { const d=(await api('/v2/matches/'+id+'/messages?locale=es&count=100'+(tok?'&page_token='+tok:''))).data;
  ms.push(...d.messages); tok=d.next_page_token; if(!tok) break; await new Promise(r=>setTimeout(r,1500)); }
 return ms.sort((a,b)=>a.timestamp-b.timestamp).map(m=>({quien:m.from===ella?'ella':'yo', texto:m.message, fecha:m.sent_date})); })()"""

PERFIL = """(async()=>{ const api=%s, id=%s;
 const m=(await api('/v2/matches/'+id)).data, uid=m.person._id, u=(await api('/user/'+uid+'?locale=es')).results||{};
 return {user_id:uid, nombre:u.name, bio:u.bio, ciudad:u.city&&u.city.name, distancia_km:u.distance_mi&&Math.round(u.distance_mi*1.609),
  trabajo:(u.jobs||[]).map(j=>[j.title&&j.title.name,j.company&&j.company.name].filter(Boolean).join(' @ ')),
  estudios:(u.schools||[]).map(s=>s.name),
  intereses:((u.user_interests||{}).selected_interests||[]).map(i=>i.name),
  descriptores:(u.selected_descriptors||[]).map(d=>d.name+': '+(d.choice_selections||[]).map(c=>c.name).join(', ')),
  prompts:(u.user_prompts&&u.user_prompts.prompts||[]).map(p=>({pregunta:p.question_text||p.prompt_text,respuesta:p.answer_text||p.text})),
  fotos:(u.photos||[]).map(f=>f.url)}; })()"""

SEND = """(async()=>{ const api=%s, id=%s, txt=%s;
 const me=(await api('/v2/profile?locale=es&include=user')).data.user._id, m=(await api('/v2/matches/'+id)).data;
 return api('/user/matches/'+id+'?locale=es',{method:'POST',body:JSON.stringify({userId:me, otherId:m.person._id, matchId:id,
  message:txt, tempMessageId:String(Math.random()).slice(2)})}); })()"""


def tinder_ws():
    tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/list"))
    return next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page" and t["url"].startswith("https://tinder.com/"))


async def run(js):
    async with websockets.connect(tinder_ws(), max_size=None) as ws:
        return await CDP(ws).ev(js)


def main(argv):
    cmd, a = (argv or ["?"])[0], [json.dumps(x) for x in argv[1:]]
    if cmd in ("chat", "perfil", "enviar") and not (len(argv) > 1 and re.fullmatch(r"[0-9a-f]{24,64}", argv[1])):
        sys.exit("match_id invalido")
    if cmd == "matches":
        js = MATCHES % API
    elif cmd == "chat":
        js = CHAT % (API, a[0])
    elif cmd == "perfil":
        js = PERFIL % (API, a[0])
    elif cmd == "enviar":
        if len(argv) < 3 or not argv[2].strip():
            sys.exit("texto vacio")
        envio.control()
        js = SEND % (API, a[0], json.dumps(" ".join(argv[2:])))
    else:
        sys.exit(__doc__)
    r = asyncio.run(run(js))
    if isinstance(r, dict) and "exception" in r:
        sys.exit(f"ERROR: {r['exception']}")
    if cmd == "enviar":
        envio.registrar("tinder", argv[1], " ".join(argv[2:]))
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
