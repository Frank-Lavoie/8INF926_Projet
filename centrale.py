from turbine import Turbine

class Centrale:
    def __init__(self, debit_max_par_turbine, nb_turbines, palier_discretisation):
        self.debit_max_par_turbine = debit_max_par_turbine
        self.palier_discretisation = palier_discretisation
        self.nb_turbines = nb_turbines
        self.turbines : Turbine = []
        for i in range(nb_turbines + 1):
            self.turbines.append(Turbine(i, debit_max_par_turbine))

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

        etats_turbine_en_cours = []
        decision_turbine_en_cours = []
        # Turbine 1
        self.turbines[1].set_niveau_amont(niveau_amont)
        for debit in debits:
            etats_turbine_en_cours.append(self.turbines[1].calculer_puissance(debit, elevation_aval))
            decision_turbine_en_cours.append(debit)
        etats.append(etats_turbine_en_cours)
        decisions.append(decision_turbine_en_cours)

        # Turbine 2-3-4-5
        for j in range(2, 6):
            etats_j = []
            decisions_j = []

            self.turbines[j].set_niveau_amont(niveau_amont)

            for debit in debits:  # débit total disponible
                meilleur = -float("inf")
                meilleur_x = 0

                for x in range(0, debit + 1, self.palier_discretisation):
                    q_restant = debit - x
                    idx = q_restant // self.palier_discretisation

                    valeur = (
                        etats[j - 2][idx]
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
    
    def reconstruire_solution(self,decisions, etats):

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
        p2 = 0.007 * self.debit_total
        p3 = 99.9812
        return p2 + p3

    # def __str__(self):
    #     return f"Centrale {self.nom} avec débits: {self.q1}, {self.q2}, {self.q3}, {self.q4}, {self.q5}"