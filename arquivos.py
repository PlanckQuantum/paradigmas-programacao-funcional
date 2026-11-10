import csv
import io
import json
from pathlib import Path


def _validar_registro(par):
    numero, registro = par
    if None in registro or any(map(lambda valor: valor is None, registro.values())):
        raise ValueError(f'CSV malformado na linha {numero}; confira o separador')
    return dict(map(lambda item: (item[0].strip(), item[1].strip()), registro.items()))


def interpretar_csv(conteudo: bytes) -> tuple[dict[str, str], ...]:
    try:
        texto = conteudo.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = conteudo.decode('cp1252')
    cabecalho = texto.splitlines()[0] if texto.strip() else ''
    if not cabecalho:
        raise ValueError('CSV vazio')
    delimitador = ';' if cabecalho.count(';') > cabecalho.count(',') else ','
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delimitador)
    nomes = tuple(map(str.strip, leitor.fieldnames or ()))
    if len(set(nomes)) != len(nomes):
        raise ValueError('CSV com colunas duplicadas')
    return tuple(map(_validar_registro, enumerate(leitor, start=2)))


ler_csv = lambda caminho: interpretar_csv(caminho.read_bytes())
ler_json = lambda caminho: json.loads(caminho.read_text(encoding='utf-8'))


def salvar_csv(caminho: Path, linhas, campos=None):
    linhas = tuple(linhas)
    if not linhas and campos is None:
        raise ValueError('Não é possível salvar CSV sem cabeçalho')
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + '.part')
    with temporario.open('w', encoding='utf-8-sig', newline='') as arquivo:
        writer = csv.DictWriter(
            arquivo, fieldnames=campos or tuple(linhas[0]),
            delimiter=';', extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(linhas)
    temporario.replace(caminho)
