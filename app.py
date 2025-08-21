# app.py — Phelipe Online (corrigido)
import streamlit as st
import google.generativeai as genai
import os
import pandas as pd
import PyPDF2
import json
from datetime import datetime

# -----------------------------------------------------------------------------
# INICIALIZAÇÃO DO SESSION_STATE
# -----------------------------------------------------------------------------
st.session_state.setdefault("analise_feita", False)
st.session_state.setdefault("data", {})
st.session_state.setdefault("csv", None)
st.session_state.setdefault("csv_filename", "")
st.session_state.setdefault("classificacao_final", "Não classificado")

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA PÁGINA
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Phelipe Online - TCE-MT", page_icon="🔍", layout="wide")
st.title("🔍 Phelipe: Assistente de Análise de PPCIs do TCE-MT")

# -----------------------------------------------------------------------------
# CONFIGURAÇÃO DA API DO GEMINI
# -----------------------------------------------------------------------------
# Busca chave primeiro nos secrets do Streamlit e, se não houver, em variável de ambiente.
api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", "")).strip()

if not api_key:
    st.error("⚠️ Configure a variável GEMINI_API_KEY em Secrets ou variável de ambiente.")
    st.stop()

try:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
except Exception:
    st.error("⚠️ Erro ao configurar a API do Gemini. Verifique a chave e tente novamente.")
    st.stop()

# -----------------------------------------------------------------------------
# PROMPT DO SISTEMA (ANÁLISE GERAL)
# -----------------------------------------------------------------------------
prompt_sistema = """
Você é Phelipe, um agente especializado em análise de recomendação do TCE-MT, com dupla expertise:
1) Técnico de controle externo (TCE-MT)
2) Especialista em controle interno da SES-MT

OBJETIVO PRINCIPAL:
Verificar se a ação do gestor é compatível com a recomendação, com base apenas nos documentos do processo.

ETAPAS DA ANÁLISE:

1. 📚 ANÁLISE MULTIDOCUMENTAL (Contexto Técnico)
   - Relatório de Auditoria: falha constatada, contexto fático, base legal, valor do dano
   - Parecer do MPC: posicionamento técnico, concordância ou ressalva
   - Decisão do TCE-MT: recomendação específica, prazo, responsabilidades
   - Resposta do Gestor: ação informada, prazo, evidência anexada

2. ⏳ RECONSTRUÇÃO DA CRONOLOGIA
   Ordene os eventos:
   - O que foi constatado?
   - Como o MPC opinou?
   - O que decidiram os conselheiros?
   - Qual foi a resposta do gestor?
   - Há coerência entre a resposta e o problema?

3. 🏥 ANÁLISE CONTEXTUAL (SES-MT)
   Avalie a viabilidade prática da ação, considerando:
   - Estrutura da SES-MT
   - Recursos humanos
   - Sistemas de informação

4. 🧩 MEMÓRIA INSTITUCIONAL
   Após a análise, gere observações como:
   > 💬 Phelipe lembra: Este tipo de irregularidade já ocorreu em 3 unidades nos últimos 18 meses.

SAÍDA:
Retorne apenas um JSON envolto em ```json ... ```, com:
{
  "relatorio_tecnico": "Texto completo com sumário cronológico, crítica técnica e conclusão.",
  "analise_contextual": "Avaliação da viabilidade dentro da realidade operacional da SES-MT.",
  "insights_capacitacao": {
    "padroes_identificados": [],
    "sugestoes_prevencao": [],
    "modus_operandi": []
  },
  "indicios_dano_erario": {
    "consta": false,
    "descricao": "Não consta",
    "fundamentacao": "Não consta"
  },
  "observacoes_memoria": "..."
}

REGRAS ESTRITAS:
- Nunca invente, suponha ou estime dados.
- Se a informação não estiver no documento, diga "Não consta".
- Sempre cite a fonte: "conforme mencionado na decisão", "segundo o PPCI".
- Use linguagem técnica, clara e objetiva.
- Retorne apenas o JSON. Nada além disso.
"""

# -----------------------------------------------------------------------------
# FUNÇÃO PARA EXTRAÇÃO DE TEXTO DE PDFs (sem OCR)
# -----------------------------------------------------------------------------
def extrair_texto_pdf(upload_files):
    documentos_texto = ""
    for file in upload_files:
        file.seek(0)
        try:
            pdf_reader = PyPDF2.PdfReader(file)
            for i, page in enumerate(pdf_reader.pages):
                try:
                    text = page.extract_text()
                except Exception:
                    text = None
                if text and text.strip():
                    documentos_texto += f"[{getattr(file, 'name', 'documento.pdf')} - Página {i + 1}]\n{text}\n\n"
                else:
                    documentos_texto += f"[{getattr(file, 'name', 'documento.pdf')} - Página {i + 1}]\n[Texto não extraído - PDF possivelmente escaneado]\n\n"
        except Exception as e:
            documentos_texto += f"[Erro ao ler {getattr(file, 'name', 'desconhecido')}: {str(e)}]\n"
    return documentos_texto or "Nenhum texto extraído."

# -----------------------------------------------------------------------------
# INTERFACE — DADOS DE ENTRADA
# -----------------------------------------------------------------------------
st.subheader("📥 Documentos do Processo")
upload_files = st.file_uploader("Envie todos os documentos (PDFs)", type=["pdf"], accept_multiple_files=True)

st.subheader("📝 Dados da Decisão (válidos para todas as recomendações)")
num_decisao = st.text_input("🔢 Número da Decisão (ex.: Acórdão 1234/2025)")
data_decisao = st.text_input("📅 Data da Decisão (ex.: 15/05/2025)")
num_processo_tce = st.text_input("📋 Número do Processo no TCE")
orgao_decisao = st.text_input("🏛️ Órgão que emitiu a decisão", value="TCE-MT")

st.subheader("📌 Análise da Recomendação")
servidor_uniseci = st.text_input("🧑‍💼 Servidor da UnISECI/SES-MT")
data_analise = datetime.now().strftime("%d/%m/%Y")
num_ppci = st.text_input("📄 Número do PPCI")
num_recomendacao = st.text_input("🔖 Número da Recomendação")
cod_responsavel = st.text_input("🔐 Código do Responsável ou Procedimento")
gestor = st.text_input("👨‍💼 Gestor (nome)")

recomendacao = st.text_area("📌 Recomendação", height=150)

status_acao = st.selectbox(
    "🔧 Status da Ação apresentada pelo Gestor",
    ["selecione...", "Implementada", "Em Implementação"],
    help="Status informado pelo gestor: se a ação já foi realizada ou está em andamento/planejada."
)

data_implementacao_gestor = st.text_input(
    "📅 Data informada pelo gestor (de implementação ou previsão)",
    help="Ex.: 15/03/2025 (para 'Em Implementação') ou 10/02/2025 (para 'Implementada')"
)

acao_gestor = st.text_area("📝 Ação do Gestor", height=150)

# -----------------------------------------------------------------------------
# AÇÃO: ANALISAR COM PHELIPE
# -----------------------------------------------------------------------------
botao_analisar = st.button("🚀 Analisar com Phelipe")

if botao_analisar and upload_files and num_decisao.strip() and status_acao != "selecione...":
    with st.spinner("Phelipe está analisando... ⏳"):
        try:
            # 1) Extrai texto dos PDFs
            documentos_texto = extrair_texto_pdf(upload_files)

            # 2) Monta prompt completo
            prompt_completo = f"{prompt_sistema}\n\n=== DOCUMENTOS DO PROCESSO ===\n{documentos_texto}"

            # 3) Chama o modelo
            response = model.generate_content(prompt_completo)
            output = (response.text or "").strip()

            # 4) Extrai JSON da resposta
            json_str = None
            if "```json" in output:
                json_start = output.find("```json") + 7
                json_end = output.find("```", json_start)
                if json_end != -1:
                    json_str = output[json_start:json_end].strip()
            elif output.startswith("{") and output.endswith("}"):
                json_str = output

            if json_str:
                try:
                    data_saida = json.loads(json_str)
                except json.JSONDecodeError:
                    data_saida = {"relatorio_tecnico": "Erro: JSON inválido retornado pelo modelo."}
            else:
                data_saida = {"relatorio_tecnico": "Erro: Não foi possível extrair o JSON da resposta do Gemini."}

            # Salva no session_state
            st.session_state.data = data_saida
            st.session_state.analise_feita = True

            # 5) Gera CSV em memória (robusto a chaves variantes)
            ind_erario = data_saida.get("indicios_dano_erario", {})
            # Aceita variações: "consta", "consta_dano", "consta_rano"
            consta_dano = bool(
                ind_erario.get("consta") or
                ind_erario.get("consta_dano") or
                ind_erario.get("consta_rano")
            )

            insights = data_saida.get("insights_capacitacao", {})
            sugestoes_prev = insights.get("sugestoes_prevencao", [])
            if not isinstance(sugestoes_prev, list):
                sugestoes_prev = [str(sugestoes_prev)]

            df = pd.DataFrame([{
                "data_analise": data_analise,
                "servidor_uniseci": servidor_uniseci,
                "num_decisao": num_decisao,
                "data_decisao": data_decisao,
                "num_processo_tce": num_processo_tce,
                "num_ppci": num_ppci,
                "num_recomendacao": num_recomendacao,
                "cod_responsavel": cod_responsavel,
                "orgao_decisao": orgao_decisao,
                "gestor": gestor,
                "recomendacao": (recomendacao or "")[:200],
                "acao_gestor": (acao_gestor or "")[:200],
                "status_acao": status_acao,
                "data_implementacao_gestor": data_implementacao_gestor,
                "relatorio_tecnico": data_saida.get("relatorio_tecnico", "Não disponível"),
                "analise_contextual": data_saida.get("analise_contextual", "Não disponível"),
                "classificacao_final": st.session_state.classificacao_final,
                "insights_prevencao": ", ".join([str(x) for x in sugestoes_prev]) if sugestoes_prev else "Nenhuma",
                "indicio_dano": "Sim" if consta_dano else "Não",
                "detalhe_dano": ind_erario.get("descricao", "Não consta"),
                "observacoes_memoria": data_saida.get("observacoes_memoria", "Nenhuma")
            }])

            csv = df.to_csv(index=False, encoding="utf-8-sig")
            st.session_state.csv = csv
            st.session_state.csv_filename = f"phelipe_{num_decisao.replace('/', '-').replace(' ', '_')}.csv"

        except Exception as e:
            st.error(f"❌ Erro durante a análise: {e}")

# -----------------------------------------------------------------------------
# EXIBIÇÃO DOS RESULTADOS
# -----------------------------------------------------------------------------
if st.session_state.analise_feita:
    saida = st.session_state.data

    st.subheader("📄 Relatório Técnico")
    st.write(saida.get("relatorio_tecnico", "Não disponível"))

    st.subheader("🏥 Análise Contextual (SES-MT)")
    st.write(saida.get("analise_contextual", "Não disponível"))

    # ------------------- Análise da Ação do Gestor (prompt isolado) -------------------
    st.subheader("📝 Análise da Ação do Gestor")

    try:
        prompt_analise_acao = f"""
Você é Phelipe, especialista técnico em controle interno, controle externo, SES/MT, integridade e normas aplicáveis.
Sua tarefa é avaliar diretamente se a ação do gestor cumpre a recomendação, com base apenas nos documentos.

### RECOMENDAÇÃO:
{recomendacao}

### AÇÃO DO GESTOR:
{acao_gestor}

### STATUS DA AÇÃO:
{status_acao}

### INSTRUÇÕES:
1. Compare diretamente a ação com a recomendação.
2. Se o status for "Implementada":
   - Verifique se há evidência documental da execução.
   - Avalie se a ação realmente implementou a recomendação.
3. Se o status for "Em Implementação":
   - Avalie o potencial de eficácia: a ação corrige a causa raiz?
   - Verifique se o prazo informado é coerente e factível.
4. Classifique com base nisso:
   - ✅ Compatível: ação completa e comprovada (ou plano viável)
   - ⚠️ Parcialmente compatível: ação incompleta, sem evidência ou com risco alto
   - ❌ Incompatível: ação irrelevante, contradiz a recomendação ou não corrige o problema
   - 🚫 Não Aplicável: justifique
5. Retorne apenas um texto claro, técnico e objetivo, com até 150 palavras.
6. Nunca invente dados. Se não constar, diga "Não consta no documento".
"""
        resp = model.generate_content(prompt_analise_acao)
        analise_acao = (resp.text or "").strip()
        st.write(analise_acao)

        # Atualiza a classificação final no session_state (tolerante a variações)
        texto = analise_acao.lower()
        if "✅ compatível".lower() in texto or "compativel" in texto:
            st.session_state.classificacao_final = "✅ Compatível"
        elif "⚠️ parcialmente".lower() in texto or "parcialmente" in texto:
            st.session_state.classificacao_final = "⚠️ Parcialmente compatível"
        elif "❌ incompatível".lower() in texto or "incompativel" in texto:
            st.session_state.classificacao_final = "❌ Incompatível"
        elif "🚫 não aplicável".lower() in texto or "nao aplicavel" in texto:
            st.session_state.classificacao_final = "🚫 Não Aplicável"
        else:
            st.session_state.classificacao_final = "Não classificado"

    except Exception as e:
        st.error(f"Erro ao gerar análise da ação: {e}")

    # ------------------- Classificação Final -------------------
    st.subheader("📊 Classificação Final")
    st.markdown(f"**{st.session_state.classificacao_final}**")

    # ------------------- Insights para Capacitação -------------------
    st.subheader("🎓 Insights para Capacitação")
    insights = saida.get("insights_capacitacao", {}) or {}
    st.write("**Padrões identificados:**")
    for p in insights.get("padroes_identificados", []) or []:
        st.write(f"• {p}")
    st.write("**Sugestões de prevenção:**")
    for s in insights.get("sugestoes_prevencao", []) or []:
        st.write(f"• {s}")
    st.write("**Modus Operandi (se houver indício de má-fé):**")
    for m in insights.get("modus_operandi", []) or []:
        st.write(f"• {m}")

    # ------------------- Indícios de Dano ao Erário -------------------
    st.subheader("⚠️ Indícios de Dano ao Erário")
    dano = saida.get("indicios_dano_erario", {}) or {}
    consta_dano_final = bool(dano.get("consta") or dano.get("consta_dano") or dano.get("consta_rano"))
    if consta_dano_final:
        st.markdown("**✅ Há indício de dano ao erário**")
        st.write(dano.get("descricao", "Não especificado"))
        st.caption(f"Fonte: {dano.get('fundamentacao', 'Não consta')}")
    else:
        st.markdown("**❌ Não há menção a dano ao erário**")
        st.caption(dano.get("descricao", "Não consta"))

    # ------------------- Observações de Memória -------------------
    st.subheader("🧠 Observações Contextuais (Memória Institucional)")
    obs = saida.get("observacoes_memoria", "Nenhuma observação registrada.")
    st.write(obs)

    # ------------------- Download do CSV -------------------
    if st.session_state.csv:
        st.download_button(
            "⬇️ Baixar CSV (completo)",
            data=st.session_state.csv,
            file_name=st.session_state.csv_filename,
            mime="text/csv"
        )

# -----------------------------------------------------------------------------
# PERGUNTE AO PHELIPE (busca simples na memória CSV local)
# -----------------------------------------------------------------------------
st.subheader("💬 Pergunte ao Phelipe")
pergunte = st.text_input("Ex.: Quem são os auditores? Já houve isso em Rondonópolis?")

if pergunte:
    with st.spinner("Buscando no histórico..."):
        try:
            contexto = ""
            try:
                # Evite acentos em nomes de pastas/arquivos no container
                df_hist = pd.read_csv("memoria/historico.csv", encoding="utf-8")
                candidatos = df_hist[
                    df_hist.get("num_decisao", pd.Series(dtype=str)).astype(str).str.contains(pergunte, case=False, na=False) |
                    df_hist.get("recomendacao", pd.Series(dtype=str)).astype(str).str.contains(pergunte, case=False, na=False) |
                    df_hist.get("gestor", pd.Series(dtype=str)).astype(str).str.contains(pergunte, case=False, na=False)
                ]
                if not candidatos.empty:
                    contexto += "📌 Casos semelhantes encontrados:\n"
                    for _, row in candidatos.head(10).iterrows():
                        rec = str(row.get("recomendacao", ""))[:100]
                        nd = str(row.get("num_decisao", ""))
                        contexto += f"- {nd}: {rec}...\n"
            except Exception:
                contexto += "⚠️ Erro ao carregar histórico.\n"

            if contexto.strip():
                prompt_busca = f"""
Com base no contexto abaixo, responda à pergunta com rigor técnico.
Se a informação não estiver no documento, diga "Não consta".

Pergunta: {pergunte}
Contexto: {contexto}
"""
                resposta_busca = model.generate_content(prompt_busca)
                st.write((resposta_busca.text or "").strip())
            else:
                st.info("🔍 Nenhum dado encontrado para responder.")

        except Exception as e:
            st.error(f"Erro na busca: {e}")
