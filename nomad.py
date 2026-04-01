import sys
import os
from centrale import Centrale

# Lecture des paramètres depuis les variables d'environnement (passées par interface.py)
DEBIT_TOTAL  = float(os.environ.get('NOMAD_DEBIT',  567.58))
NIVEAU_AMONT = float(os.environ.get('NOMAD_NIVEAU', 137.88))
DEBIT_MAX    = float(os.environ.get('NOMAD_DEBIT_MAX', 160))
TURBINES     = [int(t) for t in os.environ.get('NOMAD_TURBINES', '1,2,3,4,5').split(',')]

centrale = Centrale(
    nb_turbines=len(TURBINES),
    debit_max_par_turbine=DEBIT_MAX,
    palier_discretisation=5,
    turbines_disponibles=TURBINES
)

def eval_nomad(x):
    Q_last = DEBIT_TOTAL - sum(x)

    if Q_last < 0 or Q_last > DEBIT_MAX:
        f = 1e20
        c1 = 1
        c2 = 1
        return f, c1, c2

    x_full = x + [Q_last]

    f = centrale.boite_noire(DEBIT_TOTAL, NIVEAU_AMONT, x_full)

    # Contraintes
    c1 = 0
    c2 = 0

    return f, c1, c2


if __name__ == "__main__":
    # 1) lire le fichier
    filename = sys.argv[1]

    with open(filename, "r") as f:
        values = [round(float(v)) for v in f.read().split()]

    # 2) évaluer
    f, c1, c2 = eval_nomad(values)

    # 3) SORTIE POUR NOMAD
    print(f, c1, c2)