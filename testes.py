import streamlit as st
from utils import setupAula, cursos_dict, trata_alternativas, quiz_orquestrator, gera_sugestoes, guardrail_camada_final
st.set_page_config(layout="wide")
import os
import json
from langchain_openai import AzureChatOpenAI
from datetime import datetime, timedelta
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas

#azure blog setup
AZURE_ACCOUNT_NAME = os.getenv('AZURE_ACCOUNT_NAME')
AZURE_ACCOUNT_KEY = os.getenv('AZURE_ACCOUNT_KEY')
AZURE_CONTAINER_NAME = os.getenv('AZURE_CONTAINER_NAME')
def upload_and_generate_sas_token(file_path, blob_name):  
    _, extensao = os.path.splitext(file_path)  
    extensao = extensao.split('?')[0]  
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")  
    unique_blob_name = f"{blob_name}_{timestamp}{extensao}"  
    try:  
        blob_service_client = BlobServiceClient(account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net",  
                                                credential=AZURE_ACCOUNT_KEY)  
        blob_container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)  
        with open(file_path, "rb") as file:  
            blob_client = blob_container_client.upload_blob(name=unique_blob_name, data=file, overwrite=True)
        token_expiry = datetime.now() + timedelta(hours=120)  
        sas_token = generate_blob_sas(  
            account_name=AZURE_ACCOUNT_NAME,  
            container_name=AZURE_CONTAINER_NAME,  
            blob_name=unique_blob_name,  
            account_key=AZURE_ACCOUNT_KEY,  
            permission=BlobSasPermissions(read=True),  
            expiry=token_expiry  )
        return f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{unique_blob_name}?{sas_token}"  
    except Exception as e:  
        print(f"Erro ao fazer upload do arquivo PDF e gerar o token SAS: {str(e)}") 
         

#Setup inicial
llm = AzureChatOpenAI(
  openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"],
  azure_deployment = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]
)

st.session_state['data_hora']= datetime.now().strftime("%d/%m/%Y %H:%M")
#render
colA, colB = st.columns(spec=[0.7,0.3])
with colA:
    st.title("Quiz assistant - Adaptive Learning")
with colB:
    logo='logo_cogna.png'
    st.image(logo)
    
    
with st.sidebar:
    st.image(logo)

    cursos=cursos_dict()
    user_name = st.text_input('Insira seu nome e confirme')
    user_curso = st.selectbox("Curso", (cursos.keys()))
    if user_curso:
        user_materia = st.selectbox("Materia", cursos[user_curso])
    questao_inicial = st.toggle("Questão inicial do quiz", value = True)
    with st.form("my-form"):
        sugestoes_embaixador = st.text_area(label='Comentários e sugestões',placeholder='Durante o teste, a IA respondeu...')
        confirm_button = st.form_submit_button("Salva comentário")
    
    
    send_log = st.button(label='Enviar resultado do teste', type ='primary')
    if send_log:
        st.markdown('Dados enviados!')
        st.markdown(':rocket:')


comando_titulo, comando_descricao, feedback, alternativas, conteudo_aula = setupAula(user_materia)
#Stop no caso de problema na requisição
if comando_titulo=='':
    st.stop()
col1, col2 = st.columns(spec=[0.6,0.4])
with col1: 
    st.markdown(comando_titulo)
    st.markdown(comando_descricao)
    alternativas = alternativas.replace('[','').replace(']','').replace("'",'"')
    alternativas, alternativa_correta = trata_alternativas(alternativas)
    st.radio('alternativas',alternativas)
    st.markdown(f"Gabarito: {feedback}. Alternativa correta: {alternativas[alternativa_correta.index('True')]}.")

with col2:
    if 'st_messages' not in st.session_state:
        st.session_state['st_messages'] = []
        st.session_state['messages'] = []
        st.session_state['sugestoes'] = ''
        st.session_state['opcao_A_input'] = ''
        st.session_state['opcao_B_input'] = ''
        st.session_state['opcao_C_input'] = ''
        st.session_state['historico_sugestoes']=[]
    reset_chat = st.button('Resetar histórico',use_container_width=True)
    if reset_chat:
        st.session_state['st_messages'] = []
        st.session_state['messages'] = [] 
        st.session_state['sugestoes'] = ''
        st.session_state['opcao_A_input'] = ''
        st.session_state['opcao_B_input'] = ''
        st.session_state['opcao_C_input'] = ''
        st.session_state['historico_sugestoes']=[]
        
    #Interação inicial
    if st.session_state['st_messages'] == []:
        completion, messages = quiz_orquestrator(llm=llm,
                                            input_aluno='',
                                            messages=st.session_state['messages'],
                                            user_name=user_name,
                                            user_curso=user_curso,
                                            questao_inicial=questao_inicial,
                                            questao=f"Questao:{comando_titulo}.{comando_descricao}.",
                                            conteudo_aula=conteudo_aula)
        st.session_state['messages'] = messages
        st.session_state['st_messages'].append({"role": "assistant", "content": completion}) 
    

    #Renderiza chat                
    for n,message in enumerate(st.session_state['st_messages']):
        with st.chat_message(message["role"]):
                st.markdown(message["content"]) 

        
        if st.session_state['sugestoes']=='':
            if n+1==len(st.session_state['st_messages']):
                with st.chat_message('user'):
                    st.session_state['sugestoes'] = gera_sugestoes(llm=llm, questao=f"Questao:{comando_titulo}.{comando_descricao}.",  messages=st.session_state['messages'])  
                    st.session_state['historico_sugestoes'].append(st.session_state['sugestoes'])
                    opcao_A=st.session_state['sugestoes'][1]
                    opcao_B=st.session_state['sugestoes'][2]
                    opcao_C=st.session_state['sugestoes'][3]
                    st.markdown('Aqui vão algumas sugestões de interação:') 
                    opcao_A_input = st.button(opcao_A,key=f'{opcao_A}_{n}')
                    opcao_B_input = st.button(opcao_B,key=f'{opcao_B}_{n}')
                    opcao_C_input = st.button(opcao_C,key=f'{opcao_C}_{n}')
                    st.session_state['opcao_A_input']=opcao_A_input
                    st.session_state['opcao_B_input']=opcao_B_input
                    st.session_state['opcao_C_input']=opcao_C_input
        else:
             if n+1==len(st.session_state['st_messages']):
                with st.chat_message('user'):
                    opcao_A=st.session_state['sugestoes'][1]
                    opcao_B=st.session_state['sugestoes'][2]
                    opcao_C=st.session_state['sugestoes'][3]
                    st.markdown('Aqui vão algumas sugestões de interação:') 
                    opcao_A_input = st.button(opcao_A,key=f'{opcao_A}_{n}')
                    opcao_B_input = st.button(opcao_B,key=f'{opcao_B}_{n}')
                    opcao_C_input = st.button(opcao_C,key=f'{opcao_C}_{n}')
                    st.session_state['opcao_A_input']=opcao_A_input
                    st.session_state['opcao_B_input']=opcao_B_input
                    st.session_state['opcao_C_input']=opcao_C_input
                    
    #teste botoes  
    if st.session_state['opcao_A_input']:
        completion, messages = quiz_orquestrator(llm=llm,
                                    input_aluno=st.session_state['sugestoes'][1],
                                    messages=st.session_state['messages'],
                                    user_name=user_name,
                                    user_curso=user_curso,
                                    questao_inicial=questao_inicial,
                                    questao=f"Questao:{comando_titulo}.{comando_descricao}.",
                                    conteudo_aula=conteudo_aula)
        st.session_state['messages'] = messages
        st.session_state['st_messages'].extend([{"role": "user", "content": st.session_state['sugestoes'][1]},
                                            {"role": "assistant", "content": completion}])
        st.session_state['sugestoes'] = gera_sugestoes(llm=llm, questao=f"Questao:{comando_titulo}.{comando_descricao}.",  messages=st.session_state['messages'])  
        st.session_state['historico_sugestoes'].append(st.session_state['sugestoes'])
        st.rerun()     
    if st.session_state['opcao_B_input']:
        completion, messages = quiz_orquestrator(llm=llm,
                                    input_aluno=st.session_state['sugestoes'][2],
                                    messages=st.session_state['messages'],
                                    user_name=user_name,
                                    user_curso=user_curso,
                                    questao_inicial=questao_inicial,
                                    questao=f"Questao:{comando_titulo}.{comando_descricao}.",
                                    conteudo_aula=conteudo_aula)
        st.session_state['messages'] = messages
        st.session_state['st_messages'].extend([{"role": "user", "content": st.session_state['sugestoes'][2]},
                                            {"role": "assistant", "content": completion}])
        st.session_state['sugestoes'] = gera_sugestoes(llm=llm, questao=f"Questao:{comando_titulo}.{comando_descricao}.",  messages=st.session_state['messages'])  
        st.session_state['historico_sugestoes'].append(st.session_state['sugestoes'])
        st.rerun()    
    if st.session_state['opcao_C_input']:
        completion, messages = quiz_orquestrator(llm=llm,
                                    input_aluno=st.session_state['sugestoes'][3],
                                    messages=st.session_state['messages'],
                                    user_name=user_name,
                                    user_curso=user_curso,
                                    questao_inicial=questao_inicial,
                                    questao=f"Questao:{comando_titulo}.{comando_descricao}.",
                                    conteudo_aula=conteudo_aula)
        st.session_state['messages'] = messages
        st.session_state['st_messages'].extend([{"role": "user", "content": st.session_state['sugestoes'][3]},
                                            {"role": "assistant", "content": completion}])
        st.session_state['sugestoes'] = gera_sugestoes(llm=llm, questao=f"Questao:{comando_titulo}.{comando_descricao}.",  messages=st.session_state['messages'])  
        st.session_state['historico_sugestoes'].append(st.session_state['sugestoes'])
        st.rerun()  
            
        #Monta interação de chat pós introdução
    if resposta_aluno := st.chat_input("Ou escreva a sua dúvida aqui"):
        completion, messages = quiz_orquestrator(llm=llm,
                                            input_aluno=resposta_aluno,
                                            messages=st.session_state['messages'],
                                            user_name=user_name,
                                            user_curso=user_curso,
                                            questao_inicial=questao_inicial,
                                            questao=f"Questao:{comando_titulo}.{comando_descricao}.",
                                            conteudo_aula=conteudo_aula)
        completion = guardrail_camada_final(llm, f"Questao:{comando_titulo}.{comando_descricao}.", completion)
        st.session_state['messages'] = messages
        st.session_state['st_messages'].extend([{"role": "user", "content": resposta_aluno},
                                                {"role": "assistant", "content": completion}])
        st.rerun()  
        

if send_log:
    log = {
            'data_teste':[st.session_state['data_hora']],
            'nome_usuario':[user_name],
            'nome_curso':[user_curso],
            'sugestoes_embaixador':[sugestoes_embaixador],
            'questao':[f"Questao:{comando_titulo}.{comando_descricao}."],
            'gabarito':[f"Gabarito: {feedback}. Alternativa correta: {alternativas[alternativa_correta.index('True')]}."],
            'historico':[st.session_state['messages']],
            'historico_sugestoes':[st.session_state['historico_sugestoes']]
        }
    with open("adaptive-teste-zero.json", "w") as outfile:
        json.dump(log, outfile, indent=4, sort_keys=False)
    upload_success = upload_and_generate_sas_token('.//adaptive-teste-zero.json','adaptive-teste-zero')
    st.write(upload_success)
    
        
