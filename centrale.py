from turbine import Turbine

class Centrale:
    def __init__(self, debit_max_par_turbine, nb_turbines, palier_discretisation, turbines_disponibles=None):
        self.debit_max_par_turbine = debit_max_par_turbine
        self.palier_discretisation = palier_discretisation
        self.nb_turbines = nb_turbines

        if turbines_disponibles is not None:
            numeros = turbines_disponibles
        else:
            numeros = list(range(1, nb_turbines + 1))

        self.turbines: list[Turbine] = [Turbine(n, debit_max_par_turbine) for n in numeros]

    def set_debit_total(self, debit_total):
        self.debit_total = min(debit_total, self.debit_max_par_turbine * len(self.turbines))

    def get_paliers_discretise(self, debit):
        paliers = [0]
        index = 0

        while(debit > 0):
            ajout = min(debit, self.palier_discretisation)
            paliers.append(index * self.palier_discretisation + ajout)
            index += 1
            debit -= ajout
        return paliers

    def repartir_debit2(self, debit, niveau_amont):
        self.set_debit_total(debit)
        elevation_aval = self.elevation_aval()
        debits = self.get_paliers_discretise(self.debit_total)
        etats = []
        decisions = []

        self.turbines[0].set_niveau_amont(niveau_amont)
        etats_t0 = []
        decisions_t0 = []
        for q in debits:
            etats_t0.append(self.turbines[0].calculer_puissance(q, elevation_aval))
            decisions_t0.append(q)
        etats.append(etats_t0)
        decisions.append(decisions_t0)

        for j in range(1, len(self.turbines)):
            etats_j = []
            decisions_j = []

            self.turbines[j].set_niveau_amont(niveau_amont)

            for q in debits:
                meilleur = -float("inf")
                meilleur_x = 0

                for x in range(0, q + 1, self.palier_discretisation):
                    q_restant = q - x
                    idx = q_restant // self.palier_discretisation

                    valeur = (
                        etats[j - 1][idx]
                        + self.turbines[j].calculer_puissance(x, elevation_aval)
                    )

                    if valeur > meilleur:
                        meilleur = valeur
                        meilleur_x = x

                etats_j.append(meilleur)
                decisions_j.append(meilleur_x)

            etats.append(etats_j)
            decisions.append(decisions_j)

        return etats, decisions

    def reconstruire_solution(self, decisions, etats):

        nb_turbines = len(decisions)
        solution = [0] * nb_turbines

        q_restant = self.debit_total
        idx = q_restant // self.palier_discretisation

        # reconstruction en remontant les turbines
        for i in range(nb_turbines - 1, -1, -1):
            x = decisions[i][idx]
            solution[i] = x

            q_restant -= x
            idx = q_restant // self.palier_discretisation

        # puissance totale optimale (déjà calculée par la DP)
        puissance_totale = etats[-1][self.debit_total // self.palier_discretisation]

        return solution, puissance_totale


    def elevation_aval(self):
        p1 = -1.4527e-06 * (self.debit_total ** 2)
        p2 = 0.007 * self.debit_total
        p3 = 99.9812
        return p1 + p2 + p3

    # def __str__(self):
    #     return f"Centrale {self.nom} avec débits: {self.q1}, {self.q2}, {self.q3}, {self.q4}, {self.q5}"