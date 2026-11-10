from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from functools import reduce
from itertools import chain, groupby
from processamento import Tarifa, Vinculo, UFS

@dataclass(frozen=True)
class ItemUF:
    uf: str
    tarifa: Tarifa

@dataclass(frozen=True)
class Fotografia:
    itens: tuple[ItemUF, ...]
    conflitos: tuple[str, ...]
    sem_mapeamento: tuple[str, ...]
    distribuidoras_vigentes: int

@dataclass(frozen=True)
class ResumoUF:
    uf: str
    quantidade: int
    media: Decimal | None
    minima: Decimal | None
    maxima: Decimal | None


media = lambda valores: (lambda par: par[0] / par[1] if par[1] else None)(
    reduce(lambda acc, valor: (acc[0] + valor, acc[1] + 1),
           valores, (Decimal(0), 0))
)


def fotografia(tarifas: tuple[Tarifa, ...], vinculos: tuple[Vinculo, ...], referencia: date) -> Fotografia:
    vigentes = tuple(filter(lambda t: t.inicio <= referencia <= t.fim, tarifas))
    grupos = tuple(map(
        lambda par: (par[0], tuple(par[1])),
        groupby(sorted(vigentes, key=lambda t: t.cnpj), key=lambda t: t.cnpj)
    ))

    escolher = lambda par: (
        par[0],
        None if len(frozenset(map(lambda t: (t.te, t.tusd), par[1]))) != 1
        else max(par[1], key=lambda t: (t.inicio, t.fim, t.resolucao, t.agente))
    )
    escolhidas = tuple(map(escolher, grupos))
    validas = tuple(filter(lambda t: t is not None, map(lambda par: par[1], escolhidas)))

    ufs_da_tarifa = lambda t: tuple(sorted(frozenset(map(
        lambda vinculo: vinculo.uf,
        filter(lambda vinculo:
               vinculo.cnpj == t.cnpj and vinculo.inicio <= referencia <= vinculo.fim,
               vinculos)
    ))))

    itens = tuple(chain.from_iterable(map(
        lambda t: map(lambda uf: ItemUF(uf, t), ufs_da_tarifa(t)), validas
    )))
    return Fotografia(
        itens,
        tuple(map(lambda par: par[0], filter(lambda par: par[1] is None, escolhidas))),
        tuple(map(lambda t: t.cnpj, filter(lambda t: not ufs_da_tarifa(t), validas))),
        len(grupos)
    )


def resumir(itens: tuple[ItemUF, ...]) -> tuple[ResumoUF, ...]:
    valores_da_uf = lambda uf: tuple(map(
        lambda t: t.total,
        reduce(
            lambda acc, item: {**acc, item.tarifa.cnpj: item.tarifa},
            filter(lambda item: item.uf == uf, itens), {}
        ).values()
    ))
    resumir_uf = lambda uf: (lambda valores: ResumoUF(
        uf, len(valores), media(valores),
        min(valores) if valores else None,
        max(valores) if valores else None
    ))(valores_da_uf(uf))
    return tuple(map(resumir_uf, UFS))


ranking = lambda resumos: tuple(sorted(
    filter(lambda r: r.media is not None, resumos),
    key=lambda r: (-r.media, r.uf)
))


diferencas_por_uf = lambda estado, resumos: (
    dict(map(
        lambda outro: (
            outro.uf,
            abs(estado.media - outro.media).quantize(
                Decimal('0.0001'), rounding=ROUND_HALF_UP
            )
        ),
        filter(lambda outro: outro.media is not None, resumos)
    )) if estado.media is not None else {}
)
