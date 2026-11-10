import argparse
import calendar
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
from itertools import chain
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from arquivos import salvar_csv
from processamento import CODIGOS_UF, normalizar_cnpj, numero

BASE = 'https://dadosabertos.aneel.gov.br/api/3/action/'
TARIFAS_ID = 'fcf2906c-7c32-4b9b-a637-054e7a5234f4'
INDGER_ID = 'fd10c9d4-cb76-4020-a322-e79afb13eaf7'
CSV_OFICIAL = 'https://dadosabertos.aneel.gov.br/dataset/5a583f3e-1646-4f67-bf0f-69db4203e89e/resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4/download/tarifas-homologadas-distribuidoras-energia-eletrica.csv'
GEO_URL = 'https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF'
FILTRO_API = {'DscSubGrupo':'B1','DscModalidadeTarifaria':'Convencional',
              'DscClasse':'Residencial','DscSubClasse':'Residencial',
              'DscBaseTarifaria':'Tarifa de Aplicação'}
PASTA = Path(__file__).resolve().parent / 'dados'


def obter(url):
    with urlopen(Request(url, headers={'User-Agent': 'ProjetoAcademicoTarifas/1.0'}),
                 timeout=90) as resposta:
        raw = resposta.read()
    return gzip.decompress(raw) if raw[:2] == b'\x1f\x8b' else raw


def _consultar_paginas(recurso, filtros, campos, registros=(), total=None):
    if total is not None and len(registros) >= total:
        return registros
    parametros = {
        'resource_id': recurso, 'filters': json.dumps(filtros),
        'limit': 5000, 'offset': len(registros), 'sort': '_id asc'
    }
    if campos:
        parametros['fields'] = ','.join(campos)
    pagina = json.loads(obter(BASE + 'datastore_search?' + urlencode(parametros)))
    if not pagina.get('success'):
        raise RuntimeError(f'Consulta recusada: {pagina.get("error")}')
    resultado = pagina['result']
    if total is not None and resultado['total'] != total:
        raise RuntimeError('A base mudou durante a coleta. Execute novamente.')
    total = resultado['total']
    novos = tuple(resultado['records'])
    if not novos and len(registros) < total:
        raise RuntimeError('Paginação incompleta: a coleta foi interrompida')
    return _consultar_paginas(recurso, filtros, campos, registros + novos, total)


consultar = lambda recurso, filtros, campos=None: _consultar_paginas(recurso, filtros, campos)


def _converter_evidencia(registro):
    codigos = dict(CODIGOS_UF)
    municipio = str(registro['CodMunicipioIBGE']).strip()
    if len(municipio) != 7 or not municipio.isdigit() or municipio[:2] not in codigos:
        raise ValueError(f'Código de município inválido: {municipio}')
    inicio = date.fromisoformat(registro['DatReferenciaInformada'])
    fim = date(inicio.year, inicio.month, calendar.monthrange(inicio.year, inicio.month)[1])
    fonte = f'https://dadosabertos.aneel.gov.br/dataset/indger-indicadores-gerenciais-da-distribuicao/resource/{INDGER_ID}'
    return (normalizar_cnpj(registro['NumCNPJ']), codigos[municipio[:2]],
            inicio.replace(day=1).isoformat(), fim.isoformat(), fonte)


gerar_vinculos = lambda registros: tuple(map(
    lambda valores: dict(zip(('CNPJ', 'UF', 'Inicio', 'Fim', 'Fonte'), valores)),
    sorted(set(map(
        _converter_evidencia,
        filter(lambda registro: numero(registro['QtdUCAtiva']) > 0, registros)
    )))
))


hash_arquivo = lambda caminho: hashlib.sha256(caminho.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anos', type=int, nargs='+', default=[2024, 2025],
                        help='Dezembro de cada ano para evidência geográfica')
    args = parser.parse_args()
    PASTA.mkdir(exist_ok=True)

    tarifas = consultar(TARIFAS_ID, FILTRO_API)
    if not tarifas:
        raise RuntimeError('Fonte retornou zero tarifas; arquivos anteriores preservados')

    anos = tuple(sorted(set(args.anos)))
    consultas = tuple(map(lambda ano: (
        ano, consultar(
            INDGER_ID, {'DatReferenciaInformada': f'{ano}-12-01'},
            ('NumCNPJ','SigAgente','CodMunicipioIBGE','DatReferenciaInformada','QtdUCAtiva')
        )
    ), anos))
    vazia = next(filter(lambda par: not par[1], consultas), None)
    if vazia is not None:
        raise RuntimeError(f'Não há evidência municipal em dezembro/{vazia[0]}; escolha ano disponível')
    evidencias = tuple(chain.from_iterable(map(lambda par: par[1], consultas)))
    vinculos = gerar_vinculos(evidencias)
    geo = json.loads(obter(GEO_URL))
    if set(map(lambda feature: feature['properties']['codarea'], geo['features'])) != set(map(lambda par: par[0], CODIGOS_UF)):
        raise RuntimeError('Malha do IBGE não contém exatamente as 27 UFs esperadas')

    salvar_csv(PASTA / 'tarifas_aneel.csv', tarifas,
               tuple(filter(lambda campo: campo != '_id', tarifas[0])))
    salvar_csv(PASTA / 'evidencias_indger.csv', evidencias)
    salvar_csv(PASTA / 'mapeamento_aneel.csv', vinculos)
    (PASTA / 'brasil_ufs.geojson').write_text(json.dumps(geo), encoding='utf-8')

    caminhos = tuple(map(lambda nome: PASTA / nome, (
        'tarifas_aneel.csv', 'evidencias_indger.csv',
        'mapeamento_aneel.csv', 'brasil_ufs.geojson'
    )))
    manifesto = {
        'origem': 'ANEEL / IBGE; dados reais',
        'coletado_em_utc': datetime.now(timezone.utc).isoformat(),
        'tarifas_resource_id': TARIFAS_ID, 'tarifas_csv_original': CSV_OFICIAL,
        'filtro_api': FILTRO_API, 'registros_tarifarios': len(tarifas),
        'indger_resource_id': INDGER_ID, 'anos_mapeados': list(anos),
        'registros_municipais': len(evidencias), 'vinculos_uf': len(vinculos),
        'geojson_url': GEO_URL, 'licenca_aneel': 'Open Data Commons Open Database License (ODbL)',
        'nota': 'Mapeamento derivado de municípios com UC ativa > 0, apenas no mês observado; cobertura parcial possível.',
        'sha256': dict(map(lambda p: (p.name, hash_arquivo(p)), caminhos))
    }
    (PASTA / 'fontes.json').write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=2), encoding='utf-8'
    )


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError) as erro:
        raise SystemExit(f'Coleta não concluída: {erro}.')
