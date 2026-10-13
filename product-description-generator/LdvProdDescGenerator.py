import pandas as pd
from openai import OpenAI
from tqdm import tqdm
import time
import os
from dotenv import load_dotenv
from ddgs import DDGS

load_dotenv('keys.env')
API_KEY = os.getenv("OPENAI_API_KEY")
ARQUIVO_ENTRADA = "LISTA_PRODUTOS_TESTE.xlsx"
ARQUIVO_SAIDA = "PRODUTOS_DESCRIÇÃO.xlsx"
ARQUIVO_MANUAL = "MANUAL_INSTRUÇÕES.txt"
NOME_COLUNA_PRODUTO = "DESCRPROD"

if not API_KEY:
    raise ValueError("Chave da API não encontrada em keys.env (variável OPENAI_API_KEY)")

client = OpenAI(api_key=API_KEY)


def carregar_manual(caminho_arquivo):
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERRO CRÍTICO: O arquivo '{caminho_arquivo}' não foi encontrado.")
        exit()


def pesquisar_na_web(termo_busca):
    try:
        with DDGS() as ddgs:
            resultados = list(ddgs.text(termo_busca, region='br-pt', max_results=3))
            if not resultados:
                return "Nenhuma informação encontrada na web."

            texto = ""
            for res in resultados:
                texto += f"- {res['body']}\n"
            return texto
    except Exception as e:
        return f"Erro na busca: {str(e)}"


def gerar_descricao(produto, dados_web, texto_manual):
    prompt_usuario = f"""
    PRODUTO: {produto}

    DADOS TÉCNICOS ENCONTRADOS (Use estes fatos):
    {dados_web}

    TAREFA:
    
    Escreva uma descrição técnica para este produto.
    Use APENAS os dados técnicos encontrados para garantir veracidade técnica.
    Se as informações forem insuficientes, faça uma descrição genérica mas não invente especificações técnicas.
    Escreva a descrição do produto seguindo estritamente o MANUAL DE INSTRUÇÕES fornecido nas regras do sistema.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system",
                 "content": f"Você é um especialista em marketing de e-commerce. Siga estritamente este MANUAL DE INSTRUÇÕES:\n\n{texto_manual}"},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Erro ao gerar: {str(e)}"


def main():
    print("--- Iniciando Automação com Manual ---")

    print(f"Lendo manual de instruções: {ARQUIVO_MANUAL}...")
    conteudo_manual = carregar_manual(ARQUIVO_MANUAL)
    print("Manual carregado com sucesso!")

    try:
        df = pd.read_excel(ARQUIVO_ENTRADA)
    except FileNotFoundError:
        print("Arquivo Excel de entrada não encontrado.")
        return

    descricoes = []
    dados_pesquisados = []

    for produto in tqdm(df[NOME_COLUNA_PRODUTO], desc="Processando"):
        if pd.isna(produto) or str(produto).strip() == "":
            descricoes.append("Vazio")
            dados_pesquisados.append("Vazio")
            continue

        info_web = pesquisar_na_web(f"{produto} ficha técnica")
        dados_pesquisados.append(info_web)

        descricao = gerar_descricao(produto, info_web, conteudo_manual)
        descricoes.append(descricao)

        time.sleep(1)

    df_resultado = pd.DataFrame({
        "Nome do Produto": df[NOME_COLUNA_PRODUTO],
        "Dados Web": dados_pesquisados,
        "Descrição Final": descricoes
    })

    df_resultado.to_excel(ARQUIVO_SAIDA, index=False)
    print(f"Concluído! Arquivo salvo: {ARQUIVO_SAIDA}")


if __name__ == "__main__":
    main()