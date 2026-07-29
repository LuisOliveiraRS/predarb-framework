from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from app.paper.final_paper_assurance_qualification_gate import (
    final_paper_assurance_qualification_gate,
)


router = APIRouter(
    prefix="/paper/final-assurance/qualification-gate",
    tags=["paper-final-assurance-qualification-gate"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PredArb | Gate de Qualificação Final Paper</title>
  <style>
    :root{color-scheme:dark;--bg:#090c0f;--panel:#151a20;--line:#2b333d;--text:#f5f7f9;--muted:#9ca9b5;--accent:#ff6a00;--good:#44c47d;--warning:#f6c453;--critical:#ff6b6b}
    *{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at top right,rgba(255,106,0,.16),transparent 35rem),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,sans-serif}
    main{width:min(1240px,calc(100% - 28px));margin:0 auto;padding:32px 0 56px}header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:22px}h1,h2,p{margin-top:0}h1{margin-bottom:8px;font-size:clamp(30px,5vw,50px);letter-spacing:-.04em}h2{font-size:18px}.muted{color:var(--muted)}
    .actions,.badges{display:flex;flex-wrap:wrap;gap:10px}.badges{margin-bottom:20px}button,a.button{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text);font:inherit;text-decoration:none;cursor:pointer}button{border-color:var(--accent);background:var(--accent);color:#111;font-weight:760}.badge{padding:8px 11px;border:1px solid var(--line);border-radius:999px;background:rgba(68,196,125,.08);color:var(--good);font-size:12px}
    .hero{display:grid;grid-template-columns:280px 1fr;gap:16px;margin-bottom:18px}.decision,.panel,.metric,.check{border:1px solid var(--line);border-radius:16px;background:rgba(21,26,32,.94);box-shadow:0 18px 55px rgba(0,0,0,.18)}.decision{display:grid;min-height:250px;place-items:center;padding:20px;text-align:center}.status{font-size:23px;font-weight:820;letter-spacing:.05em}.score{margin-top:8px;font-size:64px;font-weight:820;letter-spacing:-.06em}.panel{margin-bottom:18px;padding:20px}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px}.metric{padding:15px;box-shadow:none}.label{margin-bottom:8px;color:var(--muted);font-size:12px}.value{font-size:24px;font-weight:770;letter-spacing:-.04em}.checks{display:grid;gap:10px}.check{display:grid;grid-template-columns:90px 1fr auto;gap:14px;align-items:center;padding:14px;border-radius:12px;box-shadow:none}.check-status{font-size:12px;font-weight:800;letter-spacing:.08em}.check-title{margin-bottom:4px;font-weight:730}.check-value{color:var(--muted);font-size:12px;text-align:right}.qualified,.pass{color:var(--good)}.pending,.no_data{color:var(--warning)}.blocked,.fail,.critical{color:var(--critical)}.footer{color:var(--muted);font-size:12px}
    @media(max-width:760px){header{flex-direction:column}.hero{grid-template-columns:1fr}.check{grid-template-columns:1fr}.check-value{text-align:left}.actions{width:100%}button,a.button{flex:1}}
  </style>
</head>
<body>
<main>
  <header>
    <div><h1>Gate de Qualificação Final Paper</h1><p class="muted">Qualificação técnica baseada em garantia atual, estabilidade histórica e segurança operacional.</p></div>
    <div class="actions">
      <button id="refreshButton" type="button">Avaliar</button>
      <a class="button" href="/paper/final-assurance/qualification-gate/export.json">Exportar JSON</a>
      <a class="button" href="/paper/final-assurance/dashboard">Garantia atual</a>
      <a class="button" href="/paper/final-assurance/history/dashboard">Histórico</a>
    </div>
  </header>

  <section class="badges">
    <span class="badge">Escopo: PAPER_ASSURANCE_QUALIFICATION_ONLY</span>
    <span class="badge">Somente leitura</span>
    <span class="badge">Não autoriza a próxima fase</span>
    <span class="badge">Execução live e financeira bloqueada</span>
  </section>

  <section class="hero">
    <article class="decision"><div><div id="gateStatus" class="status">CARREGANDO</div><div id="gateScore" class="score">--</div><div class="muted">Score de qualificação</div></div></article>
    <article class="panel"><h2>Resumo consolidado</h2><div id="metrics" class="metrics"></div></article>
  </section>

  <section class="panel"><h2>Critérios do gate</h2><div id="checks" class="checks"></div></section>
  <p id="lastUpdate" class="footer">Carregando dados...</p>
</main>
<script>
function ensureSafe(p){for(const f of ["paper_execution_authorized","live_authorization","execution_authorized","live_execution","financial_execution","next_step_authorized"]){if(p[f]!==false)throw new Error(`Guarda inválida: ${f}`)}if(p.read_only!==true)throw new Error("Payload não é somente leitura.")}
function esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function css(v){return String(v||"").toLowerCase()}
function metric(label,value){return `<article class="metric"><div class="label">${esc(label)}</div><div class="value">${esc(value)}</div></article>`}
function render(p){ensureSafe(p);const s=p.summary||{};const status=document.getElementById("gateStatus");status.textContent=p.status||"NO_DATA";status.className=`status ${css(p.status)}`;document.getElementById("gateScore").textContent=Number(p.qualification_score||0).toFixed(0);document.getElementById("metrics").innerHTML=[metric("Garantia atual",s.assurance_status||"-"),metric("Score atual",Number(s.assurance_score||0).toFixed(2)),metric("Avaliações",Number(s.history_entries||0).toFixed(0)),metric("Último histórico",s.latest_history_status||"-"),metric("Score médio",Number(s.average_history_score||0).toFixed(2)),metric("Sequência ASSURED",Number(s.current_streak||0).toFixed(0)),metric("Integridade",s.integrity_status||"-"),metric("Monitor",s.monitor_status||"-"),metric("Incidentes ativos",Number(s.active_incidents||0).toFixed(0)),metric("Falhas runtime",Number(s.total_runtime_failures||0).toFixed(0))].join("");document.getElementById("checks").innerHTML=(p.checks||[]).map(c=>`<article class="check"><div class="check-status ${css(c.status)} ${css(c.severity)}">${esc(c.status)}</div><div><div class="check-title">${esc(c.title)}</div><div class="muted">${esc(c.message)}</div></div><div class="check-value">Atual: ${esc(JSON.stringify(c.current_value))}<br>Esperado: ${esc(JSON.stringify(c.expected_value))}</div></article>`).join("")}
async function refresh(){const b=document.getElementById("refreshButton");b.disabled=true;b.textContent="Avaliando...";try{const r=await fetch("/paper/final-assurance/qualification-gate/report",{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());document.getElementById("lastUpdate").textContent="Última avaliação: "+new Date().toLocaleString("pt-BR")+" | Gate restrito ao ambiente Paper"}catch(e){document.getElementById("lastUpdate").textContent="Falha: "+e.message}finally{b.disabled=false;b.textContent="Avaliar"}}
document.getElementById("refreshButton").addEventListener("click",refresh);refresh();setInterval(refresh,15000);
</script>
</body>
</html>"""


def _report():
    return final_paper_assurance_qualification_gate.evaluate()


@router.get("/health")
async def final_assurance_qualification_gate_health():
    report = _report()
    return {
        "status": report["status"],
        "qualified": report["qualified"],
        "scope": report["scope"],
        "qualification_score": report["qualification_score"],
        "summary": report["summary"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/report")
async def final_assurance_qualification_gate_report():
    return _report()


@router.get("/dashboard", response_class=HTMLResponse)
async def final_assurance_qualification_gate_dashboard():
    return HTMLResponse(
        content=DASHBOARD_HTML,
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/export.json")
async def final_assurance_qualification_gate_export_json():
    return Response(
        content=json.dumps(
            _report(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-paper-assurance-qualification-gate.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
