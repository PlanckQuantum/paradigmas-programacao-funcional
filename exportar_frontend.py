from pathlib import Path
import hashlib
import json
import math
from itertools import chain
from arquivos import ler_csv, ler_json
from processamento import processar, normalizar_vinculos, CODIGOS_UF, UFS
from analise import fotografia, resumir, ranking, diferencas_por_uf

RAIZ = Path(__file__).resolve().parent
NOMES = dict(zip(UFS, ('Acre','Alagoas','Amapá','Amazonas','Bahia','Ceará',
    'Distrito Federal','Espírito Santo','Goiás','Maranhão','Mato Grosso','Mato Grosso do Sul',
    'Minas Gerais','Pará','Paraíba','Paraná','Pernambuco','Piauí','Rio de Janeiro',
    'Rio Grande do Norte','Rio Grande do Sul','Rondônia','Roraima','Santa Catarina',
    'São Paulo','Sergipe','Tocantins')))


def _aneis(feature):
    geometria = feature['geometry']
    if geometria['type'] == 'Polygon':
        return tuple(geometria['coordinates'])
    if geometria['type'] == 'MultiPolygon':
        return tuple(chain.from_iterable(geometria['coordinates']))
    raise ValueError('A malha deve conter apenas polígonos')


projetar = lambda ponto: (
    math.radians(ponto[0]),
    -math.log(math.tan(math.pi / 4 + math.radians(ponto[1]) / 2))
)


def projetar_mapa(geo):
    pontos = tuple(map(
        projetar,
        chain.from_iterable(chain.from_iterable(map(_aneis, geo['features'])))
    ))
    xmin, xmax = min(map(lambda p: p[0], pontos)), max(map(lambda p: p[0], pontos))
    ymin, ymax = min(map(lambda p: p[1], pontos)), max(map(lambda p: p[1], pontos))
    escala = min(560 / (xmax - xmin), 550 / (ymax - ymin))
    dx = (640 - (xmax - xmin) * escala) / 2
    dy = (600 - (ymax - ymin) * escala) / 2

    caminho = lambda anel: 'M' + 'L'.join(map(
        lambda ponto: f'{(ponto[0]-xmin)*escala+dx:.2f},{(ponto[1]-ymin)*escala+dy:.2f}',
        map(projetar, anel)
    )) + 'Z'
    codigos = dict(CODIGOS_UF)
    return tuple(map(lambda feature: {
        'uf': codigos[feature['properties']['codarea']],
        'path': ''.join(map(caminho, _aneis(feature)))
    }, geo['features']))


formatar_tarifa = lambda t: {
    'nome': t.agente, 'cnpj': t.cnpj, 'te': str(t.te), 'tusd': str(t.tusd),
    'total': str(t.total), 'inicio': t.inicio.isoformat(),
    'fim': t.fim.isoformat(), 'resolucao': t.resolucao
}


def formatar_estado(resumo, foto, resumos):
    tarifas = tuple(sorted(map(
        lambda item: item.tarifa,
        filter(lambda item: item.uf == resumo.uf, foto.itens)
    ), key=lambda t: t.total))
    return {
        'uf': resumo.uf, 'nome': NOMES[resumo.uf], 'quantidade': resumo.quantidade,
        'media': str(resumo.media) if resumo.media is not None else None,
        'diferencas': dict(map(
            lambda item: (item[0], str(item[1])),
            diferencas_por_uf(resumo, resumos).items()
        )),
        'minima': str(resumo.minima) if resumo.minima is not None else None,
        'maxima': str(resumo.maxima) if resumo.maxima is not None else None,
        'distribuidoras': list(map(formatar_tarifa, tarifas))
    }


def criar_referencia(dia, tarifas, vinculos):
    foto = fotografia(tarifas, vinculos, dia)
    resumos = resumir(foto.itens)
    ordem = ranking(resumos)
    return {
        'data': dia.isoformat(), 'ano': dia.year,
        'estados': list(map(lambda resumo: formatar_estado(resumo, foto, resumos), resumos)),
        'ranking': list(map(lambda resumo: resumo.uf, ordem)),
        'cobertura': len(ordem),
        'distribuidoras': len(set(map(lambda item: item.tarifa.cnpj, foto.itens))),
        'conflitos': list(foto.conflitos), 'semMapeamento': list(foto.sem_mapeamento)
    }


def preparar(tarifas, vinculos, geo, manifesto):
    resultado = processar(tarifas)
    vinculos = normalizar_vinculos(vinculos)
    datas = tuple(sorted(set(map(
        lambda v: v.fim,
        filter(lambda v: any(map(
            lambda t: t.cnpj == v.cnpj and t.inicio <= v.fim <= t.fim,
            resultado.tarifas
        )), vinculos)
    ))))
    referencias = list(map(
        lambda dia: criar_referencia(dia, resultado.tarifas, vinculos), datas
    ))
    return {
        'fonte': 'ANEEL', 'coleta': manifesto['coletado_em_utc'],
        'linhas': resultado.total_linhas, 'foraPerfil': resultado.fora_recorte,
        'invalidas': len(resultado.problemas), 'referencias': referencias,
        'mapa': projetar_mapa(geo), 'hashesOriginais': manifesto['sha256']
    }


def main():
    pasta = RAIZ / 'dados'
    manifesto = ler_json(pasta / 'fontes.json')
    alterado = next(filter(
        lambda par: hashlib.sha256((pasta / par[0]).read_bytes()).hexdigest() != par[1],
        manifesto['sha256'].items()
    ), None)
    if alterado:
        raise ValueError(
            f'Arquivo alterado desde a coleta: {alterado[0]}. '
            'Atualize o manifesto oficial antes de exportar.'
        )
    payload = preparar(
        ler_csv(pasta / 'tarifas_aneel.csv'),
        ler_csv(pasta / 'mapeamento_aneel.csv'),
        ler_json(pasta / 'brasil_ufs.geojson'), manifesto
    )
    destino = RAIZ / 'interface/src/data/painel.json'
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')),
                       encoding='utf-8')


if __name__ == '__main__':
    main()
