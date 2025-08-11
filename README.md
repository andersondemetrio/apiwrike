# Configuração do Projeto com Wrike e Importação de Dados

## 1. Criar a pasta `.streamlit`

No diretório raiz do seu projeto, crie uma pasta oculta chamada `.streamlit`. Essa pasta é utilizada pelo Streamlit para armazenar configurações e variáveis sensíveis.

---

## 2. Adicionar a variável de acesso da API do Wrike

Dentro da pasta `.streamlit`, crie um arquivo para armazenar suas variáveis de ambiente, por exemplo, `secrets.toml` (ou outro arquivo conforme sua aplicação).

No arquivo, adicione a seguinte linha:

```toml
wrike_access_token = "SUA_API_KEY_DO_APP_WRIKE"
