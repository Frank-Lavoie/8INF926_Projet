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
from flask import render_template

app = flask.Flask(__name__)

# Config
NOMAD_EXE = r"C:\Users\arman\Desktop\nomad.3.9.1_Personal\bin\nomad.exe"
NOMAD_EXE = r"C:\Program Files (x86)\nomad.3.9.1\bin\nomad.exe"


@app.route('/')
def home():
    return render_template('pd.html', title="Optimisation par programmation dynamique")

@app.route('/nomad-page')
def nomad_page():
    return render_template('nomad.html', title="Optimisation boite noire")

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

@app.route('/pd-stats', methods=['GET'])
def verifier_pd():
    nrows = 100
    df = pd.read_excel("data.xlsx", nrows=nrows)

    total_diff_puissance = 0
    nb_diff_turbines = 0

    rows = []
    temps_total = 0

    cols_turbines = ['Q1 (m3/s)','Q2 (m3/s)','Q3 (m3/s)','Q4 (m3/s)','Q5 (m3/s)']
    turbines_data = df[cols_turbines].values

    for i in range(nrows):

        niv_amont = df['Niv Amont (m)'].iloc[i]
        qtot = df['Qtot (m3/s)'].iloc[i]

        # Turbines inactives dans les données réelles (Q == 0)
        turbines_inactives_reel = [
            j + 1 for j, col in enumerate(cols_turbines)
            if turbines_data[i][j] == 0
        ]

        # Toujours passer les 5 turbines à l'optimiseur
        jsonObject = {
            'turbines_disponibles': [1, 2, 3, 4, 5],
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

        # turbines estimées (Q != 0 dans la solution)
        nb_turbines_estimee = sum(
            v != 0 for v in response_json['solution_indexed'].values()
        )

        # turbines réelles actives (Q != 0 dans les données)
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

        rows.append({
          "i": i,
          "puissance_reelle": round(puissance_reel, 2),
          "puissance_estimee": round(puissance_estimee, 2),
          "diff_puissance": round(diff_puissance, 2),
          "puissance_style": puissance_style,
          "nb_turbines_reel": nb_turbines_reel,
          "nb_turbines_estimee": nb_turbines_estimee,
          "diff_turbines": diff_turbines,
          "turbine_style": turbine_style
      })

    moyenne_diff_puissance = total_diff_puissance / nrows
    return render_template('pd_stats.html',rows=rows, moyenne_diff_puissance=moyenne_diff_puissance, temps_total=temps_total, nb_diff_turbines=nb_diff_turbines, nrows=nrows)

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

MAX_BB_EVAL   80

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

        # Turbines inactives dans les données réelles (Q == 0)
        turbines_inactives_reel = [
            j + 1 for j, col in enumerate(cols_turbines)
            if turbines_data[i][j] == 0
        ]

        nb_turbines_reel = int((turbines_data[i] != 0).sum())

        # Toujours passer les 5 turbines
        payload = {
            'turbines_disponibles': [1, 2, 3, 4, 5],
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
        return i, puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree, solution, turbines_inactives_reel

    resultats = [None] * nrows
    temps_total = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(evaluer_ligne, i): i for i in range(nrows)}
        for future in as_completed(futures):
            i, puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree, solution, turbines_inactives_reel = future.result()
            resultats[i] = (puissance_estimee, nb_turbines_reel, nb_turbines_estimee, duree, solution, turbines_inactives_reel)
            temps_total += duree

    total_diff_puissance = 0
    nb_diff_turbines = 0
    rows_html = ""
    for i in range(nrows):
        puissance_estimee, nb_turbines_reel, nb_turbines_estimee, _, solution, turbines_inactives_reel = resultats[i]
        puissance_reel    = df['Puissance totale'].iloc[i]
        diff_puissance    = abs(puissance_reel - puissance_estimee)
        diff_turbines     = abs(nb_turbines_reel - nb_turbines_estimee)
        total_diff_puissance += diff_puissance
        if diff_turbines != 0:
            nb_diff_turbines += 1
        puissance_style = "background-color:red;" if diff_puissance > 20 else ""
        turbine_style   = "background-color:red;" if diff_turbines != 0 else ""

        # Colonnes détail des 5 turbines
        turbines_detail = ""
        for t in range(1, 6):
            q_val = solution.get(t, solution.get(str(t), 0))
            is_inactive_reel = t in turbines_inactives_reel
            cell_style = "color:#aaa;font-style:italic;" if is_inactive_reel else ""
            label = f"{q_val} m³/s" + (" (inactif)" if is_inactive_reel else "")
            turbines_detail += f'<td style="{cell_style}">T{t}: {label}</td>'

        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{puissance_reel:.2f}</td>
            <td>{puissance_estimee:.2f}</td>
            <td style="{puissance_style}">{diff_puissance:.2f}</td>
            <td>{nb_turbines_reel}</td>
            <td>{nb_turbines_estimee}</td>
            <td style="{turbine_style}">{diff_turbines}</td>
            {turbines_detail}
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
            <th>T1</th>
            <th>T2</th>
            <th>T3</th>
            <th>T4</th>
            <th>T5</th>
        </tr>
        {rows_html}
    </table>
    """
    return html


if __name__ == '__main__':
    app.run(debug=True)