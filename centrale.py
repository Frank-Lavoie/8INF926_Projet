from turbine import Turbine

class Centrale:
    def __init__(self, debit_max_par_turbine, nb_turbines, palier_discretisation):
        self.debit_max_par_turbine = debit_max_par_turbine
        self.palier_discretisation = palier_discretisation
        self.nb_turbines = nb_turbines
        self.turbines : Turbine = []
        for i in range(nb_turbines):
            self.turbines.append(Turbine(i))

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

    def repartir_debit(self, debit, niveau_amont):

        self.set_debit_total(debit)
        elevation_aval = self.elevation_aval()

        PAS = self.palier_discretisation
        Q_MAX = min(debit, self.debit_max_par_turbine)

        N_Q = Q_MAX // PAS + 1
        NB_T = len(self.turbines)

        # tableaux DP
        etats = [[0 for _ in range(N_Q)] for _ in range(NB_T + 1)]
        decisions = [[0 for _ in range(N_Q)] for _ in range(NB_T + 1)]

        # condition initiale
        for j in range(N_Q):
            etats[0][j] = 0

        # programmation dynamique
        for turbine in self.turbines:
            i = int(turbine.numero)
            turbine.set_niveau_amont(niveau_amont)

            for j in range(N_Q):
                q = j * PAS
                meilleur = float('-inf')
                meilleur_x = 0

                for x in range(0, min(self.debit_max_par_turbine, q) + PAS, PAS):
                    j_restant = (q - x) // PAS

                    valeur = (
                        etats[i - 1][j_restant]
                        + turbine.calculer_puissance(x, elevation_aval)
                    )

                    if valeur > meilleur:
                        meilleur = valeur
                        meilleur_x = x

                etats[i][j] = meilleur
                decisions[i][j] = meilleur_x

        return etats, decisions
        
    def construire_solution(self, etats, decisions):
       pass


    def elevation_aval(self):
        p2 = 0.007 * self.debit_total
        p3 = 99.9812
        return p2 + p3

    # def __str__(self):
    #     return f"Centrale {self.nom} avec débits: {self.q1}, {self.q2}, {self.q3}, {self.q4}, {self.q5}"