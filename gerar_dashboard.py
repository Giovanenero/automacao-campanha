"""
gerar_dashboard.py
==================
Gera o dashboard.html a partir de consolidado.csv e dashboard_template.html.

Uso:
    python gerar_dashboard.py
    python gerar_dashboard.py --csv outro_arquivo.csv --output meu_dashboard.html
"""

import argparse
import ast
import json
import os
import sys

try:
    import pandas as pd
    from shapely import wkt
    from shapely.geometry import MultiPolygon
except ImportError as e:
    sys.exit(f"Dependência ausente: {e}\nInstale com: pip install pandas shapely")


# ---------------------------------------------------------------------------
# Configurações padrão
# ---------------------------------------------------------------------------
DEFAULT_CSV      = "consolidado.csv"
DEFAULT_TEMPLATE = "dashboard_template.html"
DEFAULT_OUTPUT   = "dashboard.html"
SIMPLIFY_TOL     = 0.005   # graus — reduz tamanho do arquivo


# ---------------------------------------------------------------------------
# Processamento do CSV
# ---------------------------------------------------------------------------
def processar_csv(csv_path: str) -> list[dict]:
    df = pd.read_csv(csv_path, sep=";", encoding="utf-8")

    # Remove registros sem cidade válida
    df = df[df["cidade"].notna() & (df["cidade"].str.strip() != "NAO_ENCONTRADO")]

    records = []
    for _, row in df.iterrows():
        geom_raw = row.get("geometry", "")
        if not isinstance(geom_raw, str) or not geom_raw.strip():
            continue

        try:
            geom = wkt.loads(geom_raw)
        except Exception:
            continue

        # Garante que temos um Polygon (pega o maior em MultiPolygon)
        if geom.geom_type == "MultiPolygon":
            geom = max(geom.geoms, key=lambda g: g.area)
        elif geom.geom_type != "Polygon":
            continue

        geom = geom.simplify(SIMPLIFY_TOL, preserve_topology=True)
        coords = [[round(lat, 5), round(lon, 5)]
                  for lon, lat in geom.exterior.coords]

        # tipo_emendas pode vir como string representando lista
        te = row.get("tipo_emendas", "")
        if isinstance(te, str) and te.strip().startswith("["):
            try:
                te = ast.literal_eval(te)
            except Exception:
                te = []
        elif not isinstance(te, list):
            te = []

        def safe_int(v):
            try: return int(float(v) if pd.notna(v) else 0)
            except: return 0

        def safe_float(v):
            try: return float(str(v).replace(",", ".")) if pd.notna(v) else 0.0
            except: return 0.0

        records.append({
            "c":  str(row.get("cidade", "")).strip(),
            "of": safe_int(row.get("total_oficios")),
            "ro": str(row.get("resumo_oficio",        "") or "").strip(),
            "ts": safe_int(row.get("total_solicitacoes")),
            "rs": str(row.get("resumo_solicitacoes",  "") or "").strip(),
            "vt": safe_float(row.get("Valor total")),
            "vl": safe_float(row.get("Valor liberado")),
            "re": str(row.get("resumo_emendas",       "") or "").strip(),
            "te": te,
            "g":  coords,
        })

    return records


# ---------------------------------------------------------------------------
# Geração do dashboard
# ---------------------------------------------------------------------------
def gerar(csv_path: str, template_path: str, output_path: str) -> None:
    print(f"[1/3] Lendo dados de '{csv_path}'...")
    records = processar_csv(csv_path)
    print(f"      {len(records)} municípios processados.")

    print(f"[2/3] Lendo template '{template_path}'...")
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    if '<script id="dataScript">' not in html:
        sys.exit("ERRO: placeholder '<script id=\"dataScript\">' não encontrado no template.")

    data_json  = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    data_tag   = f'<script>window.MAPA_DATA={data_json};</script>'
    html_final = html.replace('<script id="dataScript">window.MAPA_DATA=[];</script>', data_tag)

    print(f"[3/3] Salvando '{output_path}'...")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_final)

    size_kb = round(os.path.getsize(output_path) / 1024, 1)
    print(f"\n✔  Dashboard gerado com sucesso: {output_path}  ({size_kb} KB)")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera dashboard.html a partir de consolidado.csv")
    parser.add_argument("--csv",      default=DEFAULT_CSV,      help="Caminho do CSV consolidado")
    parser.add_argument("--template", default=DEFAULT_TEMPLATE, help="Caminho do template HTML")
    parser.add_argument("--output",   default=DEFAULT_OUTPUT,   help="Caminho do HTML de saída")
    args = parser.parse_args()

    for path, label in [(args.csv, "CSV"), (args.template, "template")]:
        if not os.path.isfile(path):
            sys.exit(f"ERRO: {label} não encontrado: '{path}'")

    gerar(args.csv, args.template, args.output)
