"""
Gera um card SVG personalizado com suas estatísticas do GitHub,
incluindo contribuições em repositórios privados (ex.: da empresa).

Uso:
  STATS_TOKEN=ghp_xxx python scripts/gerar_stats.py      # dados reais
  python scripts/gerar_stats.py --demo                     # dados de exemplo

Variáveis opcionais:
  STATS_NOME     nome exibido (padrão: nome do perfil no GitHub)
  STATS_CARGO    linha abaixo do nome, ex.: "Engenheiro de Software na Acme"
  STATS_EMPRESA  usado na frase de resumo, ex.: "Acme"

Nomes de repositórios privados nunca aparecem no card.
"""
import datetime as dt
import json
import os
import random
import sys
import urllib.request
from collections import Counter
from xml.sax.saxutils import escape

MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

TEMAS = {
    "claro": {
        "fundo": "#EEF2F1", "texto": "#1D2B2A", "suave": "#5E706D", "linha": "#CFD9D6",
        "barra_min": "#B9D6CD", "barra_max": "#1F6F5C", "destaque": "#1F6F5C",
        "linguagens": ["#1F6F5C", "#3E8E7A", "#6AAE9C", "#9BC9BC", "#C6E0D8", "#DDE7E4"],
    },
    "escuro": {
        "fundo": "#13201E", "texto": "#E4EEEB", "suave": "#8FA6A1", "linha": "#2A3A37",
        "barra_min": "#2C4A43", "barra_max": "#7FD6BC", "destaque": "#7FD6BC",
        "linguagens": ["#7FD6BC", "#5DB59C", "#45907C", "#356F60", "#2A5248", "#22403A"],
    },
}

QUERY = """
query($from: DateTime!, $to: DateTime!) {
  viewer {
    login name
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalRepositoriesWithContributedCommits
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        contributions { totalCount }
        repository { isPrivate primaryLanguage { name } }
      }
    }
  }
}
"""


def fmt(n):
    return f"{n:,}".replace(",", ".")


def buscar_dados(token):
    hoje = dt.datetime.now(dt.timezone.utc)
    variaveis = {"from": (hoje - dt.timedelta(days=364)).isoformat(), "to": hoje.isoformat()}
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": variaveis}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        resp = json.load(r)
    if "errors" in resp:
        sys.exit(f"Erro da API do GitHub: {resp['errors']}")
    v = resp["data"]["viewer"]
    c = v["contributionsCollection"]

    dias = [(d["date"], d["contributionCount"])
            for w in c["contributionCalendar"]["weeks"] for d in w["contributionDays"]]

    linguagens = Counter()
    privadas = 0
    for item in c["commitContributionsByRepository"]:
        n = item["contributions"]["totalCount"]
        repo = item["repository"]
        if repo["isPrivate"]:
            privadas += n
        if repo["primaryLanguage"]:
            linguagens[repo["primaryLanguage"]["name"]] += n

    return {
        "nome": os.getenv("STATS_NOME") or v["name"] or v["login"],
        "cargo": os.getenv("STATS_CARGO", ""),
        "empresa": os.getenv("STATS_EMPRESA", ""),
        "total": c["contributionCalendar"]["totalContributions"],
        "commits": c["totalCommitContributions"] + c["restrictedContributionsCount"],
        "prs": c["totalPullRequestContributions"],
        "revisoes": c["totalPullRequestReviewContributions"],
        "repos": c["totalRepositoriesWithContributedCommits"],
        "fracao_privada": privadas / max(1, c["totalCommitContributions"]),
        "dias": dias,
        "linguagens": linguagens,
    }


def dados_demo():
    random.seed(7)
    hoje = dt.date.today()
    inicio = hoje - dt.timedelta(days=364 + (hoje.weekday() + 1) % 7)
    dias = []
    d = inicio
    while d <= hoje:
        util = d.weekday() < 5
        base = random.choice([0, 2, 4, 6, 9]) if util else random.choice([0, 0, 0, 1])
        if dt.date(hoje.year, 1, 1) - dt.timedelta(days=10) < d < dt.date(hoje.year, 1, 1) + dt.timedelta(days=5):
            base = 0
        dias.append((d.isoformat(), base))
        d += dt.timedelta(days=1)
    total = sum(n for _, n in dias)
    return {
        "nome": "Mariana Costa", "cargo": "Engenheira de Software na Acme Pagamentos",
        "empresa": "Acme", "total": total, "commits": int(total * 0.72), "prs": 214,
        "revisoes": 309, "repos": 18, "fracao_privada": 0.91, "dias": dias,
        "linguagens": Counter({"TypeScript": 820, "Python": 510, "Go": 230, "SQL": 120, "Shell": 60, "HCL": 40}),
    }


def misturar(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def sequencias(dias):
    contagens = [n for _, n in dias]
    recorde = atual = 0
    for n in contagens:
        atual = atual + 1 if n > 0 else 0
        recorde = max(recorde, atual)
    i = len(contagens) - 1
    if contagens[i] == 0:  # hoje ainda sem commit não quebra a sequência
        i -= 1
    corrente = 0
    while i >= 0 and contagens[i] > 0:
        corrente += 1
        i -= 1
    return corrente, recorde


def desenhar(d, tema):
    t = TEMAS[tema]
    W, H, P = 840, 400, 36
    fonte = "'Avenir Next','Segoe UI',system-ui,-apple-system,Helvetica,Arial,sans-serif"
    s = []

    # semanas
    semanas = [d["dias"][i:i + 7] for i in range(0, len(d["dias"]), 7)]
    totais = [sum(n for _, n in w) for w in semanas]
    pico = max(totais) or 1
    i_pico = totais.index(pico)

    corrente, recorde = sequencias(d["dias"])
    por_dia = Counter()
    for data, n in d["dias"]:
        por_dia[dt.date.fromisoformat(data).weekday()] += n
    dia_ativo = DIAS[por_dia.most_common(1)[0][0]] if por_dia else "—"

    s.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
             f'font-family="{fonte}" role="img" aria-label="Estatísticas de contribuição de {escape(d["nome"])}">')
    s.append(f'<rect width="{W}" height="{H}" rx="14" fill="{t["fundo"]}"/>')

    # cabeçalho
    s.append(f'<text x="{P}" y="{P + 24}" font-size="24" font-weight="600" fill="{t["texto"]}">{escape(d["nome"])}</text>')
    if d["cargo"]:
        s.append(f'<text x="{W - P}" y="{P + 24}" font-size="13" text-anchor="end" fill="{t["suave"]}">{escape(d["cargo"])}</text>')
    frase = f'{fmt(d["total"])} contribuições nos últimos 12 meses'
    if d["fracao_privada"] >= 0.5:
        frase += f', {round(d["fracao_privada"] * 100)}% delas em repositórios privados'
        if d["empresa"]:
            frase += f' da {escape(d["empresa"])}'
    s.append(f'<text x="{P}" y="{P + 50}" font-size="14" fill="{t["suave"]}">{frase}.</text>')

    # onda de semanas
    topo, base = 116, 236
    alt = base - topo
    largura = (W - 2 * P) / len(semanas)
    for i, total in enumerate(totais):
        h = max(2, alt * total / pico) if total else 2
        intensidade = total / pico
        cor = misturar(t["barra_min"], t["barra_max"], intensidade) if total else t["linha"]
        x = P + i * largura + 1
        s.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{largura - 2:.1f}" height="{h:.1f}" rx="2" fill="{cor}"/>')

    # anotação do pico
    x_pico = P + i_pico * largura + largura / 2
    data_pico = dt.date.fromisoformat(semanas[i_pico][0][0])
    rotulo = f'pico: {fmt(pico)} na semana de {data_pico.day} {MESES[data_pico.month - 1]}'
    ancora = "start" if x_pico < W / 2 else "end"
    dx = 10 if ancora == "start" else -10
    s.append(f'<circle cx="{x_pico:.1f}" cy="{topo - 9}" r="3" fill="{t["destaque"]}"/>')
    s.append(f'<text x="{x_pico + dx:.1f}" y="{topo - 5}" font-size="12" text-anchor="{ancora}" fill="{t["suave"]}">{rotulo}</text>')

    # meses
    ultimo = None
    for i, w in enumerate(semanas):
        m = dt.date.fromisoformat(w[0][0]).month
        if m != ultimo and i > 0:
            s.append(f'<text x="{P + i * largura:.1f}" y="{base + 18}" font-size="11" fill="{t["suave"]}">{MESES[m - 1]}</text>')
        ultimo = m
    s.append(f'<line x1="{P}" y1="{base + 34}" x2="{W - P}" y2="{base + 34}" stroke="{t["linha"]}"/>')

    # números
    numeros = [
        (fmt(d["commits"]), "commits"),
        (fmt(d["prs"]), "pull requests"),
        (fmt(d["revisoes"]), "revisões de código"),
        (fmt(d["repos"]), "repositórios"),
        (f'{corrente} dia' + ('s' if corrente != 1 else ''), f'seguidos, recorde {recorde}'),
        (dia_ativo, "dia mais ativo"),
    ]
    # colunas com largura conforme o texto, espaço restante dividido entre elas
    larguras = [max(len(v) * 12, len(r) * 6.6) for v, r in numeros]
    folga = (W - 2 * P - sum(larguras)) / (len(numeros) - 1)
    x = P
    for (valor, rotulo), largura in zip(numeros, larguras):
        s.append(f'<text x="{x:.1f}" y="{base + 68}" font-size="20" font-weight="600" fill="{t["texto"]}">{valor}</text>')
        s.append(f'<text x="{x:.1f}" y="{base + 87}" font-size="12" fill="{t["suave"]}">{rotulo}</text>')
        x += largura + folga

    # linguagens (ponderadas pelos seus commits, não pelo tamanho do repositório)
    top = d["linguagens"].most_common(5)
    resto = sum(d["linguagens"].values()) - sum(n for _, n in top)
    if resto > 0:
        top.append(("outras", resto))
    soma = sum(n for _, n in top) or 1
    y_barra = base + 112
    x = P
    lx = P
    for i, (nome, n) in enumerate(top):
        w = (W - 2 * P) * n / soma
        cor = t["linguagens"][i % len(t["linguagens"])]
        s.append(f'<rect x="{x:.1f}" y="{y_barra}" width="{max(w - 2, 1):.1f}" height="8" rx="2" fill="{cor}"/>')
        x += w
        texto = f'{escape(nome)} {round(100 * n / soma)}%'
        s.append(f'<circle cx="{lx + 4}" cy="{y_barra + 28}" r="4" fill="{cor}"/>')
        s.append(f'<text x="{lx + 13}" y="{y_barra + 32}" font-size="12" fill="{t["suave"]}">{texto}</text>')
        lx += 13 + len(texto) * 7 + 18

    s.append("</svg>")
    return "\n".join(s)


def main():
    demo = "--demo" in sys.argv
    if demo:
        dados = dados_demo()
    else:
        token = os.getenv("STATS_TOKEN")
        if not token:
            sys.exit("Defina STATS_TOKEN com um token de acesso pessoal (ou use --demo).")
        dados = buscar_dados(token)
    pasta = os.getenv("STATS_SAIDA", ".")
    for tema in TEMAS:
        caminho = os.path.join(pasta, f"stats-{tema}.svg")
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(desenhar(dados, tema))
        print("gerado:", caminho)


if __name__ == "__main__":
    main()
