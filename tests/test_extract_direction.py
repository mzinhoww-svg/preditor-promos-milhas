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


def test_inclusive_lista_origens_e_destino_vem_do_para():
    o = _first("Transferência bonificada: até 80% de bônus para a Smiles, inclusive Livelo e Esfera, até 20/10.")
    assert (o.origem, o.destino) == ("livelo", "smiles")


def test_exceto_programa_nao_conta():
    o = _first("A Smiles oferece até 80% de bônus nas transferências de pontos da Livelo, exceto Esfera, até 20/10.")
    assert (o.origem, o.destino) == ("livelo", "smiles")


def test_inclusive_livelo_e_esfera_travessao_para_a_smiles():
    o = _first("Último dia para ganhar até 90% de bônus nas transferências de pontos de todos os parceiros "
               "financeiros – inclusive Livelo e Esfera – para a Smiles. A oferta é válida até hoje (20).")
    assert (o.origem, o.destino) == ("livelo", "smiles")


def test_todos_os_parceiros_exceto_esfera_nao_inventa_origem():
    ofs = extract("Segue valendo a oferta da Smiles de 70% de bônus nas transferências de pontos, válido para "
                  "todos os parceiros financeiros, exceto Esfera. Válida somente até hoje (12).",
                  first_seen_at="2026-02-12T10:00:00-03:00").ofertas
    assert all(o.origem != "esfera" and o.destino != "esfera" for o in ofs)


def test_milhas_bonus_conta_como_bonus():
    o = _first("O LATAM Pass está oferecendo até 35% de milhas bônus nas transferências da Livelo. "
               "A campanha é válida até 23h59 de amanhã (25).")
    assert o.bonus_pct == 35 and (o.origem, o.destino) == ("livelo", "latam_pass")
