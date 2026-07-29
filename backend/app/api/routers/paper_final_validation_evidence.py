from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from app.paper.final_paper_validation import final_paper_validation
from app.paper.final_paper_validation_evidence import (
    FinalPaperValidationEvidence,
)


router = APIRouter(
    prefix="/paper/final-validation/evidence",
    tags=["paper-final-validation-evidence"],
)


DASHBOARD_HTML = r"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PredArb | Evidências da Validação Final Paper</title>
  <style>
    :root{color-scheme:dark;--bg:#090c0f;--panel:#151a20;--line:#2b333d;--text:#f5f7f9;--muted:#9ca9b5;--accent:#ff6a00;--good:#44c47d;--warning:#f6c453;--critical:#ff6b6b}
    *{box-sizing:border-box} body{margin:0;min-height:100vh;background:radial-gradient(circle at top right,rgba(255,106,0,.16),transparent 35rem),var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,sans-serif}
    main{width:min(1240px,calc(100% - 28px));margin:0 auto;padding:32px 0 56px} header{display:flex;justify-content:space-between;gap:20px;align-items:flex-start;margin-bottom:22px}
    h1,h2,p{margin-top:0} h1{margin-bottom:8px;font-size:clamp(30px,5vw,50px);letter-spacing:-.04em} h2{font-size:18px}.muted{color:var(--muted)}
    .actions,.badges{display:flex;flex-wrap:wrap;gap:10px}.badges{margin-bottom:20px} button,a.button{display:inline-flex;align-items:center;justify-content:center;min-height:42px;padding:0 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text);font:inherit;text-decoration:none;cursor:pointer}
    button.primary{background:var(--accent);border-color:var(--accent);color:#111;font-weight:760} button:disabled{opacity:.55;cursor:wait}.badge{padding:8px 11px;border:1px solid var(--line);border-radius:999px;color:var(--good);background:rgba(68,196,125,.08);font-size:12px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:18px}.card,.panel{border:1px solid var(--line);border-radius:16px;background:rgba(21,26,32,.94);box-shadow:0 18px 55px rgba(0,0,0,.18)}.card{padding:16px}.label{margin-bottom:8px;color:var(--muted);font-size:12px}.value{font-size:25px;font-weight:780;letter-spacing:-.04em}.panel{margin-bottom:18px;padding:20px;overflow:hidden}
    .table-wrap{overflow-x:auto} table{width:100%;min-width:1200px;border-collapse:collapse} th,td{padding:12px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;font-size:13px} th{color:var(--muted)}.valid,.paper_validated{color:var(--good)}.broken,.paper_blocked{color:var(--critical)}.empty,.paper_pending,.insufficient_data{color:var(--warning)}code{color:#dbe4eb}.footer{color:var(--muted);font-size:12px}
    @media(max-width:760px){header{flex-direction:column}.actions{width:100%}button,a.button{flex:1}}
  </style>
</head>
<body>
  <main>
    <header>
      <div><h1>Evidências da Validação Final Paper</h1><p class="muted">Arquivo probatório encadeado por SHA-256.</p></div>
      <div class="actions">
        <button id="refreshButton" type="button">Atualizar</button>
        <button id="captureButton" class="primary" type="button">Registrar evidência</button>
        <a class="button" href="/paper/final-validation/evidence/export.csv">CSV</a>
        <a class="button" href="/paper/final-validation/evidence/export.json">JSON</a>
        <a class="button" href="/paper/final-validation/dashboard">Validação atual</a>
      </div>
    </header>
    <section class="badges">
      <span class="badge">Captura manual confirmada</span><span class="badge">Cadeia SHA-256</span><span class="badge">Sem truncamento automático</span><span class="badge">Próxima fase não autorizada</span>
    </section>
    <section id="summaryGrid" class="grid"></section>
    <section class="panel"><h2>Evidências registradas</h2><div class="table-wrap"><table><thead><tr><th>Status</th><th>Capturado em</th><th>Score</th><th>Garantia</th><th>Gate</th><th>Sequência QUALIFIED</th><th>Falhas runtime</th><th>Hash</th><th>Hash anterior</th></tr></thead><tbody id="entriesBody"></tbody></table></div></section>
    <p id="lastUpdate" class="footer">Carregando...</p>
  </main>
  <script>
    const integer=new Intl.NumberFormat("pt-BR");
    function ensureSafe(p){for(const f of["paper_execution_authorized","live_authorization","execution_authorized","live_execution","financial_execution","next_step_authorized"]){if(p[f]!==false)throw new Error(`Guarda inválida: ${f}`)}if(p.read_only!==true)throw new Error("Payload não é somente leitura.")}
    function esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
    function dt(v){if(!v)return"-";const d=new Date(v);return Number.isNaN(d.getTime())?esc(v):d.toLocaleString("pt-BR")}
    function shortHash(v){return v?`${v.slice(0,12)}…${v.slice(-8)}`:"-"}
    function card(l,v,c=""){return `<article class="card"><div class="label">${esc(l)}</div><div class="value ${c}">${esc(v)}</div></article>`}
    function render(p){ensureSafe(p);const s=p.summary||{},i=p.integrity||{},e=p.entries||[];document.getElementById("summaryGrid").innerHTML=[card("Integridade",i.integrity_status||"EMPTY",String(i.integrity_status||"empty").toLowerCase()),card("Evidências",integer.format(Number(s.total_entries||0))),card("Último status",s.latest_status||"-",String(s.latest_status||"").toLowerCase()),card("Último score",s.latest_score===null?"-":Number(s.latest_score).toFixed(2)),card("Chain head",shortHash(s.chain_head)),card("Arquivo",s.evidence_path||"-")].join("");const b=document.getElementById("entriesBody");if(!e.length){b.innerHTML='<tr><td colspan="9" class="muted">Nenhuma evidência registrada.</td></tr>';return}b.innerHTML=e.map(x=>{const d=x.summary||{};return `<tr><td class="${String(x.status||"").toLowerCase()}">${esc(x.status)}</td><td>${dt(x.captured_at)}</td><td>${Number(x.validation_score||0).toFixed(2)}</td><td>${esc(d.assurance_status||"-")}</td><td>${esc(d.gate_status||"-")}</td><td>${integer.format(Number(d.qualified_streak||0))}</td><td>${integer.format(Number(d.total_runtime_failures||0))}</td><td><code title="${esc(x.entry_hash)}">${shortHash(x.entry_hash)}</code></td><td><code title="${esc(x.previous_hash)}">${shortHash(x.previous_hash)}</code></td></tr>`}).join("")}
    async function refresh(){const b=document.getElementById("refreshButton");b.disabled=true;b.textContent="Atualizando...";try{const r=await fetch("/paper/final-validation/evidence/snapshot?limit=250",{cache:"no-store"});if(!r.ok)throw new Error(`HTTP ${r.status}`);render(await r.json());document.getElementById("lastUpdate").textContent="Última atualização: "+new Date().toLocaleString("pt-BR")+" | Ambiente Paper"}catch(e){document.getElementById("lastUpdate").textContent="Falha ao carregar: "+e.message}finally{b.disabled=false;b.textContent="Atualizar"}}
    async function capture(){if(!window.confirm("Registrar evidência imutável da Validação Final Paper atual?"))return;const b=document.getElementById("captureButton");b.disabled=true;b.textContent="Registrando...";try{const r=await fetch("/paper/final-validation/evidence/capture?confirm=CAPTURE-FINAL-PAPER-VALIDATION-EVIDENCE",{method:"POST"});if(!r.ok)throw new Error(`HTTP ${r.status}: ${await r.text()}`);ensureSafe(await r.json());await refresh()}catch(e){window.alert("Falha no registro: "+e.message)}finally{b.disabled=false;b.textContent="Registrar evidência"}}
    document.getElementById("refreshButton").addEventListener("click",refresh);document.getElementById("captureButton").addEventListener("click",capture);refresh();setInterval(refresh,15000);
  </script>
</body>
</html>"""


def _evidence() -> FinalPaperValidationEvidence:
    return FinalPaperValidationEvidence()


def _safe_base() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/health")
async def final_validation_evidence_health():
    evidence = _evidence()
    summary = evidence.summary()
    integrity = evidence.verify()

    return {
        "status": "healthy",
        "total_entries": summary["total_entries"],
        "integrity_status": integrity["integrity_status"],
        "integrity_valid": integrity["valid"],
        **_safe_base(),
    }


@router.get("/summary")
async def final_validation_evidence_summary():
    return _evidence().summary()


@router.get("/verify")
async def final_validation_evidence_verify():
    return _evidence().verify()


@router.get("/latest")
async def final_validation_evidence_latest():
    return {
        "evidence": _evidence().latest(),
        **_safe_base(),
    }


@router.get("/entries")
async def final_validation_evidence_entries(
    limit: int = Query(default=100, ge=1, le=5000),
):
    entries = _evidence().list_entries(limit=limit)

    return {
        "count": len(entries),
        "entries": entries,
        **_safe_base(),
    }


@router.get("/snapshot")
async def final_validation_evidence_snapshot(
    limit: int = Query(default=250, ge=1, le=5000),
):
    evidence = _evidence()

    return {
        "summary": evidence.summary(),
        "integrity": evidence.verify(),
        "latest": evidence.latest(),
        "entries": evidence.list_entries(limit=limit),
        **_safe_base(),
    }


@router.post("/capture")
async def final_validation_evidence_capture(
    confirm: str = Query(...),
):
    if confirm != "CAPTURE-FINAL-PAPER-VALIDATION-EVIDENCE":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-FINAL-PAPER-VALIDATION-EVIDENCE."
            ),
        )

    try:
        report = final_paper_validation.evaluate()
        return _evidence().capture(report)

    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get(
    "/dashboard",
    response_class=HTMLResponse,
)
async def final_validation_evidence_dashboard():
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


@router.get("/export.csv")
async def final_validation_evidence_export_csv(
    limit: int = Query(default=5000, ge=1, le=5000),
):
    entries = _evidence().list_entries(limit=limit)

    fieldnames = [
        "id", "captured_at", "report_generated_at", "status",
        "validated", "scope", "validation_score",
        "assurance_status", "assurance_score", "gate_status",
        "gate_score", "gate_history_entries", "qualified_streak",
        "total_runtime_failures", "failure_codes",
        "previous_hash", "entry_hash",
    ]

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        extrasaction="ignore",
    )
    writer.writeheader()

    for entry in entries:
        summary = entry.get("summary") or {}
        writer.writerow(
            {
                "id": entry.get("id"),
                "captured_at": entry.get("captured_at"),
                "report_generated_at": entry.get("report_generated_at"),
                "status": entry.get("status"),
                "validated": entry.get("validated"),
                "scope": entry.get("scope"),
                "validation_score": entry.get("validation_score"),
                "assurance_status": summary.get("assurance_status"),
                "assurance_score": summary.get("assurance_score"),
                "gate_status": summary.get("gate_status"),
                "gate_score": summary.get("gate_score"),
                "gate_history_entries": summary.get("gate_history_entries"),
                "qualified_streak": summary.get("qualified_streak"),
                "total_runtime_failures": summary.get("total_runtime_failures"),
                "failure_codes": ",".join(entry.get("failure_codes") or []),
                "previous_hash": entry.get("previous_hash"),
                "entry_hash": entry.get("entry_hash"),
            }
        )

    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-paper-validation-evidence.csv"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )


@router.get("/export.json")
async def final_validation_evidence_export_json():
    evidence = _evidence()

    payload = {
        "summary": evidence.summary(),
        "integrity": evidence.verify(),
        "entries": evidence.list_entries(limit=5000),
        **_safe_base(),
    }

    return Response(
        content=json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                "attachment; "
                'filename="predarb-final-paper-validation-evidence.json"'
            ),
            "Cache-Control": "no-store",
            "X-PredArb-Live-Authorization": "false",
            "X-PredArb-Financial-Execution": "false",
            "X-PredArb-Next-Step-Authorization": "false",
        },
    )
