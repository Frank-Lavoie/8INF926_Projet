class Turbine:
    def __init__(self, numero):
        self.numero = numero

    def set_niveau_amont(self, niv_amont):
        self.niv_amont = niv_amont

    def calculer_puissance(self, debit, elevation_aval):
        h_nette = self.hauteur_nette(debit, elevation_aval)
        match self.numero:
            case 1 : return self.puissance_1(h_nette, debit)
            case 2 : return self.puissance_2(h_nette, debit)
            case 3 : return self.puissance_3(h_nette, debit)
            case 4 : return self.puissance_4(h_nette, debit)
            case 5 : return self.puissance_5(h_nette, debit)
        return 0

    def hauteur_brutte(self, elevation_aval):
        return self.niv_amont - elevation_aval

    def hauteur_nette(self, debit, elevation_aval):
        hauteur_brutte = self.hauteur_brutte(elevation_aval)
        print(hauteur_brutte)
        return hauteur_brutte - (0.5 * (10 ** -5 ) * (debit ** 2))   

    def degre_2(self, params, h_nette, q):
        p1 = params[0]
        p2 = params[1] * h_nette
        p3 = params[2] * q
        p4 = params[3] * (h_nette ** 2)
        p5 = params[4] * h_nette * q
        p6 = params[5] * (q ** 2)
        return p1 + p2 + p3 + p4 + p5 + p6

    def degre_3(self, params, h_nette, q):
        p1 = params[0]
        p2 = params[1] * h_nette
        p3 = params[2] * q
        p4 = params[3] * (h_nette ** 2)
        p5 = params[4] * h_nette * q
        p6 = params[5] * (q ** 2)
        p7 = params[6] * (h_nette ** 3)
        p8 = params[7] * (h_nette ** 2) * q
        p9 = params[8] * h_nette * (q ** 2)
        p10 = params[9] * (q ** 3)
        return p1 + p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9 + p10

    def puissance_1(self, h_nette, q):
        params = [-59.6891, 3.9525, -0.0633, -0.0644, 0.0120, -3.6976e-04]
        print(h_nette, q)
        return self.degre_2(params, h_nette, q)

    def puissance_2(self, h_nette, q):
        params = [81.5899, -4.1377, -0.2848, 0.0515, 0.0178, -0.0001]
        return self.degre_2(params, h_nette, q)

    def puissance_3(self, h_nette, q):
        params = [-836.9078, 66.9682, 0.8639, -1.7739, 
                -0.0509, 0.003, 0.0155, 0.0008, 0.0, -1.1553e-05]
        return self.degre_3(params, h_nette, q)

    def puissance_4(self, h_nette, q):
        params = [-2.6141e+03, 192.2533, 7.8875, -4.5859, -0.45,
                0.0024, 0.0351, 0.0064, 8.9819e-05, -1.9560e-05]
        return self.degre_3(params, h_nette, q)

    def puissance_5(self, h_nette, q):
        params = [-662.6103, 50.3204, 0.6475, -1.2511, -0.0426,
                0.0042, 0.0101, 0.0008, 0, 0]
        return self.degre_3(params, h_nette, q)