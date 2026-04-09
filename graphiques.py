import os, re, sys, shutil, tempfile, subprocess, time
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from centrale import Centrale

# Config
DATA_FILE   = "data.xlsx"
NROWS       = 100
DEBIT_MAX   = 160
PALIER_PD   = 5
NOMAD_EXE   = r"C:\Program Files (x86)\nomad.3.9.1\bin\nomad.exe"
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUT_DIR     = os.path.join(BASE_DIR, "graphiques")
os.makedirs(OUT_DIR, exist_ok=True)

COLS_TURBINES = ['Q1 (m3/s)', 'Q2 (m3/s)', 'Q3 (m3/s)', 'Q4 (m3/s)', 'Q5 (m3/s)']

# Helpers

def turbines_actives_depuis_excel(row_data):
    """Retourne toujours les 5 turbines ; celles à Q=0 seront inactives (débit=0)."""
    return [1, 2, 3, 4, 5]


def run_pd(qtot, niv_amont, turbines):
    """Appelle directement la classe Centrale, pas besoin de Flask."""
    nb_turbines = len(turbines)
    debit_total = int(round(float(qtot) / PALIER_PD) * PALIER_PD)
    c = Centrale(nb_turbines=nb_turbines, debit_max_par_turbine=DEBIT_MAX,
                 palier_discretisation=PALIER_PD, turbines_disponibles=turbines)
    etats, decisions = c.repartir_debit2(debit_total, float(niv_amont))
    solution, puissance = c.reconstruire_solution(decisions=decisions, etats=etats)
    return float(puissance), solution


def run_nomad(qtot, niv_amont, turbines):
    """Lance NOMAD directement (sans passer par Flask) et retourne (puissance, nb_iterations)."""
    nb_turbines = len(turbines)
    dim         = nb_turbines - 1
    debit_total = int(round(float(qtot) / 5) * 5)
    x0          = min(DEBIT_MAX, max(5, (debit_total // nb_turbines // 5) * 5))

    with tempfile.TemporaryDirectory() as tmpdir:
        for f in ['nomad.py', 'centrale.py', 'turbine.py']:
            shutil.copy(os.path.join(BASE_DIR, f), tmpdir)

        python_exe = sys.executable
        bat_path   = os.path.join(tmpdir, 'bb.bat')
        with open(bat_path, 'w') as bf:
            bf.write(f'@echo off\n"{python_exe}" "%~dp0nomad.py" %*\n')

        x0_str   = ' '.join([str(x0)]        * dim)
        lb_str   = ' '.join(['0']             * dim)
        ub_str   = ' '.join([str(DEBIT_MAX)]  * dim)
        type_str = ' '.join(['R']             * dim)
        gran_str = ' '.join(['5']             * dim)

        param = f"""DIMENSION      {dim}
BB_EXE         bb.bat
BB_OUTPUT_TYPE OBJ PB PB
X0             ( {x0_str} )
LOWER_BOUND    ( {lb_str} )
UPPER_BOUND    ( {ub_str} )
BB_INPUT_TYPE  ( {type_str} )
GRANULARITY    ( {gran_str} )
MAX_BB_EVAL   80
"""
        with open(os.path.join(tmpdir, 'param.txt'), 'w') as pf:
            pf.write(param)

        env = os.environ.copy()
        env['NOMAD_DEBIT']     = str(debit_total)
        env['NOMAD_NIVEAU']    = str(float(niv_amont))
        env['NOMAD_DEBIT_MAX'] = str(DEBIT_MAX)
        env['NOMAD_TURBINES']  = ','.join(str(t) for t in turbines)

        result = subprocess.run(
            [NOMAD_EXE, 'param.txt'],
            cwd=tmpdir, capture_output=True, text=True, env=env, timeout=300
        )
        output = result.stdout + result.stderr

    nb_iter = None
    for pattern in [
        r'blackbox evaluations\s*:\s*(\d+)',
        r'Blackbox evaluations\s*:\s*(\d+)',
        r'BBE\s*=\s*(\d+)',
        r'(\d+)\s+blackbox',
    ]:
        m = re.search(pattern, output, re.I)
        if m:
            nb_iter = int(m.group(1))
            break

    if nb_iter is None:
        bbe_lines = re.findall(r'^\s*\d+\s+[\d\.\-]+', output, re.M)
        if bbe_lines:
            nb_iter = len(bbe_lines)

    best_x = None
    for line in output.splitlines():
        m2 = re.search(r'best feasible solution\s*:\s*\(([\d\s\.\-]+)\)', line, re.I)
        if m2:
            best_x = [float(v) for v in m2.group(1).split()]
            break

    if best_x is None:
        return None, nb_iter, []

    x_vars = [int(round(float(v) / 5) * 5) for v in best_x[:dim]]
    q_last = int(debit_total) - sum(x_vars)
    q_last = max(0, min(int(DEBIT_MAX), q_last))
    x_full = x_vars + [q_last]

    c = Centrale(nb_turbines=nb_turbines, debit_max_par_turbine=DEBIT_MAX,
                 palier_discretisation=5, turbines_disponibles=turbines)
    f_val = c.boite_noire(int(debit_total), float(niv_amont), x_full)
    if isinstance(f_val, tuple):
        f_val = f_val[0]

    convergence = []
    best_so_far = None
    for line in output.splitlines():
        m = re.match(r'^\s*(\d+)\s+([-\d\.]+)\s*$', line.strip())
        if m:
            bbe = int(m.group(1))
            obj = float(m.group(2))
            if best_so_far is None or obj < best_so_far:
                best_so_far = obj
            convergence.append((bbe, -best_so_far))

    return float(-f_val), nb_iter, convergence



def collecter():
    df = pd.read_excel(DATA_FILE, nrows=NROWS)
    turbines_data = df[COLS_TURBINES].values

    resultats = []
    for i in range(NROWS):
        niv_amont      = df['Niv Amont (m)'].iloc[i]
        qtot           = df['Qtot (m3/s)'].iloc[i]
        puissance_reel = df['Puissance totale'].iloc[i]

        turbines         = turbines_actives_depuis_excel(turbines_data[i])
        nb_turbines_reel = len(turbines)

        print(f"Test {i+1:3d}/100 - Qtot={qtot:.0f}  turbines={turbines}", end='  ')

        # PD
        t0 = time.perf_counter()
        p_pd, solution_pd = run_pd(qtot, niv_amont, turbines)
        t_pd = time.perf_counter() - t0
        nb_actives_pd = sum(1 for q in solution_pd if q > 0)

        # NOMAD
        t0 = time.perf_counter()
        p_nomad, nb_iter, convergence = run_nomad(qtot, niv_amont, turbines)
        t_nomad = time.perf_counter() - t0

        print(f"PD={p_pd:.2f} MW  NOMAD={round(p_nomad,2) if p_nomad else 'N/A'} MW  "
              f"iter={nb_iter}  t_nomad={t_nomad:.1f}s")

        resultats.append({
            'ligne':          i,
            'puissance_reel': puissance_reel,
            'p_pd':           p_pd,
            'p_nomad':        p_nomad,
            'diff_pd':        abs(puissance_reel - p_pd)    if p_pd    is not None else None,
            'diff_nomad':     abs(puissance_reel - p_nomad) if p_nomad is not None else None,
            'nb_iter':        nb_iter,
            't_pd':           t_pd,
            't_nomad':        t_nomad,
            'nb_turbines':    nb_turbines_reel,
            'nb_actives_pd':  nb_actives_pd,
            'convergence':    convergence,
        })

    return pd.DataFrame(resultats)


# Style commun

STYLE = {
    'pd':    {'color': '#1d5c8a', 'label': 'Prog. dynamique'},
    'nomad': {'color': '#2e8b57', 'label': 'NOMAD'},
    'reel':  {'color': '#888',    'label': 'Réel'},
}

def savefig(name):
    path = os.path.join(OUT_DIR, name)
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  → {path}")


# Graphiques

def graph_puissance_moyenne(df):
    """Puissance moyenne réelle vs PD vs NOMAD, groupée par nombre de turbines."""
    grouped = df.groupby('nb_turbines')[['puissance_reel', 'p_pd', 'p_nomad']].mean().reset_index()
    x     = np.arange(len(grouped))
    width = 0.25
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - width, grouped['puissance_reel'], width, color=STYLE['reel']['color'],  label=STYLE['reel']['label'],  alpha=0.85)
    ax.bar(x,         grouped['p_pd'],           width, color=STYLE['pd']['color'],    label=STYLE['pd']['label'],    alpha=0.85)
    ax.bar(x + width, grouped['p_nomad'],        width, color=STYLE['nomad']['color'], label=STYLE['nomad']['label'], alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(n)} turbine{'s' if n > 1 else ''}" for n in grouped['nb_turbines']])
    ax.set_ylabel('Puissance moyenne (MW)')
    ax.set_title('Puissance moyenne - Réel vs PD vs NOMAD\n(par nombre de turbines actives)')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)
    savefig('01_puissance_moyenne.png')


def graph_erreur_moyenne(df):
    """Erreur absolue moyenne globale + par nb turbines."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Gauche : barres globales
    ax = axes[0]
    vals   = [df['diff_pd'].mean(), df['diff_nomad'].mean()]
    colors = [STYLE['pd']['color'], STYLE['nomad']['color']]
    labels = [STYLE['pd']['label'], STYLE['nomad']['label']]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, width=0.4)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                f'{val:.2f} MW', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_ylabel('Erreur absolue moyenne (MW)')
    ax.set_title('Erreur absolue moyenne globale\n(100 tests)')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(vals) * 1.3)

    # Droite : par nb turbines
    ax2 = axes[1]
    grouped = df.groupby('nb_turbines')[['diff_pd', 'diff_nomad']].mean().reset_index()
    x     = np.arange(len(grouped))
    width = 0.35
    ax2.bar(x - width/2, grouped['diff_pd'],    width, color=STYLE['pd']['color'],    label=STYLE['pd']['label'],    alpha=0.85)
    ax2.bar(x + width/2, grouped['diff_nomad'], width, color=STYLE['nomad']['color'], label=STYLE['nomad']['label'], alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{int(n)} turbine{'s' if n > 1 else ''}" for n in grouped['nb_turbines']])
    ax2.set_ylabel('Erreur absolue moyenne (MW)')
    ax2.set_title('Erreur moyenne par nombre de turbines actives')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    savefig('02_erreur_moyenne.png')


def graph_distribution_erreur(df):
    """Histogramme de la distribution des erreurs."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=True)
    for ax, col, style in [
        (axes[0], 'diff_pd',    STYLE['pd']),
        (axes[1], 'diff_nomad', STYLE['nomad']),
    ]:
        data = df[col].dropna()
        ax.hist(data, bins=15, color=style['color'], alpha=0.85, edgecolor='white')
        ax.axvline(data.mean(),   color='black', linestyle='--', linewidth=1.3,
                   label=f"Moy.    = {data.mean():.2f} MW")
        ax.axvline(data.median(), color='gray',  linestyle=':',  linewidth=1.3,
                   label=f"Médiane = {data.median():.2f} MW")
        ax.set_xlabel('Erreur absolue (MW)')
        ax.set_ylabel('Nombre de tests')
        ax.set_title(f"Distribution des erreurs - {style['label']}")
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
    fig.tight_layout()
    savefig('03_distribution_erreurs.png')


def graph_iterations_nomad(df):
    """Itérations NOMAD : distribution + moyenne par nb turbines."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Gauche : histogramme
    ax = axes[0]
    iters = df['nb_iter'].dropna()
    ax.hist(iters, bins=20, color=STYLE['nomad']['color'], alpha=0.85, edgecolor='white')
    ax.axvline(iters.mean(),   color='black', linestyle='--', linewidth=1.3,
               label=f"Moy.    = {iters.mean():.0f} éval.")
    ax.axvline(iters.median(), color='gray',  linestyle=':',  linewidth=1.3,
               label=f"Médiane = {iters.median():.0f} éval.")
    ax.set_xlabel("Nombre d'évaluations boîte noire")
    ax.set_ylabel('Nombre de tests')
    ax.set_title("Distribution du nombre d'itérations NOMAD\n(100 tests)")
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    # Droite : moyenne par nb turbines
    ax2 = axes[1]
    grouped = df.groupby('nb_turbines')['nb_iter'].mean().reset_index()
    bars = ax2.bar(
        [f"{int(n)} turbine{'s' if n > 1 else ''}" for n in grouped['nb_turbines']],
        grouped['nb_iter'],
        color=STYLE['nomad']['color'], alpha=0.85
    )
    for bar, val in zip(bars, grouped['nb_iter']):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f'{val:.0f}', ha='center', va='bottom', fontsize=9)
    ax2.set_xlabel('Nombre de turbines actives')
    ax2.set_ylabel("Itérations moyennes")
    ax2.set_title("Itérations NOMAD moyennes\npar nombre de turbines actives")
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    savefig('04_iterations_nomad.png')


def graph_temps_calcul(df):
    """Temps de calcul moyen : global + par nb turbines."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    # Gauche : barres globales
    ax = axes[0]
    vals   = [df['t_pd'].mean(), df['t_nomad'].mean()]
    colors = [STYLE['pd']['color'], STYLE['nomad']['color']]
    labels = [STYLE['pd']['label'], STYLE['nomad']['label']]
    bars = ax.bar(labels, vals, color=colors, alpha=0.85, width=0.4)
    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.002,
                f'{val:.3f} s', ha='center', va='bottom', fontsize=10, fontweight='bold')
    ax.set_ylabel('Temps moyen (s)')
    ax.set_title('Temps de calcul moyen\n(100 tests)')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, max(vals) * 1.3)

    # Droite : par nb turbines
    ax2 = axes[1]
    grouped = df.groupby('nb_turbines')[['t_pd', 't_nomad']].mean().reset_index()
    x     = np.arange(len(grouped))
    width = 0.35
    ax2.bar(x - width/2, grouped['t_pd'],    width, color=STYLE['pd']['color'],    label=STYLE['pd']['label'],    alpha=0.85)
    ax2.bar(x + width/2, grouped['t_nomad'], width, color=STYLE['nomad']['color'], label=STYLE['nomad']['label'], alpha=0.85)
    ax2.set_xticks(x)
    ax2.set_xticklabels([f"{int(n)} turbine{'s' if n > 1 else ''}" for n in grouped['nb_turbines']])
    ax2.set_ylabel('Temps moyen (s)')
    ax2.set_title('Temps de calcul moyen\npar nombre de turbines actives')
    ax2.legend()
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    savefig('05_temps_calcul.png')


def graph_scatter_pd_vs_nomad(df):
    """Scatter puissance PD vs NOMAD - qui est meilleur ?"""
    fig, ax = plt.subplots(figsize=(7, 7))
    sc = ax.scatter(df['p_pd'], df['p_nomad'],
                    c=df['nb_turbines'], cmap='Blues',
                    edgecolors='white', linewidths=0.5, s=60, alpha=0.9)
    cb = fig.colorbar(sc, ax=ax)
    cb.set_label('Nb turbines actives')
    lims = [min(df['p_pd'].min(), df['p_nomad'].min()) - 2,
            max(df['p_pd'].max(), df['p_nomad'].max()) + 2]
    ax.plot(lims, lims, 'k--', linewidth=1, label='PD = NOMAD')
    ax.set_xlabel('Puissance PD (MW)')
    ax.set_ylabel('Puissance NOMAD (MW)')
    ax.set_title('Puissance PD vs NOMAD - 100 tests')
    ax.legend()
    ax.set_xlim(lims); ax.set_ylim(lims)
    ax.grid(alpha=0.3)
    pct = (df['p_nomad'] > df['p_pd']).mean() * 100
    ax.text(0.05, 0.95, f"NOMAD > PD : {pct:.0f}% des tests",
            transform=ax.transAxes, fontsize=9, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
    savefig('06_scatter_pd_vs_nomad.png')


def graph_convergence_moyenne(df):
    N_POINTS = 100
    x_norm   = np.linspace(0, 100, N_POINTS)

    courbes = []
    for _, row in df.iterrows():
        conv = row['convergence']
        p_final = row['p_nomad']
        if not conv or p_final is None or p_final == 0:
            continue

        bbes      = np.array([c[0] for c in conv])
        puiss     = np.array([c[1] for c in conv])
        bbe_max   = bbes[-1]

        # Normaliser l'axe BBE en 0-100%
        x_pct = bbes / bbe_max * 100

        y_interp = np.interp(x_norm, x_pct, puiss / p_final * 100)
        courbes.append(y_interp)

    if not courbes:
        print("  Aucune courbe de convergence disponible.")
        return

    courbes_arr = np.array(courbes)
    y_mean      = courbes_arr.mean(axis=0)
    y_p10       = np.percentile(courbes_arr, 10, axis=0)
    y_p90       = np.percentile(courbes_arr, 90, axis=0)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Bande p10-p90
    ax.fill_between(x_norm, y_p10, y_p90,
                    color=STYLE['nomad']['color'], alpha=0.15,
                    label='Percentiles 10–90%')

    # Courbe moyenne
    ax.plot(x_norm, y_mean,
            color=STYLE['nomad']['color'], linewidth=2,
            label=f'Moyenne ({len(courbes)} tests)')

    # Ligne de référence 99%
    ax.axhline(99, color='gray', linestyle=':', linewidth=1, label='99% de la valeur finale')

    # Annoter quelques repères
    for pct_x in [10, 25, 50, 75]:
        idx    = int(pct_x / 100 * (N_POINTS - 1))
        val    = y_mean[idx]
        ax.annotate(f'{val:.1f}%',
                    xy=(x_norm[idx], val),
                    xytext=(x_norm[idx] + 1, val - 3),
                    fontsize=8, color=STYLE['nomad']['color'])

    ax.set_xlabel("Progression des itérations (%)")
    ax.set_ylabel("% de la puissance finale atteinte")
    ax.set_title("Convergence moyenne de NOMAD - 100 tests\n"
                 "(axe X normalisé : 0% = 1re évaluation, 100% = dernière)")
    ax.set_xlim(0, 100)
    ax.set_ylim(80, 101)
    ax.legend()
    ax.grid(alpha=0.3)
    savefig('08_convergence_moyenne.png')


def graph_boxplot_comparaison(df):
    """Boxplot distribution des erreurs et des temps PD vs NOMAD."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    ax = axes[0]
    bp = ax.boxplot(
        [df['diff_pd'].dropna(), df['diff_nomad'].dropna()],
        labels=[STYLE['pd']['label'], STYLE['nomad']['label']],
        patch_artist=True,
        medianprops={'color': 'black', 'linewidth': 1.5}
    )
    bp['boxes'][0].set_facecolor(STYLE['pd']['color'])
    bp['boxes'][1].set_facecolor(STYLE['nomad']['color'])
    for box in bp['boxes']:
        box.set_alpha(0.7)
    ax.set_ylabel('Erreur absolue (MW)')
    ax.set_title('Distribution des erreurs - PD vs NOMAD')
    ax.grid(axis='y', alpha=0.3)

    ax2 = axes[1]
    bp2 = ax2.boxplot(
        [df['t_pd'].dropna(), df['t_nomad'].dropna()],
        labels=[STYLE['pd']['label'], STYLE['nomad']['label']],
        patch_artist=True,
        medianprops={'color': 'black', 'linewidth': 1.5}
    )
    bp2['boxes'][0].set_facecolor(STYLE['pd']['color'])
    bp2['boxes'][1].set_facecolor(STYLE['nomad']['color'])
    for box in bp2['boxes']:
        box.set_alpha(0.7)
    ax2.set_ylabel('Temps (s)')
    ax2.set_title('Distribution des temps de calcul - PD vs NOMAD')
    ax2.grid(axis='y', alpha=0.3)

    fig.tight_layout()
    savefig('07_boxplot_comparaison.png')


# Tableau récapitulatif

def imprimer_tableau(df):
    print("\n" + "=" * 65)
    print("TABLEAU RÉCAPITULATIF - 100 TESTS")
    print("=" * 65)
    stats = {
        'Erreur abs. PD (MW)':    df['diff_pd'],
        'Erreur abs. NOMAD (MW)': df['diff_nomad'],
        'Temps PD (s)':           df['t_pd'],
        'Temps NOMAD (s)':        df['t_nomad'],
        'Itérations NOMAD':       df['nb_iter'],
    }
    print(f"{'Métrique':<28} {'Moy.':>8} {'Méd.':>8} {'Min':>8} {'Max':>8}")
    print("-" * 65)
    for label, serie in stats.items():
        s = serie.dropna()
        print(f"{label:<28} {s.mean():>8.2f} {s.median():>8.2f} {s.min():>8.2f} {s.max():>8.2f}")
    print("=" * 65)

    # Export CSV
    rows = []
    for label, serie in stats.items():
        s = serie.dropna()
        rows.append({'Métrique': label, 'Moyenne': round(s.mean(), 3),
                     'Médiane': round(s.median(), 3), 'Min': round(s.min(), 3), 'Max': round(s.max(), 3)})
    recap = pd.DataFrame(rows)
    path = os.path.join(OUT_DIR, 'tableau_recap.csv')
    recap.to_csv(path, index=False, encoding='utf-8-sig')
    print(f"\nTableau exporté : {path}")


if __name__ == '__main__':
    print("=" * 65)
    print("Collecte des résultats (100 tests PD + NOMAD)...")
    print("Turbines actives déduites depuis data.xlsx (Q != 0).")
    print("=" * 65)

    df = collecter()

    csv_path = os.path.join(OUT_DIR, 'resultats_100tests.csv')
    df.to_csv(csv_path, index=False)
    print(f"\nRésultats bruts sauvegardés : {csv_path}")

    print("\nGénération des graphiques...")
    graph_puissance_moyenne(df)
    graph_erreur_moyenne(df)
    graph_distribution_erreur(df)
    graph_iterations_nomad(df)
    graph_temps_calcul(df)
    graph_scatter_pd_vs_nomad(df)
    graph_convergence_moyenne(df)
    graph_boxplot_comparaison(df)

    imprimer_tableau(df)

    print(f"\n8 graphiques générés dans : {OUT_DIR}")