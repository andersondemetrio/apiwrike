# acesso.py

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests
import re
import urllib.parse

# ---- CONFIGURAÇÃO BÁSICA ----
st.set_page_config(page_title="Dashboard de Projetos - Wrike", layout="wide")

st.title("📊 Dashboard de Projetos - Wrike")
st.markdown("Dashboard interativo com dados em tempo real da API do Wrike.")

# ---- CONEXÃO COM A API ----
@st.cache_data
def get_wrike_tasks(token):
    """
    Busca todas as tarefas do Wrike atribuídas ao usuário do token.
    A função trata a paginação para garantir que todas as tarefas sejam carregadas.
    """
    base_url = "https://www.wrike.com/api/v4/tasks"
    headers = {
        "Authorization": f"Bearer {token}"
    }

    # Campos opcionais válidos na API v4 do Wrike
    # Removidos campos inválidos e corrigidos os nomes
    optional_fields = [
        "customFields",
        "authorIds",
        "hasAttachments",
        "permalink",
        "priority",
        "followedByMe",
        "followerIds",
        "superParentIds",
        "subTaskIds",
        "superTaskIds",
        "metadata"
    ]
   
    all_tasks = []
    next_page_token = None

    while True:
        try:
            # Parâmetros da requisição
            params = {}
            if next_page_token:
                params['nextPageToken'] = next_page_token
           
            # Primeiro, tenta com campos opcionais
            if not all_tasks:  # Primeira tentativa
                # Formato correto para campos opcionais (sem aspas extras)
                params['fields'] = '["customFields","authorIds","hasAttachments","permalink","priority","superParentIds"]'
           
            response = requests.get(base_url, headers=headers, params=params)
           
            # Se der erro nos campos opcionais, tenta requisição simples
            if response.status_code == 400 and 'invalid_parameter' in response.text.lower():
                st.warning("Alguns campos opcionais não estão disponíveis. Fazendo requisição básica.")
                # Limpa os parâmetros e tenta novamente
                params = {}
                if next_page_token:
                    params['nextPageToken'] = next_page_token
                response = requests.get(base_url, headers=headers, params=params)
           
            response.raise_for_status()
           
            data = response.json()
            all_tasks.extend(data.get('data', []))
           
            # Verificar se há próxima página
            if 'nextPageToken' in data:
                next_page_token = data['nextPageToken']
            else:
                break
               
        except requests.exceptions.HTTPError as e:
            st.error(f"Erro HTTP ao conectar com a API do Wrike: {e}")
            st.error(f"Status: {response.status_code}. Mensagem: {response.text}")
            return []
        except requests.exceptions.RequestException as e:
            st.error(f"Erro na requisição à API do Wrike: {e}")
            return []
        except Exception as e:
            st.error(f"Erro inesperado: {e}")
            return []
   
    st.success(f"✅ {len(all_tasks)} tarefas carregadas com sucesso!")
    return all_tasks

@st.cache_data
def get_user_id(token):
    """Obtém o ID do usuário atual a partir do token de acesso."""
    url = "https://www.wrike.com/api/v4/contacts"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    params = {'me': 'true'}
   
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
       
        data = response.json()
        if data.get('data'):
            user_info = data['data'][0]
            st.info(f"👤 Conectado como: {user_info.get('firstName', '')} {user_info.get('lastName', '')}")
            return user_info['id']
        else:
            st.error("Dados do usuário não encontrados na resposta da API.")
            return None
           
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao obter dados do usuário: {e}")
        return None

@st.cache_data
def get_account_info(token, account_ids):
    """
    Obtém informações das contas/clientes para facilitar a identificação.
    """
    if not account_ids:
        return {}
    
    # Remove duplicatas e valores None
    unique_account_ids = list(set(filter(None, account_ids)))
    account_info = {}
    
    # Para cada account ID, tenta obter informações básicas
    for account_id in unique_account_ids:
        try:
            # Nota: A API do Wrike pode não ter endpoint direto para account info
            # Neste caso, usaremos o ID como nome de exibição
            account_info[account_id] = f"Cliente {account_id[-8:]}"  # Últimos 8 caracteres
        except Exception as e:
            account_info[account_id] = f"Cliente {account_id[-8:]}"
    
    return account_info

# ---- FUNÇÕES AUXILIARES ----
def is_user_responsible(task, user_id):
    """
    Verifica se o usuário é responsável pela tarefa.
    Trata diferentes formatos de responsáveis.
    """
    # Verifica authorIds (autor da tarefa)
    if 'authorIds' in task and task['authorIds']:
        if user_id in task['authorIds']:
            return True
   
    # Se não há campo de responsáveis específico, assume que o autor é responsável
    # Ou verifica se há responsibleIds (em caso de formato antigo)
    if 'responsibleIds' in task and task['responsibleIds']:
        return user_id in task['responsibleIds']
   
    # Se não encontrar campos de responsabilidade, considera todas as tarefas
    return True

def get_parent_ids(task):
    """
    Obtém os IDs dos pais da tarefa, tratando diferentes campos possíveis
    """
    if 'superParentIds' in task and task['superParentIds']:
        return task['superParentIds']
    elif 'parentIds' in task and task['parentIds']:
        return task['parentIds']
    else:
        return []

def format_client_display(account_id, account_info):
    """
    Formata o nome de exibição do cliente
    """
    if account_id in account_info:
        return f"{account_info[account_id]} ({account_id[-8:]})"
    return f"Cliente {account_id[-8:] if account_id else 'N/A'}"

# ---- LÓGICA PARA EXTRAIR DADOS DE CAMPOS PERSONALIZADOS ----
def extrair_percentual(task, custom_field_title="% Andamento"):
    """Extrai o valor de percentual de conclusão de um campo personalizado."""
    if 'customFields' in task and task['customFields']:
        for field in task['customFields']:
            field_title = field.get('title', '').strip()
            # Verifica múltiplas variações do nome do campo
            possible_titles = [
                "% Andamento",
                "%Andamento",
                "Percentual",
                "Progress",
                "Progresso",
                "Completion",
                "Complete"
            ]
           
            if any(title.lower() in field_title.lower() for title in possible_titles):
                value = field.get('value')
                if value:
                    try:
                        # Trata diferentes formatos de valor
                        valor_str = str(value).replace('%', '').replace(',', '.').strip()
                        # Extrai números (incluindo decimais)
                        match = re.search(r'(\d+(?:\.\d+)?)', valor_str)
                        if match:
                            percentual = float(match.group(1))
                            # Se o valor for maior que 100, assume que está em decimal (ex: 0.85 = 85%)
                            if percentual <= 1:
                                percentual *= 100
                            return min(percentual, 100)  # Limita a 100%
                    except (ValueError, AttributeError):
                        pass
   
    # Se não encontrar campo personalizado, usa o status da tarefa como fallback
    status = task.get('status', 'New')
    if status in ['Completed', 'Cancelled']:
        return 100.0
    elif status in ['Active', 'InProgress']:
        return 50.0  # Assume 50% se estiver em progresso
    else:
        return 0.0

def obter_prioridade(task):
    """Obtém a prioridade da tarefa."""
    priority_map = {
        'High': '🔴 Alta',
        'Normal': '🟡 Normal',
        'Low': '🟢 Baixa'
    }
    return priority_map.get(task.get('priority', 'Normal'), '🟡 Normal')

# ---- LÓGICA PRINCIPAL DO APP ----
try:
    token = st.secrets["wrike_access_token"]
    if not token:
        st.error("❌ Token de acesso do Wrike não encontrado. Verifique o arquivo 'secrets.toml'.")
        st.info("💡 Adicione sua chave de acesso no arquivo .streamlit/secrets.toml com a chave 'wrike_access_token'")
        st.stop()
   
    # Obter ID do usuário
    user_id = get_user_id(token)
    if not user_id:
        st.error("❌ Não foi possível obter o ID do usuário.")
        st.stop()
   
    # Buscar tarefas
    with st.spinner("🔄 Carregando tarefas do Wrike..."):
        tasks_data = get_wrike_tasks(token)

    if not tasks_data:
        st.warning("⚠️ Nenhuma tarefa encontrada na sua conta Wrike.")
        st.info("Verifique se você tem tarefas criadas e permissões adequadas.")
    else:
        # Converter para DataFrame
        df_tasks = pd.DataFrame(tasks_data)
       
        # Debug: mostrar colunas disponíveis
        with st.expander("🔍 Debug - Campos disponíveis"):
            st.write("Campos retornados pela API:")
            st.write(df_tasks.columns.tolist())
            if len(df_tasks) > 0:
                st.write("Exemplo de tarefa:")
                st.json(tasks_data[0])
       
        # Filtrar tarefas do usuário
        df_tasks['is_responsible'] = df_tasks.apply(lambda task: is_user_responsible(task, user_id), axis=1)
        df_filtrado = df_tasks[df_tasks['is_responsible']].copy()
       
        if df_filtrado.empty:
            st.warning("⚠️ Nenhuma tarefa encontrada para o usuário atual.")
            st.info("Todas as tarefas disponíveis serão exibidas.")
            df_filtrado = df_tasks.copy()
       
        # Extrair dados adicionais
        df_filtrado['Percentual'] = df_filtrado.apply(extrair_percentual, axis=1)
        df_filtrado['Prioridade'] = df_filtrado.apply(obter_prioridade, axis=1)
        df_filtrado['parent_ids'] = df_filtrado.apply(get_parent_ids, axis=1)

        # Obter informações dos clientes/contas
        account_ids = df_filtrado['accountId'].unique().tolist()
        account_info = get_account_info(token, account_ids)

        if not df_filtrado.empty:
           
            def classificar_status(percentual):
                if percentual == 0:
                    return "Não Iniciada"
                elif percentual < 100:
                    return "Em Andamento"
                else:
                    return "Concluída"
           
            df_filtrado['Classificacao'] = df_filtrado['Percentual'].apply(classificar_status)
            df_filtrado['Cliente_Display'] = df_filtrado['accountId'].apply(
                lambda x: format_client_display(x, account_info)
            )
           
            # ---- SIDEBAR COM FILTROS ----
            st.sidebar.header("🎛️ Filtros")
            
            # *** NOVO FILTRO POR CLIENTE ***
            st.sidebar.subheader("👥 Cliente")
            clientes_disponiveis = sorted(df_filtrado['Cliente_Display'].unique().tolist())
            cliente_selecionado = st.sidebar.selectbox(
                "Filtrar por Cliente:",
                options=['Todos os Clientes'] + clientes_disponiveis,
                help="Filtre as tarefas por ID do cliente (accountId)"
            )
            
            # Mostrar estatísticas por cliente
            if st.sidebar.checkbox("📊 Mostrar estatísticas por cliente"):
                st.sidebar.markdown("**Tasks por Cliente:**")
                cliente_stats = df_filtrado.groupby('Cliente_Display').agg({
                    'id': 'count',
                    'Percentual': 'mean'
                }).round(1)
                cliente_stats.columns = ['Total', 'Progresso Médio (%)']
                st.sidebar.dataframe(cliente_stats, use_container_width=True)
           
            # Filtro por tarefa
            task_titles = df_filtrado['title'].unique().tolist()
            task_selecionada = st.sidebar.selectbox(
                "Selecione a Task:",
                options=['Todas as Tasks'] + task_titles
            )

            # Filtro por status
            status_options = df_filtrado['status'].unique().tolist()
            status_selecionado = st.sidebar.multiselect(
                "Status:",
                options=status_options,
                default=status_options
            )
           
            # Filtro por classificação
            classificacao_options = df_filtrado['Classificacao'].unique().tolist()
            classificacao_selecionada = st.sidebar.multiselect(
                "Classificação:",
                options=classificacao_options,
                default=classificacao_options
            )

            # Aplicar filtros
            df_para_dashboard = df_filtrado.copy()
            
            # *** APLICAR FILTRO POR CLIENTE ***
            if cliente_selecionado != 'Todos os Clientes':
                df_para_dashboard = df_para_dashboard[
                    df_para_dashboard['Cliente_Display'] == cliente_selecionado
                ]
           
            if task_selecionada != 'Todas as Tasks':
                df_para_dashboard = df_para_dashboard[df_para_dashboard['title'] == task_selecionada]
               
            if status_selecionado:
                df_para_dashboard = df_para_dashboard[df_para_dashboard['status'].isin(status_selecionado)]
               
            if classificacao_selecionada:
                df_para_dashboard = df_para_dashboard[df_para_dashboard['Classificacao'].isin(classificacao_selecionada)]
           
            # ---- HEADER COM INFO DO FILTRO ATIVO ----
            if cliente_selecionado != 'Todos os Clientes':
                st.info(f"🎯 Visualizando dados do cliente: **{cliente_selecionado}**")
            
            # ---- DASHBOARD ----
            st.subheader("📋 Tabela de Status das Tasks")
            if not df_para_dashboard.empty:
                colunas_exibir = ['title', 'Cliente_Display', 'status', 'Percentual', 'Classificacao']
                if 'Prioridade' in df_para_dashboard.columns:
                    colunas_exibir.append('Prioridade')
                   
                st.dataframe(
                    df_para_dashboard[colunas_exibir].rename(columns={
                        'title': 'Título',
                        'Cliente_Display': 'Cliente',
                        'status': 'Status',
                        'Percentual': 'Progresso (%)',
                        'Classificacao': 'Classificação'
                    }),
                    use_container_width=True,
                    height=300
                )
            else:
                st.info("Nenhuma tarefa corresponde aos filtros selecionados.")
           
            # ---- MÉTRICAS ----
            col1, col2, col3, col4 = st.columns(4)
            total_tasks = len(df_para_dashboard)
            tasks_concluidas = len(df_para_dashboard[df_para_dashboard['Percentual'] >= 100])
            tasks_em_andamento = len(df_para_dashboard[(df_para_dashboard['Percentual'] > 0) & (df_para_dashboard['Percentual'] < 100)])
            tasks_nao_iniciadas = len(df_para_dashboard[df_para_dashboard['Percentual'] == 0])

            with col1:
                st.metric("Total de Tasks", total_tasks)
            with col2:
                taxa_conclusao = (tasks_concluidas / total_tasks) * 100 if total_tasks > 0 else 0
                st.metric("Taxa de Conclusão", f"{taxa_conclusao:.1f}%")
            with col3:
                st.metric("Tasks Concluídas", f"{tasks_concluidas}/{total_tasks}")
            with col4:
                media_progresso = df_para_dashboard['Percentual'].mean() if total_tasks > 0 else 0
                st.metric("Progresso Médio", f"{media_progresso:.1f}%")
           
            # ---- GRÁFICOS ----
            if total_tasks > 0:
                col1, col2 = st.columns(2)
               
                with col1:
                    st.subheader("📈 Progresso por Task")
                    df_ordenado = df_para_dashboard.sort_values('Percentual', ascending=True)
                    fig_bar = px.bar(
                        df_ordenado,
                        x='Percentual',
                        y='title',
                        orientation='h',
                        color='Percentual',
                        color_continuous_scale=['#ff4444', '#ffaa00', '#44ff44'],
                        text='Percentual',
                        title='Percentual de Conclusão por Task',
                        labels={'Percentual': '% Concluído', 'title': 'Tasks'},
                        height=max(400, len(df_para_dashboard) * 30),
                        hover_data=['Cliente_Display']
                    )
                    fig_bar.update_traces(texttemplate='%{text:.0f}%', textposition='auto')
                    fig_bar.update_layout(
                        yaxis={'automargin': True},
                        showlegend=False
                    )
                    st.plotly_chart(fig_bar, use_container_width=True)

                with col2:
                    st.subheader("🥧 Distribuição por Classificação")
                    classificacao_count = df_para_dashboard['Classificacao'].value_counts()
                    cores = {
                        'Não Iniciada': '#ff4444',
                        'Em Andamento': '#ffaa00',
                        'Concluída': '#00aa44'
                    }
                    fig_pie = px.pie(
                        values=classificacao_count.values,
                        names=classificacao_count.index,
                        title='Distribuição por Status de Progresso',
                        color_discrete_map=cores,
                        height=400
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                
                # *** NOVO GRÁFICO: PROGRESSO POR CLIENTE ***
                if cliente_selecionado == 'Todos os Clientes' and len(df_para_dashboard['Cliente_Display'].unique()) > 1:
                    st.subheader("📊 Progresso por Cliente")
                    
                    # Calcular métricas por cliente
                    cliente_metrics = df_para_dashboard.groupby('Cliente_Display').agg({
                        'Percentual': ['mean', 'count'],
                        'id': 'count'
                    }).round(1)
                    
                    # Flatten column names
                    cliente_metrics.columns = ['Progresso_Medio', 'Total_Tasks', 'Total_Tasks2']
                    cliente_metrics = cliente_metrics[['Progresso_Medio', 'Total_Tasks']].reset_index()
                    
                    fig_cliente = px.bar(
                        cliente_metrics,
                        x='Cliente_Display',
                        y='Progresso_Medio',
                        color='Progresso_Medio',
                        color_continuous_scale=['#ff4444', '#ffaa00', '#44ff44'],
                        text='Total_Tasks',
                        title='Progresso Médio por Cliente',
                        labels={
                            'Cliente_Display': 'Cliente',
                            'Progresso_Medio': 'Progresso Médio (%)',
                            'Total_Tasks': 'Nº de Tasks'
                        },
                        height=400
                    )
                    
                    fig_cliente.update_traces(
                        texttemplate='%{text} tasks<br>%{y:.0f}%',
                        textposition='outside'
                    )
                    
                    fig_cliente.update_layout(
                        xaxis_tickangle=-45,
                        showlegend=False
                    )
                    
                    st.plotly_chart(fig_cliente, use_container_width=True)

            # ---- ALERTAS E RECOMENDAÇÕES ----
            st.subheader("🚨 Alertas e Ações Recomendadas")
           
            col1, col2, col3 = st.columns(3)
           
            with col1:
                tasks_paradas = df_para_dashboard[df_para_dashboard['Percentual'] == 0]
                if not tasks_paradas.empty:
                    st.error(f"🛑 **URGENTE**\n{len(tasks_paradas)} task(s) não iniciada(s)")
                    with st.expander("Ver tasks não iniciadas"):
                        for _, task in tasks_paradas.iterrows():
                            st.write(f"• {task['title']} - {task['Cliente_Display']}")
           
            with col2:
                tasks_quase_prontas = df_para_dashboard[
                    (df_para_dashboard['Percentual'] >= 80) &
                    (df_para_dashboard['Percentual'] < 100)
                ]
                if not tasks_quase_prontas.empty:
                    st.info(f"🎯 **OPORTUNIDADE**\n{len(tasks_quase_prontas)} task(s) próximas da conclusão")
                    with st.expander("Ver tasks quase prontas"):
                        for _, task in tasks_quase_prontas.iterrows():
                            st.write(f"• {task['title']} ({task['Percentual']:.1f}%) - {task['Cliente_Display']}")
           
            with col3:
                if tasks_concluidas > 0:
                    st.success(f"🎉 **PARABÉNS**\n{tasks_concluidas} task(s) concluída(s)!")
                    with st.expander("Ver tasks concluídas"):
                        tasks_completas = df_para_dashboard[df_para_dashboard['Percentual'] >= 100]
                        for _, task in tasks_completas.iterrows():
                            st.write(f"✅ {task['title']} - {task['Cliente_Display']}")
               
        else:
            st.info("Nenhuma tarefa encontrada para este filtro.")

except KeyError:
    st.error("❌ Token de acesso não encontrado.")
    st.info("""
    📝 **Como configurar:**
    1. Crie o arquivo `.streamlit/secrets.toml`
    2. Adicione: `wrike_access_token = "seu_token_aqui"`
    3. Reinicie a aplicação
    """)
except Exception as e:
    st.error(f"❌ Erro inesperado: {str(e)}")
    st.info("Verifique sua conexão com a internet e a validade do token de acesso.")