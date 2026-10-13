# Londrivet Tools

Two small Python automations built for the catalog of a veterinary-supplies e-commerce store. Both read a spreadsheet of products and write the results back to a new spreadsheet.

| Tool | What it does |
|---|---|
| [`product-description-generator`](product-description-generator/) | Writes a technical product description for each item, based on web search results and a writing manual. |
| [`price-tracker`](price-tracker/) | Finds the minimum and maximum market price of each item on Brazilian marketplaces. |

The prompts and the writing manual are in Brazilian Portuguese, because the store and its catalog are.

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Each tool reads its API keys from a `keys.env` file **in the folder where you run it**. Copy the example and fill it in:

```bash
cp product-description-generator/keys.env.example product-description-generator/keys.env
cp price-tracker/keys.env.example price-tracker/keys.env
```

`keys.env` is git-ignored. Never commit it.

You need an [OpenAI](https://platform.openai.com/) API key for both tools and a [SerpAPI](https://serpapi.com/) key for the price tracker. Both services are paid beyond their free tiers, so try the sample data first.

## Input spreadsheet

Both tools read `LISTA_PRODUTOS_TESTE.xlsx` from the current folder and use only the column `DESCRPROD` (the product name). Extra columns are ignored. A fictional example is in [`sample-data/`](sample-data/):

```bash
cp sample-data/LISTA_PRODUTOS_TESTE.xlsx product-description-generator/
cp sample-data/LISTA_PRODUTOS_TESTE.xlsx price-tracker/
```

Real spreadsheets (`*.xlsx`) are git-ignored on purpose, since they hold the store's catalog and pricing data.

## product-description-generator

```bash
cd product-description-generator
python3 LdvProdDescGenerator.py
```

For each product it:

1. searches DuckDuckGo (Brazil region) for "`<product>` ficha técnica" and keeps the top 3 snippets;
2. sends the product, the snippets and `MANUAL_INSTRUÇÕES.txt` to `gpt-4o-mini` (temperature 0.4), instructing it to use only the facts found and not to invent specifications;
3. writes `PRODUTOS_DESCRIÇÃO.xlsx` with the product name, the web data used and the final description.

`MANUAL_INSTRUÇÕES.txt` is the style guide: technical tone, no sales language, no clinical promises, 150 to 250 words, and "if you don't have the information, leave it out". Edit it to change how descriptions are written.

## price-tracker

```bash
cd price-tracker
python3 price_tracker.py
```

For each product it:

1. queries Google Shopping through SerpAPI (up to 20 results, Brazil);
2. keeps only listings from an allowlist of marketplaces (Mercado Livre, Amazon, Shopee, Magalu, Americanas, Casas Bahia, Ponto Frio);
3. drops price outliers (below 20% or above 300% of the average) to remove accessories and bulk kits;
4. asks `gpt-4o-mini` to act as a strict judge and accept only listings that are exactly the target product, rejecting accessories, other versions and multi-unit kits;
5. writes `resultado_precos.xlsx` with the minimum price, maximum price and number of valid listings per product.

`debug_serp.py` is a variant of the same script with a more permissive store filter (it matches the allowlist against the seller name as well as the link) and error handling around the search call.

## Limitations

- The descriptions are only as good as the web snippets found; check them before publishing.
- The price judge is an LLM, so occasional wrong matches are possible. Treat the min/max as a reference, not as ground truth.
- Rows are processed one by one with no retry logic, so large spreadsheets take a while and cost API credits.
