from centrale import Centrale

centrale = Centrale(
    nb_turbines=5,
    debit_max_par_turbine=160,
    palier_discretisation=5,
    turbines_disponibles=[1, 2, 3, 4, 5]
)

DEBIT_TOTAL = round(567.58 / 5) * 5
NIVEAU_AMONT = 137.88

def eval(x):
    x = list(x)  # Q1, Q2, Q3, Q4

    Q5 = DEBIT_TOTAL - sum(x)

    # pénalité si invalide
    if Q5 < 0 or Q5 > 160:
        return 1e20, [1]

    x_full = x + [Q5]  # reconstruction des 5 turbines

    return centrale.boite_noire(DEBIT_TOTAL, NIVEAU_AMONT, x_full)

if __name__ == "__main__":
    test_x = [120, 100, 100, 100]
    print(eval(test_x))