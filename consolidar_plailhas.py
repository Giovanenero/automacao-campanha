import pandas as pd, unicodedata, requests, json, os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY=os.getenv('OPENROUTER_API_KEY')

instrucoes = """
    - Agrupe mentalmente os registros por cidade antes de analisar.
    - Identifique padrões e temas recorrentes.
    - Produza um resumo curto, claro e objetivo para cada cidade.
    - O resumo deve destacar as principais necessidades identificadas nos ofícios.
    - Não invente informações que não estejam nos dados.
    - Utilize linguagem institucional apropriada para relatórios públicos.
"""

formato_resposta = """
    Retorne APENAS um JSON válido no seguinte formato:
    [
        {{
            "cidade": "Nome da cidade",
            "resumo": "Resumo das principais demandas identificadas nos ofícios."
        }}
    ]
"""

headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}


df_emendas = pd.read_csv('files/listagem_registros_2026-03-05_12-33-16.csv', sep=';', encoding='utf8')
df_oficios = pd.read_csv('files/listagem_registros_2026-03-05_12-34-36.csv', sep=';', encoding='utf8')
df_solicitacoes = pd.read_csv('files/listagem_registros_2026-03-05_12-35-13.csv', sep=';', encoding='utf8')

# pega todos os municípios possíveis
with open('municipios/municipios_pr.txt') as f:
    municipios = f.readlines()[0]
    municipios = [municipio.strip() for municipio in municipios.split(',')]


def verify_municipio(municipio:str, default:str='NAO_ENCONTRADO'):
    """
        Verifica se o município é válido de acordo com a lista de municipios.
        Caso o município seja encontrado, retorna o nome do município. Caso contrário, retorna None.
    """

    if not municipio:
        return default
    
    municipio = str(municipio)
    
    municipio = municipio.split('-')[0]
    municipio = municipio.split('/')[0]

    municipio = unicodedata.normalize('NFKD', municipio)
    municipio = municipio.encode('ASCII', 'ignore').decode('utf-8')
    municipio = municipio.strip().upper()

    for m in municipios:
        if m.lower() == municipio.lower():
            return municipio
    return default


if not municipios:
    print("Nenhum município encontrado no arquivo municipios_pr.txt")
    exit(1)


columns = df_oficios.columns.tolist()
column_name = next((column for column in columns if 'cidade' in column.lower() or 'município' in column.lower()), None)

if column_name:

    df_oficios[column_name] = df_oficios[column_name].apply(verify_municipio)

    # agrupar o numero de oficios por cidade
    df_oficios_groupby = df_oficios.groupby(column_name).size().reset_index(name='total_oficios')
    df_oficios_groupby.rename(columns={column_name: 'cidade'}, inplace=True)
    
    # pega todos os registros agrupador por cidade e monte um resumo por cidade utulizando a api do openrouter
    registros_cidades = {}
    for cidade in df_oficios_groupby['cidade'].tolist(): 
        df_aux = df_oficios[df_oficios[column_name] == cidade]
        if df_aux.empty:
            continue
        records = df_aux.fillna('').replace('', None).to_dict(orient='records')
        registros_cidades.update({cidade: records})


    prompt = f"""
        Você é um especialista em análise de dados públicos e políticas públicas municipais.

        <contexto>
        Os dados fornecidos estão em formato JSON e representam registros de ofícios enviados por diferentes cidades. 
        Cada registro contém informações sobre o tipo de demanda, área de interesse, descrição da solicitação e outras informações relevantes.
        </contexto>

        <tarefa>
        Analise os registros de ofício e identifique, para cada cidade:
        - Os principais tipos de demandas apresentadas
        - As áreas mais recorrentes (ex: infraestrutura, saúde, educação, agricultura, transporte etc.)
        - Possíveis necessidades prioritárias da população com base nos ofícios
        </tarefa>

        <instruções>
        {instrucoes}
        </instruções>

        <dados>
        {registros_cidades}
        </dados>

        <objetivo>
        Gerar um resumo conciso que ajude equipes de gabinete e gestores públicos a compreender rapidamente 
        as principais demandas de cada município, apoiando decisões e priorização de políticas públicas.
        </objetivo>

        <formato_resposta>
        {formato_resposta}
        </formato_resposta>
    """

    messages = [{"role": "user", "content": prompt}]
    payload = {"model": 'google/gemini-2.5-flash-lite', "messages": messages, "temperature": 0.0}
    response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    response_json = response.json()
    message = response_json.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    data = json.loads(message.replace('```json', '').replace('```', ''))
    #cost = response_json.get('usage', {}).get('cost', None)
    
    df_oficios_groupby['resumo_oficio'] = None
    for item in data:
        df_oficios_groupby.loc[df_oficios_groupby['cidade'] == item['cidade'], 'resumo_oficio'] = item['resumo']



columns = df_solicitacoes.columns.tolist()
column_name = next((column for column in columns if 'cidade' in column.lower() or 'município' in column.lower()), None)

if column_name:
    df_solicitacoes[column_name] = df_solicitacoes[column_name].apply(verify_municipio)
    # agrupar o numero de solicitacoes por cidade
    df_solicitacoes_groupby = df_solicitacoes.groupby(column_name).size().reset_index(name='total_solicitacoes')
    df_solicitacoes_groupby.rename(columns={column_name: 'cidade'}, inplace=True)

    # pega todos os registros agrupador por cidade e monte um resumo por cidade utulizando a api do openrouter
    registros_cidades = {}
    for cidade in df_solicitacoes_groupby['cidade'].tolist(): 
        df_aux = df_solicitacoes[df_solicitacoes[column_name] == cidade]
        if df_aux.empty:
            continue
        records = df_aux.fillna('').replace('', None).to_dict(orient='records')
        registros_cidades.update({cidade: records})

    prompt = f"""
        Você é um especialista em análise de dados públicos e políticas públicas municipais.
        <contexto>
        Os dados fornecidos estão em formato JSON e representam registros de solicitações feitas por diferentes cidades. 
        Cada registro contém informações sobre o tipo de solicitação, área de interesse, descrição da solicitação e outras informações relevantes.
        </contexto>

        <tarefa>
        Analise os registros de solicitações e identifique, para cada cidade: 
        - Os principais tipos de solicitações apresentadas
        - As áreas mais recorrentes (ex: infraestrutura, saúde, educação, agricultura, transporte e etc.)
        - Possíveis necessidades prioritárias da população com base nas solicitações
        </tarefa>

        <instruções>
        {instrucoes}
        </instruções>

        <dados>
        {registros_cidades}
        </dados>

        <formato_resposta>
        {formato_resposta}
        </formato_resposta>
    """

    messages = [{"role": "user", "content": prompt}]
    payload = {"model": 'google/gemini-2.5-flash-lite', "messages": messages, "temperature": 0.0}
    response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    response_json = response.json()
    message = response_json.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    data = json.loads(message.replace('```json', '').replace('```', ''))
    #cost = response_json.get('usage', {}).get('cost', None)
    
    df_solicitacoes_groupby['resumo_solicitacoes'] = None
    for item in data:
        df_solicitacoes_groupby.loc[df_solicitacoes_groupby['cidade'] == item['cidade'], 'resumo_solicitacoes'] = item['resumo']

columns = df_emendas.columns.tolist()

column_valor_total = next((column for column in columns if 'valor total' in column.strip().lower()), None)
columns_valor_liberado = next((column for column in columns if 'valor liberado' in column.strip().lower()), None)
column_name = next((column for column in columns if 'cidade' in column.lower() or 'município' in column.lower()), None)


def verify_valor(valor):
    try:
        return float(valor)
    except:
        valor = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
        return float(valor)

if column_valor_total and column_name and columns_valor_liberado:
    # aplicando função à todas as colunas
    df_emendas[column_name] = df_emendas[column_name].apply(verify_municipio)
    df_emendas[column_valor_total] = df_emendas[column_valor_total].apply(verify_valor)
    df_emendas[columns_valor_liberado] = df_emendas[columns_valor_liberado].apply(verify_valor)

    # somando todos os valores por cidade
    df_emendas_groupy = df_emendas.groupby(column_name)[[column_valor_total, columns_valor_liberado]].sum().reset_index()
    df_emendas_groupy.rename(columns={column_name: 'cidade'}, inplace=True)

    # pega todos os registros agrupador por cidade e monte um resumo por cidade utulizando a api do openrouter
    registros_cidades = {}
    for cidade in df_emendas_groupy['cidade'].tolist(): 
        df_aux = df_emendas[df_emendas[column_name] == cidade]
        if df_aux.empty:
            continue
        records = df_aux.fillna('').replace('', None).to_dict(orient='records')
        registros_cidades.update({cidade: records})


    prompt = f"""
        Você é um especialista em análise de dados públicos e políticas públicas municipais.

        <contexto>
        Os dados fornecidos estão em formato JSON e representam registros de emendas parlamentares destinadas a diferentes cidades.
        Cada registro contém informações como destino das emendas, orgão, situacao e valores totais e liberados.
        </contexto>

        <tarefa>
        Analise os registros de emendas parlamentares e identifique, para cada registro da cidade:
        - O tipo de emenda (ex: saúde, educação, infraestrutura, etc.)
        Além disso, para cada cidade:
        - agrupe os registros de emendas parlamentares por tipo e some os valores totais e liberados para cada tipo de emenda.
        - Identifique as áreas mais beneficiadas pelas emendas parlamentares (ex: saúde, educação, infraestrutura, etc.)
        - Monte um resumo das principais áreas beneficiadas e possíveis necessidades prioritárias da população com base nas emendas parlamentares destinadas a cada cidade.
        </tarefa>

        <instruções>
        {instrucoes}
        - no campo "tipo_emendas" do JSON de resposta, retorne uma lista com os tipos de emendas e a quantidade para cada cidade, por exemplo: [{{"saúde": 2}}, {{"educação": 3}}, {{"infraestrutura": 8}}].
        </instruções>

        <dados>
        {registros_cidades}
        </dados>

        <formato_resposta>
        Retorne APENAS um JSON válido no seguinte formato:
        [
            {{
                "cidade": "",
                "resumo": "",
                "tipo_emendas": []
            }}
        ]
        </formato_resposta>
    """

    messages = [{"role": "user", "content": prompt}]
    payload = {"model": 'google/gemini-2.5-flash-lite', "messages": messages, "temperature": 0.0}
    response = requests.post('https://openrouter.ai/api/v1/chat/completions', headers=headers, data=json.dumps(payload))
    response.raise_for_status()
    response_json = response.json()
    message = response_json.get('choices', [{}])[0].get('message', {}).get('content', '{}')
    data = json.loads(message.replace('```json', '').replace('```', ''))
    #cost = response_json.get('usage', {}).get('cost', None)

    df_emendas_groupy[['resumo_emendas', 'tipo_emendas']] = None
    for item in data:
        try:

            df_emendas_groupy.loc[df_emendas_groupy['cidade'] == item['cidade'], 'resumo_emendas'] = item['resumo']
            df_emendas_groupy.loc[df_emendas_groupy['cidade'] == item['cidade'], 'tipo_emendas'] = str(item['tipo_emendas'])

        except:
            print(item)


df = pd.merge(df_oficios_groupby, df_solicitacoes_groupby, on='cidade', how='outer')
df = pd.merge(df, df_emendas_groupy, on='cidade', how='outer')
df = df.fillna('').replace('', None)


import geopandas as gpd
gdf = gpd.read_file('municipios/PR_Municipios_2024.shp')
gdf['NM_MUN'] = gdf['NM_MUN'].apply(verify_municipio)


# adiciona o campo geometry para plotar o mapa
df['geometry'] = df['cidade'].apply(lambda x: gdf[gdf['NM_MUN'] == x]['geometry'].values[0] if gdf[gdf['NM_MUN'] == x].shape[0] > 0 else None)

df.to_csv('consolidado.csv', index=False, sep=';', encoding='utf-8')