from preditor.extract import extract


def _first(text):
    ofs = extract(text, first_seen_at="2020-09-15T20:00:00+00:00").ofertas
    assert ofs, text
    return ofs[0]


def test_destino_oferece_bonus_nas_transferencias_da_origem():
    o = _first("Smiles oferece até 100% de bônus nas transferências da Livelo de 16/09 a 30/09.")
    assert (o.origem, o.destino) == ("livelo", "smiles")


def test_destino_oferece_bonus_nas_transferencias_feitas_da_origem():
    o = _first("Smiles oferece até 100% de bônus nas transferências feitas da Livelo de 24/11 a 30/11.")
    assert (o.origem, o.destino) == ("livelo", "smiles")


def test_origem_para_destino_continua_valendo():
    o = _first("Livelo para Smiles com 80% de bônus de 19/03 a 31/03.")
    assert (o.origem, o.destino) == ("livelo", "smiles")
