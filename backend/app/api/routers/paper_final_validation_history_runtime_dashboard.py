from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.paper.final_paper_validation import final_paper_validation
from app.paper.final_paper_validation_history import FinalPaperValidationHistory
from app.paper.final_paper_validation_history_runtime import (
    final_paper_validation_history_runtime,
)

router = APIRouter(
    prefix="/paper/final-validation/history-runtime",
    tags=["paper-final-validation-history-runtime-dashboard"],
)

DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PredArb | Runtime da Validação Final Paper</title>
  <style>
    :root { color-scheme: dark; --bg:#090c0f; --panel:#151a20; --line:#2b333d;
      --text:#f5f7f9; --muted:#9ca9b5; --accent:#ff6a00; --good:#44c47d;
      --warning:#f6c453; --critical:#ff6b6b; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Inter,system-ui,sans-serif;
      background:radial-gradient(circle at top right,rgba(255,106,0,.16),transparent 35rem),var(--bg); }
    main { width:min(1220px,calc(100% - 28px)); margin:0 auto; padding:32px 0 56px; }
    header { display:flex; justify-content:space-between; gap:20px; margin-bottom:22px; }
    h1,h2,p { margin-top:0; } h1 { margin-bottom:8px; font-size:clamp(30px,5vw,50px); letter-spacing:-.04em; }
    h2 { margin-bottom:14px; font-size:18px; } .muted { color:var(--muted); }
    .actions,.safety,.control-row { display:flex; flex-wrap:wrap; gap:10px; }
    .safety { margin-bottom:20px; }
    button,a.button,input { min-height:42px; border:1px solid var(--line); border-radius:10px;
      background:var(--panel); color:var(--text); font:inherit; }
    button,a.button { display:inline-flex; align-items:center; justify-content:center; padding:0 16px;
      text-decoration:none; cursor:pointer; }
    button.primary { border-color:var(--accent); background:var(--accent); color:#111; font-weight:760; }
    button.danger { border-color:var(--critical); color:var(--critical); }
    button:disabled { opacity:.55; cursor:wait; } input { width:130px; padding:0 12px; }
    .badge { padding:8px 11px; border:1px solid var(--line); border-radius:999px;
      background:rgba(68,196,125,.08); color:var(--good); font-size:12px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:18px; }
    .card,.panel { border:1px solid var(--line); border-radius:16px; background:rgba(21,26,32,.94);
      box-shadow:0 18px 55px rgba(0,0,0,.18); }
    .card { padding:16px; } .card-label { margin-bottom:8px; color:var(--muted); font-size:12px; }
    .card-value { font-size:25px; font-weight:780; letter-spacing:-.04em; }
    .panel { margin-bottom:18px; padding:20px; } .control-row { align-items:end; }
    .field { display:grid; gap:6px; } .field label { color:var(--muted); font-size:12px; }
    .running,.paper_validated { color:var(--good); } .paper_pending,.insufficient_data { color:var(--warning); }
    .paper_blocked { color:var(--critical); } .stopped,.unknown { color:var(--muted); }
    pre { max-height:420px; margin:0; padding:16px; overflow:auto; border:1px solid var(--line);
      border-radius:12px; background:rgba(0,0,0,.25); color:#dbe4eb; font-size:12px; line-height:1.55; }
    .footer { color:var(--muted); font-size:12px; }
    @media (max-width:760px) { header{flex-direction:column}.actions{width:100%} button,a.button{flex:1} }
  </style>
</head>
<body>
<main>
  <header>
    <div><h1>Runtime da Validação Final Paper</h1>
      <p class="muted">Captura periódica e controlada das avaliações finais do ambiente Paper.</p></div>
    <div class="actions">
      <a class="button" href="/paper/final-validation/dashboard">Validação atual</a>
      <a class="button" href="/paper/final-validation/history/dashboard">Histórico</a>
    </div>
  </header>

  <section class="safety">
    <span class="badge">Início manual obrigatório</span>
    <span class="badge">Somente avaliações são persistidas</span>
    <span class="badge">Próxima fase não autorizada</span>
    <span class="badge">Execução live e financeira bloqueada</span>
  </section>

  <section id="summaryGrid" class="grid"></section>

  <section class="panel">
    <h2>Controles administrativos</h2>
    <div class="control-row">
      <div class="field"><label for="intervalInput">Intervalo em segundos</label>
        <input id="intervalInput" type="number" min="30" max="86400" step="1" value="300"></div>
      <button id="startButton" class="primary" type="button">Iniciar runtime</button>
      <button id="stopButton" class="danger" type="button">Parar runtime</button>
      <button id="cycleButton" type="button">Registrar agora</button>
      <button id="resetButton" type="button">Resetar estatísticas</button>
      <button id="refreshButton" type="button">Atualizar</button>
    </div>
  </section>

  <section class="panel"><h2>Último ciclo</h2><pre id="lastCycle">Carregando...</pre></section>
  <p id="lastUpdate" class="footer">Carregando dados...</p>
</main>
<script>
const integer=new Intl.NumberFormat("pt-BR",{maximumFractionDigits:0});
function ensureSafe(p){for(const f of ["paper_execution_authorized","execution_authorized","live_execution","financial_execution","live_authorization","next_step_authorized"]){if(p[f]!==false)throw new Error("Guardas de segurança inválidas.")}}
function esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function cls(v){return String(v||"").toLowerCase()}
function card(l,v,c=""){return `<article class="card"><div class="card-label">${esc(l)}</div><div class="card-value ${c}">${esc(v)}</div></article>`}
function render(p){ensureSafe(p);const r=p.runtime||{},v=p.validation||{},h=p.history||{},running=r.running===true;
 document.getElementById("summaryGrid").innerHTML=[
  card("Runtime",running?"EXECUTANDO":"PARADO",running?"running":"stopped"),
  card("Validação atual",v.status||"INSUFFICIENT_DATA",cls(v.status)),
  card("Score final",Number(v.validation_score||0).toFixed(2)),
  card("Ciclos",integer.format(Number(r.total_cycles||0))),
  card("Sucessos",integer.format(Number(r.successful_cycles||0))),
  card("Falhas",integer.format(Number(r.failed_cycles||0))),
  card("Avaliações persistidas",integer.format(Number(h.total_entries||0))),
  card("Maior sequência validada",integer.format(Number(h.longest_validated_streak||0)))
 ].join("");
 document.getElementById("intervalInput").value=Number(r.interval_seconds||300);
 document.getElementById("lastCycle").textContent=JSON.stringify(r.last_result||{status:"Nenhum ciclo executado"},null,2);
 document.getElementById("startButton").disabled=running;document.getElementById("stopButton").disabled=!running;document.getElementById("resetButton").disabled=running;}
async function refresh(){const b=document.getElementById("refreshButton");b.disabled=true;b.textContent="Atualizando...";try{const r=await fetch("/paper/final-validation/history-runtime/snapshot",{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());document.getElementById("lastUpdate").textContent="Última atualização: "+new Date().toLocaleString("pt-BR")+" | Runtime manual | Ambiente Paper"}catch(e){document.getElementById("lastUpdate").textContent="Falha ao atualizar: "+e.message}finally{b.disabled=false;b.textContent="Atualizar"}}
async function post(u){const r=await fetch(u,{method:"POST"});if(!r.ok)throw new Error(`HTTP ${r.status}: `+await r.text());const p=await r.json();ensureSafe(p);return p}
async function startRuntime(){if(!confirm("Iniciar o runtime do histórico da Validação Final Paper?"))return;const i=Math.max(30,Math.min(86400,Number(document.getElementById("intervalInput").value||300)));await post("/paper/final-validation/history-runtime/start?confirm=START-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME&interval_seconds="+encodeURIComponent(i)+"&run_immediately=true");await refresh()}
async function stopRuntime(){if(!confirm("Parar o runtime do histórico da Validação Final Paper?"))return;await post("/paper/final-validation/history-runtime/stop?confirm=STOP-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME");await refresh()}
async function runCycle(){if(!confirm("Registrar agora a avaliação final do ambiente Paper?"))return;await post("/paper/final-validation/history-runtime/cycle?confirm=CAPTURE-FINAL-PAPER-VALIDATION");await refresh()}
async function resetStats(){if(!confirm("Resetar somente as estatísticas deste runtime?"))return;await post("/paper/final-validation/history-runtime/reset-statistics?confirm=RESET-FINAL-PAPER-VALIDATION-HISTORY-RUNTIME");await refresh()}
async function guarded(fn){try{await fn()}catch(e){alert("Operação não concluída: "+e.message)}}
document.getElementById("refreshButton").onclick=refresh;
document.getElementById("startButton").onclick=()=>guarded(startRuntime);
document.getElementById("stopButton").onclick=()=>guarded(stopRuntime);
document.getElementById("cycleButton").onclick=()=>guarded(runCycle);
document.getElementById("resetButton").onclick=()=>guarded(resetStats);
refresh();setInterval(refresh,5000);
</script>
</body>
</html>"""


def _safe_flags() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.get("/dashboard", response_class=HTMLResponse)
async def final_validation_history_runtime_dashboard():
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


@router.get("/snapshot")
async def final_validation_history_runtime_dashboard_snapshot():
    return {
        "runtime": final_paper_validation_history_runtime.status(),
        "validation": final_paper_validation.evaluate(),
        "history": FinalPaperValidationHistory().summary(),
        "manual_start_required": True,
        "read_only_snapshot": True,
        **_safe_flags(),
    }
