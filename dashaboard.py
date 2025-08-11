# dashboard_wrike.py
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# ---- CONFIGURAÇÃO BÁSICA ----
st.set_page_config(page_title="Dashboard de Projetos - Wrike", layout="wide")

st.title("📊 Dashboard de Projetos - Wrike")

# ---- UPLOAD DO ARQUIVO ----
uploaded_file = st.file_uploader("📂 Envie o arquivo CSV/XLSX exportado do Wrike", type=["csv", "xlsx"])

if uploaded_file:
    try:
        # Detecta se é CSV ou XLSX
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # ---- MOSTRAR ESTRUTURA DO ARQUIVO ----
        st.subheader("🔍 Estrutura do Arquivo")
        st.write("**Colunas encontradas:**")
        st.write(list(df.columns))
        
        # Mostrar primeiras linhas para análise
        st.write("**Primeiras 5 linhas:**")
        st.dataframe(df.head())

        # ---- LIMPEZA DOS NOMES DAS COLUNAS ----
        df.columns = [col.strip() for col in df.columns]  # remove espaços extras
        
        # ---- SELEÇÃO MANUAL DE COLUNAS ----
        st.subheader("⚙️ Configuração de Colunas")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            coluna_nome = st.selectbox("Selecione a coluna do NOME/TÍTULO:", df.columns)
        
        with col2:
            coluna_status = st.selectbox("Selecione a coluna do STATUS:", df.columns)
        
        with col3:
            # Buscar colunas que podem ter percentual
            colunas_numericas = [col for col in df.columns if 'percent' in col.lower() or 'concl' in col.lower() or '%' in col.lower() or 'progress' in col.lower()]
            if not colunas_numericas:
                colunas_numericas = df.select_dtypes(include=['number']).columns.tolist()
            if not colunas_numericas:
                colunas_numericas = df.columns.tolist()
                
            coluna_percentual = st.selectbox("Selecione a coluna do PERCENTUAL:", colunas_numericas)

        # ---- PROCESSAMENTO DOS DADOS ----
        if st.button("🚀 Gerar Dashboard"):
            try:
                # Criar DataFrame simplificado
                df_dashboard = pd.DataFrame({
                    'Nome': df[coluna_nome],
                    'Status': df[coluna_status],
                    'Percentual': df[coluna_percentual]
                })

                # Limpar dados de percentual - versão mais robusta
                df_dashboard['Percentual_Original'] = df_dashboard['Percentual'].copy()
                
                # Diferentes tratamentos para percentual
                def extrair_percentual(valor):
                    if pd.isna(valor) or valor == '' or valor == 'None':
                        return 0.0
                    
                    # Se já é número
                    try:
                        num = float(valor)
                        return num if num <= 100 else num/100  # Se > 100, assume que está em decimal
                    except:
                        pass
                    
                    # Se é string, extrair número
                    import re
                    valor_str = str(valor).replace('%', '').replace(',', '.')
                    match = re.search(r'(\d+(?:\.\d+)?)', valor_str)
                    if match:
                        return float(match.group(1))
                    
                    # Se não achou número, assume 0
                    return 0.0

                df_dashboard['Percentual'] = df_dashboard['Percentual'].apply(extrair_percentual)
                
                # Classificar tasks por status de conclusão
                def classificar_status(percentual):
                    if percentual == 0:
                        return "Não Iniciada"
                    elif percentual < 25:
                        return "Iniciada"
                    elif percentual < 50:
                        return "Em Desenvolvimento"
                    elif percentual < 75:
                        return "Em Progresso"
                    elif percentual < 100:
                        return "Quase Concluída"
                    else:
                        return "Concluída"

                df_dashboard['Classificacao'] = df_dashboard['Percentual'].apply(classificar_status)
                
                # Adicionar colunas de análise
                df_dashboard['Dias_Estimados'] = None  # Pode ser preenchido se tiver dados de prazo
                df_dashboard['Prioridade'] = 'Normal'  # Pode ser customizado

                # ---- TABELA ----
                st.subheader("📋 Tabela de Status dos Projetos")
                st.dataframe(df_dashboard, use_container_width=True)

                # ---- MÉTRICAS ESPECÍFICAS PARA TASKS ----
                col1, col2, col3, col4 = st.columns(4)
                
                total_tasks = len(df_dashboard)
                tasks_concluidas = len(df_dashboard[df_dashboard['Percentual'] >= 100])
                tasks_em_andamento = len(df_dashboard[(df_dashboard['Percentual'] > 0) & (df_dashboard['Percentual'] < 100)])
                tasks_nao_iniciadas = len(df_dashboard[df_dashboard['Percentual'] == 0])
                
                with col1:
                    st.metric("Total de Tasks", total_tasks)
                
                with col2:
                    if total_tasks > 0:
                        taxa_conclusao = (tasks_concluidas / total_tasks) * 100
                        st.metric("Taxa de Conclusão", f"{taxa_conclusao:.1f}%")
                    else:
                        st.metric("Taxa de Conclusão", "0%")
                
                with col3:
                    st.metric("Tasks Concluídas", f"{tasks_concluidas}/{total_tasks}")
                
                with col4:
                    if total_tasks > 0:
                        media_progresso = df_dashboard['Percentual'].mean()
                        st.metric("Progresso Médio", f"{media_progresso:.1f}%")
                    else:
                        st.metric("Progresso Médio", "0%")

                # ---- MÉTRICAS DETALHADAS ----
                st.subheader("📊 Distribuição das Tasks")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Tabela de classificação
                    classificacao_count = df_dashboard['Classificacao'].value_counts()
                    st.write("**Por Status de Progresso:**")
                    for status, count in classificacao_count.items():
                        porcentagem = (count / total_tasks) * 100 if total_tasks > 0 else 0
                        st.write(f"- {status}: {count} tasks ({porcentagem:.1f}%)")
                
                with col2:
                    # Métricas de performance
                    st.write("**Métricas de Performance:**")
                    if total_tasks > 0:
                        st.write(f"- Tasks em Atraso (0%): {tasks_nao_iniciadas}")
                        st.write(f"- Tasks em Andamento: {tasks_em_andamento}")
                        st.write(f"- Taxa de Progresso: {((tasks_em_andamento + tasks_concluidas) / total_tasks * 100):.1f}%")
                        
                        # Velocity (tasks concluídas)
                        if tasks_concluidas > 0:
                            st.write(f"- Velocity: {tasks_concluidas} tasks finalizadas")
                    else:
                        st.write("Nenhuma task encontrada.")

                # ---- GRÁFICO DE BARRAS - MELHORADO ----
                st.subheader("📈 Progresso por Task")
                
                # Ordenar por percentual para melhor visualização
                df_ordenado = df_dashboard.sort_values('Percentual', ascending=True)
                
                fig_bar = px.bar(
                    df_ordenado,
                    x='Percentual',
                    y='Nome',
                    orientation='h',  # Horizontal para nomes longos
                    color='Percentual',
                    color_continuous_scale=['#ff4444', '#ffaa00', '#44ff44'],
                    text='Percentual',
                    title='Percentual de Conclusão por Task',
                    height=max(400, len(df_dashboard) * 25)  # Altura dinâmica
                )
                
                fig_bar.update_traces(texttemplate='%{text:.0f}%', textposition='auto')
                fig_bar.update_layout(
                    xaxis_title="% Concluído",
                    yaxis_title="Tasks",
                    showlegend=False,
                    yaxis={'automargin': True}  # Melhor formatação dos nomes
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                # ---- GRÁFICO DE PIZZA - CLASSIFICAÇÃO ----
                st.subheader("🥧 Distribuição por Classificação")
                
                classificacao_count = df_dashboard['Classificacao'].value_counts()
                
                # Cores customizadas para cada status
                cores = {
                    'Não Iniciada': '#ff4444',
                    'Iniciada': '#ff8800', 
                    'Em Desenvolvimento': '#ffaa00',
                    'Em Progresso': '#88aa00',
                    'Quase Concluída': '#44aa44',
                    'Concluída': '#00aa44'
                }
                
                cores_grafico = [cores.get(status, '#888888') for status in classificacao_count.index]
                
                fig_pie = px.pie(
                    values=classificacao_count.values,
                    names=classificacao_count.index,
                    title='Distribuição de Tasks por Status de Progresso',
                    color_discrete_sequence=cores_grafico
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                
                # ---- GRÁFICO DE FUNIL ----
                st.subheader("🔄 Funil de Progresso")
                
                funil_dados = [
                    ('Tasks Criadas', total_tasks),
                    ('Tasks Iniciadas', tasks_em_andamento + tasks_concluidas),
                    ('Tasks em Progresso (>50%)', len(df_dashboard[df_dashboard['Percentual'] >= 50])),
                    ('Tasks Quase Prontas (>75%)', len(df_dashboard[df_dashboard['Percentual'] >= 75])),
                    ('Tasks Concluídas', tasks_concluidas)
                ]
                
                fig_funil = go.Figure()
                
                for i, (nome, valor) in enumerate(funil_dados):
                    fig_funil.add_trace(go.Funnel(
                        y=[nome],
                        x=[valor],
                        textinfo="value+percent initial"
                    ))
                
                fig_funil.update_layout(title="Funil de Progresso das Tasks", height=400)
                st.plotly_chart(fig_funil, use_container_width=True)

                # ---- GAUGE - PERFORMANCE GERAL ----
                st.subheader("⚡ KPIs de Performance")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Taxa de conclusão
                    taxa_conclusao = (tasks_concluidas / total_tasks * 100) if total_tasks > 0 else 0
                    
                    fig_gauge1 = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = taxa_conclusao,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "Taxa de Conclusão (%)"},
                        gauge = {
                            'axis': {'range': [None, 100]},
                            'bar': {'color': "green"},
                            'steps': [
                                {'range': [0, 20], 'color': "lightgray"},
                                {'range': [20, 40], 'color': "yellow"},
                                {'range': [40, 60], 'color': "orange"},
                                {'range': [60, 80], 'color': "lightgreen"},
                                {'range': [80, 100], 'color': "green"}
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 80
                            }
                        }
                    ))
                    
                    fig_gauge1.update_layout(height=300)
                    st.plotly_chart(fig_gauge1, use_container_width=True)
                
                with col2:
                    # Progresso médio
                    progresso_medio = df_dashboard['Percentual'].mean() if total_tasks > 0 else 0
                    
                    fig_gauge2 = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = progresso_medio,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "Progresso Médio (%)"},
                        gauge = {
                            'axis': {'range': [None, 100]},
                            'bar': {'color': "blue"},
                            'steps': [
                                {'range': [0, 25], 'color': "lightgray"},
                                {'range': [25, 50], 'color': "yellow"},
                                {'range': [50, 75], 'color': "orange"},
                                {'range': [75, 100], 'color': "lightblue"}
                            ],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 90
                            }
                        }
                    ))
                    
                    fig_gauge2.update_layout(height=300)
                    st.plotly_chart(fig_gauge2, use_container_width=True)

                # ---- ALERTAS E RECOMENDAÇÕES ----
                st.subheader("🚨 Alertas e Ações Recomendadas")
                
                # Tasks que precisam de atenção urgente
                tasks_paradas = df_dashboard[df_dashboard['Percentual'] == 0]
                if not tasks_paradas.empty:
                    st.error(f"🛑 **URGENTE**: {len(tasks_paradas)} task(s) não iniciada(s)")
                    with st.expander("Ver tasks não iniciadas"):
                        st.dataframe(tasks_paradas[['Nome', 'Status', 'Percentual']], use_container_width=True)
                
                # Tasks com pouco progresso
                tasks_baixo_progresso = df_dashboard[(df_dashboard['Percentual'] > 0) & (df_dashboard['Percentual'] < 25)]
                if not tasks_baixo_progresso.empty:
                    st.warning(f"⚠️ **ATENÇÃO**: {len(tasks_baixo_progresso)} task(s) com pouco progresso (<25%)")
                    with st.expander("Ver tasks com baixo progresso"):
                        st.dataframe(tasks_baixo_progresso[['Nome', 'Status', 'Percentual']], use_container_width=True)
                
                # Tasks próximas da conclusão - oportunidades de quick wins
                tasks_quase_prontas = df_dashboard[(df_dashboard['Percentual'] >= 80) & (df_dashboard['Percentual'] < 100)]
                if not tasks_quase_prontas.empty:
                    st.info(f"🎯 **OPORTUNIDADE**: {len(tasks_quase_prontas)} task(s) próximas da conclusão (≥80%)")
                    st.success("💡 **Dica**: Foque nestas tasks para quick wins!")
                    with st.expander("Ver tasks quase prontas"):
                        st.dataframe(tasks_quase_prontas[['Nome', 'Status', 'Percentual']], use_container_width=True)
                
                # Tasks concluídas - celebração
                if tasks_concluidas > 0:
                    st.success(f"🎉 **PARABÉNS**: {tasks_concluidas} task(s) concluída(s)!")
                
                # Resumo geral e recomendações
                st.subheader("📋 Resumo Executivo")
                
                if total_tasks > 0:
                    # Calcular métricas avançadas
                    taxa_progresso = ((tasks_em_andamento + tasks_concluidas) / total_tasks) * 100
                    
                    st.write("**Status Geral do Projeto:**")
                    
                    if taxa_conclusao >= 80:
                        st.success(f"✅ Projeto em excelente andamento! {taxa_conclusao:.1f}% das tasks concluídas.")
                    elif taxa_conclusao >= 60:
                        st.info(f"👍 Projeto progredindo bem. {taxa_conclusao:.1f}% das tasks concluídas.")
                    elif taxa_conclusao >= 40:
                        st.warning(f"⚠️ Projeto precisa de mais atenção. Apenas {taxa_conclusao:.1f}% das tasks concluídas.")
                    else:
                        st.error(f"🚨 Projeto em situação crítica! Apenas {taxa_conclusao:.1f}% das tasks concluídas.")
                    
                    st.write("**Recomendações:**")
                    
                    if tasks_nao_iniciadas > 0:
                        st.write(f"- 🚀 Iniciar {tasks_nao_iniciadas} task(s) pendente(s)")
                    
                    if len(tasks_quase_prontas) > 0:
                        st.write(f"- 🎯 Finalizar {len(tasks_quase_prontas)} task(s) quase prontas para quick wins")
                    
                    if len(tasks_baixo_progresso) > 0:
                        st.write(f"- 🔍 Investigar blockers em {len(tasks_baixo_progresso)} task(s) com baixo progresso")
                    
                    # Projeção simples
                    if progresso_medio > 0:
                        tasks_restantes = total_tasks - tasks_concluidas
                        st.write(f"- 📊 Com o progresso atual, restam aproximadamente {tasks_restantes} tasks para conclusão")
                
                else:
                    st.info("Nenhuma task encontrada para análise.")

            except Exception as e:
                st.error(f"Erro ao processar os dados: {str(e)}")
                st.write("Verifique se as colunas selecionadas estão corretas.")

    except Exception as e:
        st.error(f"Erro ao carregar o arquivo: {str(e)}")
        st.write("Verifique se o arquivo está no formato correto.")

else:
    st.info("📤 Envie um arquivo CSV ou XLSX exportado do Wrike para visualizar o dashboard.")
    
    st.markdown("""
    ### Como usar:
    1. **Exporte dados do Wrike** em formato CSV ou Excel
    2. **Faça upload** do arquivo usando o botão acima
    3. **Configure as colunas** correspondentes aos seus dados
    4. **Clique em "Gerar Dashboard"** para visualizar os gráficos
    
    ### Dicas:
    - Certifique-se de que há uma coluna com percentuais de conclusão
    - O dashboard funciona melhor com dados de projetos/tarefas
    - Você pode ajustar as colunas caso os nomes sejam diferentes
    """)