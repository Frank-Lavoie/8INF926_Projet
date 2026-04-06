import flask
import json
import os
import subprocess
import tempfile
import re
from centrale import Centrale
import pandas as pd
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

app = flask.Flask(__name__)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Centrale Hydraulique — Optimisation</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f4f1eb; --surface: #fffdf8; --border: #d6cfc0;
      --text: #1a1714; --muted: #7a7165;
      --accent: #1d5c8a; --accent2: #2e8b57; --danger: #c0392b;
      --radius: 6px;
    }
    body {
      background: var(--bg); color: var(--text);
      font-family: 'Fraunces', Georgia, serif;
      min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; padding: 60px 24px 80px;
    }
    header { text-align: center; margin-bottom: 52px; }
    header h1 { font-size: clamp(2rem,5vw,3rem); font-weight:300; letter-spacing:-0.02em; line-height:1.1; }
    header h1 em { font-style:italic; color:var(--accent); }
    header p { margin-top:10px; font-family:'DM Mono',monospace; font-size:0.78rem; color:var(--muted); letter-spacing:0.08em; text-transform:uppercase; }

    .card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: var(--radius); padding: 36px 40px;
      width: 100%; max-width: 580px; box-shadow: 0 2px 12px rgba(0,0,0,.05);
    }
    .card + .card { margin-top: 24px; }
    .card-title {
      font-family:'DM Mono',monospace; font-size:0.7rem; letter-spacing:0.12em;
      text-transform:uppercase; color:var(--muted);
      margin-bottom:24px; padding-bottom:12px; border-bottom:1px solid var(--border);
    }
    .field { display:flex; flex-direction:column; gap:6px; margin-bottom:20px; }
    .field:last-child { margin-bottom:0; }
    label { font-family:'DM Mono',monospace; font-size:0.75rem; color:var(--muted); letter-spacing:0.05em; }

    input[type="number"] {
      font-family:'DM Mono',monospace; font-size:0.95rem; color:var(--text);
      background:var(--bg); border:1px solid var(--border); border-radius:var(--radius);
      padding:10px 14px; width:100%; transition:border-color .2s; -moz-appearance:textfield;
    }
    input[type="number"]:focus { outline:none; border-color:var(--accent); }
    input[type="number"]::-webkit-outer-spin-button,
    input[type="number"]::-webkit-inner-spin-button { -webkit-appearance:none; }

    .input-row { display:flex; align-items:center; gap:12px; }
    input[type="range"] { padding:0; border:none; background:none; cursor:pointer; accent-color:var(--accent); flex:1; }
    .range-val { font-family:'DM Mono',monospace; font-size:0.85rem; color:var(--accent); min-width:42px; text-align:right; }

    /* ── Turbine chips ── */
    .turbine-section-header {
      display:flex; align-items:center; justify-content:space-between; margin-bottom:12px;
    }
    .chip-actions { display:flex; gap:8px; }
    .btn-small {
      font-family:'DM Mono',monospace; font-size:0.68rem; letter-spacing:0.06em;
      text-transform:uppercase; padding:4px 10px;
      border:1px solid var(--border); border-radius:var(--radius);
      background:transparent; color:var(--muted); cursor:pointer;
      transition:border-color .15s, color .15s; width:auto; margin:0;
    }
    .btn-small:hover { border-color:var(--accent); color:var(--accent); }

    .nb-row { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
    .nb-row label { white-space:nowrap; margin-bottom:0; }
    .nb-row input[type="number"] { width:72px; padding:7px 10px; font-size:0.85rem; }
    .btn-apply {
      font-family:'DM Mono',monospace; font-size:0.72rem; letter-spacing:0.06em;
      text-transform:uppercase; padding:7px 14px;
      border:1px solid var(--accent); border-radius:var(--radius);
      background:transparent; color:var(--accent); cursor:pointer;
      transition:background .15s, color .15s; white-space:nowrap; width:auto; margin:0;
    }
    .btn-apply:hover { background:var(--accent); color:#fff; }

    .turbine-checks { display:flex; flex-wrap:wrap; gap:8px; }
    .turbine-chip {
      display:flex; align-items:center; gap:7px; padding:8px 14px;
      border:1px solid var(--border); border-radius:var(--radius);
      cursor:pointer; font-family:'DM Mono',monospace; font-size:0.78rem;
      color:var(--muted); background:var(--bg);
      transition:border-color .15s, background .15s, color .15s; user-select:none;
    }
    .turbine-chip:hover { border-color:var(--accent); color:var(--accent); }
    .turbine-chip.on { border-color:var(--accent); background:#e8f1f8; color:var(--accent); }
    .turbine-chip.on .dot { background:var(--accent); }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--border); transition:background .15s; flex-shrink:0; }
    .nb-active { font-family:'DM Mono',monospace; font-size:0.7rem; color:var(--muted); margin-top:10px; }
    .nb-active span { color:var(--accent); font-weight:500; }

    /* ── Main button ── */
    .btn-main {
      width:100%; margin-top:8px; padding:14px 20px;
      background:var(--accent); color:#fff; border:none; border-radius:var(--radius);
      font-family:'DM Mono',monospace; font-size:0.82rem; letter-spacing:0.08em;
      text-transform:uppercase; cursor:pointer; transition:background .2s, transform .1s;
    }
    .btn-main:hover { background:#164d77; }
    .btn-main:active { transform:scale(.98); }
    .btn-main:disabled { background:var(--border); color:var(--muted); cursor:not-allowed; }

    /* ── Results ── */
    #result-section { display:none; width:100%; max-width:580px; }
    #result-section.visible { display:block; }
    .result-header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:20px; }
    .power-badge { font-family:'DM Mono',monospace; font-size:1.1rem; color:var(--accent2); font-weight:500; }
    .turbine-list { display:flex; flex-direction:column; gap:10px; }
    .turbine-row {
      display:flex; align-items:center; gap:16px; padding:14px 18px;
      background:var(--surface); border:1px solid var(--border);
      border-radius:var(--radius); animation:slideIn .35s ease both;
    }
    .turbine-row.inactive { opacity:.35; border-style:dashed; }
    @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
    .turbine-num { font-family:'DM Mono',monospace; font-size:0.7rem; color:var(--muted); letter-spacing:0.1em; width:28px; flex-shrink:0; }
    .bar-wrap { flex:1; height:6px; background:var(--border); border-radius:99px; overflow:hidden; }
    .bar-fill { height:100%; background:var(--accent); border-radius:99px; transition:width .6s cubic-bezier(.4,0,.2,1); }
    .debit-val { font-family:'DM Mono',monospace; font-size:0.82rem; color:var(--text); min-width:80px; text-align:right; }

    .error-box { background:#fdf0ef; border:1px solid #e8b4b0; border-radius:var(--radius); padding:14px 18px; font-family:'DM Mono',monospace; font-size:0.8rem; color:var(--danger); }

    #spinner { display:none; text-align:center; padding:16px; font-family:'DM Mono',monospace; font-size:0.75rem; color:var(--muted); letter-spacing:0.1em; }
    #spinner.visible { display:block; }
    .dot-anim::after { content:''; animation:dots 1.2s steps(4,end) infinite; }
    @keyframes dots { 0%{content:''} 25%{content:'.'} 50%{content:'..'} 75%{content:'...'} }

    footer { margin-top:60px; font-family:'DM Mono',monospace; font-size:0.68rem; color:var(--border); letter-spacing:0.08em; text-align:center; }
  </style>
</head>
<body>

<header>
  <h1>Centrale <em>Hydraulique</em></h1>
  <p>Optimisation par programmation dynamique</p>
  <p style="margin-top:14px;display:flex;gap:24px;justify-content:center;">
    <a href="/verifier" style="font-family:'DM Mono',monospace;font-size:0.75rem;color:var(--accent);text-decoration:none;letter-spacing:0.08em;text-transform:uppercase;">Statistiques DP →</a>
    <a href="/nomad-page" style="font-family:'DM Mono',monospace;font-size:0.75rem;color:var(--accent);text-decoration:none;letter-spacing:0.08em;text-transform:uppercase;">Boîte noire — NOMAD →</a>
  </p>
</header>

<div class="card">
  <div class="card-title">Configuration de la centrale</div>

  <div class="field">
    <div class="turbine-section-header">
      <label style="margin-bottom:0">Turbines disponibles</label>
      <div class="chip-actions">
        <button class="btn-small" onclick="toutCocher()">Tout cocher</button>
        <button class="btn-small" onclick="toutDecocher()">Tout décocher</button>
      </div>
    </div>
    <div class="turbine-checks" id="turbine-checks"></div>
    <div class="nb-active" id="nb-active-label"></div>
  </div>

  <div class="field">
    <label>Palier discrétisation (m³/s)</label>
    <div class="input-row">
      <input type="range" id="palier" min="1" max="20" value="5"
             oninput="document.getElementById('palier_val').textContent=this.value">
      <span class="range-val" id="palier_val">5</span>
    </div>
  </div>

  <div class="field">
    <label>Débit max par turbine (m³/s)</label>
    <input type="number" id="debit_max" value="160" min="1" max="1000" step="1">
  </div>
</div>

<div class="card">
  <div class="card-title">Paramètres d'optimisation</div>
  <div class="field">
    <label>Débit total à répartir (m³/s)</label>
    <input type="number" id="debit_total" value="220" min="1" max="5000" step="0.1">
  </div>
  <div class="field">
    <label>Niveau amont (m)</label>
    <input type="number" id="niveau_amont" value="137.76" min="0" max="300" step="0.01">
  </div>
  <button class="btn-main" id="btn" onclick="optimiser()">Lancer l'optimisation</button>
</div>

<div id="spinner"><span class="dot-anim">Calcul en cours</span></div>
<div id="result-section"></div>

<footer>Optimisation DP — Centrale Hydraulique</footer>

<script>
// ── Chip management ───────────────────────────────────────────────────────────

function genererTurbines() {
  const n = 5;
  const container = document.getElementById('turbine-checks');

  // Mémoriser états existants
  const existing = {};
  container.querySelectorAll('.turbine-chip').forEach(c => {
    existing[c.dataset.id] = c.classList.contains('on');
  });

  container.innerHTML = '';
  for (let i = 1; i <= n; i++) {
    const on = (existing[i] !== undefined) ? existing[i] : true;
    const chip = document.createElement('div');
    chip.className = 'turbine-chip' + (on ? ' on' : '');
    chip.dataset.id = i;
    chip.innerHTML = `<span class="dot"></span>T${i}`;
    chip.onclick = () => { chip.classList.toggle('on'); majCompteur(); };
    container.appendChild(chip);
  }
  majCompteur();
}

function majCompteur() {
  const total   = document.querySelectorAll('.turbine-chip').length;
  const actives = document.querySelectorAll('.turbine-chip.on').length;
  document.getElementById('nb-active-label').innerHTML =
    `<span>${actives}</span> / ${total} turbine${total>1?'s':''} disponible${actives>1?'s':''}`;
}

function toutCocher()   { document.querySelectorAll('.turbine-chip').forEach(c=>c.classList.add('on'));    majCompteur(); }
function toutDecocher() { document.querySelectorAll('.turbine-chip').forEach(c=>c.classList.remove('on')); majCompteur(); }

function getTurbinesDisponibles() {
  return Array.from(document.querySelectorAll('.turbine-chip.on')).map(c => parseInt(c.dataset.id));
}

genererTurbines(); // init


// ── Optimisation ──────────────────────────────────────────────────────────────

async function optimiser() {
  const btn     = document.getElementById('btn');
  const spinner = document.getElementById('spinner');
  const section = document.getElementById('result-section');

  const turbines_disponibles = getTurbinesDisponibles();
  if (turbines_disponibles.length === 0) {
    section.innerHTML = '<div class="card"><div class="error-box">Veuillez sélectionner au moins une turbine.</div></div>';
    section.classList.add('visible');
    return;
  }

  btn.disabled = true;
  spinner.classList.add('visible');
  section.classList.remove('visible');
  section.innerHTML = '';

  const payload = {
    turbines_disponibles: turbines_disponibles,
    nb_turbines_total:    5,
    debit_max:            parseFloat(document.getElementById('debit_max').value),
    palier:               parseInt(document.getElementById('palier').value),
    debit_total:          parseFloat(document.getElementById('debit_total').value),
    niveau_amont:         parseFloat(document.getElementById('niveau_amont').value),
  };

  try {
    const res  = await fetch('/optimiser', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    const data = await res.json();
    spinner.classList.remove('visible');
    btn.disabled = false;

    if (data.error) {
      section.innerHTML = `<div class="card"><div class="error-box">${data.error}</div></div>`;
      section.classList.add('visible');
      return;
    }

    const nbTotal    = payload.nb_turbines_total;
    const activeSet  = new Set(turbines_disponibles);
    const maxDebit   = data.max_debit || 1;

    let rows = '';
    for (let i = 1; i <= nbTotal; i++) {
      const isActive = activeSet.has(i);
      const q        = isActive ? (data.solution_indexed[i] ?? 0) : null;
      const pct      = isActive ? ((q / payload.debit_max) * 100).toFixed(1) : 100;
      const label    = isActive ? `${q} m³/s` : 'indisponible';
      rows += `
        <div class="turbine-row${isActive?'':' inactive'}" style="animation-delay:${(i-1)*55}ms">
          <span class="turbine-num">T${i}</span>
          <div class="bar-wrap"><div class="bar-fill" style="width:0%;background:${isActive?'var(--accent)':'var(--border)'}" data-pct="${pct}"></div></div>
          <span class="debit-val">${label}</span>
        </div>`;
    }

    section.innerHTML = `
      <div class="card">
        <div class="result-header">
          <div class="card-title" style="margin:0;border:none;padding:0;">Répartition optimale</div>
          <span class="power-badge">${data.puissance.toFixed(2)} MW</span>
        </div>
        <div class="turbine-list">${rows}</div>
      </div>`;

    section.classList.add('visible');
    requestAnimationFrame(() => {
      section.querySelectorAll('.bar-fill').forEach(b => { b.style.width = (b.dataset.pct||0)+'%'; });
    });

  } catch(e) {
    spinner.classList.remove('visible');
    btn.disabled = false;
    section.innerHTML = `<div class="card"><div class="error-box">Erreur réseau : ${e.message}</div></div>`;
    section.classList.add('visible');
  }
}
</script>
</body>
</html>"""


@app.route('/')
def home():
    return HTML


@app.route('/optimiser', methods=['POST'])
def optimiser():
    try:
        data = flask.request.get_json()

        turbines_disponibles = list(data.get('turbines_disponibles', []))
        nb_turbines          = len(turbines_disponibles)
        debit_max            = float(data.get('debit_max', 160))
        palier               = int(data.get('palier', 5))
        debit_total          = float(data.get('debit_total', 220))
        niveau_amont         = float(data.get('niveau_amont', 137.76))

        if nb_turbines == 0:
            return flask.jsonify({'error': 'Veuillez sélectionner au moins une turbine.'}), 400

        # Arrondir au palier (entier)
        debit_total = int(round(round(debit_total / palier) * palier))

        debit_max_centrale = int(round(round(nb_turbines * debit_max / palier) * palier))
        if debit_total > debit_max_centrale:
            return flask.jsonify({
                'error': (
                    f"Optimisation impossible : débit demandé ({debit_total} m³/s) "
                    f"supérieur à la capacité des {nb_turbines} turbine(s) disponible(s) "
                    f"({nb_turbines} × {debit_max:.0f} = {int(nb_turbines * debit_max)} m³/s max)."
                )
            }), 400

        centrale = Centrale(
            nb_turbines=nb_turbines,
            debit_max_par_turbine=debit_max,
            palier_discretisation=palier,
            turbines_disponibles=turbines_disponibles
        )

        etats, decisions = centrale.repartir_debit2(debit_total, niveau_amont)
        solution, puissance = centrale.reconstruire_solution(decisions=decisions, etats=etats)

        # Mapp solution
        solution_indexed = {
            int(turbines_disponibles[i]): int(solution[i])
            for i in range(len(solution))
        }
        max_debit = max(solution) if solution else 1
        return flask.jsonify({
            'solution_indexed': solution_indexed,
            'puissance':        puissance,
            'max_debit':        max_debit,
        })

    except Exception as e:
        return flask.jsonify({'error': str(e)}), 500

@app.route('/verifier', methods=['GET'])
@app.route('/verifier', methods=['GET'])
def verifier():
    nrows = 100
    df = pd.read_excel("data.xlsx", nrows=nrows)

    total_diff_puissance = 0
    nb_diff_turbines = 0

    rows_html = ""
    temps_total = 0

    cols_turbines = ['Q1 (m3/s)','Q2 (m3/s)','Q3 (m3/s)','Q4 (m3/s)','Q5 (m3/s)']
    turbines_data = df[cols_turbines].values

    for i in range(nrows):

        niv_amont = df['Niv Amont (m)'].iloc[i]
        qtot = df['Qtot (m3/s)'].iloc[i]

        # Déduire les turbines actives depuis les données réelles (Q != 0)
        turbines_actives = [
            j + 1 for j, col in enumerate(cols_turbines)
            if turbines_data[i][j] != 0
        ]
        if not turbines_actives:
            turbines_actives = [1]  # fallback sécuritaire

        jsonObject = {
            'turbines_disponibles': turbines_actives,
            'debit_total': qtot,
            'niveau_amont': niv_amont,
            'palier' : 5
        }

        start = time.perf_counter()
        response_json = requests.post(
            'http://127.0.0.1:5000/optimiser',
            json=jsonObject
        ).json()
        temps_total += time.perf_counter() - start

        # turbines estimées
        nb_turbines_estimee = sum(
            v != 0 for v in response_json['solution_indexed'].values()
        )

        # turbines réelles
        nb_turbines_reel = (turbines_data[i] != 0).sum()

        puissance_reel = df['Puissance totale'].iloc[i]
        puissance_estimee = response_json['puissance']

        diff_puissance = abs(puissance_reel - puissance_estimee)
        diff_turbines = abs(nb_turbines_reel - nb_turbines_estimee)

        total_diff_puissance += diff_puissance

        if diff_turbines != 0:
            nb_diff_turbines += 1

        puissance_style = "background-color:red;" if diff_puissance > 20 else ""
        turbine_style = "background-color:red;" if diff_turbines != 0 else ""

        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{puissance_reel:.2f}</td>
            <td>{puissance_estimee:.2f}</td>
            <td style="{puissance_style}">{diff_puissance:.2f}</td>
            <td>{nb_turbines_reel}</td>
            <td>{nb_turbines_estimee}</td>
            <td style="{turbine_style}">{diff_turbines}</td>
        </tr>
        """

    moyenne_diff_puissance = total_diff_puissance / nrows

    html = f"""
    <h2>Sommaire</h2>
    <ul>
        <li>Moyenne des différences de puissance : <b>{moyenne_diff_puissance:.2f}</b></li>
        <li>Nombre de différences de turbines : <b>{nb_diff_turbines}</b> / {nrows}</li>
        <li>Temps moyen par optimisation : {temps_total / nrows}</li>
    </ul>

    <h2>Détails</h2>

    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>Ligne</th>
            <th>Puissance réelle</th>
            <th>Puissance estimée</th>
            <th>Différence puissance</th>
            <th>Turbines réelles</th>
            <th>Turbines estimées</th>
            <th>Différence turbines</th>
        </tr>

        {rows_html}

    </table>
    """

    return html


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE NOMAD
# ══════════════════════════════════════════════════════════════════════════════

HTML_NOMAD = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Centrale Hydraulique — NOMAD</title>
  <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;1,9..144,300&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg: #f4f1eb; --surface: #fffdf8; --border: #d6cfc0;
      --text: #1a1714; --muted: #7a7165;
      --accent: #1d5c8a; --accent2: #2e8b57; --danger: #c0392b;
      --radius: 6px;
    }
    body {
      background: var(--bg); color: var(--text);
      font-family: 'Fraunces', Georgia, serif;
      min-height: 100vh; display: flex; flex-direction: column;
      align-items: center; padding: 60px 24px 80px;
    }
    .nav-bar { display:flex; gap:24px; margin-bottom:32px; }
    .nav-link { font-family:'DM Mono',monospace; font-size:0.75rem; color:var(--accent); text-decoration:none; letter-spacing:0.08em; text-transform:uppercase; }
    .nav-link:hover { text-decoration:underline; }
    header { text-align: center; margin-bottom: 52px; }
    header h1 { font-size: clamp(2rem,5vw,3rem); font-weight:300; letter-spacing:-0.02em; line-height:1.1; }
    header h1 em { font-style:italic; color:var(--accent); }
    header p { margin-top:10px; font-family:'DM Mono',monospace; font-size:0.78rem; color:var(--muted); letter-spacing:0.08em; text-transform:uppercase; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius); padding: 36px 40px; width: 100%; max-width: 580px; box-shadow: 0 2px 12px rgba(0,0,0,.05); }
    .card + .card { margin-top: 24px; }
    .card-title { font-family:'DM Mono',monospace; font-size:0.7rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:24px; padding-bottom:12px; border-bottom:1px solid var(--border); }
    .field { display:flex; flex-direction:column; gap:6px; margin-bottom:20px; }
    .field:last-child { margin-bottom:0; }
    label { font-family:'DM Mono',monospace; font-size:0.75rem; color:var(--muted); letter-spacing:0.05em; }
    input[type="number"] { font-family:'DM Mono',monospace; font-size:0.95rem; color:var(--text); background:var(--bg); border:1px solid var(--border); border-radius:var(--radius); padding:10px 14px; width:100%; transition:border-color .2s; -moz-appearance:textfield; }
    input[type="number"]:focus { outline:none; border-color:var(--accent); }
    input[type="number"]::-webkit-outer-spin-button, input[type="number"]::-webkit-inner-spin-button { -webkit-appearance:none; }
    .turbine-section-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
    .chip-actions { display:flex; gap:8px; }
    .btn-small { font-family:'DM Mono',monospace; font-size:0.68rem; letter-spacing:0.06em; text-transform:uppercase; padding:4px 10px; border:1px solid var(--border); border-radius:var(--radius); background:transparent; color:var(--muted); cursor:pointer; transition:border-color .15s, color .15s; width:auto; margin:0; }
    .btn-small:hover { border-color:var(--accent); color:var(--accent); }
    .turbine-checks { display:flex; flex-wrap:wrap; gap:8px; }
    .turbine-chip { display:flex; align-items:center; gap:7px; padding:8px 14px; border:1px solid var(--border); border-radius:var(--radius); cursor:pointer; font-family:'DM Mono',monospace; font-size:0.78rem; color:var(--muted); background:var(--bg); transition:border-color .15s, background .15s, color .15s; user-select:none; }
    .turbine-chip:hover { border-color:var(--accent); color:var(--accent); }
    .turbine-chip.on { border-color:var(--accent); background:#e8f1f8; color:var(--accent); }
    .turbine-chip.on .dot { background:var(--accent); }
    .dot { width:7px; height:7px; border-radius:50%; background:var(--border); transition:background .15s; flex-shrink:0; }
    .nb-active { font-family:'DM Mono',monospace; font-size:0.7rem; color:var(--muted); margin-top:10px; }
    .nb-active span { color:var(--accent); font-weight:500; }
    .btn-main { width:100%; margin-top:8px; padding:14px 20px; background:var(--accent); color:#fff; border:none; border-radius:var(--radius); font-family:'DM Mono',monospace; font-size:0.82rem; letter-spacing:0.08em; text-transform:uppercase; cursor:pointer; transition:background .2s; }
    .btn-main:hover { background:#164d77; }
    .btn-main:disabled { background:var(--border); color:var(--muted); cursor:not-allowed; }
    #result-section { display:none; width:100%; max-width:580px; }
    #result-section.visible { display:block; }
    .result-header { display:flex; justify-content:space-between; align-items:baseline; margin-bottom:20px; }
    .power-badge { font-family:'DM Mono',monospace; font-size:1.1rem; color:var(--accent2); font-weight:500; }
    .turbine-list { display:flex; flex-direction:column; gap:10px; }
    .turbine-row { display:flex; align-items:center; gap:16px; padding:14px 18px; background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); animation:slideIn .35s ease both; }
    .turbine-row.inactive { opacity:.35; border-style:dashed; }
    @keyframes slideIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
    .turbine-num { font-family:'DM Mono',monospace; font-size:0.7rem; color:var(--muted); letter-spacing:0.1em; width:28px; flex-shrink:0; }
    .bar-wrap { flex:1; height:6px; background:var(--border); border-radius:99px; overflow:hidden; }
    .bar-fill { height:100%; background:var(--accent); border-radius:99px; transition:width .6s cubic-bezier(.4,0,.2,1); }
    .debit-val { font-family:'DM Mono',monospace; font-size:0.82rem; color:var(--text); min-width:80px; text-align:right; }
    .error-box { background:#fdf0ef; border:1px solid #e8b4b0; border-radius:var(--radius); padding:14px 18px; font-family:'DM Mono',monospace; font-size:0.8rem; color:var(--danger); }
    #spinner { display:none; text-align:center; padding:16px; font-family:'DM Mono',monospace; font-size:0.75rem; color:var(--muted); letter-spacing:0.1em; }
    #spinner.visible { display:block; }
    .dot-anim::after { content:''; animation:dots 1.2s steps(4,end) infinite; }
    @keyframes dots { 0%{content:''} 25%{content:'.'} 50%{content:'..'} 75%{content:'...'} }
    footer { margin-top:60px; font-family:'DM Mono',monospace; font-size:0.68rem; color:var(--border); letter-spacing:0.08em; text-align:center; }
  </style>
</head>
<body>

<div class="nav-bar">
  <a class="nav-link" href="/">← Programmation dynamique</a>
  <a class="nav-link" href="/stats-nomad">Statistiques NOMAD →</a>
</div>

<header>
  <h1>Centrale <em>Hydraulique</em></h1>
  <p>Optimisation boîte noire — NOMAD</p>
</header>

<div class="card">
  <div class="card-title">Configuration</div>
  <div class="field">
    <div class="turbine-section-header">
      <label style="margin-bottom:0">Turbines disponibles</label>
      <div class="chip-actions">
        <button class="btn-small" onclick="toutCocher()">Tout cocher</button>
        <button class="btn-small" onclick="toutDecocher()">Tout décocher</button>
      </div>
    </div>
    <div class="turbine-checks" id="turbine-checks"></div>
    <div class="nb-active" id="nb-active-label"></div>
  </div>
  <div class="field">
    <label>Débit max par turbine (m³/s)</label>
    <input type="number" id="debit_max" value="160" min="1" max="400" step="1">
  </div>
</div>

<div class="card">
  <div class="card-title">Paramètres d'optimisation</div>
  <div class="field">
    <label>Débit total à répartir (m³/s)</label>
    <input type="number" id="debit_total" value="565" min="5" max="800" step="5">
  </div>
  <div class="field">
    <label>Niveau amont (m)</label>
    <input type="number" id="niveau_amont" value="137.76" min="100" max="200" step="0.01">
  </div>
  <button class="btn-main" id="btn" onclick="lancer()">Lancer NOMAD</button>
</div>

<div id="spinner"><span class="dot-anim">Optimisation en cours</span></div>
<div id="result-section"></div>

<footer>NOMAD 3.9.1 — Boîte noire</footer>

<script>
function genererTurbines() {
  const container = document.getElementById('turbine-checks');
  container.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const chip = document.createElement('div');
    chip.className = 'turbine-chip on';
    chip.dataset.id = i;
    chip.innerHTML = '<span class="dot"></span>T' + i;
    chip.onclick = () => { chip.classList.toggle('on'); majCompteur(); };
    container.appendChild(chip);
  }
  majCompteur();
}
function majCompteur() {
  const total   = document.querySelectorAll('.turbine-chip').length;
  const actives = document.querySelectorAll('.turbine-chip.on').length;
  document.getElementById('nb-active-label').innerHTML =
    '<span>' + actives + '</span> / ' + total + ' turbine' + (total>1?'s':'') + ' disponible' + (actives>1?'s':'');
}
function toutCocher()   { document.querySelectorAll('.turbine-chip').forEach(c=>c.classList.add('on'));    majCompteur(); }
function toutDecocher() { document.querySelectorAll('.turbine-chip').forEach(c=>c.classList.remove('on')); majCompteur(); }
function getTurbinesDisponibles() {
  return Array.from(document.querySelectorAll('.turbine-chip.on')).map(c => parseInt(c.dataset.id));
}
genererTurbines();

async function lancer() {
  const btn     = document.getElementById('btn');
  const spinner = document.getElementById('spinner');
  const section = document.getElementById('result-section');

  const turbines_disponibles = getTurbinesDisponibles();
  if (turbines_disponibles.length === 0) {
    section.innerHTML = '<div class="card"><div class="error-box">Veuillez sélectionner au moins une turbine.</div></div>';
    section.classList.add('visible');
    return;
  }

  btn.disabled = true;
  spinner.classList.add('visible');
  section.classList.remove('visible');
  section.innerHTML = '';

  const payload = {
    turbines_disponibles: turbines_disponibles,
    debit_total:  parseFloat(document.getElementById('debit_total').value),
    niveau_amont: parseFloat(document.getElementById('niveau_amont').value),
    debit_max:    parseInt(document.getElementById('debit_max').value),
  };

  try {
    const res  = await fetch('/nomad', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload) });
    const data = await res.json();
    spinner.classList.remove('visible');
    btn.disabled = false;

    if (data.error) {
      section.innerHTML = '<div class="card"><div class="error-box">' + data.error + '</div></div>';
      section.classList.add('visible');
      return;
    }

    const activeSet = new Set(turbines_disponibles);
    let rows = '';
    for (let i = 1; i <= 5; i++) {
      const isActive = activeSet.has(i);
      const q   = isActive ? (data.solution[i] ?? 0) : null;
      const pct = isActive ? ((q / payload.debit_max) * 100).toFixed(1) : 100;
      const label = isActive ? q + ' m³/s' : 'indisponible';
      rows += '<div class="turbine-row' + (isActive?'':' inactive') + '" style="animation-delay:' + ((i-1)*55) + 'ms">' +
        '<span class="turbine-num">T' + i + '</span>' +
        '<div class="bar-wrap"><div class="bar-fill" style="width:0%;background:' + (isActive?'var(--accent)':'var(--border)') + '" data-pct="' + pct + '"></div></div>' +
        '<span class="debit-val">' + label + '</span></div>';
    }

    section.innerHTML =
      '<div class="card">' +
        '<div class="result-header">' +
          '<div class="card-title" style="margin:0;border:none;padding:0;">Répartition optimale — NOMAD</div>' +
          '<span class="power-badge">' + data.puissance.toFixed(2) + ' MW</span>' +
        '</div>' +
        '<div class="turbine-list">' + rows + '</div>' +
      '</div>';

    section.classList.add('visible');
    requestAnimationFrame(() => {
      section.querySelectorAll('.bar-fill').forEach(b => { b.style.width = (b.dataset.pct||0)+'%'; });
    });

  } catch(e) {
    spinner.classList.remove('visible');
    btn.disabled = false;
    section.innerHTML = '<div class="card"><div class="error-box">Erreur réseau : ' + e.message + '</div></div>';
    section.classList.add('visible');
  }
}
</script>
</body>
</html>"""


NOMAD_EXE = r"C:\Users\arman\Desktop\nomad.3.9.1_Personal\bin\nomad.exe"


@app.route('/nomad-page')
def nomad_page():
    return HTML_NOMAD


@app.route('/nomad', methods=['POST'])
def nomad_optimiser():
    try:
        data                 = flask.request.get_json()
        turbines_disponibles = list(data.get('turbines_disponibles', [1,2,3,4,5]))
        nb_turbines          = len(turbines_disponibles)
        debit_total          = int(round(float(data.get('debit_total', 565)) / 5) * 5)
        niveau_amont         = float(data.get('niveau_amont', 137.76))
        debit_max            = int(data.get('debit_max', 160))

        if nb_turbines == 0:
            return flask.jsonify({'error': 'Veuillez sélectionner au moins une turbine.'}), 400
        if debit_total > nb_turbines * debit_max:
            return flask.jsonify({'error': f"Débit total ({debit_total}) supérieur à la capacité ({nb_turbines} × {debit_max} = {nb_turbines*debit_max} m³/s)."}), 400

        dim = nb_turbines - 1  # Q1..Q(n-1), Qn = total - sum

        with tempfile.TemporaryDirectory() as tmpdir:
            import shutil, sys as _sys
            base = os.path.dirname(os.path.abspath(__file__))
            for f in ['nomad.py', 'centrale.py', 'turbine.py']:
                shutil.copy(os.path.join(base, f), tmpdir)

            python_exe = _sys.executable
            x0 = min(debit_max, max(5, (debit_total // nb_turbines // 5) * 5))

            bat_path = os.path.join(tmpdir, 'bb.bat')
            with open(bat_path, 'w') as bf:
                bf.write(f'@echo off\n"{python_exe}" "%~dp0nomad.py" %*\n')

            x0_str    = ' '.join([str(x0)] * dim)
            lb_str    = ' '.join(['0'] * dim)
            ub_str    = ' '.join([str(debit_max)] * dim)
            type_str  = ' '.join(['R'] * dim)
            gran_str  = ' '.join(['5'] * dim)

            param_content = f"""DIMENSION      {dim}

BB_EXE         bb.bat

BB_OUTPUT_TYPE OBJ PB PB

X0             ( {x0_str} )

LOWER_BOUND    ( {lb_str} )
UPPER_BOUND    ( {ub_str} )

BB_INPUT_TYPE  ( {type_str} )

GRANULARITY    ( {gran_str} )

SOLUTION_FILE  sol.txt
"""
            param_path = os.path.join(tmpdir, 'param.txt')
            with open(param_path, 'w') as pf:
                pf.write(param_content)

            env = os.environ.copy()
            env['NOMAD_DEBIT']      = str(debit_total)
            env['NOMAD_NIVEAU']     = str(niveau_amont)
            env['NOMAD_DEBIT_MAX']  = str(debit_max)
            env['NOMAD_TURBINES']   = ','.join(str(t) for t in turbines_disponibles)

            result = subprocess.run(
                [NOMAD_EXE, param_path],
                cwd=tmpdir, capture_output=True, text=True, env=env, timeout=120
            )
            output = result.stdout + result.stderr

            # Parser la solution directement depuis stdout
            best_x = None
            for line in output.splitlines():
                if 'best feasible solution' in line:
                    match = re.search(r'\(\s*([\d\s]+)\s*\)', line)
                    if match:
                        best_x = [float(v) for v in match.group(1).split()]
                        break

            if best_x is None:
                return flask.jsonify({'error': "NOMAD n'a pas trouvé de solution.\n" + output[:800]}), 500

            x_vars = best_x[:dim]
            q_last = debit_total - sum(x_vars)
            x_full = x_vars + [q_last]

            solution = {turbines_disponibles[i]: x_full[i] for i in range(nb_turbines)}
            c = Centrale(
                nb_turbines=nb_turbines,
                debit_max_par_turbine=debit_max,
                palier_discretisation=5,
                turbines_disponibles=turbines_disponibles
            )
            puissance = -c.boite_noire(debit_total, niveau_amont, x_full)

            solution = {turbines_disponibles[i]: x_full[i] for i in range(nb_turbines)}

            return flask.jsonify({'solution': solution, 'puissance': puissance})

    except subprocess.TimeoutExpired:
        return flask.jsonify({'error': 'NOMAD a dépassé le temps limite (120s).'}), 500
    except FileNotFoundError as e:
      return flask.jsonify({'error': f'FileNotFoundError: {e}'}), 500
    except Exception as e:
        return flask.jsonify({'error': str(e)}), 500


from concurrent.futures import ThreadPoolExecutor, as_completed

@app.route('/stats-nomad')
def stats_nomad():
    nrows = 100
    df = pd.read_excel("data.xlsx", nrows=nrows)

    cols_turbines = ['Q1 (m3/s)', 'Q2 (m3/s)', 'Q3 (m3/s)', 'Q4 (m3/s)', 'Q5 (m3/s)']
    turbines_data = df[cols_turbines].values

    def evaluer_ligne(i):
        niv_amont = df['Niv Amont (m)'].iloc[i]
        qtot      = df['Qtot (m3/s)'].iloc[i]

        # Déduire les turbines actives depuis les données réelles (Q != 0)
        turbines_actives = [
            j + 1 for j, col in enumerate(cols_turbines)
            if turbines_data[i][j] != 0
        ]
        if not turbines_actives:
            turbines_actives = [1]  # fallback sécuritaire

        nb_turbines_reel = len(turbines_actives)

        payload = {
            'turbines_disponibles': turbines_actives,
            'debit_total':  qtot,
            'niveau_amont': niv_amont,
            'debit_max':    160,
        }
        start = time.perf_counter()
        response_json = requests.post('http://127.0.0.1:5000/nomad', json=payload).json()
        duree = time.perf_counter() - start
        puissance_estimee = response_json.get('puissance', 0)
        solution = response_json.get('solution', {})
        nb_turbines_estimee = sum(1 for v in solution.values() if v != 0)
        return i, puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree

    resultats = [None] * nrows
    temps_total = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluer_ligne, i): i for i in range(nrows)}
        for future in as_completed(futures):
            i, puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree = future.result()
            resultats[i] = (puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree)
            temps_total += duree

    total_diff_puissance = 0
    nb_diff_turbines = 0
    rows_html = ""
    for i in range(nrows):
        puissance_estimee, nb_turbines_reel, nb_turbines_estimee, _ = resultats[i]
        puissance_reel    = df['Puissance totale'].iloc[i]
        diff_puissance    = abs(puissance_reel - puissance_estimee)
        diff_turbines     = abs(nb_turbines_reel - nb_turbines_estimee)
        total_diff_puissance += diff_puissance
        if diff_turbines != 0:
            nb_diff_turbines += 1
        puissance_style = "background-color:red;" if diff_puissance > 20 else ""
        turbine_style   = "background-color:red;" if diff_turbines != 0 else ""
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{puissance_reel:.2f}</td>
            <td>{puissance_estimee:.2f}</td>
            <td style="{puissance_style}">{diff_puissance:.2f}</td>
            <td>{nb_turbines_reel}</td>
            <td>{nb_turbines_estimee}</td>
            <td style="{turbine_style}">{diff_turbines}</td>
        </tr>
        """

    moyenne_diff = total_diff_puissance / nrows
    html = f"""
    <h2>Sommaire — NOMAD</h2>
    <ul>
        <li>Moyenne des différences de puissance : <b>{moyenne_diff:.2f}</b> MW</li>
        <li>Nombre de différences de turbines : <b>{nb_diff_turbines}</b> / {nrows}</li>
        <li>Temps moyen par optimisation : <b>{temps_total / nrows:.2f}</b> s</li>
    </ul>
    <p><a href="/nomad-page">← Retour NOMAD</a></p>
    <h2>Détails</h2>
    <table border="1" cellpadding="5" cellspacing="0">
        <tr>
            <th>Ligne</th>
            <th>Puissance réelle</th>
            <th>Puissance estimée</th>
            <th>Différence puissance</th>
            <th>Turbines réelles</th>
            <th>Turbines estimées</th>
            <th>Différence turbines</th>
        </tr>
        {rows_html}
    </table>
    """
    return html


if __name__ == '__main__':
    app.run(debug=True)