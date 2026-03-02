import flask
from centrale import Centrale

app = flask.Flask(__name__)

@app.route('/')
def home():
    centrale = Centrale(nb_turbines=5, debit_max_par_turbine=160, palier_discretisation=5)
    paliers = centrale.get_paliers_discretise(580.3)
    # # etats, decisions = centrale.repartir_debit(580.3, 137.89)
    # # etats = f"{etats[0]}</br>{etats[1]}</br>{etats[2]}</br>{etats[3]}</br>{etats[4]}</br>"
    # # decisions = f"{decisions[0]}</br>{decisions[1]}</br>{decisions[2]}</br>{decisions[3]}</br>{decisions[4]}</br>"
    # # centrale.construire_solution(etats, decisions)
    # return f"{etats}</br></br>{decisions}"
    etats, decisions = centrale.repartir_debit2(580, 137.89)
    sol, p = centrale.reconstruire_solution(decisions=decisions, etats=etats)
    return f"{sol}</br>{p}"

if __name__ == '__main__':
    app.run(debug=True)