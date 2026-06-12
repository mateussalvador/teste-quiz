import streamlit as st
import sqlite3
import json
import random
import pandas as pd

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Quiz Personalizado", layout="centered")

# --- CONEXÃO COM O BANCO DE DADOS ---
def conectar_bd():
    conn = sqlite3.connect("quiz_database.db", check_same_thread=False)
    cursor = conn.cursor()
    # Tabela de questões
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT NOT NULL,
            alternativas TEXT NOT NULL, -- Guardado como JSON string
            resposta_correta TEXT NOT NULL
        )
    ''')
    # Tabela de relatórios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT NOT NULL,
            pergunta TEXT NOT NULL,
            resposta_usuario TEXT NOT NULL,
            resposta_correta TEXT NOT NULL,
            acertou INTEGER NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

conn = conectar_bd()
cursor = conn.cursor()

# --- AUTENTICAÇÃO SIMPLES PARA O ADMIN ---
def checar_senha():
    def password_entered():
        if st.session_state["password"] == st.secrets["admin_password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Senha do Administrador", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Senha do Administrador", type="password", on_change=password_entered, key="password")
        st.error("Senha incorreta.")
        return False
    return True

# --- NAVEGAÇÃO ---
aba = st.sidebar.selectbox("Navegação", ["Responder Quiz", "Área do Admin (Restrito)"])

# ==========================================
# 1. ÁREA DO USUÁRIO (QUIZ)
# ==========================================
if aba == "Responder Quiz":
    st.title("🎯 Teste seus Conhecimentos")
    
    # Identificação do Usuário
    nome_usuario = st.text_input("Digite seu nome para iniciar:", key="nome_usuario")
    
    if nome_usuario:
        # Buscar todas as questões do banco
        cursor.execute("SELECT id, pergunta, alternativas, resposta_correta FROM questoes")
        todas_questoes = cursor.fetchall()
        
        if not todas_questoes:
            st.warning("Nenhuma questão cadastrada no momento. Avise o administrador!")
        else:
            num_questoes = st.number_input("Quantas questões deseja responder?", min_value=1, max_value=20, value=3)
            
            if st.button("Gerar Quiz"):
                # Sorteia com reposição (podendo repetir, conforme solicitado)
                st.session_state["questoes_quiz"] = random.choices(todas_questoes, k=num_questoes)
                st.session_state["respostas_enviadas"] = False
                st.session_state["respostas_usuario"] = {}
            
            # Renderizar o Quiz
            if "questoes_quiz" in st.session_state:
                with st.form("form_quiz"):
                    for idx, q in enumerate(st.session_state["questoes_quiz"]):
                        q_id, pergunta, alternativas_json, correta = q
                        alternativas = json.loads(alternativas_json)
                        
                        st.subheader(f"Questão {idx+1}: {pergunta}")
                        # Chave única para cada questão baseada no índice do loop para permitir repetição
                        st.session_state["respostas_usuario"][idx] = st.radio(
                            "Escolha a alternativa correta:", 
                            alternativas, 
                            key=f"q_{idx}"
                        )
                        st.write("---")
                    
                    enviar = st.form_submit_button("Enviar Respostas")
                    
                    if enviar:
                        acertos = 0
                        for idx, q in enumerate(st.session_state["questoes_quiz"]):
                            q_id, pergunta, alternativas_json, correta = q
                            resp_usuario = st.session_state["respostas_usuario"][idx]
                            
                            acertou = 1 if resp_usuario == correta else 0
                            if acertou:
                                acertos += 1
                            
                            # Salva no relatório de desempenho
                            cursor.execute('''
                                INSERT INTO relatorios (usuario, pergunta, resposta_usuario, resposta_correta, acertou)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (nome_usuario, pergunta, resp_usuario, correta, acertou))
                        
                        conn.commit()
                        st.success(f"Quiz finalizado, {nome_usuario}! Você acertou {acertos} de {len(st.session_state['questoes_quiz'])} questões.")
                        st.balloons()

# ==========================================
# 2. ÁREA DO ADMINISTRADOR
# ==========================================
elif aba == "Área do Admin (Restrito)":
    st.title("🔐 Painel de Controle")
    
    if checar_senha():
        st.success("Autenticado com sucesso!")
        
        menu_admin = st.tabs(["Criar Questão", "Gerenciar Questões", "Relatório de Usuários"])
        
        # --- ABA: CRIAR QUESTÃO ---
        with menu_admin[0]:
            st.header("Adicionar Nova Questão")
            nova_pergunta = st.text_area("Enunciado da Questão:")
            
            num_alternativas = st.number_input("Número de alternativas:", min_value=2, max_value=10, value=4)
            alternativas_lista = []
            
            for i in range(int(num_alternativas)):
                alt = st.text_input(f"Alternativa {i+1}:", key=f"nova_alt_{i}")
                if alt:
                    alternativas_lista.append(alt)
            
            if alternativas_lista:
                resposta_correta = st.selectbox("Selecione a alternativa correta:", alternativas_lista)
            
            if st.button("Salvar Questão"):
                if nova_pergunta and len(alternativas_lista) == num_alternativas:
                    alternativas_json = json.dumps(alternativas_lista)
                    cursor.execute('''
                        INSERT INTO questoes (pergunta, alternativas, resposta_correta)
                        VALUES (?, ?, ?)
                    ''', (nova_pergunta, alternativas_json, resposta_correta))
                    conn.commit()
                    st.success("Questão adicionada com sucesso!")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos obrigatórios.")

        # --- ABA: GERENCIAR QUESTÕES (EDITAR/REMOVER) ---
        with menu_admin[1]:
            st.header("Questões Cadastradas")
            cursor.execute("SELECT id, pergunta, alternativas, resposta_correta FROM questoes")
            linhas = cursor.fetchall()
            
            if not linhas:
                st.info("Nenhuma questão cadastrada.")
            for linha in linhas:
                q_id, perg, alts, corr = linha
                with st.expander(f"ID {q_id}: {perg[:50]}..."):
                    st.write(f"**Pergunta Completa:** {perg}")
                    st.write(f"**Alternativas:** {json.loads(alts)}")
                    st.write(f"**Correta:** {corr}")
                    
                    if st.button(f"Excluir Questão ID {q_id}", key=f"del_{q_id}"):
                        cursor.execute("DELETE FROM questoes WHERE id = ?", (q_id,))
                        conn.commit()
                        st.success(f"Questão {q_id} removida!")
                        st.rerun()

        # --- ABA: RELATÓRIOS ---
        with menu_admin[2]:
            st.header("Desempenho dos Usuários")
            df_relatorio = pd.read_sql_query("SELECT usuario, pergunta, resposta_usuario, resposta_correta, acertou, data_hora FROM relatorios", conn)
            
            if df_relatorio.empty:
                st.info("Nenhum usuário respondeu ao quiz ainda.")
            else:
                st.dataframe(df_relatorio)
                
                # Métricas Rápidas
                total_respostas = len(df_relatorio)
                total_acertos = df_relatorio['acertou'].sum()
                taxa_acerto = (total_acertos / total_respostas) * 100
                
                col1, col2 = st.columns(2)
                col1.metric("Total de Respostas Submetidas", total_respostas)
                col2.metric("Taxa Média de Acerto", f"{taxa_acerto:.1f}%")
                
                # Botão para limpar logs se necessário
                if st.button("Limpar Histórico de Relatórios"):
                    cursor.execute("DELETE FROM relatorios")
                    conn.commit()
                    st.success("Histórico limpo!")
                    st.rerun()