import os
import sys
import pandas as pd
import re
import json
from dotenv import load_dotenv
from openai import OpenAI
from serpapi import GoogleSearch
from statistics import mean, stdev


# --- CONFIGURAÇÕES ---
carregou = load_dotenv("keys.env")

if not carregou:
    print("⚠️  Erro: Arquivo 'keys.env' não encontrado!")
    print("Certifique-se de criar o arquivo na mesma pasta do script.")
    sys.exit()

# Recupera as chaves das variáveis de ambiente
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

# Verificação de segurança
if not OPENAI_API_KEY:
    print("❌ Erro: Variável 'OPENAI_API_KEY' não encontrada dentro de keys.env")
    sys.exit()

if not SERPAPI_KEY:
    print("❌ Erro: Variável 'SERPAPI_API_KEY' não encontrada dentro de keys.env")
    sys.exit()

# Domínios permitidos (Marketplaces)
ALLOWLIST_TERMS = [
    "mercadolivre",
    "mercado livre", # Às vezes o 'source' vem com espaço
    "amazon",
    "shopee",
    "magazineluiza",
    "magazine luiza",
    "magalu",
    "americanas",
    "casasbahia",
    "casas bahia",
    "pontofrio",
    "ponto frio"
]
# Inicializa cliente OpenAI
client = OpenAI(api_key=OPENAI_API_KEY)


def limpar_preco(preco_str):
    """Converte string de preço (R$ 1.200,00) para float (1200.00)"""
    if not preco_str:
        return None
    # Remove tudo que não é dígito ou vírgula
    nums = re.sub(r'[^\d,]', '', str(preco_str))
    # Troca vírgula por ponto
    nums = nums.replace(',', '.')
    try:
        return float(nums)
    except ValueError:
        return None


def buscar_google_shopping(termo):
    print(f"\n--- Buscando: '{termo}' ---")
    params = {
        "engine": "google_shopping",
        "q": termo,
        "gl": "br",
        "hl": "pt-br",
        "api_key": SERPAPI_KEY,
        "num": 20
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        shopping_results = results.get("shopping_results", [])

        dados_coletados = []

        for item in shopping_results:
            # Pega os dados brutos
            link = item.get("link", "").lower()
            source = item.get("source", "").lower()  # Ex: "amazon.com.br - seller"
            title = item.get("title", "")

            # --- NOVA LÓGICA DE FILTRO ---
            # Verifica se ALGUM termo da allowlist está no LINK ou no NOME DA LOJA (source)
            passou_filtro = False
            for termo_permitido in ALLOWLIST_TERMS:
                if termo_permitido in link or termo_permitido in source:
                    passou_filtro = True
                    break  # Já achou, para de procurar

            if passou_filtro:
                # print(f"  ✅ ACEITO: {source} | {title[:30]}...")
                dados_coletados.append({
                    "titulo": title,
                    "preco_raw": item.get("price"),
                    "preco_float": item.get("extracted_price"),
                    "link": item.get("link"),  # Mantém o link original
                    "loja": item.get("source")
                })
            else:
                # Debug para você ver o que está sendo rejeitado e por quê
                # Descomente a linha abaixo se quiser ver o "lixo" sendo filtrado
                # print(f"  ❌ REJEITADO: Source='{source}' Link='{link[:30]}...'")
                pass

        return dados_coletados

    except Exception as e:
        print(f"Erro na busca: {e}")
        return []


def filtro_heuristico_precos(candidatos):
    """Remove outliers óbvios (muito baratos ou muito caros) antes da IA"""
    if not candidatos:
        return []

    precos = [c['preco_float'] for c in candidatos if c['preco_float'] is not None]

    if len(precos) < 2:
        return candidatos  # Poucos dados para estatística, manda tudo para IA

    media = mean(precos)

    # Regra: Aceita preços entre 20% e 300% da média (ajustável)
    # Isso elimina acessórios baratos (5% do valor) ou kits industriais (1000% do valor)
    limite_min = media * 0.2
    limite_max = media * 3.0

    filtrados = []
    for c in candidatos:
        p = c['preco_float']
        if p and limite_min <= p <= limite_max:
            filtrados.append(c)

    return filtrados


def validar_com_ia(produto_alvo, candidato):
    """O Juiz: Decide se o anúncio é EXATAMENTE o produto alvo"""

    prompt = f"""
    Você é um auditor de preços rigoroso.

    PRODUTO ALVO (O que eu quero): "{produto_alvo}"
    ANÚNCIO ENCONTRADO: "{candidato['titulo']}"
    PREÇO: {candidato['preco_raw']}

    TAREFA:
    Verifique se o anúncio é EXATAMENTE o produto alvo.
    1. Rejeite se for apenas um acessório (capa, bateria, cabo, hélice).
    2. Rejeite se for uma versão diferente (voltagem errada, tamanho errado, potência errada).
    3. Rejeite se for um lote/kit com múltiplas unidades (se o alvo for unitário).

    Responda APENAS um JSON:
    {{
        "match": true/false,
        "motivo": "Explicação curta"
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Modelo rápido e barato
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Erro na IA: {e}")
        return {"match": False, "motivo": "Erro API"}


# --- FLUXO PRINCIPAL ---

def main():
    # 1. Ler Excel de Entrada
    try:
        df = pd.read_excel("LISTA_PRODUTOS_TESTE.xlsx")
    except FileNotFoundError:
        print("Arquivo não encontrado.")
        return

    resultados_finais = []

    print(f"Iniciando processamento de {len(df)} produtos...\n")

    for index, row in df.iterrows():
        produto_nome = row['DESCRPROD']
        print(f"🔍 Pesquisando: {produto_nome}")

        # A. Coleta Abrangente
        candidatos = buscar_google_shopping(produto_nome)
        print(f"   -> Encontrados {len(candidatos)} anúncios em marketplaces permitidos.")

        # B. Filtro Heurístico (Barato)
        candidatos_filtrados = filtro_heuristico_precos(candidatos)
        removidos = len(candidatos) - len(candidatos_filtrados)
        if removidos > 0:
            print(f"   -> {removidos} removidos por discrepância absurda de preço.")

        precos_validos = []

        # C. Validação IA (O Juiz)
        for item in candidatos_filtrados:
            decisao = validar_com_ia(produto_nome, item)

            if decisao['match']:
                precos_validos.append(item['preco_float'])
                # print(f"      ✅ Match: {item['titulo']} - R$ {item['preco_float']}")
            else:
                pass
                # print(f"      ❌ Rejeitado: {item['titulo']} ({decisao['motivo']})")

        # D. Registrar Mínimo e Máximo
        if precos_validos:
            min_price = min(precos_validos)
            max_price = max(precos_validos)
            print(f"   🏁 Resultado: Min R$ {min_price} | Max R$ {max_price}")
        else:
            min_price = None
            max_price = None
            print("   ⚠️ Nenhum produto válido encontrado após validação.")

        resultados_finais.append({
            "Produto": produto_nome,
            "Preço Mínimo": min_price,
            "Preço Máximo": max_price,
            "Qtd Anúncios Válidos": len(precos_validos)
        })
        print("-" * 30)

    # 2. Salvar Excel de Saída
    df_resultado = pd.DataFrame(resultados_finais)
    df_resultado.to_excel("resultado_precos.xlsx", index=False)
    print("\n✅ Processo finalizado! Arquivo 'resultado_precos.xlsx' gerado.")


if __name__ == "__main__":
    main()